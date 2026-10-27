"""Integration tests for document indexing lifecycle, chunk inspection, and RBAC enforcement."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.services.vector_store import get_vector_store
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def test_upload_auto_indexing_and_chunk_inspection(client: TestClient, seeded_db: dict) -> None:
    """Verify document upload automatically indexes chunks and owner can inspect them."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    diana = users["diana@example.com"]      # HR Manager (cross-department)
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Microservices deployment instructions and container orchestrator parameters.",
        "Page 2: Incident response checklist for on-call engineers.",
    ])

    files = {"file": ("eng_playbook.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "title": "Engineering Playbook"}
    headers_charlie = get_auth_header(charlie.id)

    # 1. Upload document as Charlie (Engineering Manager)
    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers_charlie)
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    doc_id = upload_data["document"]["id"]
    assert upload_data["document"]["status"] == "indexed"

    # 2. Inspect chunks as Charlie (uploader/manager)
    chunks_res = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_charlie)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) == 2
    assert "Page 1" in chunks[0]["location"]
    assert "Page 2" in chunks[1]["location"]

    # 3. Inspect chunks as Alice (Engineering employee - same department)
    headers_alice = get_auth_header(alice.id)
    alice_chunks_res = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_alice)
    assert alice_chunks_res.status_code == 200
    assert len(alice_chunks_res.json()) == 2

    # 4. Unauthorized inspection attempt by Diana (HR Manager - cross-department)
    headers_diana = get_auth_header(diana.id)
    diana_res = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_diana)
    assert diana_res.status_code == 403

    # 5. Manual re-indexing endpoint test
    reindex_res = client.post(f"/api/v1/documents/{doc_id}/index", headers=headers_charlie)
    assert reindex_res.status_code == 200
    reindex_data = reindex_res.json()
    assert reindex_data["status"] == "indexed"
    assert reindex_data["chunks_indexed"] == 2

    # 6. Unauthorized re-index attempt by regular employee (Alice)
    alice_reindex_res = client.post(f"/api/v1/documents/{doc_id}/index", headers=headers_alice)
    assert alice_reindex_res.status_code == 403

    # 7. Document deletion purges vector store chunks
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=headers_charlie)
    assert del_res.status_code == 200

    vstore = get_vector_store()
    remaining_chunks = vstore.get_by_document(uuid.UUID(doc_id))
    assert remaining_chunks == []
