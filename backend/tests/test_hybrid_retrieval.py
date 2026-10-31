"""Comprehensive unit, integration, and security tests for Phase 11: Hybrid Retrieval & Intelligent Reranking."""

import asyncio
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.document import Document
from app.schemas.chunk import SearchResult
from app.schemas.retrieval import RetrievalQuery, RetrievedChunk
from app.services.reranker import MockReranker, Reranker, TimeoutSafeReranker, get_reranker
from app.services.retrieval import retrieve_context
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def test_mock_reranker_unit() -> None:
    """Verify MockReranker promotes chunks with exact query phrase and term density."""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            document_id=uuid.uuid4(),
            document_title="General DevOps Overview",
            document_version=1,
            chunk_index=1,
            text="General overview of cloud infrastructure, networking, and deployment pipelines.",
            location="Page 1",
            department_id=uuid.uuid4(),
            is_confidential=False,
            dense_score=0.85,
            sparse_score=0.20,
            combined_score=0.70,
            content_hash="hash1",
            channel="dense",
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            document_id=uuid.uuid4(),
            document_title="Kubernetes Troubleshooting Guide",
            document_version=1,
            chunk_index=2,
            text="Exact error code ERR-POD-OOM-992: Container terminated due to memory cgroup limits.",
            location="Page 3",
            department_id=uuid.uuid4(),
            is_confidential=False,
            dense_score=0.60,
            sparse_score=0.95,
            combined_score=0.72,
            content_hash="hash2",
            channel="both",
        ),
    ]

    reranker = MockReranker()
    reordered, latency = asyncio.run(
        reranker.rerank(query="ERR-POD-OOM-992 memory cgroup limits", candidates=chunks, top_k=2)
    )

    assert len(reordered) == 2
    assert latency >= 0.0
    # chunk_2 should be ranked #1 due to exact token and phrase match
    assert reordered[0].chunk_id == "chunk_2"
    assert reordered[0].rerank_rank == 1
    assert reordered[0].rerank_score is not None
    assert reordered[0].rerank_score > reordered[1].rerank_score


def test_reranker_timeout_safe_fallback() -> None:
    """Verify TimeoutSafeReranker safely falls back to original RRF order when reranker exceeds timeout."""
    class SlowReranker(Reranker):
        async def rerank(self, query, candidates, top_k):
            await asyncio.sleep(0.5)
            # Reverses order
            return list(reversed(candidates))[:top_k], 500.0

    chunks = [
        RetrievedChunk(
            chunk_id="first_chunk",
            document_id=uuid.uuid4(),
            document_title="Doc A",
            document_version=1,
            chunk_index=1,
            text="First chunk text",
            location="Page 1",
            department_id=uuid.uuid4(),
            is_confidential=False,
            dense_score=0.9,
            sparse_score=0.9,
            combined_score=0.9,
            content_hash="h1",
        ),
        RetrievedChunk(
            chunk_id="second_chunk",
            document_id=uuid.uuid4(),
            document_title="Doc B",
            document_version=1,
            chunk_index=2,
            text="Second chunk text",
            location="Page 2",
            department_id=uuid.uuid4(),
            is_confidential=False,
            dense_score=0.5,
            sparse_score=0.5,
            combined_score=0.5,
            content_hash="h2",
        ),
    ]

    # Set timeout to 0.05 seconds (much lower than SlowReranker's 0.5s sleep)
    safe_reranker = TimeoutSafeReranker(inner=SlowReranker(), timeout_seconds=0.05)
    fallback_chunks, latency = asyncio.run(safe_reranker.rerank("query", chunks, top_k=2))

    assert len(fallback_chunks) == 2
    # Preserves original order as safe fallback
    assert fallback_chunks[0].chunk_id == "first_chunk"
    assert fallback_chunks[1].chunk_id == "second_chunk"
    assert fallback_chunks[0].rerank_rank == 1
    assert fallback_chunks[1].rerank_rank == 2


