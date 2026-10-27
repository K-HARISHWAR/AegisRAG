"""Integration tests for document upload API, security validation, extraction lifecycle, and deletion."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient

from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_docx, _create_sample_pdf, _create_sample_xlsx


def test_manager_pdf_upload_success(client: TestClient, seeded_db: dict) -> None:
    """Verify department manager can upload valid PDF to their assigned department."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Engineering Manager
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf([
        "Page 1: Microservices deployment instructions and container orchestrator parameters.",
        "Page 2: Incident response checklist for on-call engineers.",
    ])

    files = {"file": ("deployment_guide.pdf", pdf_bytes, "application/pdf")}
    data = {
        "department_id": str(eng_id),
        "title": "Production Deployment Guide",
        "is_confidential": "false",
    }

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["document"]["title"] == "Production Deployment Guide"
    assert res_data["document"]["file_type"] == "pdf"
    assert res_data["document"]["status"] in ("uploaded", "indexed")
    assert res_data["extraction_status"] == "success"
    assert res_data["total_passages"] == 2


def test_manager_docx_upload_success(client: TestClient, seeded_db: dict) -> None:
    """Verify department manager can upload valid DOCX file and extract paragraphs."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id

    docx_bytes = _create_sample_docx(["Architecture decision records: choosing PostgreSQL and ChromaDB."])
    files = {"file": ("adr_001.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"department_id": str(eng_id), "is_confidential": "false"}

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 201
    assert response.json()["document"]["file_type"] == "docx"
    assert response.json()["total_passages"] >= 1


def test_manager_xlsx_upload_success(client: TestClient, seeded_db: dict) -> None:
    """Verify manager can upload XLSX spreadsheet with cell coordinate provenance."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    diana = users["diana@example.com"]  # HR Manager
    hr_id = depts["HR"].id

    xlsx_bytes = _create_sample_xlsx({
        "Headcount": [
            ["Role", "Openings", "Budget"],
            ["Staff Engineer", "2", "$400k"],
        ]
    })
    files = {"file": ("q4_headcount.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"department_id": str(hr_id), "is_confidential": "true"}

    headers = get_auth_header(diana.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 201
    assert response.json()["document"]["file_type"] == "xlsx"
    assert response.json()["document"]["is_confidential"] is True


def test_employee_upload_denied(client: TestClient, seeded_db: dict) -> None:
    """Verify regular employees are denied upload permissions."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    alice = users["alice@example.com"]  # Employee
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf(["Test page"])
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id)}

    headers = get_auth_header(alice.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 403
    assert "not authorized to upload documents" in response.json()["detail"]


def test_manager_upload_to_other_department_denied(client: TestClient, seeded_db: dict) -> None:
    """Verify managers cannot upload to departments they do not manage."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Eng Manager
    hr_id = depts["HR"].id                  # HR department

    pdf_bytes = _create_sample_pdf(["Test page"])
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(hr_id)}

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 403
    assert "not authorized to upload documents for this department" in response.json()["detail"]


def test_disallowed_file_extension_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify unsupported extensions (.sh, .exe, .py) are rejected with HTTP 400."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id

    files = {"file": ("attack_script.sh", b"#!/bin/bash\necho dangerous", "application/x-sh")}
    data = {"department_id": str(eng_id)}

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_spoofed_file_magic_bytes_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify files with renamed extensions but invalid magic signatures are rejected."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id

    # Renamed plain text payload claiming to be a PDF
    fake_pdf = b"This is just raw ASCII text pretending to be a PDF file."
    files = {"file": ("disguised.pdf", fake_pdf, "application/pdf")}
    data = {"department_id": str(eng_id)}

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 400
    assert "Invalid PDF signature" in response.json()["detail"]


def test_oversized_file_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify files exceeding 20 MB size limit are rejected with HTTP 413."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id

    # 21 MB payload
    oversized = b"%PDF-1.4\n" + (b"0" * (21 * 1024 * 1024))
    files = {"file": ("huge_document.pdf", oversized, "application/pdf")}
    data = {"department_id": str(eng_id)}

    headers = get_auth_header(charlie.id)
    response = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)

    assert response.status_code == 413
    assert "exceeds maximum allowed limit" in response.json()["detail"]


def test_get_document_content_and_idempotent_deletion(client: TestClient, seeded_db: dict) -> None:
    """Verify content retrieval respects RBAC and document deletion is idempotent."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    charlie = users["charlie@example.com"]  # Eng Manager
    bob = users["bob@example.com"]          # HR Employee
    eng_id = depts["Engineering"].id

    # 1. Charlie uploads a document
    pdf_bytes = _create_sample_pdf(["Confidential server recovery key: KEY-998877."])
    files = {"file": ("recovery.pdf", pdf_bytes, "application/pdf")}
    data = {"department_id": str(eng_id), "is_confidential": "true"}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # 2. Charlie (authorized manager) inspects content
    content_res = client.get(f"/api/v1/documents/{doc_id}/content", headers=get_auth_header(charlie.id))
    assert content_res.status_code == 200
    assert "KEY-998877" in content_res.json()["passages"][0]["text"]
    assert content_res.json()["passages"][0]["location"] == "Page 1"

    # 3. Bob (HR employee) attempts to read content: 403 Forbidden
    bob_res = client.get(f"/api/v1/documents/{doc_id}/content", headers=get_auth_header(bob.id))
    assert bob_res.status_code == 403

    # 4. Charlie deletes document
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=get_auth_header(charlie.id))
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 5. Subsequent delete call is idempotent (returns 200)
    del_again_res = client.delete(f"/api/v1/documents/{doc_id}", headers=get_auth_header(charlie.id))
    assert del_again_res.status_code == 200

    # 6. Subsequent get call returns 404
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers=get_auth_header(charlie.id))
    assert get_res.status_code == 404
