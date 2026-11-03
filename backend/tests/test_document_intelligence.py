"""Unit, integration, and security tests for Phase 16 Document Intelligence, OCR, and Table Extraction."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
import docx
import openpyxl
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image

from app.services.extraction import extract_document_text, generate_extraction_preview
from app.services.ocr import MockOCRAdapter, set_ocr_adapter, DefaultOCRAdapter
from tests.conftest import get_auth_header
from tests.test_extraction import _create_sample_pdf


def _create_scanned_pdf() -> bytes:
    """Generate an image-only PDF with zero native text characters."""
    img = Image.new("RGB", (120, 60), color=(240, 240, 240))
    img_io = io.BytesIO()
    img.save(img_io, format="PNG")
    img_io.seek(0)

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    c.drawImage(ImageReader(img_io), 50, 50, width=120, height=60)
    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf.getvalue()


def _create_docx_with_table() -> bytes:
    """Generate a DOCX containing a table with explicit column headers."""
    doc = docx.Document()
    doc.add_paragraph("Enterprise Infrastructure Topology and Cluster Mapping:")

    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Cluster Name"
    hdr_cells[1].text = "IP Address"
    hdr_cells[2].text = "Security Level"

    row_data = [
        ("prod-db-omega", "10.0.4.52", "Confidential Tier-1"),
        ("staging-api-01", "10.0.8.10", "Internal Standard"),
    ]
    for cluster, ip, sec in row_data:
        row_cells = table.add_row().cells
        row_cells[0].text = cluster
        row_cells[1].text = ip
        row_cells[2].text = sec

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _create_xlsx_with_headers() -> bytes:
    """Generate an XLSX spreadsheet with sheet name and structured grid headers."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ExecutiveBonuses"

    # Row 1: Header
    ws.append(["Employee Name", "Department", "Performance Band", "Bonus Payout"])
    # Row 2 & 3: Data rows
    ws.append(["Alex Rivera", "Engineering", "Band-E8", "$65,000 USD"])
    ws.append(["Samantha Vance", "HR", "Band-M7", "$45,000 USD"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_scanned_pdf_is_searchable_with_ocr_and_page_citations(client: TestClient, seeded_db: dict) -> None:
    """Integration: Scanned PDF routes to OCR adapter, extracts text, and produces page citations in chat."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    charlie = users["charlie@example.com"]  # Engineering Manager
    alice = users["alice@example.com"]      # Engineering Employee
    eng_id = depts["Engineering"].id

    # Configure mock OCR adapter to extract exact text
    mock_ocr = MockOCRAdapter(
        default_confidence=0.96,
        text_override="The disaster recovery recovery-point-objective RPO is strictly 15 minutes for all Tier-1 clusters.",
    )
    set_ocr_adapter(mock_ocr)

    try:
        scanned_bytes = _create_scanned_pdf()

        # 1. Upload scanned PDF as Charlie
        files = {"file": ("scanned_rpo_policy.pdf", scanned_bytes, "application/pdf")}
        data = {"department_id": str(eng_id), "title": "Scanned RPO Policy"}
        up_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
        assert up_res.status_code == 201
        up_data = up_res.json()

        assert up_data["extraction_status"] in ("success", "uploaded", "indexed")
        assert up_data["quality_report"] is not None
        assert up_data["quality_report"]["ocr_pages"] >= 1
        assert up_data["quality_report"]["has_ocr"] is True

        # 2. Query as Alice
        chat_res = client.post(
            "/api/v1/chat/query",
            json={"query": "What is the disaster recovery recovery-point-objective RPO?"},
            headers=get_auth_header(alice.id),
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert chat_data["abstained"] is False
        assert "15 minutes" in chat_data["answer"]
        assert any("Page 1" in c["location"] for c in chat_data["citations"])
    finally:
        set_ocr_adapter(DefaultOCRAdapter())


def test_native_text_pdf_not_duplicated_by_ocr() -> None:
    """Unit: Native text PDF extracts digital text directly and does NOT duplicate through OCR."""
    mock_ocr = MockOCRAdapter(default_confidence=0.99, text_override="DUPLICATE OCR TEXT")
    set_ocr_adapter(mock_ocr)

    try:
        pdf_bytes = _create_sample_pdf([
            "Page 1: Native digital vector text detailing microservices deployment parameters.",
        ])

        extraction = extract_document_text("pdf", pdf_bytes, filename="native_playbook.pdf")
        assert extraction.status == "success"
        assert len(extraction.passages) == 1
        assert "Native digital vector text" in extraction.passages[0].text
        assert "DUPLICATE OCR TEXT" not in extraction.passages[0].text
        assert extraction.quality_report.native_text_pages == 1
        assert extraction.quality_report.ocr_pages == 0
        assert mock_ocr.call_count == 0  # OCR was never called!
    finally:
        set_ocr_adapter(DefaultOCRAdapter())


def test_docx_table_aware_extraction_preserves_headers() -> None:
    """Unit: DOCX table extraction binds each cell value with its column header."""
    docx_bytes = _create_docx_with_table()
    extraction = extract_document_text("docx", docx_bytes, filename="infra_clusters.docx")

    assert extraction.status == "success"
    assert extraction.quality_report.has_tables is True

    table_passages = [p for p in extraction.passages if p.extraction_method == "table_aware"]
    assert len(table_passages) == 2  # 2 data rows

    first_row = table_passages[0]
    assert "Cluster Name: prod-db-omega" in first_row.text
    assert "IP Address: 10.0.4.52" in first_row.text
    assert "Security Level: Confidential Tier-1" in first_row.text
    assert "Headers: Cluster Name, IP Address, Security Level" in first_row.location


def test_spreadsheet_extraction_preserves_sheet_and_cell_range(client: TestClient, seeded_db: dict) -> None:
    """Integration: Spreadsheet extraction preserves workbook, sheet, and exact cell range coordinates."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    charlie = users["charlie@example.com"]
    alice = users["alice@example.com"]
    eng_id = depts["Engineering"].id

    xlsx_bytes = _create_xlsx_with_headers()

    # 1. Verify extraction coordinates directly
    extraction = extract_document_text("xlsx", xlsx_bytes, filename="executive_bonuses.xlsx")
    assert extraction.status == "success"
    assert len(extraction.passages) == 3  # Header row + 2 data rows
    p1 = extraction.passages[1]  # First data row
    assert "Sheet: ExecutiveBonuses" in p1.location and "A2:D2" in p1.location
    assert "Employee Name: Alex Rivera" in p1.text
    assert "Bonus Payout: $65,000 USD" in p1.text

    # 2. Upload and verify RAG query cites exact sheet and cell range
    files = {"file": ("executive_bonuses.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"department_id": str(eng_id), "title": "Executive Bonus Schedule"}
    up_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=get_auth_header(charlie.id))
    assert up_res.status_code == 201

    chat_res = client.post(
        "/api/v1/chat/query",
        json={"query": "What is the bonus payout for Alex Rivera?"},
        headers=get_auth_header(alice.id),
    )
    assert chat_res.status_code == 200
    res_data = chat_res.json()
    assert res_data["abstained"] is False
    assert "$65,000" in res_data["answer"]
    assert any("ExecutiveBonuses" in c["location"] and "A2:D2" in c["location"] for c in res_data["citations"])


def test_malformed_and_suspicious_files_fail_safely(client: TestClient, seeded_db: dict) -> None:
    """Security: Malformed magic headers and corrupt archives fail safely without crashing."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    charlie = users["charlie@example.com"]
    eng_id = depts["Engineering"].id
    headers = get_auth_header(charlie.id)

    # 1. Spoofed extension: Text file disguised as PDF
    malicious_bytes = b"Hello, I am a plain text file pretending to be PDF."
    bad_pdf = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malicious.pdf", malicious_bytes, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Spoofed PDF"},
        headers=headers,
    )
    assert bad_pdf.status_code == 400
    assert "Invalid PDF signature" in bad_pdf.json()["detail"]

    # 2. Corrupt OpenXML archive
    corrupt_docx = client.post(
        "/api/v1/documents/upload",
        files={"file": ("broken.docx", b"PK\x03\x04corrupt_zip_payload_garbage", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"department_id": str(eng_id), "title": "Corrupt DOCX"},
        headers=headers,
    )
    assert corrupt_docx.status_code == 400


def test_low_quality_ocr_is_visibly_flagged() -> None:
    """Security/Quality: Low confidence OCR results trigger warnings and reduced quality score."""
    mock_ocr = MockOCRAdapter(default_confidence=0.45, text_override="Garbled low confidence scan")
    set_ocr_adapter(mock_ocr)

    try:
        scanned_bytes = _create_scanned_pdf()
        extraction = extract_document_text("pdf", scanned_bytes, filename="bad_scan.pdf")

        assert extraction.quality_report.ocr_pages >= 1
        assert len(extraction.quality_report.warnings) > 0
        assert any("Low-quality OCR" in w for w in extraction.quality_report.warnings)
        assert extraction.quality_report.quality_score <= 0.50
    finally:
        set_ocr_adapter(DefaultOCRAdapter())


def test_admin_extraction_preview_endpoint_rbac(client: TestClient, seeded_db: dict) -> None:
    """Security: Extraction preview endpoint requires appropriate permissions; unauthorized requests are rejected (403)."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}
    alice = users["alice@example.com"]      # Engineering Employee
    bob = users["bob@example.com"]          # HR Employee
    charlie = users["charlie@example.com"]  # Engineering Manager
    eng_id = depts["Engineering"].id

    pdf_bytes = _create_sample_pdf(["Page 1: System architecture overview and microservices boundary."])

    # 1. Charlie (Manager) previews file upload -> 200 OK
    files = {"file": ("preview_test.pdf", pdf_bytes, "application/pdf")}
    charlie_prev = client.post("/api/v1/documents/preview", files=files, headers=get_auth_header(charlie.id))
    assert charlie_prev.status_code == 200
    prev_data = charlie_prev.json()
    assert prev_data["quality_report"]["native_text_pages"] == 1
    assert len(prev_data["passages"]) == 1

    # 2. Charlie uploads confidential Engineering doc
    up_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("conf_arch.pdf", pdf_bytes, "application/pdf")},
        data={"department_id": str(eng_id), "title": "Confidential Architecture", "is_confidential": "true"},
        headers=get_auth_header(charlie.id),
    )
    assert up_res.status_code == 201
    doc_id = up_res.json()["document"]["id"]

    # 3. Charlie (Manager) previews existing document -> 200 OK
    charlie_existing = client.get(
        f"/api/v1/documents/{doc_id}/extraction-preview",
        headers=get_auth_header(charlie.id),
    )
    assert charlie_existing.status_code == 200
    assert charlie_existing.json()["title"] == "Confidential Architecture"

    # 4. Bob (HR Employee, unauthorized) tries to preview Engineering confidential document -> 403 Forbidden
    bob_existing = client.get(
        f"/api/v1/documents/{doc_id}/extraction-preview",
        headers=get_auth_header(bob.id),
    )
    assert bob_existing.status_code == 403

    # 5. Unauthorized employee without upload permissions attempts POST /preview -> 403 Forbidden
    # Bob has standard employee role without upload rights
    files_unauth = {"file": ("unauth.pdf", pdf_bytes, "application/pdf")}
    bob_unauth_prev = client.post("/api/v1/documents/preview", files=files_unauth, headers=get_auth_header(bob.id))
    assert bob_unauth_prev.status_code == 403
