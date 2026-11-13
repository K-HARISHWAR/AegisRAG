"""Unit and integration tests for Phase 19 Observability, Performance, Rate Limiting, and Scoped Caching."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.policy_codes import PolicyReasonCode
from app.models.user import User
from app.services.cache import SafeScopedCache, get_safe_cache
from app.services.generation import ABSTENTION_MESSAGE
from app.services.rate_limit import RateLimitExceeded, get_rate_limiter
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf

settings = get_settings()


def _upload_test_document(client: TestClient, manager_user: User, dept_id: str, title: str, content: str) -> dict:
    """Helper to upload and index a test PDF document."""
    pdf_bytes = _create_sample_pdf([content])
    files = {"file": ("test_doc.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": dept_id, "title": title}
    res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(manager_user.id))
    assert res.status_code == 201
    return res.json()


def test_rate_limiting_enforcement_and_headers(client: TestClient, seeded_db: dict) -> None:
    """Verify sliding-window rate limiting returns 429 and Retry-After on exhaustion."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]  # Regular employee: 30 requests/minute limit
    limiter = get_rate_limiter()

    # Set artificial small limit or invoke up to limit
    with patch.object(settings, "RATE_LIMIT_EMPLOYEE_PER_MINUTE", 3):
        # 1st request - ok
        res1 = client.post(
            "/api/v1/chat/query",
            json={"query": "Hello"},
            headers=get_auth_header(alice.id),
        )
        assert res1.status_code == 200

        # 2nd request - ok
        res2 = client.post(
            "/api/v1/chat/query",
            json={"query": "Hey"},
            headers=get_auth_header(alice.id),
        )
        assert res2.status_code == 200

        # 3rd request - ok
        res3 = client.post(
            "/api/v1/chat/query",
            json={"query": "Hi"},
            headers=get_auth_header(alice.id),
        )
        assert res3.status_code == 200

        # 4th request - should exceed limit and return 429
        res4 = client.post(
            "/api/v1/chat/query",
            json={"query": "Greetings"},
            headers=get_auth_header(alice.id),
        )
        assert res4.status_code == 429
        assert "Retry-After" in res4.headers
        assert int(res4.headers["Retry-After"]) > 0
        assert "Rate limit exceeded" in res4.json()["detail"]


def test_quota_endpoint(client: TestClient, seeded_db: dict) -> None:
    """Verify /api/v1/operations/quotas returns caller quota status."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    res = client.get("/api/v1/operations/quotas", headers=get_auth_header(alice.id))
    assert res.status_code == 200
    data = res.json()

    assert data["user_id"] == str(alice.id)
    assert data["email"] == alice.email
    assert data["role"] == "employee"
    assert data["rate_limit_per_minute"] == settings.RATE_LIMIT_EMPLOYEE_PER_MINUTE
    assert data["daily_quota"] == settings.DAILY_QUOTA_EMPLOYEE
    assert data["daily_queries_remaining"] <= data["daily_quota"]
    assert data["reset_seconds"] > 0


def test_safe_scoped_cache_hit_and_cross_user_isolation(client: TestClient, seeded_db: dict) -> None:
    """Verify cache hit on identical query for same user, but strict cache MISS for different user."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    bob = users["bob@example.com"]          # Sales Employee
    eng_id = str(depts["Engineering"].id)

    # Upload test document to Engineering
    _upload_test_document(
        client=client,
        manager_user=charlie,
        dept_id=eng_id,
        title="Microservice Deployment Guidelines",
        content="Page 1: Deployment standard requires 5 replicas per service cluster.",
    )

    query_payload = {
        "query": "How many replicas are required per service cluster?",
        "top_k": 3,
        "hybrid": True,
    }

    # 1. First query by Alice -> Cache MISS, generates response
    res1 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["abstained"] is False
    assert "5 replicas" in data1["answer"]

    # 2. Second query by Alice (identical query) -> Cache HIT!
    res2 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["answer"] == data1["answer"]
    assert data2["query_id"] == data1["query_id"]  # Cached response has same query_id

    # 3. Third query by Bob (different user, Sales department) -> MUST NOT serve Alice's cache!
    # Bob has no access to Engineering document, so he must abstain (Strict Cross-User Isolation)
    res3 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(bob.id))
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["abstained"] is True  # Bob receives abstention, NOT Alice's cached answer!
    assert data3["query_id"] != data1["query_id"]


