"""Document indexing orchestration: extraction, chunking, embedding generation, and vector store upsert."""

import uuid
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import Document
from app.schemas.chunk import Chunk
from app.services.chunking import create_chunks_from_passages
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.extraction import extract_document_text
from app.services.storage import StorageProvider, get_storage_provider
from app.services.vector_store import VectorStore, get_vector_store

logger = get_logger(__name__)


async def index_document(
    document: Document,
    db: AsyncSession,
    storage: StorageProvider | None = None,
    vector_store: VectorStore | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> int:
    """Extract, chunk, embed, and index a single document.
    
    Updates document status to 'indexed' upon success, or 'failed' if extraction/indexing fails.
    Returns the number of indexed chunks.
    """
    if storage is None:
        storage = get_storage_provider()
    if vector_store is None:
        vector_store = get_vector_store()
    if embedding_provider is None:
        embedding_provider = get_embedding_provider()

    # If document is marked deleted, purge any existing vectors and exit
    if document.status == "deleted":
        vector_store.delete_by_document(document.id)
        return 0

    try:
        # 1. Read document binary from storage
        file_bytes = await storage.read_file(document.storage_key)
    except FileNotFoundError:
        logger.error("Storage file not found for document %s (key=%s)", document.id, document.storage_key)
        document.status = "failed"
        db.add(document)
        await db.commit()
        return 0
    except Exception as exc:
        logger.error("Error reading file for document %s: %s", document.id, exc)
        document.status = "failed"
        db.add(document)
        await db.commit()
        return 0

    # 2. Extract structured text passages
    extraction = extract_document_text(document.file_type, file_bytes)
    if extraction.status == "failed" or not extraction.passages:
        logger.warning(
            "Extraction yielded no passages or failed for document %s: %s",
            document.id,
            extraction.warning_message,
        )
        # If extraction produced zero passages (e.g. empty file or scanned image without OCR)
        if extraction.status == "failed":
            document.status = "failed"
            db.add(document)
            await db.commit()
            return 0

    # 3. Deterministically chunk passages preserving location provenance
    chunks = create_chunks_from_passages(
        passages=extraction.passages,
        document_id=document.id,
        department_id=document.department_id,
        document_version=document.version,
        is_confidential=document.is_confidential,
        extra_metadata={"title": document.title},
    )

    if not chunks:
        logger.info("No chunks created for document %s", document.id)
        document.status = "indexed"
        db.add(document)
        await db.commit()
        return 0

    # 4. Generate dense embeddings for chunk texts
    chunk_texts = [c.text for c in chunks]
    try:
        embeddings = embedding_provider.embed_documents(chunk_texts)
    except Exception as exc:
        logger.error("Embedding generation failed for document %s: %s", document.id, exc)
        document.status = "failed"
        db.add(document)
        await db.commit()
        raise

    # 5. Upsert into vector store idempotently
    vector_store.add_chunks(chunks, embeddings)

    # 6. Update database document lifecycle status
    document.status = "indexed"
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info(
        "Successfully indexed document %s (%d passages -> %d chunks)",
        document.id,
        len(extraction.passages),
        len(chunks),
    )
    return len(chunks)


async def reindex_all_documents(
    db: AsyncSession,
    storage: StorageProvider | None = None,
    vector_store: VectorStore | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> Dict[str, Any]:
    """Reindex all active (non-deleted) documents."""
    if storage is None:
        storage = get_storage_provider()
    if vector_store is None:
        vector_store = get_vector_store()
    if embedding_provider is None:
        embedding_provider = get_embedding_provider()

    stmt = select(Document).where(Document.status != "deleted")
    result = await db.execute(stmt)
    documents = result.scalars().all()

    total_chunks = 0
    indexed_docs = 0
    failures = 0

    for doc in documents:
        try:
            count = await index_document(
                document=doc,
                db=db,
                storage=storage,
                vector_store=vector_store,
                embedding_provider=embedding_provider,
            )
            total_chunks += count
            indexed_docs += 1
        except Exception as exc:
            logger.error("Failed to reindex document %s: %s", doc.id, exc)
            failures += 1

    return {
        "total_documents": len(documents),
        "indexed_documents": indexed_docs,
        "total_chunks_indexed": total_chunks,
        "failures": failures,
    }
