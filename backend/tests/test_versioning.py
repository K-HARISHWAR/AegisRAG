"""Integration and security tests for Document Versioning, Lifecycle States, and Rollbacks."""

import uuid
import pytest
from fastapi.testclient import TestClient

from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def test_duplicate_upload_detected(client: TestClient, seeded_db: dict) -> None:
    """Verify that uploading an identical file into the same department triggers 409 Conflict."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf(["Corporate Security Policy: Passwords must be at least 16 characters."])
    files = {"file": ("sec_policy.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Corporate Security Policy"}
    headers = get_auth_header(charlie.id)

    # First upload succeeds (201 Created)
    res1 = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert res1.status_code == 201
    doc1 = res1.json()["document"]
    assert doc1["version"] == 1
    assert doc1["lifecycle_state"] == "active"
    assert doc1["logical_document_id"] == doc1["id"]

    # Re-uploading the exact same binary without revision link triggers 409 Conflict
    files2 = {"file": ("sec_policy.pdf", pdf_bytes, "application/pdf")}
    res2 = client.post("/api/v1/documents/upload", files=files2, data=data, headers=headers)
    assert res2.status_code == 409
    assert "Duplicate document detected" in res2.json()["detail"]


def test_new_version_supersedes_old_version(client: TestClient, seeded_db: dict) -> None:
    """Verify revision upload creates v2, supersedes v1, and carries over explicit grants."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]  # Regular employee
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    # 1. Upload initial v1 document (confidential)
    v1_pdf = _create_sample_pdf(["Release Protocol v1: All services must be deployed to port 8080."])
    res1 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("release_protocol.pdf", v1_pdf, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Release Protocol", "is_confidential": "true"},
        headers=headers,
    )
    assert res1.status_code == 201
    v1_doc = res1.json()["document"]
    v1_id = v1_doc["id"]

    # 2. Add an explicit grant on v1 for Alice
    grant_res = client.post(
        f"/api/v1/documents/{v1_id}/grants",
        json={"grantee_user_id": str(alice.id), "permission": "read"},
        headers=headers,
    )
    assert grant_res.status_code == 201

    # 3. Upload revision v2
    v2_pdf = _create_sample_pdf(["Release Protocol v2: All services must now be deployed to port 9090."])
    res2 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("release_protocol_v2.pdf", v2_pdf, "application/pdf")},
        data={
            "department_id": str(eng_id),
            "title": "Release Protocol",
            "revises_document_id": str(v1_id),
            "is_confidential": "true",
        },
        headers=headers,
    )
    assert res2.status_code == 201
    v2_doc = res2.json()["document"]
    v2_id = v2_doc["id"]

    # Verify v2 properties
    assert v2_doc["version"] == 2
    assert v2_doc["supersedes_id"] == v1_id
    assert v2_doc["lifecycle_state"] == "active"
    assert v2_doc["logical_document_id"] == v1_doc["logical_document_id"]

    # Verify v1 is now superseded
    v1_check = client.get(f"/api/v1/documents/{v1_id}", headers=headers)
    assert v1_check.status_code == 200
    assert v1_check.json()["lifecycle_state"] == "superseded"

    # Verify Alice inherited explicit grant access on v2
    alice_check = client.get(f"/api/v1/documents/{v2_id}", headers=get_auth_header(alice.id))
    assert alice_check.status_code == 200
    assert alice_check.json()["id"] == v2_id


def test_identical_revision_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify that uploading an identical file as a revision fails with 409 Conflict."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    pdf_bytes = _create_sample_pdf(["Architecture Roadmap 2026."])
    res1 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("roadmap.pdf", pdf_bytes, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Roadmap 2026"},
        headers=headers,
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["document"]["id"]

    # Attempt to upload identical content as revision of doc1
    res2 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("roadmap.pdf", pdf_bytes, "application/pdf")},
        data={
            "department_id": str(eng_id),
            "title": "Roadmap 2026 v2",
            "revises_document_id": str(doc1_id),
        },
        headers=headers,
    )
    assert res2.status_code == 409
    assert "Revision content is identical" in res2.json()["detail"]


