"""Secure retrieval pipeline with two-stage authorization filtering, BM25 keyword search, and RRF."""

import math
import re
import time
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.document import Document
from app.models.user import User
from app.schemas.chunk import SearchResult
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from app.services.audit import log_audit_event
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.policy import can_read_document, get_authorized_document_ids
from app.services.vector_store import VectorStore, get_vector_store

logger = get_logger(__name__)


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric terms for BM25 keyword scoring."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


class BM25Scorer:
    """Okapi BM25 implementation for lexical sparse search over candidate chunk passages."""

    def __init__(self, corpus: List[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.tokenized_corpus = [tokenize(doc) for doc in corpus]
        self.doc_lens = [len(tokens) for tokens in self.tokenized_corpus]
        self.avg_doc_len = sum(self.doc_lens) / max(1, self.corpus_size)

        # Document frequencies for all unique vocabulary words
        self.doc_freqs: Dict[str, int] = Counter()
        for tokens in self.tokenized_corpus:
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1

    def score(self, query: str) -> List[float]:
        """Compute BM25 relevance scores for all documents against the query."""
        if not self.corpus_size:
            return []

        query_terms = tokenize(query)
        scores = [0.0] * self.corpus_size

        for term in query_terms:
            df = self.doc_freqs.get(term, 0)
            if df == 0:
                continue

            # Standard Robertson-Spärck Jones IDF
            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)
            idf = max(0.0, idf)

            for doc_idx, tokens in enumerate(self.tokenized_corpus):
                tf = tokens.count(term)
                if tf == 0:
                    continue

                doc_len = self.doc_lens[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                term_score = idf * (tf * (self.k1 + 1.0)) / max(1e-6, denom)
                scores[doc_idx] += term_score

        # Normalize to 0.0 - 1.0 scale
        max_score = max(scores) if scores else 0.0
        if max_score > 0:
            return [round(s / max_score, 4) for s in scores]
        return scores


def reciprocal_rank_fusion(
    dense_scores: List[float],
    sparse_scores: List[float],
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    rrf_k: int = 60,
) -> List[float]:
    """Fuse dense and sparse rankings using Reciprocal Rank Fusion (RRF)."""
    n = len(dense_scores)
    if n == 0:
        return []

    # Sort indices by dense scores descending
    dense_ranked_indices = sorted(range(n), key=lambda i: dense_scores[i], reverse=True)
    dense_rank_map = {idx: rank + 1 for rank, idx in enumerate(dense_ranked_indices)}

    # Sort indices by sparse scores descending
    sparse_ranked_indices = sorted(range(n), key=lambda i: sparse_scores[i], reverse=True)
    sparse_rank_map = {idx: rank + 1 for rank, idx in enumerate(sparse_ranked_indices)}

    combined_scores: List[float] = [0.0] * n
    for i in range(n):
        # RRF formula
        score_dense = dense_weight / (rrf_k + dense_rank_map[i])
        score_sparse = sparse_weight / (rrf_k + sparse_rank_map[i])
        combined_scores[i] = score_dense + score_sparse

    # Normalize to 0.0 - 1.0
    max_score = max(combined_scores) if combined_scores else 0.0
    min_score = min(combined_scores) if combined_scores else 0.0
    score_range = max_score - min_score

    if score_range > 0:
        return [round((s - min_score) / score_range, 4) for s in combined_scores]
    elif max_score > 0:
        return [1.0] * n
    return [0.0] * n


async def retrieve_context(
    query_params: RetrievalQuery,
    current_user: User,
    db: AsyncSession,
    vector_store: Optional[VectorStore] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
    ip_address: Optional[str] = None,
) -> RetrievalResponse:
    """Execute two-stage authorized hybrid retrieval.
    
    Stage 1: Pre-retrieval vector search filtering with trusted PostgreSQL document IDs.
    Stage 2: Post-retrieval revalidation verifying permissions and metadata against PostgreSQL.
    """
    start_time = time.perf_counter()

    if vector_store is None:
        vector_store = get_vector_store()
    if embedding_provider is None:
        embedding_provider = get_embedding_provider()

    # -------------------------------------------------------------------------
    # STAGE 1 (Pre-Retrieval Filter): Derive authorized documents from PostgreSQL
    # -------------------------------------------------------------------------
    allowed_doc_ids = await get_authorized_document_ids(current_user, db)

    # Fail closed: If user has no access to any documents, return empty immediately
    if not allowed_doc_ids:
        elapsed = (time.perf_counter() - start_time) * 1000
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="retrieval_query",
            outcome="deny",
            resource_type="query",
            details={"reason": "no_authorized_documents", "query": query_params.query[:80]},
            ip_address=ip_address,
        )
        return RetrievalResponse(
            query=query_params.query,
            chunks=[],
            total_candidates_found=0,
            authorized_documents_count=0,
            execution_time_ms=round(elapsed, 2),
        )

    # Generate query embedding
    query_vector = embedding_provider.embed_query(query_params.query)

    # Candidate pool size: retrieve a wider set of candidates for hybrid re-ranking
    candidate_limit = max(query_params.top_k * 3, 15)

    # Dense vector search pre-filtered strictly by allowed_document_ids
    dense_candidates: List[SearchResult] = vector_store.search(
        query_embedding=query_vector,
        top_k=candidate_limit,
        allowed_document_ids=allowed_doc_ids,
    )

    if not dense_candidates:
        elapsed = (time.perf_counter() - start_time) * 1000
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="retrieval_query",
            outcome="allow",
            resource_type="query",
            details={"candidates_found": 0, "returned": 0, "query": query_params.query[:80]},
            ip_address=ip_address,
        )
        return RetrievalResponse(
            query=query_params.query,
            chunks=[],
            total_candidates_found=0,
            authorized_documents_count=len(allowed_doc_ids),
            execution_time_ms=round(elapsed, 2),
        )

    # -------------------------------------------------------------------------
    # STAGE 2 (Post-Retrieval Revalidation): Re-check against PostgreSQL
    # -------------------------------------------------------------------------
    candidate_doc_ids = list({c.document_id for c in dense_candidates})

    stmt = (
        select(Document)
        .options(selectinload(Document.grants))
        .where(Document.id.in_(candidate_doc_ids), Document.status != "deleted")
    )
    result = await db.execute(stmt)
    active_docs_map: Dict[uuid.UUID, Document] = {d.id: d for d in result.scalars().all()}

    valid_candidates: List[SearchResult] = []
    for candidate in dense_candidates:
        doc = active_docs_map.get(candidate.document_id)
        if not doc:
            logger.warning("Stage 2 rejected candidate: doc %s not in active PostgreSQL docs", candidate.document_id)
            continue

        # Revalidate authorization against current database records
        is_allowed = await can_read_document(current_user, doc, db)
        if not is_allowed:
            logger.warning("Stage 2 authorization mismatch: user %s denied read on doc %s", current_user.id, doc.id)
            await log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="post_retrieval_revalidation",
                outcome="deny",
                resource_id=str(doc.id),
                resource_type="document",
                details={"chunk_id": candidate.chunk_id},
                ip_address=ip_address,
            )
            continue

        valid_candidates.append(candidate)

    if not valid_candidates:
        elapsed = (time.perf_counter() - start_time) * 1000
        return RetrievalResponse(
            query=query_params.query,
            chunks=[],
            total_candidates_found=0,
            authorized_documents_count=len(allowed_doc_ids),
            execution_time_ms=round(elapsed, 2),
        )

    # -------------------------------------------------------------------------
    # Hybrid Scoring (Dense + BM25 Sparse Reciprocal Rank Fusion)
    # -------------------------------------------------------------------------
    candidate_texts = [c.text for c in valid_candidates]
    dense_scores = [c.similarity_score for c in valid_candidates]

    if query_params.hybrid:
        bm25 = BM25Scorer(candidate_texts)
        sparse_scores = bm25.score(query_params.query)
        combined_scores = reciprocal_rank_fusion(dense_scores, sparse_scores)
    else:
        sparse_scores = [0.0] * len(valid_candidates)
        combined_scores = dense_scores

    # Build RetrievedChunk objects with verified PostgreSQL document titles
    scored_chunks: List[Tuple[float, RetrievedChunk]] = []
    for i, cand in enumerate(valid_candidates):
        c_score = combined_scores[i]
        d_score = dense_scores[i]
        s_score = sparse_scores[i]

        if c_score < query_params.score_threshold:
            continue

        doc = active_docs_map[cand.document_id]

        retrieved = RetrievedChunk(
            chunk_id=cand.chunk_id,
            document_id=cand.document_id,
            document_title=doc.title,
            document_version=cand.document_version,
            chunk_index=cand.chunk_index,
            text=cand.text,
            location=cand.location,
            department_id=cand.department_id,
            is_confidential=cand.is_confidential,
            dense_score=d_score,
            sparse_score=s_score,
            combined_score=c_score,
            content_hash=cand.metadata.get("content_hash", ""),
            metadata=cand.metadata,
        )
        scored_chunks.append((c_score, retrieved))

    # Sort descending by combined score and truncate to top_k
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    final_chunks = [item[1] for item in scored_chunks[: query_params.top_k]]

    elapsed = (time.perf_counter() - start_time) * 1000

    # Audit logging for query execution
    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="retrieval_query",
        outcome="allow",
        resource_type="query",
        details={
            "query_preview": query_params.query[:80],
            "candidates_found": len(valid_candidates),
            "returned_chunks": len(final_chunks),
            "authorized_docs_count": len(allowed_doc_ids),
            "hybrid": query_params.hybrid,
            "latency_ms": round(elapsed, 2),
        },
        ip_address=ip_address,
    )

    return RetrievalResponse(
        query=query_params.query,
        chunks=final_chunks,
        total_candidates_found=len(valid_candidates),
        authorized_documents_count=len(allowed_doc_ids),
        execution_time_ms=round(elapsed, 2),
    )
