"""Embedding provider interface, Chroma ONNX default provider, and deterministic test mock."""

import hashlib
import math
from abc import ABC, abstractmethod
from typing import List

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingProvider(ABC):
    """Abstract base class for document and query text embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of embedding model."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a batch of document texts."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Compute embedding for a single user query."""
        pass

    def validate_dimension(self, vector: List[float]) -> None:
        """Enforce strict dimensionality matching."""
        if len(vector) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, received {len(vector)}."
            )


class ChromaDefaultEmbeddingProvider(EmbeddingProvider):
    """Production/dev embedding provider using Chroma's built-in ONNX all-MiniLM-L6-v2 model."""

    def __init__(self, expected_dim: int = 384, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._dimension = expected_dim
        self._model_name = model_name
        from chromadb.utils import embedding_functions
        self._ef = embedding_functions.DefaultEmbeddingFunction()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self._ef(texts)
        result: List[List[float]] = []
        for v in vectors:
            v_list = [float(x) for x in v]
            self.validate_dimension(v_list)
            result.append(v_list)
        return result

    def embed_query(self, text: str) -> List[float]:
        vectors = self.embed_documents([text])
        if not vectors:
            return [0.0] * self.dimension
        return vectors[0]


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Fast, deterministic unit-normalized embedding provider for testing and isolation."""

    def __init__(self, dimension: int = 384, model_name: str = "mock-deterministic-384") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> List[float]:
        """Generate a deterministic, normalized vector based on word presence and SHA-256 seed."""
        # Clean text
        words = text.lower().strip().split()
        vec = [0.0] * self.dimension

        if not words:
            vec[0] = 1.0
            return vec

        # Use MD5/SHA256 hashes of words to activate predictable dimensions
        for word in words:
            h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.0

        # Also blend in overall hash for semantic uniqueness
        overall_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        for i in range(min(16, self.dimension)):
            vec[(overall_hash >> (i * 4)) % self.dimension] += 0.5

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0

        self.validate_dimension(vec)
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._generate_vector(text)


def get_embedding_provider() -> EmbeddingProvider:
    """Factory returning the active embedding provider based on environment."""
    current_settings = get_settings()
    if current_settings.ENVIRONMENT == "test":
        return DeterministicMockEmbeddingProvider(dimension=current_settings.EMBEDDING_DIMENSION)
    try:
        return ChromaDefaultEmbeddingProvider(expected_dim=current_settings.EMBEDDING_DIMENSION)
    except Exception as exc:
        logger.warning("Could not initialize Chroma ONNX embedding, falling back to deterministic provider: %s", exc)
        return DeterministicMockEmbeddingProvider(dimension=current_settings.EMBEDDING_DIMENSION)
