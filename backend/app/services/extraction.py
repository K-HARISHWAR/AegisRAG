"""Safe multi-format text extraction preserving document provenance (page, paragraph, sheet/cell)."""

import io
from typing import Any, List
from pydantic import BaseModel
import pypdf
import docx
import openpyxl

from app.core.logging import get_logger

logger = get_logger(__name__)


class ExtractedPassage(BaseModel):
    """Granular extracted passage with exact citation coordinates."""

    text: str
    location: str
    passage_index: int
    metadata: dict[str, Any] = {}


class ExtractionResult(BaseModel):
    """Aggregate result of document text extraction."""

    passages: List[ExtractedPassage]
    total_characters: int
    status: str  # "success", "scanned_warning", "empty_warning", "failed"
    warning_message: str | None = None
    metadata: dict[str, Any] = {}


def extract_pdf(file_bytes: bytes) -> ExtractionResult:
    """Extract text from PDF pages, preserving page numbers and detecting scanned documents."""
    passages: List[ExtractedPassage] = []
    total_chars = 0

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        num_pages = len(reader.pages)

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            cleaned = text.strip()

            if cleaned:
                total_chars += len(cleaned)
                passages.append(
                    ExtractedPassage(
                        text=cleaned,
                        location=f"Page {page_idx}",
                        passage_index=len(passages) + 1,
                        metadata={"page_number": page_idx, "page_count": num_pages},
                    )
                )

        # Scanned PDF detection: very few characters extracted across multiple pages
        status = "success"
        warning = None
        if total_chars < 50 or (num_pages > 0 and (total_chars / num_pages) < 15):
            status = "scanned_warning"
            warning = "Scanned PDF detected with little or no extractable text. OCR is required."

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=warning,
            metadata={"page_count": num_pages, "format": "pdf"},
        )
    except Exception as exc:
        logger.error("PDF extraction failed: %s", str(exc))
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=f"Failed to parse PDF document: {str(exc)}",
            metadata={"format": "pdf"},
        )


def extract_docx(file_bytes: bytes) -> ExtractionResult:
    """Extract text from DOCX files, preserving paragraph order and table structures."""
    passages: List[ExtractedPassage] = []
    total_chars = 0

    try:
        doc = docx.Document(io.BytesIO(file_bytes))

        # 1. Paragraphs
        for p_idx, p in enumerate(doc.paragraphs, start=1):
            cleaned = p.text.strip()
            if cleaned:
                total_chars += len(cleaned)
                passages.append(
                    ExtractedPassage(
                        text=cleaned,
                        location=f"Paragraph {p_idx}",
                        passage_index=len(passages) + 1,
                        metadata={"paragraph_number": p_idx},
                    )
                )

        # 2. Tables
        for t_idx, table in enumerate(doc.tables, start=1):
            for r_idx, row in enumerate(table.rows, start=1):
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    row_content = " | ".join(row_texts)
                    total_chars += len(row_content)
                    passages.append(
                        ExtractedPassage(
                            text=row_content,
                            location=f"Table {t_idx}, Row {r_idx}",
                            passage_index=len(passages) + 1,
                            metadata={"table_number": t_idx, "row_number": r_idx},
                        )
                    )

        status = "success" if total_chars > 0 else "empty_warning"
        warning = "Document contains no extractable text." if total_chars == 0 else None

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=warning,
            metadata={"format": "docx"},
        )
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", str(exc))
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=f"Failed to parse DOCX document: {str(exc)}",
            metadata={"format": "docx"},
        )


def extract_xlsx(file_bytes: bytes) -> ExtractionResult:
    """Extract text from XLSX sheets, preserving sheet names and cell coordinates."""
    passages: List[ExtractedPassage] = []
    total_chars = 0

    try:
        # Load in read-only and data-only mode to prevent macro execution
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                # Filter out None and empty cells
                cell_values = [str(val).strip() for val in row if val is not None and str(val).strip()]
                if cell_values:
                    row_content = " | ".join(cell_values)
                    total_chars += len(row_content)
                    passages.append(
                        ExtractedPassage(
                            text=row_content,
                            location=f"Sheet: {sheet_name}!Row {row_idx}",
                            passage_index=len(passages) + 1,
                            metadata={"sheet_name": sheet_name, "row_number": row_idx},
                        )
                    )

        wb.close()
        status = "success" if total_chars > 0 else "empty_warning"
        warning = "Spreadsheet contains no extractable text." if total_chars == 0 else None

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=warning,
            metadata={"sheet_names": wb.sheetnames, "format": "xlsx"},
        )
    except Exception as exc:
        logger.error("XLSX extraction failed: %s", str(exc))
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=f"Failed to parse XLSX document: {str(exc)}",
            metadata={"format": "xlsx"},
        )


def extract_document_text(file_type: str, file_bytes: bytes) -> ExtractionResult:
    """Extract text from supported document types based on extension."""
    norm_type = file_type.lower().lstrip(".")
    if norm_type == "pdf":
        return extract_pdf(file_bytes)
    elif norm_type == "docx":
        return extract_docx(file_bytes)
    elif norm_type == "xlsx":
        return extract_xlsx(file_bytes)
    else:
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=f"Unsupported format '{file_type}' for text extraction.",
            metadata={"format": norm_type},
        )
