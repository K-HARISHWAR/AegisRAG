"""Unit tests for ChromaVectorStore adapter, pre-retrieval filtering, and dimension validation."""

import uuid
import pytest

from app.schemas.chunk import Chunk
from app.services.embeddings import DeterministicMockEmbeddingProvider
from app.services.vector_store import ChromaVectorStore


@pytest.fixture
def test_vector_store() -> ChromaVectorStore:
    """Fixture providing a fresh in-memory ChromaVectorStore for each test."""
    store = ChromaVectorStore(
        collection_name=f"test_collection_{uuid.uuid4().hex[:8]}",
        in_memory=True,
    )
    yield store
    store.reset()


@pytest.fixture
def mock_embedder() -> DeterministicMockEmbeddingProvider:
    return DeterministicMockEmbeddingProvider(dimension=384)


def _make_sample_chunk(
    doc_id: uuid.UUID,
    chunk_index: int,
    text: str,
    dept_id: uuid.UUID | None = None,
    is_confidential: bool = False,
) -> Chunk:
    dept = dept_id or uuid.uuid4()
    return Chunk(
        chunk_id=f"{doc_id}_{chunk_index}",
        document_id=doc_id,
        document_version=1,
        chunk_index=chunk_index,
        text=text,
        location=f"Page {chunk_index}",
        department_id=dept,
        is_confidential=is_confidential,
        content_hash=f"hash_{chunk_index}",
        metadata={"title": "Test Doc"},
    )


def test_add_chunks_and_count(test_vector_store: ChromaVectorStore, mock_embedder: DeterministicMockEmbeddingProvider) -> None:
    """Verify adding chunks increases vector store count."""
    doc_id = uuid.uuid4()
    chunks = [
        _make_sample_chunk(doc_id, 1, "First chunk text about infrastructure."),
        _make_sample_chunk(doc_id, 2, "Second chunk text about firewalls."),
    ]
    embeddings = mock_embedder.embed_documents([c.text for c in chunks])

    added = test_vector_store.add_chunks(chunks, embeddings)
    assert added == 2
    assert test_vector_store.count() == 2


def test_idempotent_upsert(test_vector_store: ChromaVectorStore, mock_embedder: DeterministicMockEmbeddingProvider) -> None:
    """Verify re-indexing the same document purges old entries and updates without duplicates."""
    doc_id = uuid.uuid4()
    chunks_v1 = [
        _make_sample_chunk(doc_id, 1, "Initial version of chunk 1."),
        _make_sample_chunk(doc_id, 2, "Initial version of chunk 2."),
    ]
    emb_v1 = mock_embedder.embed_documents([c.text for c in chunks_v1])
    test_vector_store.add_chunks(chunks_v1, emb_v1)
    assert test_vector_store.count() == 2

    # Re-index with only 1 revised chunk
    chunks_v2 = [
        _make_sample_chunk(doc_id, 1, "Updated single chunk version."),
    ]
    emb_v2 = mock_embedder.embed_documents([c.text for c in chunks_v2])
    test_vector_store.add_chunks(chunks_v2, emb_v2)

    assert test_vector_store.count() == 1
    stored = test_vector_store.get_by_document(doc_id)
    assert len(stored) == 1
    assert stored[0].text == "Updated single chunk version."


def test_dimension_mismatch_rejection_add(test_vector_store: ChromaVectorStore) -> None:
    """Verify add_chunks raises ValueError when embedding dimension does not match settings."""
    doc_id = uuid.uuid4()
    chunks = [_make_sample_chunk(doc_id, 1, "Text")]
    # Pass 10-dimensional vector instead of 384
    bad_embeddings = [[0.1] * 10]

    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        test_vector_store.add_chunks(chunks, bad_embeddings)


def test_dimension_mismatch_rejection_search(test_vector_store: ChromaVectorStore) -> None:
    """Verify search raises ValueError when query vector dimension does not match settings."""
    bad_query_vector = [0.1] * 10
    with pytest.raises(ValueError, match="Query embedding dimension mismatch"):
        test_vector_store.search(bad_query_vector, top_k=5)


def test_search_pre_retrieval_filtering(test_vector_store: ChromaVectorStore, mock_embedder: DeterministicMockEmbeddingProvider) -> None:
    """Verify search pre-retrieval filter restricts candidates strictly to authorized documents."""
    doc_eng = uuid.uuid4()
    doc_fin = uuid.uuid4()

    eng_chunk = _make_sample_chunk(doc_eng, 1, "Kubernetes cluster configuration guide.")
    fin_chunk = _make_sample_chunk(doc_fin, 1, "Quarterly corporate revenue and dividend forecast.")

    all_chunks = [eng_chunk, fin_chunk]
    embeddings = mock_embedder.embed_documents([c.text for c in all_chunks])
    test_vector_store.add_chunks(all_chunks, embeddings)
    assert test_vector_store.count() == 2

    query_vec = mock_embedder.embed_query("Kubernetes cluster")

    # 1. Search unrestricted
    all_results = test_vector_store.search(query_vec, top_k=5)
    assert len(all_results) == 2

    # 2. Search restricted to Engineering doc
    eng_results = test_vector_store.search(query_vec, top_k=5, allowed_document_ids=[doc_eng])
    assert len(eng_results) == 1
    assert eng_results[0].document_id == doc_eng

    # 3. Search restricted to Finance doc
    fin_results = test_vector_store.search(query_vec, top_k=5, allowed_document_ids=[doc_fin])
    assert len(fin_results) == 1
    assert fin_results[0].document_id == doc_fin

    # 4. Search with empty allowed list fails closed (returns empty immediately)
    empty_results = test_vector_store.search(query_vec, top_k=5, allowed_document_ids=[])
    assert empty_results == []


def test_delete_by_document(test_vector_store: ChromaVectorStore, mock_embedder: DeterministicMockEmbeddingProvider) -> None:
    """Verify deleting a document removes only its chunks and leaves other documents intact."""
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()

    chunk_a = _make_sample_chunk(doc_a, 1, "Doc A content.")
    chunk_b = _make_sample_chunk(doc_b, 1, "Doc B content.")

    embeddings = mock_embedder.embed_documents([chunk_a.text, chunk_b.text])
    test_vector_store.add_chunks([chunk_a, chunk_b], embeddings)
    assert test_vector_store.count() == 2

    # Delete Doc A
    deleted_count = test_vector_store.delete_by_document(doc_a)
    assert deleted_count == 1
    assert test_vector_store.count() == 1

    # Verify Doc B remains
    remaining = test_vector_store.get_by_document(doc_b)
    assert len(remaining) == 1
    assert remaining[0].text == "Doc B content."

    # Verify Doc A is gone
    gone = test_vector_store.get_by_document(doc_a)
    assert gone == []


def test_health_check_and_reset(test_vector_store: ChromaVectorStore) -> None:
    """Verify health_check responds True and reset clears all vectors."""
    assert test_vector_store.health_check() is True
    test_vector_store.reset()
    assert test_vector_store.count() == 0
