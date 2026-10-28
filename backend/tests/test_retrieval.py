"""Integration and security tests for hybrid retrieval, two-stage RBAC filtering, and audit logging."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.schemas.chunk import SearchResult
from app.schemas.retrieval import RetrievalQuery
from app.services.retrieval import BM25Scorer, reciprocal_rank_fusion, retrieve_context
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def test_bm25_scorer_unit() -> None:
    """Verify BM25 ranking prioritizes passages matching query terms."""
    corpus = [
        "Kubernetes container pods and service networking configuration guide.",
        "Human resources annual open enrollment and dental health insurance plan.",
        "General quarterly business executive summary and revenue projections.",
    ]
    bm25 = BM25Scorer(corpus)
    scores_k8s = bm25.score("kubernetes networking guide")
    assert scores_k8s[0] > scores_k8s[1]
    assert scores_k8s[0] > scores_k8s[2]

    scores_hr = bm25.score("dental insurance enrollment")
    assert scores_hr[1] > scores_hr[0]
    assert scores_hr[1] > scores_hr[2]


def test_reciprocal_rank_fusion_unit() -> None:
    """Verify RRF fusion combines rankings into normalized bounded scores."""
    dense = [0.9, 0.5, 0.2]
    sparse = [0.2, 0.8, 0.1]
    fused = reciprocal_rank_fusion(dense, sparse)

    assert len(fused) == 3
    for s in fused:
        assert 0.0 <= s <= 1.0


def test_employee_department_retrieval_success(client: TestClient, seeded_db: dict) -> None:
    """Verify an employee can retrieve non-confidential documents from their assigned department."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Microservices deployment instructions and Kubernetes cluster parameters.",
        "Page 2: Incident response procedures for production on-call rotations.",
    ])

    # 1. Upload Engineering doc as Charlie
    files = {"file": ("eng_deployment.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Engineering Deployment Guide"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201

    # 2. Query as Alice (Engineering employee)
    query_payload = {
        "query": "Kubernetes microservices deployment parameters",
        "top_k": 5,
        "hybrid": True,
    }
    retrieval_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert retrieval_res.status_code == 200
    res_data = retrieval_res.json()

    assert len(res_data["chunks"]) > 0
    top_chunk = res_data["chunks"][0]
    assert top_chunk["document_title"] == "Engineering Deployment Guide"
    assert "Page 1" in top_chunk["location"]
    assert top_chunk["dense_score"] > 0
    assert top_chunk["combined_score"] > 0
    assert top_chunk["content_hash"] != ""


def test_cross_department_retrieval_denied(client: TestClient, seeded_db: dict) -> None:
    """Verify an employee CANNOT retrieve documents from another department (Stage 1 pre-retrieval isolation)."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    diana = users["diana@example.com"]  # HR Manager
    alice = users["alice@example.com"]  # Engineering Employee
    hr_id = depts["HR"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: HR confidential compensation bands, salary schedules, and executive bonus formulas.",
    ])

    # 1. Upload HR document as Diana
    files = {"file": ("hr_salaries.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(hr_id), "title": "HR Salary Schedules"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(diana.id))
    assert upload_res.status_code == 201

    # 2. Alice (Engineering employee) attempts to query HR salary schedules
    query_payload = {
        "query": "compensation bands and salary schedules",
        "top_k": 5,
        "hybrid": True,
    }
    retrieval_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert retrieval_res.status_code == 200
    res_data = retrieval_res.json()

    # Zero HR chunks must be returned to Alice
    assert len(res_data["chunks"]) == 0


def test_confidential_document_retrieval_isolation(client: TestClient, seeded_db: dict) -> None:
    """Verify confidential documents are accessible to department managers but hidden from regular employees."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Secret unreleased kernel vulnerability patch and zero-day advisory.",
    ])

    # 1. Upload as confidential Engineering doc
    files = {"file": ("zero_day_patch.pdf", pdf_bytes, "application/pdf")}
    data = {
        "department_id": str(eng_id),
        "title": "Confidential Zero-Day Advisory",
        "is_confidential": "true",
    }
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201

    query_payload = {
        "query": "zero-day kernel vulnerability patch",
        "top_k": 5,
    }

    # 2. Alice (regular employee in Engineering) queries: MUST return 0 chunks
    alice_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert alice_res.status_code == 200
    assert len(alice_res.json()["chunks"]) == 0

    # 3. Charlie (department manager in Engineering) queries: CAN retrieve it
    charlie_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(charlie.id))
    assert charlie_res.status_code == 200
    charlie_chunks = charlie_res.json()["chunks"]
    assert len(charlie_chunks) > 0
    assert charlie_chunks[0]["document_title"] == "Confidential Zero-Day Advisory"