def test_retrieval_does_not_mix_versions(client: TestClient, seeded_db: dict) -> None:
    """Verify vector search and hybrid retrieval strictly query only active document revisions."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    # 1. Ingest v1
    v1_pdf = _create_sample_pdf(["Microservice default database port is configured to 5432."])
    res1 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("db_config.pdf", v1_pdf, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Database Configuration"},
        headers=headers,
    )
    assert res1.status_code == 201
    v1_id = res1.json()["document"]["id"]

    # 2. Ingest v2 revising v1
    v2_pdf = _create_sample_pdf(["Microservice default database port is migrated to 6432."])
    res2 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("db_config_v2.pdf", v2_pdf, "application/pdf")},
        data={
            "department_id": str(eng_id),
            "title": "Database Configuration",
            "revises_document_id": str(v1_id),
        },
        headers=headers,
    )
    assert res2.status_code == 201
    v2_id = res2.json()["document"]["id"]

    # 3. Query retrieval pipeline for database port
    query_payload = {"query": "What is the microservice default database port?", "top_k": 5}
    ret_res = client.post("/api/v1/retrieval/query", json=query_payload, headers=headers)
    assert ret_res.status_code == 200
    chunks = ret_res.json()["chunks"]

    assert len(chunks) > 0
    # Every returned chunk must originate from the active revision (v2)
    for c in chunks:
        assert c["document_id"] == v2_id
        assert c["document_version"] == 2
        assert "5432" not in c["text"]
        assert "6432" in c["text"]


def test_version_aware_citations_and_rollback(client: TestClient, seeded_db: dict) -> None:
    """Verify generated citations reflect active version, and rollback cleanly restores v1 citations."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    # 1. Upload v1
    v1_pdf = _create_sample_pdf(["Backup retention duration is set to 30 days."])
    res1 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("backup_policy.pdf", v1_pdf, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Backup Policy"},
        headers=headers,
    )
    v1_id = res1.json()["document"]["id"]

    # 2. Upload v2
    v2_pdf = _create_sample_pdf(["Backup retention duration is updated to 90 days."])
    res2 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("backup_policy_v2.pdf", v2_pdf, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Backup Policy", "revises_document_id": str(v1_id)},
        headers=headers,
    )
    v2_id = res2.json()["document"]["id"]

    # 3. Chat query on v2
    chat_res1 = client.post(
        "/api/v1/chat/query",
        json={"query": "What is the backup retention duration?"},
        headers=headers,
    )
    assert chat_res1.status_code == 200
    res1_json = chat_res1.json()
    assert len(res1_json["citations"]) > 0
    assert res1_json["citations"][0]["document_version"] == 2
    assert res1_json["citations"][0]["document_id"] == v2_id

    # 4. Rollback to v1
    rollback_res = client.post(f"/api/v1/documents/{v1_id}/rollback", headers=headers)
    assert rollback_res.status_code == 200
    restored = rollback_res.json()
    assert restored["id"] == v1_id
    assert restored["lifecycle_state"] == "active"

    # Verify v2 is now superseded
    v2_check = client.get(f"/api/v1/documents/{v2_id}", headers=headers)
    assert v2_check.json()["lifecycle_state"] == "superseded"

    # 5. Chat query after rollback: now cites v1
    chat_res2 = client.post(
        "/api/v1/chat/query",
        json={"query": "What is the backup retention duration?"},
        headers=headers,
    )
    assert chat_res2.status_code == 200
    res2_json = chat_res2.json()
    assert len(res2_json["citations"]) > 0
    assert res2_json["citations"][0]["document_version"] == 1
    assert res2_json["citations"][0]["document_id"] == v1_id


def test_document_history_endpoint(client: TestClient, seeded_db: dict) -> None:
    """Verify /documents/{id}/history returns complete revision timeline in descending order."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    # v1
    v1_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("handbook.pdf", _create_sample_pdf(["Handbook chapter 1"]), "application/pdf")},
        data={"department_id": str(eng_id), "title": "Engineering Handbook"},
        headers=headers,
    )
    v1_id = v1_res.json()["document"]["id"]

    # v2
    v2_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("handbook_v2.pdf", _create_sample_pdf(["Handbook chapter 2"]), "application/pdf")},
        data={"department_id": str(eng_id), "title": "Engineering Handbook", "revises_document_id": str(v1_id)},
        headers=headers,
    )
    v2_id = v2_res.json()["document"]["id"]

    # v3
    v3_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("handbook_v3.pdf", _create_sample_pdf(["Handbook chapter 3"]), "application/pdf")},
        data={"department_id": str(eng_id), "title": "Engineering Handbook", "revises_document_id": str(v2_id)},
        headers=headers,
    )
    v3_id = v3_res.json()["document"]["id"]

    # Fetch history via v2_id
    history_res = client.get(f"/api/v1/documents/{v2_id}/history", headers=headers)
    assert history_res.status_code == 200
    hist = history_res.json()
    assert hist["total_revisions"] == 3
    assert hist["active_version"] == 3
    assert len(hist["revisions"]) == 3

    # Check order is descending by version
    assert hist["revisions"][0]["version"] == 3
    assert hist["revisions"][0]["id"] == v3_id
    assert hist["revisions"][0]["lifecycle_state"] == "active"

    assert hist["revisions"][1]["version"] == 2
    assert hist["revisions"][1]["id"] == v2_id
    assert hist["revisions"][1]["lifecycle_state"] == "superseded"

    assert hist["revisions"][2]["version"] == 1
    assert hist["revisions"][2]["id"] == v1_id
    assert hist["revisions"][2]["lifecycle_state"] == "superseded"


def test_unauthorized_revision_and_rollback_denied(client: TestClient, seeded_db: dict) -> None:
    """Verify regular employees or unprivileged managers cannot revise or roll back documents."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Eng Manager
    bob = users["bob@example.com"]          # HR Employee
    eng_id = depts["Engineering"].id

    # 1. Charlie uploads initial doc
    v1_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("prod_secrets.pdf", _create_sample_pdf(["Secret key: 12345"]), "application/pdf")},
        data={"department_id": str(eng_id), "title": "Secrets"},
        headers=get_auth_header(charlie.id),
    )
    v1_id = v1_res.json()["document"]["id"]

    # 2. Bob attempts to revise Charlie's document -> 403 Forbidden
    v2_pdf = _create_sample_pdf(["Bob's modified secrets."])
    rev_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("fake_secrets.pdf", v2_pdf, "application/pdf")},
        data={"department_id": str(eng_id), "revises_document_id": str(v1_id)},
        headers=get_auth_header(bob.id),
    )
    assert rev_res.status_code == 403

    # 3. Bob attempts to call rollback -> 403 Forbidden
    rb_res = client.post(f"/api/v1/documents/{v1_id}/rollback", headers=get_auth_header(bob.id))
    assert rb_res.status_code == 403
