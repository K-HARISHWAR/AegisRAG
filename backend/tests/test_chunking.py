"""Unit tests for deterministic chunking, provenance preservation, and content hashing."""

import uuid
import pytest
from app.services.chunking import create_chunks_from_passages, split_text_with_overlap
from app.services.extraction import ExtractedPassage


def test_split_text_with_overlap_basic() -> None:
    """Verify basic text splitting respects chunk size and overlap boundaries."""
    text = "One two three four five six seven eight nine ten eleven twelve."
    chunks = split_text_with_overlap(text, chunk_size=30, chunk_overlap=10)

    assert len(chunks) >= 2
    # Ensure words are not split in half
    for chunk in chunks:
        words = chunk.split()
        for w in words:
            assert w in text.split()


def test_split_text_empty_and_short() -> None:
    """Verify empty text returns empty list, and short text returns single chunk."""
    assert split_text_with_overlap("") == []
    assert split_text_with_overlap("   ") == []

    short = "Brief paragraph."
    res = split_text_with_overlap(short, chunk_size=100)
    assert res == [short]


def test_create_chunks_preserves_provenance() -> None:
    """Verify extracted passages retain precise location markers in chunk metadata."""
    doc_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    passages = [
        ExtractedPassage(
            location="Page 1",
            text="First page content discussing network topology and perimeter controls.",
            passage_index=1,
            metadata={"page_number": 1},
        ),
        ExtractedPassage(
            location="Page 2",
            text="Second page content detailing cryptographic key rotations and HSM access.",
            passage_index=2,
            metadata={"page_number": 2},
        ),
    ]

    chunks = create_chunks_from_passages(
        passages=passages,
        document_id=doc_id,
        department_id=dept_id,
        document_version=1,
        is_confidential=False,
    )

    assert len(chunks) == 2
    assert chunks[0].location == "Page 1"
    assert chunks[0].chunk_index == 1
    assert chunks[0].document_id == doc_id
    assert chunks[0].department_id == dept_id
    assert not chunks[0].is_confidential

    assert chunks[1].location == "Page 2"
    assert chunks[1].chunk_index == 2
    assert chunks[1].document_id == doc_id


def test_chunk_content_hash_stability() -> None:
    """Verify identical passage text and provenance generates identical content hash."""
    doc_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    passage_a = ExtractedPassage(
        location="Paragraph 4",
        text="Deterministic output guarantee.",
        passage_index=1,
    )

    chunks_run1 = create_chunks_from_passages([passage_a], doc_id, dept_id)
    chunks_run2 = create_chunks_from_passages([passage_a], doc_id, dept_id)

    assert len(chunks_run1) == 1
    assert len(chunks_run2) == 1
    assert chunks_run1[0].content_hash == chunks_run2[0].content_hash
    assert chunks_run1[0].chunk_id == chunks_run2[0].chunk_id

    # Modifying the text produces a different content hash
    passage_diff = ExtractedPassage(
        location="Paragraph 4",
        text="Altered output guarantee.",
        passage_index=1,
    )
    chunks_diff = create_chunks_from_passages([passage_diff], doc_id, dept_id)
    assert chunks_diff[0].content_hash != chunks_run1[0].content_hash