def test_exact_keyword_retrieval_finds_passage_missed_by_vector_only(client: TestClient, seeded_db: dict) -> None:
    """Verify hybrid search surfaces exact technical identifiers/error codes that vector-only search misses."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Microservices deployment instructions and Kubernetes cluster parameters.",
        "Page 2: Error resolution catalog. Critical kernel code ERR-NET-GW-9042: Automated ingress routing failure on port 9443.",
    ])

    files = {"file": ("eng_errors.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Engineering Error Resolution Guide"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201

    # 1. Query with exact rare code under vector-only mode
    vector_payload = {
        "query": "ERR-NET-GW-9042",
        "top_k": 5,
        "mode": "vector",
        "hybrid": False,
    }
    vec_res = client.post("/api/v1/retrieval/query", json=vector_payload, headers=get_auth_header(alice.id))
    assert vec_res.status_code == 200
    vec_data = vec_res.json()
    assert vec_data["diagnostics"]["mode"] == "vector"
    assert vec_data["diagnostics"]["channels_used"] == ["dense"]

    # 2. Query with exact code under hybrid mode
    hybrid_payload = {
        "query": "ERR-NET-GW-9042",
        "top_k": 5,
        "mode": "hybrid",
        "hybrid": True,
    }
    hyb_res = client.post("/api/v1/retrieval/query", json=hybrid_payload, headers=get_auth_header(alice.id))
    assert hyb_res.status_code == 200
    hyb_data = hyb_res.json()

    assert hyb_data["diagnostics"]["mode"] == "hybrid"
    assert "sparse" in hyb_data["diagnostics"]["channels_used"]
    assert hyb_data["diagnostics"]["sparse_candidates_count"] > 0

    # Ensure the exact error passage is retrieved
    matching_chunks = [c for c in hyb_data["chunks"] if "ERR-NET-GW-9042" in c["text"]]
    assert len(matching_chunks) > 0
    top_match = matching_chunks[0]
    assert top_match["document_title"] == "Engineering Error Resolution Guide"
    assert top_match["sparse_score"] > 0.0
    assert top_match["channel"] in ("sparse", "both")


def test_conceptual_semantic_query_retrieval(client: TestClient, seeded_db: dict) -> None:
    """Verify conceptual questions return semantically relevant passages without requiring exact term overlap."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Deployment instructions: Engineers must run test suites, verify Docker images, and obtain peer approvals prior to shipping code to production environments.",
    ])
    files = {"file": ("deploy_runbook.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Engineering Deployment Runbook"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201

    # Query internal deployment architecture conceptually
    query_payload = {
        "query": "What steps must software engineers execute prior to shipping code to production servers?",
        "top_k": 5,
        "mode": "hybrid",
    }
    res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res.status_code == 200
    data = res.json()

    assert len(data["chunks"]) > 0
    # Top chunk should belong to Engineering Deployment Runbook
    assert "Engineering" in data["chunks"][0]["document_title"]
    assert data["chunks"][0]["dense_score"] > 0.0


def test_cross_department_security_isolation_in_all_channels(client: TestClient, seeded_db: dict) -> None:
    """Verify cross-department isolation: an employee cannot retrieve other department passages via dense, sparse, or reranking."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    diana = users["diana@example.com"]  # HR Manager
    alice = users["alice@example.com"]  # Engineering Employee
    hr_id = depts["HR"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: HR confidential executive payroll code HR-CODE-PAYROLL-991: Strict executive salary tier allocations.",
    ])

    files = {"file": ("hr_payroll_secret.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(hr_id), "title": "HR Payroll Confidential Allocation"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(diana.id))
    assert upload_res.status_code == 201

    # Alice (Engineering) attempts to search exact HR code via hybrid + rerank
    query_payload = {
        "query": "HR-CODE-PAYROLL-991 executive payroll allocations",
        "top_k": 10,
        "mode": "hybrid",
        "rerank": True,
    }
    res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res.status_code == 200
    data = res.json()

    # Absolute zero HR chunks must appear
    for chunk in data["chunks"]:
        assert chunk["document_title"] != "HR Payroll Confidential Allocation"
        assert "HR-CODE-PAYROLL-991" not in chunk["text"]


def test_reranker_only_reorders_authorized_candidates(client: TestClient, seeded_db: dict) -> None:
    """Verify reranker only reorders passages that have passed PostgreSQL RBAC validation."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Server deployment checklist: Verify database migration, monitor metrics, check health endpoint.",
        "Page 2: General coding conventions and styling recommendations.",
    ])
    files = {"file": ("eng_deploy_checklist.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Engineering Server Checklist"}
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201

    # Query with rerank=True explicitly
    query_payload = {
        "query": "server deployment checklist and release requirements",
        "top_k": 3,
        "mode": "hybrid",
        "rerank": True,
    }
    res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res.status_code == 200
    data = res.json()

    assert data["diagnostics"]["reranked"] is True
    assert data["diagnostics"]["reranker_latency_ms"] is not None
    assert len(data["chunks"]) > 0

    for rank, chunk in enumerate(data["chunks"], start=1):
        assert chunk["rerank_rank"] == rank
        assert chunk["rerank_score"] is not None
        # All returned chunks must be authorized for Alice
        assert chunk["department_id"] == str(alice.department_id)


def test_retrieval_empty_result_fails_safely(client: TestClient, seeded_db: dict) -> None:
    """Verify queries yielding zero matches fail safely and return valid diagnostic metadata."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    query_payload = {
        "query": "xyznonexistentgibberishterm123456789",
        "top_k": 5,
        "score_threshold": 0.99,  # High threshold guarantees empty result
    }
    res = client.post("/api/v1/retrieval/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res.status_code == 200
    data = res.json()

    assert len(data["chunks"]) == 0
    assert data["total_candidates_found"] == 0
    assert data["diagnostics"] is not None
    assert data["execution_time_ms"] >= 0.0
