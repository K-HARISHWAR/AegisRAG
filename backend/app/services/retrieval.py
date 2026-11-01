"""Secure retrieval pipeline with two-stage authorization filtering, multi-channel hybrid search, RRF, and intelligent reranking."""

import math
import re
import time
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import Document
from app.models.user import User
from app.schemas.chunk import SearchResult
from app.schemas.retrieval import RetrievalDiagnostics, RetrievalQuery, RetrievalResponse, RetrievedChunk
from app.services.audit import log_audit_event
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.policy import can_read_document, get_authorized_document_ids
from app.services.reranker import get_reranker
from app.services.vector_store import VectorStore, get_vector_store

logger = get_logger(__name__)
settings = get_settings()


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
    """Execute two-stage authorized hybrid retrieval with multi-channel candidate generation, RRF, and reranking.

    Stage 1: Pre-retrieval filtering with PostgreSQL-authorized document IDs on both dense and sparse channels.
    Stage 2: Post-retrieval revalidation verifying permissions and metadata against PostgreSQL records before reranking.
    """
    start_time = time.perf_counter()

    if vector_store is None:
        vector_store = get_vector_store()
    if embedding_provider is None:
        embedding_provider = get_embedding_provider()

    # Determine active retrieval mode: request override takes precedence, then server config
    retrieval_mode = query_params.mode or settings.RETRIEVAL_MODE
    # Backwards compatibility: if query_params.hybrid is explicitly False and mode not specified, use vector
    if query_params.mode is None and not query_params.hybrid:
        retrieval_mode = "vector"

    # Determine whether to execute reranker
    should_rerank = query_params.rerank if query_params.rerank is not None else settings.ENABLE_RERANKER

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
        diagnostics = RetrievalDiagnostics(
            mode=retrieval_mode,
            channels_used=["dense"] if retrieval_mode == "vector" else ["dense", "sparse"],
            dense_candidates_count=0,
            sparse_candidates_count=0,
            fused_candidates_count=0,
            post_validation_count=0,
            reranked=False,
            reranker_latency_ms=None,
            authorized_documents_count=0,
        )
        return RetrievalResponse(
            query=query_params.query,
            chunks=[],
            total_candidates_found=0,
            authorized_documents_count=0,
            execution_time_ms=round(elapsed, 2),
            diagnostics=diagnostics,
        )

    # Candidate pool size: retrieve wider candidate set for multi-channel fusion
    candidate_limit = max(query_params.top_k * 3, 15)

    # -------------------------------------------------------------------------
    # CHANNEL 1: Dense Vector Retrieval (Pre-filtered by allowed_document_ids)
    # -------------------------------------------------------------------------
    query_vector = embedding_provider.embed_query(query_params.query)
    dense_candidates: List[SearchResult] = vector_store.search(
        query_embedding=query_vector,
        top_k=candidate_limit,
        allowed_document_ids=allowed_doc_ids,
    )

    dense_map: Dict[str, Tuple[int, SearchResult]] = {}
    for rank, cand in enumerate(dense_candidates, start=1):
        dense_map[cand.chunk_id] = (rank, cand)

    # -------------------------------------------------------------------------
    # CHANNEL 2: Sparse Lexical Retrieval (BM25 over authorized document corpus)
    # -------------------------------------------------------------------------
    sparse_candidates: List[SearchResult] = []
    sparse_map: Dict[str, Tuple[int, SearchResult, float]] = {}

    if retrieval_mode == "hybrid":
        all_authorized_chunks = vector_store.get_chunks_by_documents(allowed_doc_ids)
        if all_authorized_chunks:
            chunk_texts = [c.text for c in all_authorized_chunks]
            bm25 = BM25Scorer(chunk_texts)
            scores = bm25.score(query_params.query)

            # Collect chunks with non-zero keyword score
            scored_sparse = [
                (scores[i], chunk)
                for i, chunk in enumerate(all_authorized_chunks)
                if scores[i] > 0.0
            ]
            # Sort descending by BM25 score
            scored_sparse.sort(key=lambda x: x[0], reverse=True)
            top_sparse = scored_sparse[:candidate_limit]

            for rank, (score, cand) in enumerate(top_sparse, start=1):
                sparse_candidates.append(cand)
                sparse_map[cand.chunk_id] = (rank, cand, score)

    # -------------------------------------------------------------------------
    # MULTI-CHANNEL FUSION & DEDUPLICATION (Reciprocal Rank Fusion)
    # -------------------------------------------------------------------------
    channels_used = ["dense"]
    if retrieval_mode == "hybrid":
        channels_used.append("sparse")

    all_candidate_ids = set(dense_map.keys()) | set(sparse_map.keys())
    if not all_candidate_ids:
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
        diagnostics = RetrievalDiagnostics(
            mode=retrieval_mode,
            channels_used=channels_used,
            dense_candidates_count=len(dense_candidates),
            sparse_candidates_count=len(sparse_candidates),
            fused_candidates_count=0,
            post_validation_count=0,
            reranked=False,
            reranker_latency_ms=None,
            authorized_documents_count=len(allowed_doc_ids),
        )
        return RetrievalResponse(
            query=query_params.query,
            chunks=[],
            total_candidates_found=0,
            authorized_documents_count=len(allowed_doc_ids),
            execution_time_ms=round(elapsed, 2),
            diagnostics=diagnostics,
        )

    # Calculate RRF scores and assemble candidate metadata
    rrf_k = settings.RRF_K
    dense_weight = settings.HYBRID_DENSE_WEIGHT
    sparse_weight = settings.HYBRID_SPARSE_WEIGHT
    penalty_rank = 1000  # Penalty rank for candidate not present in a channel

    fused_pool: List[Tuple[float, SearchResult, str, Optional[int], Optional[int], float, float]] = []

    for cid in all_candidate_ids:
        in_dense = cid in dense_map
        in_sparse = cid in sparse_map

        cand_dense_info = dense_map.get(cid)
        cand_sparse_info = sparse_map.get(cid)

        # Retrieve base SearchResult
        base_cand = cand_dense_info[1] if cand_dense_info else cand_sparse_info[1]

        dense_rank = cand_dense_info[0] if cand_dense_info else None
        sparse_rank = cand_sparse_info[0] if cand_sparse_info else None

        dense_score = base_cand.similarity_score if in_dense else 0.0
        sparse_score = cand_sparse_info[2] if cand_sparse_info else 0.0

        if retrieval_mode == "vector":
            channel_label = "dense"
            combined_score = dense_score
        else:
            if in_dense and in_sparse:
                channel_label = "both"
            elif in_dense:
                channel_label = "dense"
            else:
                channel_label = "sparse"

            # Compute RRF score
            effective_dense_rank = dense_rank if dense_rank is not None else penalty_rank
            effective_sparse_rank = sparse_rank if sparse_rank is not None else penalty_rank

            score_dense = dense_weight / (rrf_k + effective_dense_rank)
            score_sparse = sparse_weight / (rrf_k + effective_sparse_rank)
            combined_score = score_dense + score_sparse

        fused_pool.append((
            combined_score,
            base_cand,
            channel_label,
            dense_rank,
            sparse_rank,
            dense_score,
            sparse_score,
        ))

    # Normalize fused RRF scores to 0.0 - 1.0 range if in hybrid mode
    if retrieval_mode == "hybrid" and fused_pool:
        scores = [item[0] for item in fused_pool]
        max_s = max(scores)
        min_s = min(scores)
        diff = max_s - min_s
        normalized_fused_pool = []
        for item in fused_pool:
            norm_s = round((item[0] - min_s) / diff, 4) if diff > 0 else 1.0
            normalized_fused_pool.append((norm_s, *item[1:]))
        fused_pool = normalized_fused_pool

    # Sort descending by combined score
    fused_pool.sort(key=lambda x: x[0], reverse=True)

    # -------------------------------------------------------------------------
    # STAGE 2 (Post-Retrieval Revalidation): Re-check against PostgreSQL records
    # -------------------------------------------------------------------------
    candidate_doc_ids = list({item[1].document_id for item in fused_pool})

    stmt = (
        select(Document)
        .options(selectinload(Document.grants))
        .where(
            Document.id.in_(candidate_doc_ids),
            Document.status != "deleted",
            Document.lifecycle_state == "active",
        )
    )
    result = await db.execute(stmt)
    active_docs_map: Dict[uuid.UUID, Document] = {d.id: d for d in result.scalars().all()}

    valid_retrieved_chunks: List[RetrievedChunk] = []

    for combined_score, cand, channel, d_rank, s_rank, d_score, s_score in fused_pool:
        doc = active_docs_map.get(cand.document_id)
        if not doc:
            logger.warning("Stage 2 rejected candidate: doc %s not in active PostgreSQL docs", cand.document_id)
            continue

        # Revalidate authorization against current database records (fail closed if not active)
        is_allowed = await can_read_document(current_user, doc, db, require_active=True)
        if not is_allowed:
            logger.warning("Stage 2 authorization mismatch: user %s denied read on doc %s", current_user.id, doc.id)
            await log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="post_retrieval_revalidation",
                outcome="deny",
                resource_id=str(doc.id),
                resource_type="document",
                details={"chunk_id": cand.chunk_id, "channel": channel},
                ip_address=ip_address,
            )
            continue

        if combined_score < query_params.score_threshold:
            continue

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
            combined_score=combined_score,
            content_hash=cand.metadata.get("content_hash", ""),
            channel=channel,
            dense_rank=d_rank,
            sparse_rank=s_rank,
            rerank_score=None,
            rerank_rank=None,
            metadata=cand.metadata,
        )
        valid_retrieved_chunks.append(retrieved)

    # -------------------------------------------------------------------------
    # STAGE 3 (Intelligent Reranking Adapter): Reorder authorized candidates
    # -------------------------------------------------------------------------
    reranker_latency_ms: Optional[float] = None

    if should_rerank and valid_retrieved_chunks:
        reranker = get_reranker(settings)
        # Rerank the top candidates (up to candidate_limit)
        rerank_input = valid_retrieved_chunks[:candidate_limit]
        final_chunks, reranker_latency_ms = await reranker.rerank(
            query=query_params.query,
            candidates=rerank_input,
            top_k=query_params.top_k,
        )
    else:
        final_chunks = valid_retrieved_chunks[: query_params.top_k]

    elapsed = (time.perf_counter() - start_time) * 1000

    diagnostics = RetrievalDiagnostics(
        mode=retrieval_mode,
        channels_used=channels_used,
        dense_candidates_count=len(dense_candidates),
        sparse_candidates_count=len(sparse_candidates),
        fused_candidates_count=len(fused_pool),
        post_validation_count=len(valid_retrieved_chunks),
        reranked=should_rerank,
        reranker_latency_ms=reranker_latency_ms,
        authorized_documents_count=len(allowed_doc_ids),
    )

    # Structured audit logging for retrieval execution
    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="retrieval_query",
        outcome="allow",
        resource_type="query",
        details={
            "query_preview": query_params.query[:80],
            "mode": retrieval_mode,
            "channels": channels_used,
            "dense_count": len(dense_candidates),
            "sparse_count": len(sparse_candidates),
            "returned_chunks": len(final_chunks),
            "authorized_docs_count": len(allowed_doc_ids),
            "reranked": should_rerank,
            "latency_ms": round(elapsed, 2),
        },
        ip_address=ip_address,
    )

    return RetrievalResponse(
        query=query_params.query,
        chunks=final_chunks,
        total_candidates_found=len(valid_retrieved_chunks),
        authorized_documents_count=len(allowed_doc_ids),
        execution_time_ms=round(elapsed, 2),
        diagnostics=diagnostics,
    )