def test_explicit_grant_cross_department_retrieval(client: TestClient, seeded_db: dict) -> None:
    """Verify an explicit DocumentGrant allows cross-department retrieval for the grantee."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    diana = users["diana@example.com"]  # HR Manager
    alice = users["alice@example.com"]  # Engineering Employee
    hr_id = depts["HR"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Company-wide onboarding checklist and security awareness requirements.",
    ])

    # 1. Upload HR doc
    files = {"file": ("onboarding.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(hr_id), "title": "Onboarding Policy"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(diana.id))
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    query_payload = {"query": "onboarding checklist and security awareness", "top_k": 5}

    # 2. Before grant, Alice cannot retrieve it
    pre_grant_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert len(pre_grant_res.json()["chunks"]) == 0

    # 3. Diana grants read access explicitly to Alice
    grant_payload = {"grantee_user_id": str(alice.id), "permission": "read"}
    grant_res = client.post(f"/api/v1/documents/{doc_id}/grants", json=grant_payload, headers=get_auth_header(diana.id))
    assert grant_res.status_code == 201

    # 4. After grant, Alice CAN retrieve it
    post_grant_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert post_grant_res.status_code == 200
    chunks = post_grant_res.json()["chunks"]
    assert len(chunks) > 0
    assert chunks[0]["document_title"] == "Onboarding Policy"


@pytest.mark.asyncio
async def test_stage2_post_retrieval_revalidation_defense(db_session: AsyncSession, seeded_db: dict) -> None:
    """Verify Stage 2 drops candidate chunks if vector store metadata returns an unauthorized document ID."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    alice = users["alice@example.com"]  # Engineering Employee
    hr_id = depts["HR"].id

    # Create an HR document in DB
    hr_doc = Document(
        title="Restricted HR Records",
        owner_id=users["diana@example.com"].id,
        department_id=hr_id,
        storage_key="doc_unauthorized_key",
        file_type="pdf",
        file_size_bytes=1000,
        checksum_sha256="fake_sha256",
        is_confidential=False,
        status="indexed",
    )
    db_session.add(hr_doc)
    await db_session.commit()
    await db_session.refresh(hr_doc)

    # Mock vector store that simulates returning an unauthorized HR chunk
    class MockLeakingVectorStore:
        def search(self, **kwargs) -> list[SearchResult]:
            return [
                SearchResult(
                    chunk_id="spoofed_chunk_1",
                    document_id=hr_doc.id,  # Unauthorized for Alice!
                    document_version=1,
                    chunk_index=1,
                    text="Unauthorized HR compensation text leaked from vector store.",
                    location="Page 1",
                    department_id=hr_id,
                    is_confidential=False,
                    similarity_score=0.99,
                    metadata={"content_hash": "leak_hash"},
                )
            ]

    # Query as Alice using retrieve_context
    retrieval_query = RetrievalQuery(query="HR compensation text", top_k=5, hybrid=False)
    response = await retrieve_context(
        query_params=retrieval_query,
        current_user=alice,
        db=db_session,
        vector_store=MockLeakingVectorStore(),
    )

    # Stage 2 MUST have detected unauthorized document ID and rejected it
    assert len(response.chunks) == 0


def test_retrieval_audit_event_logged(client: TestClient, seeded_db: dict) -> None:
    """Verify an audit event is persisted upon executing a retrieval query."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    query_payload = {"query": "Audit verification query text", "top_k": 3}
    res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res.status_code == 200

    # Query audit logs as admin
    admin = users["admin@example.com"]
    audit_res = client.get("/api/v1/admin/audit-logs?limit=5", headers=get_auth_header(admin.id))
    assert audit_res.status_code == 200
    events = audit_res.json()

    query_events = [e for e in events if e["action"] == "retrieval_query"]
    assert len(query_events) > 0
    assert query_events[0]["actor_user_id"] == str(alice.id)
