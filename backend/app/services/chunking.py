"""Deterministic text chunking preserving source provenance and stable content hashes."""

import hashlib
import uuid
from typing import Any, List

from app.schemas.chunk import Chunk
from app.services.extraction import ExtractedPassage


def split_text_with_overlap(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """Split text into overlapping segments without breaking words when possible."""
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [clean_text]

    words = clean_text.split()
    chunks: List[str] = []
    current_words: List[str] = []
    current_length = 0

    for word in words:
        word_len = len(word) + 1  # include space
        if current_length + word_len > chunk_size and current_words:
            chunk_str = " ".join(current_words)
            chunks.append(chunk_str)

            # Calculate overlap words from the end of current_words
            overlap_words: List[str] = []
            overlap_len = 0
            for w in reversed(current_words):
                if overlap_len + len(w) + 1 > chunk_overlap:
                    break
                overlap_words.insert(0, w)
                overlap_len += len(w) + 1

            current_words = overlap_words
            current_length = sum(len(w) + 1 for w in current_words)

        current_words.append(word)
        current_length += word_len

    if current_words:
        final_chunk = " ".join(current_words)
        if not chunks or final_chunk != chunks[-1]:
            chunks.append(final_chunk)

    return chunks


def create_chunks_from_passages(
    passages: List[ExtractedPassage],
    document_id: uuid.UUID,
    department_id: uuid.UUID,
    document_version: int = 1,
    is_confidential: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    extra_metadata: dict[str, Any] | None = None,
) -> List[Chunk]:
    """Deterministically transform extracted passages into indexed Chunks."""
    chunks: List[Chunk] = []
    chunk_index = 1
    base_meta = extra_metadata or {}

    for passage in passages:
        sub_texts = split_text_with_overlap(
            passage.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for part_idx, sub_text in enumerate(sub_texts, start=1):
            part_suffix = f" (part {part_idx})" if len(sub_texts) > 1 else ""
            location_label = f"{passage.location}{part_suffix}"

            # Compute stable SHA-256 content hash
            hash_input = f"{document_id}:{location_label}:{sub_text}"
            content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            # Deterministic, unique chunk ID
            chunk_id = f"{document_id}_{chunk_index}_{content_hash[:8]}"

            chunk_meta = {
                **base_meta,
                **passage.metadata,
                "location": location_label,
                "part_number": part_idx,
            }

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    document_version=document_version,
                    chunk_index=chunk_index,
                    text=sub_text,
                    location=location_label,
                    department_id=department_id,
                    is_confidential=is_confidential,
                    content_hash=content_hash,
                    metadata=chunk_meta,
                )
            )
            chunk_index += 1

    return chunks
