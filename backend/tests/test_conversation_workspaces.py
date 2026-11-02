"""Unit, integration, and security tests for Phase 15 Conversation Workspaces & Controlled Memory."""

import uuid
from fastapi.testclient import TestClient
import pytest

from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def test_thread_isolation_cannot_access_other_users_thread(client: TestClient, seeded_db: dict) -> None:
    """Security/IDOR: User cannot fetch, message, or delete another user's thread by ID."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    bob = users["bob@example.com"]

    # Alice creates a thread
    th_resp = client.post(
        "/api/v1/threads",
        headers=get_auth_header(alice.id),
        json={"title": "Alice Private Thread"},
    )
    assert th_resp.status_code == 201
    alice_thread_id = th_resp.json()["id"]

    # 1. Bob attempts to GET Alice's thread -> 404 (fail closed, zero IDOR leakage)
    bob_get = client.get(
        f"/api/v1/threads/{alice_thread_id}",
        headers=get_auth_header(bob.id),
    )
    assert bob_get.status_code == 404

    # 2. Bob attempts to POST a message into Alice's thread -> 404
    bob_msg = client.post(
        f"/api/v1/threads/{alice_thread_id}/messages",
        headers=get_auth_header(bob.id),
        json={"query": "Sneaky unauthorized injection"},
    )
    assert bob_msg.status_code == 404

    # 3. Bob attempts to DELETE Alice's thread -> 404
    bob_del = client.delete(
        f"/api/v1/threads/{alice_thread_id}",
        headers=get_auth_header(bob.id),
    )
    assert bob_del.status_code == 404

    # 4. Bob listing threads should NOT include Alice's thread
    bob_list = client.get("/api/v1/threads", headers=get_auth_header(bob.id))
    assert bob_list.status_code == 200
    assert not any(t["id"] == alice_thread_id for t in bob_list.json())


def test_new_thread_has_no_prior_context(client: TestClient, seeded_db: dict) -> None:
    """Integration: A new thread starts clean with zero previous messages or residual state."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]
    eng_id = depts["Engineering"].id

    headers_charlie = get_auth_header(charlie.id)
    headers_alice = get_auth_header(alice.id)

    # Ingest document
    pdf_bytes = _create_sample_pdf([
        "Page 1: The Tier-1 outage SLA guarantees initial response within 15 minutes.",
    ])
    files = {"file": ("sla_policy.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "SLA Policy"}
    up_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers_charlie)
    assert up_res.status_code == 201

    # 1. Thread 1: Ask question
    t1_resp = client.post("/api/v1/threads", headers=headers_alice, json={"title": "Thread 1"})
    t1_id = t1_resp.json()["id"]

    msg1 = client.post(
        f"/api/v1/threads/{t1_id}/messages",
        headers=headers_alice,
        json={"query": "What is the Tier-1 outage SLA response time?"},
    )
    assert msg1.status_code == 201

    t1_details = client.get(f"/api/v1/threads/{t1_id}", headers=headers_alice).json()
    assert len(t1_details["messages"]) == 2  # user + assistant

    # 2. Thread 2: Fresh thread
    t2_resp = client.post("/api/v1/threads", headers=headers_alice, json={"title": "Thread 2"})
    t2_id = t2_resp.json()["id"]

    t2_details = client.get(f"/api/v1/threads/{t2_id}", headers=headers_alice).json()
    assert len(t2_details["messages"]) == 0
    assert len(t2_details["bookmarks"]) == 0


def test_thread_rename_archive_and_delete(client: TestClient, seeded_db: dict) -> None:
    """Unit: Thread lifecycle transitions: rename, archive toggle, and permanent deletion."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    headers = get_auth_header(alice.id)

    # Create
    th = client.post("/api/v1/threads", headers=headers, json={"title": "Initial Title"}).json()
    th_id = th["id"]

    # Rename
    renamed = client.patch(
        f"/api/v1/threads/{th_id}",
        headers=headers,
        json={"title": "Updated Workspace Title"},
    ).json()
    assert renamed["title"] == "Updated Workspace Title"

    # Archive
    archived = client.patch(
        f"/api/v1/threads/{th_id}",
        headers=headers,
        json={"is_archived": True},
    ).json()
    assert archived["is_archived"] is True

    # Listing without include_archived does not return it
    active_list = client.get("/api/v1/threads", headers=headers).json()
    assert not any(t["id"] == th_id for t in active_list)

    # Listing with include_archived=true returns it
    all_list = client.get("/api/v1/threads?include_archived=true", headers=headers).json()
    assert any(t["id"] == th_id for t in all_list)

    # Delete
    del_resp = client.delete(f"/api/v1/threads/{th_id}", headers=headers)
    assert del_resp.status_code == 200

    # Ensure 404
    assert client.get(f"/api/v1/threads/{th_id}", headers=headers).status_code == 404


def test_revoked_document_access_revalidated_in_followup(client: TestClient, seeded_db: dict) -> None:
    """Security: Revoking document grant between turns blocks historical excerpt reuse in follow-up."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    alice = users["alice@example.com"]      # Engineering Employee
    charlie = users["charlie@example.com"]  # Engineering Manager
    eng_id = depts["Engineering"].id

    headers_alice = get_auth_header(alice.id)
    headers_charlie = get_auth_header(charlie.id)

    # 1. Charlie uploads a confidential document
    pdf_bytes = _create_sample_pdf([
        "Page 1: The production database master credentials are encrypted in HashiCorp Vault cluster omega-9 at port 8200.",
    ])
    files = {"file": ("database_master_vault.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Database Master Vault", "is_confidential": "true"}
    up_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers_charlie)
    assert up_res.status_code == 201
    secrets_doc_id = up_res.json()["document"]["id"]

    # 2. Charlie grants Alice temporary read access
    grant_resp = client.post(
        f"/api/v1/documents/{secrets_doc_id}/grants",
        headers=headers_charlie,
        json={"grantee_user_id": str(alice.id), "permission": "read"},
    )
    assert grant_resp.status_code == 201
    grant_id = grant_resp.json()["id"]

    # 3. Alice starts thread and asks about Vault keys (Turn 1 - Allowed)
    th_resp = client.post("/api/v1/threads", headers=headers_alice, json={"title": "Vault Inquiries"})
    th_id = th_resp.json()["id"]

    turn1 = client.post(
        f"/api/v1/threads/{th_id}/messages",
        headers=headers_alice,
        json={"query": "Where are the production database master credentials stored?"},
    )
    assert turn1.status_code == 201
    t1_data = turn1.json()
    assert t1_data["abstained"] is False
    assert any("Database Master Vault" in c.get("document_title", "") for c in t1_data["citations"])

    # Alice bookmarks a snippet while granted
    bm_resp = client.post(
        f"/api/v1/threads/{th_id}/bookmarks",
        headers=headers_alice,
        json={
            "document_id": str(secrets_doc_id),
            "title": "Secret location",
            "snippet": "Stored in Vault cluster omega-9",
            "location": "Page 1",
            "content_hash": "sec12345678",
        },
    )
    assert bm_resp.status_code == 201

    # 4. Charlie REVOKES Alice's grant
    del_resp = client.delete(
        f"/api/v1/documents/{secrets_doc_id}/grants/{grant_id}",
        headers=headers_charlie,
    )
    assert del_resp.status_code == 200

    # 5. Alice asks a follow-up in the same thread (Turn 2):
    # Since grant is revoked, Alice no longer has read permission on the confidential doc.
    # The retrieval filters it out, and historical context revalidates permissions, redacting revoked citations.
    turn2 = client.post(
        f"/api/v1/threads/{th_id}/messages",
        headers=headers_alice,
        json={"query": "Can you provide more details on those master credentials?"},
    )
    assert turn2.status_code == 201
    t2_data = turn2.json()
    assert not any("Database Master Vault" in c.get("document_title", "") for c in t2_data["citations"])
    assert t2_data["abstained"] is True

    # 6. Fetch thread details as Alice:
    # The bookmark to the revoked document is filtered out!
    th_details = client.get(f"/api/v1/threads/{th_id}", headers=headers_alice).json()
    assert len(th_details["messages"]) == 4  # 2 user + 2 assistant
    assert len(th_details["bookmarks"]) == 0  # Filtered out because access is revoked!


def test_bookmark_revalidation_and_access(client: TestClient, seeded_db: dict) -> None:
    """Security: Bookmarking verifies active document access; unauthorized documents cannot be bookmarked."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    docs = {d.title: d for d in seeded_db["documents"]}
    runbook_doc = docs["engineering_runbook.pdf"]
    secrets_doc = docs["infra_secrets_master.docx"]  # Confidential, Alice does not have access

    headers_alice = get_auth_header(alice.id)

    # Create thread with default empty body
    th_id = client.post("/api/v1/threads", headers=headers_alice).json()["id"]

    # 1. Bookmark snippet from runbook (Authorized) -> 201
    bm_resp = client.post(
        f"/api/v1/threads/{th_id}/bookmarks",
        headers=headers_alice,
        json={
            "document_id": str(runbook_doc.id),
            "title": "Deployment Guidelines",
            "location": "Page 2",
            "snippet": "Canary verification required before full release.",
            "content_hash": "a1b2c3d4e5f6",
            "notes": "Remember for next release",
        },
    )
    assert bm_resp.status_code == 201
    bm_data = bm_resp.json()
    assert bm_data["title"] == "Deployment Guidelines"
    bm_id = bm_data["id"]

    # 2. Attempt to bookmark snippet from secrets document (Unauthorized) -> 403
    unauth_bm = client.post(
        f"/api/v1/threads/{th_id}/bookmarks",
        headers=headers_alice,
        json={
            "document_id": str(secrets_doc.id),
            "title": "Root Vault",
            "location": "Section 3",
            "snippet": "Vault cluster omega-9",
            "content_hash": "112233445566",
        },
    )
    assert unauth_bm.status_code == 403

    # 3. Delete bookmark
    del_bm = client.delete(f"/api/v1/threads/bookmarks/{bm_id}", headers=headers_alice)
    assert del_bm.status_code == 200
