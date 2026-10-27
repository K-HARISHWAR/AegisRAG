"""Vector store interface and ChromaDB adapter enforcing idempotent indexing and pre-retrieval filtering."""

import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.chunk import Chunk, DocumentChunkRead, SearchResult

logger = get_logger(__name__)
settings = get_settings()


class VectorStore(ABC):
    """Abstract interface for vector database operations."""

    @abstractmethod
    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        """Idempotently add or update chunks in the vector collection."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        allowed_document_ids: List[uuid.UUID] | None = None,
    ) -> List[SearchResult]:
        """Perform semantic search with pre-retrieval authorization filtering."""
        pass

    @abstractmethod
    def get_by_document(self, document_id: uuid.UUID) -> List[DocumentChunkRead]:
        """Fetch all indexed chunks for a given document ID."""
        pass

    @abstractmethod
    def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Idempotently remove all indexed chunks for a given document ID."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return total indexed vectors."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verify vector database connectivity and responsiveness."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Clear all indexed vectors (for testing or full re-indexing)."""
        pass


class ChromaVectorStore(VectorStore):
    """ChromaDB implementation with metadata indexing and pre-search authorization filtering."""

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str | None = None,
        in_memory: bool = False,
    ) -> None:
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.persist_dir = persist_directory or settings.CHROMA_PERSIST_DIRECTORY

        if in_memory:
            self._client = chromadb.EphemeralClient()
        else:
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "AegisRAG enterprise chunks with RBAC metadata"},
        )
        logger.info("Initialized ChromaVectorStore (collection=%s, count=%d)", self.collection_name, self._collection.count())

    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        """Upsert chunks idempotently into ChromaDB."""
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch between chunks count ({len(chunks)}) and embeddings count ({len(embeddings)})")

        # Validate embedding dimensions strictly
        for idx, emb in enumerate(embeddings):
            if len(emb) != settings.EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Embedding dimension mismatch at index {idx}: expected {settings.EMBEDDING_DIMENSION}, got {len(emb)}"
                )

        # First, purge old chunks for this document to handle shortened/edited document versions cleanly
        doc_id = chunks[0].document_id
        self.delete_by_document(doc_id)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[dict[str, Any]] = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            metadatas.append({
                "document_id": str(chunk.document_id),
                "document_version": chunk.document_version,
                "chunk_index": chunk.chunk_index,
                "location": chunk.location,
                "department_id": str(chunk.department_id),
                "is_confidential": chunk.is_confidential,
                "content_hash": chunk.content_hash,
            })

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Indexed %d chunks for document %s in ChromaDB", len(chunks), doc_id)
        return len(chunks)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        allowed_document_ids: List[uuid.UUID] | None = None,
    ) -> List[SearchResult]:
        """Perform semantic search with pre-retrieval filtering on allowed document IDs."""
        if len(query_embedding) != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {settings.EMBEDDING_DIMENSION}, got {len(query_embedding)}"
            )

        total_vectors = self._collection.count()
        if total_vectors == 0:
            return []

        # Enforce pre-retrieval filter
        where_filter = None
        if allowed_document_ids is not None:
            # If authorized document IDs list is empty, return empty immediately (fail closed)
            if len(allowed_document_ids) == 0:
                return []
            allowed_str_ids = [str(d) for d in allowed_document_ids]
            if len(allowed_str_ids) == 1:
                where_filter = {"document_id": allowed_str_ids[0]}
            else:
                where_filter = {"document_id": {"$in": allowed_str_ids}}

        n_results = min(top_k, total_vectors)

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        raw_results = self._collection.query(**query_kwargs)

        results: List[SearchResult] = []
        if not raw_results or not raw_results.get("ids") or not raw_results["ids"][0]:
            return []

        ids = raw_results["ids"][0]
        docs = raw_results["documents"][0] if raw_results.get("documents") else [""] * len(ids)
        metas = raw_results["metadatas"][0] if raw_results.get("metadatas") else [{}] * len(ids)
        distances = raw_results["distances"][0] if raw_results.get("distances") else [0.0] * len(ids)

        for chunk_id, text, meta, dist in zip(ids, docs, metas, distances):
            # Chroma returns L2 squared distance by default (or cosine distance depending on collection)
            # Convert to normalized similarity score (0.0 - 1.0)
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=uuid.UUID(meta["document_id"]),
                    document_version=meta.get("document_version", 1),
                    chunk_index=meta.get("chunk_index", 1),
                    text=text,
                    location=meta.get("location", "Unknown location"),
                    department_id=uuid.UUID(meta["department_id"]),
                    is_confidential=bool(meta.get("is_confidential", False)),
                    similarity_score=round(similarity, 4),
                    metadata=meta,
                )
            )

        return results

    def get_by_document(self, document_id: uuid.UUID) -> List[DocumentChunkRead]:
        """Fetch all indexed chunks for a given document ID."""
        data = self._collection.get(where={"document_id": str(document_id)})
        results: List[DocumentChunkRead] = []
        if not data or not data.get("ids"):
            return results

        ids = data["ids"]
        docs = data["documents"] if data.get("documents") else [""] * len(ids)
        metas = data["metadatas"] if data.get("metadatas") else [{}] * len(ids)

        for chunk_id, text, meta in zip(ids, docs, metas):
            results.append(
                DocumentChunkRead(
                    chunk_id=chunk_id,
                    chunk_index=meta.get("chunk_index", 1),
                    location=meta.get("location", "Unknown location"),
                    text=text,
                    content_hash=meta.get("content_hash", ""),
                )
            )
        results.sort(key=lambda c: c.chunk_index)
        return results

    def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunks belonging to a document ID."""
        try:
            initial = self._collection.count()
            self._collection.delete(where={"document_id": str(document_id)})
            after = self._collection.count()
            deleted = initial - after
            logger.info("Deleted %d chunks for document %s from ChromaDB", deleted, document_id)
            return deleted
        except Exception as exc:
            logger.warning("Error deleting chunks for document %s: %s", document_id, exc)
            return 0

    def count(self) -> int:
        return self._collection.count()

    def health_check(self) -> bool:
        try:
            return self._collection.count() >= 0
        except Exception:
            return False

    def reset(self) -> None:
        """Reset the Chroma collection."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "AegisRAG enterprise chunks with RBAC metadata"},
        )


_global_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Dependency / singleton returning active ChromaVectorStore."""
    global _global_vector_store
    if _global_vector_store is None:
        current_settings = get_settings()
        is_test = current_settings.ENVIRONMENT == "test"
        _global_vector_store = ChromaVectorStore(
            persist_directory=current_settings.CHROMA_PERSIST_DIRECTORY,
            collection_name=current_settings.CHROMA_COLLECTION_NAME,
            in_memory=is_test,
        )
    return _global_vector_store