def test_safe_scoped_cache_invalidation_on_doc_version_change(client: TestClient, seeded_db: dict) -> None:
    """Verify cache is invalidated when document versions change."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]
    eng_id = str(depts["Engineering"].id)

    # 1. Upload Document V1
    _upload_test_document(
        client=client,
        manager_user=charlie,
        dept_id=eng_id,
        title="Database Scaling Policy",
        content="Page 1: Primary database memory limit is 32 gigabytes.",
    )

    query_payload = {
        "query": "What is the primary database memory limit?",
        "top_k": 3,
        "hybrid": True,
    }

    # Alice queries V1
    res1 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res1.status_code == 200
    data1 = res1.json()
    assert "32 gigabytes" in data1["answer"]

    # Identical query -> Cache HIT
    res2 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res2.status_code == 200
    assert res2.json()["query_id"] == data1["query_id"]

    # 2. Upload new version or document to change document set/versions
    _upload_test_document(
        client=client,
        manager_user=charlie,
        dept_id=eng_id,
        title="Database Scaling Policy Update",
        content="Page 1: Primary database memory limit is updated to 64 gigabytes.",
    )

    # Query again -> doc_versions_hash changed -> Cache MISS -> Fresh generation
    res3 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["query_id"] != data1["query_id"]


def test_distributed_traces_recorded_and_sanitized(client: TestClient, seeded_db: dict) -> None:
    """Verify distributed traces record discrete stage spans, tokens, cost, and sanitize sensitive data."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    alice = users["alice@example.com"]

    # 1. Run a chat query with custom correlation ID
    custom_req_id = "test-corr-id-12345"
    chat_res = client.post(
        "/api/v1/chat/query",
        json={"query": "Hello Aegis assistant"},
        headers={**get_auth_header(alice.id), "X-Request-ID": custom_req_id},
    )
    assert chat_res.status_code == 200

    # 2. Query traces as Admin
    traces_res = client.get("/api/v1/operations/traces", headers=get_auth_header(admin.id))
    assert traces_res.status_code == 200
    traces = traces_res.json()
    assert len(traces) >= 1

    matched = [t for t in traces if t["request_id"] == custom_req_id]
    assert len(matched) == 1
    trace = matched[0]

    assert trace["request_id"] == custom_req_id
    assert trace["user_id"] == str(alice.id)
    assert trace["total_latency_ms"] > 0
    assert trace["slowest_stage"] in ["policy", "retrieval", "generation", "citation_validation", "cache", "unknown"]
    assert trace["total_tokens"] > 0
    assert trace["estimated_cost_usd"] >= 0.0

    # Verify spans contain expected stages
    span_names = [s["stage_name"] for s in trace["spans"]]
    assert "policy" in span_names

    # 3. Query individual trace by request correlation ID
    single_res = client.get(f"/api/v1/operations/traces/{custom_req_id}", headers=get_auth_header(admin.id))
    assert single_res.status_code == 200
    assert single_res.json()["request_id"] == custom_req_id

    # 4. Verify sanitization: Ensure no sensitive keywords leak into trace metadata
    for span in trace["spans"]:
        meta = span.get("metadata", {})
        for k, v in meta.items():
            assert "password" not in k.lower()
            assert "secret" not in k.lower()
            assert "authorization" not in k.lower()


def test_operations_metrics_endpoint(client: TestClient, seeded_db: dict) -> None:
    """Verify /api/v1/operations/metrics aggregates p50/p95 stage latencies and alerts."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    alice = users["alice@example.com"]

    # Run queries to populate telemetry
    client.post("/api/v1/chat/query", json={"query": "Hi"}, headers=get_auth_header(alice.id))
    client.post("/api/v1/chat/query", json={"query": "Hello"}, headers=get_auth_header(alice.id))

    metrics_res = client.get("/api/v1/operations/metrics", headers=get_auth_header(admin.id))
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()

    assert metrics["total_requests"] >= 2
    assert "stage_latencies" in metrics
    assert "slowest_stages_distribution" in metrics
    assert "cache_hit_rate" in metrics
    assert isinstance(metrics["active_alerts"], list)


def test_provider_timeout_graceful_abstention(client: TestClient, seeded_db: dict) -> None:
    """Verify system catches LLM provider timeout gracefully and falls back to responsible abstention."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]
    eng_id = str(depts["Engineering"].id)

    # Upload document so retrieval finds chunks
    _upload_test_document(
        client=client,
        manager_user=charlie,
        dept_id=eng_id,
        title="Network Gateway Runbook",
        content="Page 1: Default gateway IP address is 10.0.0.1 with subnet mask 255.255.255.0.",
    )

    # Simulate timeout in LLM provider
    async def mock_timeout(*args, **kwargs):
        raise asyncio.TimeoutError("Upstream provider timed out")

    with patch("app.services.llm.MockLLMProvider.generate", side_effect=mock_timeout):
        with patch.object(settings, "LLM_MAX_RETRIES", 1):
            with patch.object(settings, "LLM_RETRY_BACKOFF_SECONDS", 0.01):
                res = client.post(
                    "/api/v1/chat/query",
                    json={"query": "What is the default gateway IP address?", "top_k": 3},
                    headers=get_auth_header(alice.id),
                )
                assert res.status_code == 200
                data = res.json()

                # Must gracefully abstain without crashing
                assert data["abstained"] is True
                assert data["abstention_reason"] == "provider_timeout"
                assert data["answer"] == ABSTENTION_MESSAGE


def test_admin_cache_purge_and_rbac(client: TestClient, seeded_db: dict) -> None:
    """Verify admin can purge cache, but standard user is denied (HTTP 403)."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    alice = users["alice@example.com"]

    # Alice cannot purge cache -> 403 Forbidden
    res_alice = client.post("/api/v1/operations/cache/clear", headers=get_auth_header(alice.id))
    assert res_alice.status_code == 403

    # Admin can purge cache -> 200 OK
    res_admin = client.post("/api/v1/operations/cache/clear", headers=get_auth_header(admin.id))
    assert res_admin.status_code == 200
    assert "cleared_entries" in res_admin.json()
