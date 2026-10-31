"""Intelligent reranking adapter with pluggable providers, strict timeouts, and safe fallback."""

import asyncio
import re
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.retrieval import RetrievedChunk

logger = get_logger(__name__)


def _tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric tokens."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


class Reranker(ABC):
    """Abstract interface for passage reranking over already-authorized candidates."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> Tuple[List[RetrievedChunk], float]:
        """Rerank candidates and return (reordered_chunks, latency_ms)."""
        pass


class MockReranker(Reranker):
    """High-speed deterministic cross-attentive token-overlap and phrase proximity reranker.
    
    Provides offline and unit-test execution without external GPU/network dependencies.
    """

    async def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> Tuple[List[RetrievedChunk], float]:
        start = time.perf_counter()
        if not candidates:
            return [], 0.0

        query_terms = _tokenize(query)
        clean_query = query.strip().lower()
        query_len = max(1, len(query_terms))

        scored_candidates: List[Tuple[float, RetrievedChunk]] = []

        for cand in candidates:
            cand_tokens = _tokenize(cand.text)
            cand_len = max(1, len(cand_tokens))
            cand_text_lower = cand.text.lower()

            # 1. Exact phrase match bonus
            phrase_bonus = 0.4 if clean_query in cand_text_lower else 0.0

            # 2. Token overlap coverage (fraction of unique query terms present)
            matched_terms = [t for t in query_terms if t in cand_tokens]
            coverage = len(set(matched_terms)) / len(set(query_terms)) if query_terms else 0.0

            # 3. Term density (frequency of query terms relative to passage length)
            density = min(1.0, len(matched_terms) / min(cand_len, 50))

            # 4. Location relevance bonus (e.g. title/heading match)
            title_bonus = 0.15 if any(t in cand.document_title.lower() for t in query_terms) else 0.0

            # Combined rerank score: blend token features with baseline RRF score
            raw_rerank_score = (
                0.35 * coverage +
                0.25 * phrase_bonus +
                0.15 * density +
                0.10 * title_bonus +
                0.15 * cand.combined_score
            )
            normalized_score = round(min(1.0, max(0.0, raw_rerank_score)), 4)

            # Assign score to chunk copy
            cand_copy = cand.model_copy(update={"rerank_score": normalized_score})
            scored_candidates.append((normalized_score, cand_copy))

        # Sort descending by rerank score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Update rerank_rank
        final_list: List[RetrievedChunk] = []
        for rank, (score, chunk) in enumerate(scored_candidates[:top_k], start=1):
            chunk_with_rank = chunk.model_copy(update={"rerank_rank": rank})
            final_list.append(chunk_with_rank)

        latency_ms = (time.perf_counter() - start) * 1000
        return final_list, round(latency_ms, 2)


class CrossEncoderReranker(Reranker):
    """Transformer Cross-Encoder reranker using sentence-transformers (if installed)."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info("Loaded CrossEncoder reranker: %s", self.model_name)
        except Exception as exc:
            logger.warning("Could not initialize CrossEncoder (%s): %s. Will fallback to MockReranker.", self.model_name, exc)
            self._model = None

    async def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> Tuple[List[RetrievedChunk], float]:
        start = time.perf_counter()
        if not candidates:
            return [], 0.0

        if self._model is None:
            # Fallback to MockReranker
            mock = MockReranker()
            return await mock.rerank(query, candidates, top_k)

        pairs = [[query, c.text] for c in candidates]
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, self._model.predict, pairs)

        # Normalize scores with sigmoid
        import math
        norm_scores = [round(1.0 / (1.0 + math.exp(-float(s))), 4) for s in scores]

        scored: List[Tuple[float, RetrievedChunk]] = []
        for cand, s in zip(candidates, norm_scores):
            scored.append((s, cand.model_copy(update={"rerank_score": s})))

        scored.sort(key=lambda x: x[0], reverse=True)

        final_list = [
            chunk.model_copy(update={"rerank_rank": rank})
            for rank, (_, chunk) in enumerate(scored[:top_k], start=1)
        ]
        latency_ms = (time.perf_counter() - start) * 1000
        return final_list, round(latency_ms, 2)


class TimeoutSafeReranker(Reranker):
    """Decorator wrapping any Reranker with a strict timeout and safe fallback to RRF order."""

    def __init__(self, inner: Reranker, timeout_seconds: float = 2.0) -> None:
        self.inner = inner
        self.timeout_seconds = timeout_seconds

    async def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> Tuple[List[RetrievedChunk], float]:
        start = time.perf_counter()
        if not candidates:
            return [], 0.0

        try:
            return await asyncio.wait_for(
                self.inner.rerank(query, candidates, top_k),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "Reranker timed out after %.2fs. Falling back to original RRF candidate order.",
                self.timeout_seconds,
            )
            # Safe fallback: return original top_k without reordering
            fallback = [
                c.model_copy(update={"rerank_rank": r, "rerank_score": c.combined_score})
                for r, c in enumerate(candidates[:top_k], start=1)
            ]
            return fallback, round(latency_ms, 2)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("Reranker failed with exception: %s. Falling back to original RRF candidate order.", exc)
            fallback = [
                c.model_copy(update={"rerank_rank": r, "rerank_score": c.combined_score})
                for r, c in enumerate(candidates[:top_k], start=1)
            ]
            return fallback, round(latency_ms, 2)


def get_reranker(settings: Optional[Settings] = None) -> Reranker:
    """Factory creating the configured reranker instance with timeout protection."""
    if settings is None:
        settings = get_settings()

    timeout = settings.RERANKER_TIMEOUT_SECONDS

    if settings.RERANKER_TYPE == "cross_encoder":
        inner = CrossEncoderReranker()
    else:
        inner = MockReranker()

    return TimeoutSafeReranker(inner=inner, timeout_seconds=timeout)
