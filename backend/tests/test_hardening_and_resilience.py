"""Unit and integration tests for Phase 20 Release Hardening, Feature Flags, Health, and Disaster Recovery."""

from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.feature_flags import get_feature_flags
from app.models.user import User
from app.services.disaster_recovery import DisasterRecoveryService
from app.services.vector_store import get_vector_store
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf

settings = get_settings()


def _upload_test_document(client: TestClient, manager_user: User, dept_id: str, title: str, content: str) -> dict:
    """Helper to upload and index a test PDF document."""
    pdf_bytes = _create_sample_pdf([content])
    files = {"file": ("test_hardening.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": dept_id, "title": title}
    res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(manager_user.id))
    assert res.status_code == 201
    return res.json()


def test_readiness_probe_deep_dependencies(client: TestClient) -> None:
    """Verify /health/ready tests database, vector store, storage, and providers without leaking secrets."""
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ready"
    assert "checks" in data
    checks = data["checks"]

    # Verify deep probes are checked
    assert checks["configuration"] == "healthy"
    assert checks["storage"] == "healthy"
    assert checks["database"] == "healthy"
    assert checks["vector_store"] == "healthy"
    assert checks["embedding_provider"] == "healthy"
    assert checks["llm_provider"] == "healthy"
    assert checks["feature_flags"] == "healthy"

    # Verify zero secrets or file paths leaked in healthcheck output
    raw_text = str(data)
    assert "password" not in raw_text.lower()
    assert "secret" not in raw_text.lower()
    assert "bearer" not in raw_text.lower()
    assert "postgresql://" not in raw_text
    assert "c:\\users" not in raw_text.lower()


def test_feature_flags_runtime_toggling(client: TestClient, seeded_db: dict) -> None:
    """Verify runtime feature flags can be inspected, toggled, and reset to defaults."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    alice = users["alice@example.com"]

    # 1. Get current flags
    res = client.get("/api/v1/operations/feature-flags", headers=get_auth_header(alice.id))
    assert res.status_code == 200
    flags = res.json()
    assert flags["enable_hybrid_retrieval"] is True
    assert flags["enable_workflows"] is True

    # 2. Update flags as Admin
    patch_payload = {
        "enable_hybrid_retrieval": False,
        "enable_workflows": False,
    }
    patch_res = client.patch(
        "/api/v1/operations/feature-flags",
        json=patch_payload,
        headers=get_auth_header(admin.id),
    )
    assert patch_res.status_code == 200
    updated_flags = patch_res.json()
    assert updated_flags["enable_hybrid_retrieval"] is False
    assert updated_flags["enable_workflows"] is False

    # 3. Verify workflow is disabled (503 Service Unavailable)
    wf_res = client.get("/api/v1/workflows/tools", headers=get_auth_header(alice.id))
    assert wf_res.status_code == 503
    assert "temporarily disabled" in wf_res.json()["detail"]

    # 4. Reset flags back to defaults
    reset_res = client.post("/api/v1/operations/feature-flags/reset", headers=get_auth_header(admin.id))
    assert reset_res.status_code == 200
    reset_flags = reset_res.json()
    assert reset_flags["enable_hybrid_retrieval"] is True
    assert reset_flags["enable_workflows"] is True

    # 5. Workflows should be enabled again
    wf_res2 = client.get("/api/v1/workflows/tools", headers=get_auth_header(alice.id))
    assert wf_res2.status_code == 200


def test_feature_flags_non_admin_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify standard employees cannot modify feature flags (403 Forbidden)."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    res = client.patch(
        "/api/v1/operations/feature-flags",
        json={"enable_scoped_cache": False},
        headers=get_auth_header(alice.id),
    )
    assert res.status_code == 403

    res_reset = client.post(
        "/api/v1/operations/feature-flags/reset",
        headers=get_auth_header(alice.id),
    )
    assert res_reset.status_code == 403


def test_database_backup_and_integrity_verification(client: TestClient, seeded_db: dict) -> None:
    """Verify point-in-time database snapshot creation and cryptographic integrity validation."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]

    res = client.post(
        "/api/v1/operations/disaster-recovery/backup",
        headers=get_auth_header(admin.id),
    )
    assert res.status_code == 200
    data = res.json()

    assert "filename" in data
    assert "checksum_sha256" in data
    assert data["table_counts"]["users"] >= 4
    assert data["table_counts"]["departments"] >= 2

    # Verify file was written and integrity checksum matches
    backup_path = Path(data["filepath"])
    assert backup_path.exists()

    verify_report = DisasterRecoveryService.verify_backup_integrity(backup_path)
    assert verify_report["is_valid"] is True
    assert verify_report["expected_checksum"] == data["checksum_sha256"]


def test_vector_index_rebuild_from_authoritative_database(client: TestClient, seeded_db: dict) -> None:
    """Verify vector index can be wiped and completely rebuilt from authoritative PostgreSQL records."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    admin = users["admin@example.com"]
    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]
    eng_id = str(depts["Engineering"].id)

    # 1. Upload test document into Engineering
    _upload_test_document(
        client=client,
        manager_user=charlie,
        dept_id=eng_id,
        title="Disaster Recovery Protocol",
        content="Page 1: Recovery point objective is set strictly to 15 minutes.",
    )

    query_payload = {"query": "What is the recovery point objective?", "top_k": 3}

    # Query works before rebuild
    res1 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res1.status_code == 200
    assert "15 minutes" in res1.json()["answer"]

    # 2. Simulate vector store loss/corruption by resetting vector store & clearing cache
    from app.services.cache import get_safe_cache
    vstore = get_vector_store()
    vstore.reset()
    get_safe_cache().clear()

    # Query now returns abstention because vector store index was cleared
    res2 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res2.status_code == 200
    assert res2.json()["abstained"] is True

    # 3. Admin triggers Disaster Recovery Rebuild from PostgreSQL authority
    rebuild_res = client.post(
        "/api/v1/operations/disaster-recovery/rebuild-index",
        headers=get_auth_header(admin.id),
    )
    assert rebuild_res.status_code == 200
    rebuild_data = rebuild_res.json()
    assert rebuild_data["status"] == "rebuilt"
    assert rebuild_data["documents_processed"] >= 1
    assert rebuild_data["chunks_indexed"] >= 1

    # 4. Query works again after vector store index rebuild
    res3 = client.post("/api/v1/chat/query", json=query_payload, headers=get_auth_header(alice.id))
    assert res3.status_code == 200
    assert res3.json()["abstained"] is False
    assert "15 minutes" in res3.json()["answer"]


def test_disaster_recovery_status_endpoint(client: TestClient, seeded_db: dict) -> None:
    """Verify /api/v1/operations/disaster-recovery/status returns sync status and backups list."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]

    res = client.get(
        "/api/v1/operations/disaster-recovery/status",
        headers=get_auth_header(admin.id),
    )
    assert res.status_code == 200
    data = res.json()

    assert "database_active_chunks" in data
    assert "vector_store_healthy" in data
    assert "recent_backups_count" in data
    assert isinstance(data["recent_backups"], list)


def test_secrets_sanitization_in_configs() -> None:
    """Verify application configuration does not expose secrets in representations."""
    cfg = get_settings()
    rep = repr(cfg)
    assert "test-secret" not in rep
    assert "gsk_" not in rep
