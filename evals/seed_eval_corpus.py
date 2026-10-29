"""Populates database and vector store with benchmark evaluation documents and passages."""

import hashlib
import sys
import uuid
from pathlib import Path
from typing import List

# Ensure project root and backend directory are in sys.path when running standalone
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.seed import seed_database
from app.models.document import Document
from app.schemas.chunk import Chunk
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.vector_store import VectorStore, get_vector_store


def _build_chunk(
    doc_id: uuid.UUID,
    dept_id: uuid.UUID,
    chunk_index: int,
    location: str,
    text: str,
    is_confidential: bool,
    title: str,
) -> Chunk:
    hash_input = f"{doc_id}:{location}:{text}"
    content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    return Chunk(
        chunk_id=f"{doc_id}_{chunk_index}_{content_hash[:8]}",
        document_id=doc_id,
        document_version=1,
        chunk_index=chunk_index,
        text=text,
        location=location,
        department_id=dept_id,
        is_confidential=is_confidential,
        content_hash=content_hash,
        metadata={"title": title, "location": location},
    )


def get_benchmark_chunks() -> List[Chunk]:
    """Return all deterministic ground-truth chunks for the 20 evaluation benchmark questions."""
    eng_dept_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    hr_dept_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    doc_runbook_id = uuid.UUID("55555555-5555-5555-5555-555555555551")
    doc_secrets_id = uuid.UUID("55555555-5555-5555-5555-555555555552")
    doc_leave_id = uuid.UUID("55555555-5555-5555-5555-555555555553")
    doc_comp_id = uuid.UUID("55555555-5555-5555-5555-555555555554")
    doc_disc_id = uuid.UUID("55555555-5555-5555-5555-555555555555")

    chunks: List[Chunk] = []

    # 1. engineering_runbook.pdf (Engineering, Public)
    runbook_passages = [
        (1, "Page 1", "Engineering Runbook overview: system architecture and high-availability principles."),
        (2, "Page 2", "The primary deployment procedure for production services requires automated canary verification and zero-downtime rolling updates."),
        (3, "Page 3", "Monitoring and alerting policies: Prometheus metric scrapes and Grafana dashboard alerts."),
        (4, "Page 4", "Engineers rotate service account API keys using the internal key vault with 90-day automated TTL."),
        (5, "Page 5", "The SLA response time for Tier-1 engineering outages is 15 minutes."),
        (6, "Page 6", "Database migration guidelines: backwards-compatible schema modifications only."),
        (7, "Page 7", "The Q4 architecture review action items focus on multi-region database replication."),
        (8, "Page 8", "The company policy provides a 1000 dollar annual remote work stipend for engineering home office equipment."),
        (9, "Page 9", "The staging Kubernetes cluster specifications require 8 nodes with 32 CPU cores and 128 GB memory."),
    ]
    for idx, loc, txt in runbook_passages:
        chunks.append(_build_chunk(doc_runbook_id, eng_dept_id, idx, loc, txt, False, "engineering_runbook.pdf"))

    # 2. infra_secrets_master.docx (Engineering, Confidential)
    secrets_passages = [
        (1, "Section 1", "Infrastructure root credentials and hardware security module access policies."),
        (2, "Section 2", "Production VPC peering encryption keys and tunnel parameters."),
        (3, "Section 3", "The production database master credentials and failover keys are stored in Vault cluster omega-9."),
    ]
    for idx, loc, txt in secrets_passages:
        chunks.append(_build_chunk(doc_secrets_id, eng_dept_id, idx, loc, txt, True, "infra_secrets_master.docx"))

    # 3. leave_policy.pdf (HR, Public, with grant to Alice)
    leave_passages = [
        (1, "Page 1", "The annual paid time off (PTO) policy for full-time employees provides 20 standard business days."),
        (2, "Page 2", "Sick leave policy: 10 days of paid sick leave per calendar year."),
        (3, "Page 3", "Primary caregivers are provided 16 weeks of paid parental leave."),
        (4, "Page 4", "The bereavement leave policy provides 5 consecutive paid business days for immediate family members."),
        (5, "Page 5", "The health insurance deductible for in-network specialist visits is 40 dollars copay."),
        (6, "Page 6", "The procedure for requesting cross-department document access grants requires submitting an access ticket signed by the respective department manager."),
    ]
    for idx, loc, txt in leave_passages:
        chunks.append(_build_chunk(doc_leave_id, hr_dept_id, idx, loc, txt, False, "leave_policy.pdf"))

    # 4. executive_compensation_2026.xlsx (HR, Confidential)
    comp_passages = [
        (1, "Sheet: Summary!A1:C10", "Executive compensation summary table showing total executive remuneration."),
        (2, "Sheet: Bonuses!B2:F15", "The executive bonus distribution formula is calculated as 30 percent of EBITDA surplus multiplied by department performance factor."),
    ]
    for idx, loc, txt in comp_passages:
        chunks.append(_build_chunk(doc_comp_id, hr_dept_id, idx, loc, txt, True, "executive_compensation_2026.xlsx"))

    # 5. manager_disciplinary_guide.docx (HR, Confidential)
    disc_passages = [
        (1, "Section 1", "Managerial performance expectations and employee coaching frameworks."),
        (2, "Section 2", "The performance improvement plan (PIP) escalation timelines follow a 30-day, 60-day, and 90-day structured review cadence."),
    ]
    for idx, loc, txt in disc_passages:
        chunks.append(_build_chunk(doc_disc_id, hr_dept_id, idx, loc, txt, True, "manager_disciplinary_guide.docx"))

    return chunks


async def seed_eval_corpus(
    db: AsyncSession,
    vector_store: VectorStore | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> int:
    """Seed benchmark documents into PostgreSQL and upsert corresponding chunks into VectorStore."""
    if vector_store is None:
        vector_store = get_vector_store()
    if embedding_provider is None:
        embedding_provider = get_embedding_provider()

    # Seed relational data (users, roles, departments, documents, grants)
    await seed_database(db)

    # Prepare ground-truth chunks
    chunks = get_benchmark_chunks()
    texts = [c.text for c in chunks]

    # Compute dense embeddings
    embeddings = embedding_provider.embed_documents(texts)

    # Upsert chunks into vector store
    # Group by document_id to call add_chunks per document (or all together)
    indexed_count = 0
    docs_chunks: dict[uuid.UUID, List[Chunk]] = {}
    docs_embeddings: dict[uuid.UUID, List[List[float]]] = {}

    for c, emb in zip(chunks, embeddings):
        docs_chunks.setdefault(c.document_id, []).append(c)
        docs_embeddings.setdefault(c.document_id, []).append(emb)

    for doc_id, doc_chunk_list in docs_chunks.items():
        doc_embs = docs_embeddings[doc_id]
        added = vector_store.add_chunks(doc_chunk_list, doc_embs)
        indexed_count += added

    return indexed_count
