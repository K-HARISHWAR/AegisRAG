"""Safe multi-format text extraction preserving document provenance (page, paragraph, sheet/cell) and OCR/table intelligence."""

import io
from typing import Any, List, Optional
import openpyxl
from openpyxl.utils import get_column_letter
import pypdf
import docx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentExtractionPreviewResponse, DocumentPassageRead, ExtractionQualityReport
from app.services.ocr import OCRAdapter, get_ocr_adapter

logger = get_logger(__name__)
settings = get_settings()


class ExtractedPassage(BaseModel):
    """Granular extracted passage with exact citation coordinates and provenance."""

    text: str
    location: str
    passage_index: int
    extraction_method: str = "native_text"  # "native_text", "ocr", "table_aware", "spreadsheet_grid"
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Aggregate result of document text extraction including quality report."""

    passages: List[ExtractedPassage]
    total_characters: int
    status: str  # "success", "scanned_warning", "empty_warning", "quarantined", "failed"
    warning_message: str | None = None
    quality_report: ExtractionQualityReport
    metadata: dict[str, Any] = Field(default_factory=dict)


def extract_pdf(
    file_bytes: bytes,
    filename: Optional[str] = None,
    ocr_adapter: Optional[OCRAdapter] = None,
) -> ExtractionResult:
    """Extract text from PDF pages, preserving page numbers, tables, and routing scanned pages to OCR."""
    passages: List[ExtractedPassage] = []
    total_chars = 0
    warnings: List[str] = []
    ocr_pages = 0
    native_pages = 0
    empty_pages = 0
    ocr = ocr_adapter or get_ocr_adapter()

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        num_pages = len(reader.pages)

        # Enforce maximum page count limit to prevent decompression/DoS attacks
        if num_pages > settings.MAX_DOCUMENT_PAGES:
            quarantine_msg = f"Document page count ({num_pages}) exceeds allowed limit of {settings.MAX_DOCUMENT_PAGES} pages."
            return ExtractionResult(
                passages=[],
                total_characters=0,
                status="failed",
                warning_message=quarantine_msg,
                quality_report=ExtractionQualityReport(
                    pages_processed=num_pages,
                    total_characters=0,
                    quality_score=0.0,
                    warnings=[quarantine_msg],
                    is_quarantined=True,
                    quarantine_reason=quarantine_msg,
                ),
                metadata={"format": "pdf", "page_count": num_pages},
            )

        for page_idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()

            # Rule: Native-text PDF is not duplicated by OCR.
            # If native text exists and is sufficient, use native extraction and skip OCR for this page.
            if len(text) >= settings.OCR_MIN_CHARS_PER_PAGE:
                total_chars += len(text)
                native_pages += 1
                passages.append(
                    ExtractedPassage(
                        text=text,
                        location=f"Page {page_idx}",
                        passage_index=len(passages) + 1,
                        extraction_method="native_text",
                        confidence=1.0,
                        metadata={"page_number": page_idx, "page_count": num_pages, "extraction_method": "native_text"},
                    )
                )
            else:
                # Scanned or image-heavy page detected: Attempt OCR if images or scans exist
                ocr_applied = False
                has_page_images = hasattr(page, "images") and len(page.images) > 0

                if settings.ENABLE_OCR and (has_page_images or len(text) == 0):
                    # Extract embedded image data if present in page
                    img_bytes: Optional[bytes] = None
                    if has_page_images:
                        try:
                            img_bytes = page.images[0].data
                        except Exception:
                            img_bytes = None

                    # If page explicitly has image objects, or single-page image PDF
                    if not img_bytes and has_page_images:
                        img_bytes = file_bytes

                    if img_bytes:
                        ocr_res = ocr.extract_text_from_image(img_bytes, page_number=page_idx)
                        cleaned_ocr = ocr_res.text.strip()
                        if cleaned_ocr:
                            ocr_pages += 1
                            total_chars += len(cleaned_ocr)
                            ocr_applied = True

                            if ocr_res.is_low_quality or ocr_res.warning:
                                warn_text = ocr_res.warning or f"Low-quality OCR on Page {page_idx} (confidence: {ocr_res.confidence:.2f})"
                                warnings.append(warn_text)

                            passages.append(
                                ExtractedPassage(
                                    text=cleaned_ocr,
                                    location=f"Page {page_idx}",
                                    passage_index=len(passages) + 1,
                                    extraction_method="ocr",
                                    confidence=ocr_res.confidence,
                                    metadata={
                                        "page_number": page_idx,
                                        "page_count": num_pages,
                                        "extraction_method": "ocr",
                                        "ocr_confidence": ocr_res.confidence,
                                        "is_low_quality": ocr_res.is_low_quality,
                                        **ocr_res.metadata,
                                    },
                                )
                            )

                if not ocr_applied:
                    if text:
                        total_chars += len(text)
                        native_pages += 1
                        passages.append(
                            ExtractedPassage(
                                text=text,
                                location=f"Page {page_idx}",
                                passage_index=len(passages) + 1,
                                extraction_method="native_text",
                                confidence=0.8,
                                metadata={"page_number": page_idx, "page_count": num_pages},
                            )
                        )
                    else:
                        empty_pages += 1

        # Determine extraction quality and overall status
        status = "success"
        main_warning = None

        if len(passages) == 0 and num_pages > 0:
            status = "scanned_warning"
            main_warning = "Scanned PDF detected with little or no extractable text. OCR is required."
            warnings.append(main_warning)
        elif ocr_pages > 0 and native_pages == 0:
            status = "success"
            if any("Low-quality OCR" in w for w in warnings):
                main_warning = "Scanned PDF extracted with low-confidence OCR warnings."
        elif total_chars < 50 and num_pages > 0:
            status = "scanned_warning"
            main_warning = "Scanned PDF detected with little or no extractable text. OCR is required."

        quality_score = 1.0
        if num_pages > 0:
            base_score = (native_pages * 1.0 + ocr_pages * 0.85) / num_pages
            quality_score = max(0.1, min(1.0, round(base_score, 2)))
            if any("Low-quality OCR" in w for w in warnings):
                quality_score = min(quality_score, 0.50)

        quality_report = ExtractionQualityReport(
            pages_processed=num_pages,
            ocr_pages=ocr_pages,
            native_text_pages=native_pages,
            empty_pages=empty_pages,
            total_characters=total_chars,
            quality_score=quality_score,
            warnings=warnings,
            extraction_methods=list(set(p.extraction_method for p in passages)) if passages else ["native_text"],
            has_tables=False,
            has_ocr=ocr_pages > 0,
            is_quarantined=False,
        )

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=main_warning or (warnings[0] if warnings else None),
            quality_report=quality_report,
            metadata={"page_count": num_pages, "format": "pdf", "filename": filename},
        )
    except Exception as exc:
        logger.error("PDF extraction failed: %s", str(exc))
        fail_msg = f"Failed to parse PDF document: {str(exc)}"
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=fail_msg,
            quality_report=ExtractionQualityReport(
                pages_processed=0,
                total_characters=0,
                quality_score=0.0,
                warnings=[fail_msg],
                is_quarantined=False,
            ),
            metadata={"format": "pdf"},
        )


def extract_docx(file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
    """Extract text from DOCX files, preserving paragraph order and pairing table rows with column headers."""
    passages: List[ExtractedPassage] = []
    total_chars = 0
    warnings: List[str] = []
    table_count = 0

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
                        extraction_method="native_text",
                        confidence=1.0,
                        metadata={"paragraph_number": p_idx},
                    )
                )

        # 2. Table-aware extraction: retain column headers with each row
        table_count = len(doc.tables)
        for t_idx, table in enumerate(doc.tables, start=1):
            if not table.rows:
                continue

            # First row defines table column headers
            header_cells = [c.text.strip() for c in table.rows[0].cells]
            headers = [h if h else f"Column {i+1}" for i, h in enumerate(header_cells)]
            header_summary = ", ".join(h for h in headers if h)[:40]

            for r_idx, row in enumerate(table.rows, start=1):
                raw_cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if not raw_cell_texts:
                    continue

                raw_line = " | ".join(raw_cell_texts)

                if r_idx == 1:
                    # Header row
                    row_content = raw_line
                    method = "native_text"
                else:
                    # Data row with explicit header pairs
                    row_pairs = []
                    for c_idx, cell in enumerate(row.cells):
                        cell_val = cell.text.strip()
                        if cell_val:
                            header_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx+1}"
                            row_pairs.append(f"{header_name}: {cell_val}")
                    # Retain raw line format for backward compatibility while appending header-keyed structure
                    paired_str = " | ".join(row_pairs)
                    row_content = f"{raw_line} | {paired_str}"
                    method = "table_aware"

                total_chars += len(row_content)
                location = f"Table {t_idx}, Row {r_idx} (Headers: {header_summary})" if header_summary else f"Table {t_idx}, Row {r_idx}"
                passages.append(
                    ExtractedPassage(
                        text=row_content,
                        location=location,
                        passage_index=len(passages) + 1,
                        extraction_method=method,
                        confidence=1.0,
                        metadata={
                            "table_number": t_idx,
                            "row_number": r_idx,
                            "headers": headers,
                            "extraction_method": method,
                        },
                    )
                )

        status = "success" if total_chars > 0 else "empty_warning"
        if total_chars == 0:
            warnings.append("Document contains no extractable text.")

        quality_report = ExtractionQualityReport(
            pages_processed=1,
            native_text_pages=1,
            total_characters=total_chars,
            quality_score=1.0 if total_chars > 0 else 0.0,
            warnings=warnings,
            extraction_methods=list(set(p.extraction_method for p in passages)) if passages else ["native_text"],
            has_tables=table_count > 0,
            has_ocr=False,
        )

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=warnings[0] if warnings else None,
            quality_report=quality_report,
            metadata={"format": "docx", "table_count": table_count, "filename": filename},
        )
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", str(exc))
        fail_msg = f"Failed to parse DOCX document: {str(exc)}"
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=fail_msg,
            quality_report=ExtractionQualityReport(
                pages_processed=0,
                quality_score=0.0,
                warnings=[fail_msg],
            ),
            metadata={"format": "docx"},
        )


def extract_xlsx(file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
    """Extract text from XLSX spreadsheets, preserving workbook, sheet, cell range, and column headers."""
    passages: List[ExtractedPassage] = []
    total_chars = 0
    warnings: List[str] = []
    workbook_name = filename or "Workbook"

    try:
        # Load in read-only and data-only mode to prevent macro execution
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]

            # Discover first row with non-empty values as header row
            header_map: dict[int, str] = {}
            first_row_idx = 0

            for r_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                non_empty = [c for c in row if c is not None and str(c).strip()]
                if non_empty:
                    first_row_idx = r_idx
                    for col_idx, val in enumerate(row, start=1):
                        col_letter = get_column_letter(col_idx)
                        clean_val = str(val).strip() if val is not None else ""
                        header_map[col_idx] = clean_val if clean_val else f"Col {col_letter}"
                    break

            if not header_map:
                continue

            # Process all populated rows
            for r_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                cell_values = [str(val).strip() for val in row if val is not None and str(val).strip()]
                if not cell_values:
                    continue

                raw_line = " | ".join(cell_values)

                # Identify populated columns and cell range
                populated_cols = [c_idx for c_idx, val in enumerate(row, start=1) if val is not None and str(val).strip()]
                if populated_cols:
                    min_col = get_column_letter(min(populated_cols))
                    max_col = get_column_letter(max(populated_cols))
                    cell_range = f"{min_col}{r_idx}:{max_col}{r_idx}"
                else:
                    cell_range = f"Row{r_idx}"

                if r_idx == first_row_idx:
                    row_content = raw_line
                else:
                    row_items = []
                    for col_idx, val in enumerate(row, start=1):
                        if val is not None and str(val).strip():
                            h_name = header_map.get(col_idx, f"Col {get_column_letter(col_idx)}")
                            row_items.append(f"{h_name}: {str(val).strip()}")
                    header_line = " | ".join(row_items)
                    row_content = f"{raw_line} | Workbook: {workbook_name}, Sheet: {sheet_name}, Range: {cell_range} | {header_line}"

                total_chars += len(row_content)
                # Location satisfies both "Sheet: name!Row 1" and "Range: A2:D2"
                location = f"Sheet: {sheet_name}!Row {r_idx}, Range: {cell_range}"

                passages.append(
                    ExtractedPassage(
                        text=row_content,
                        location=location,
                        passage_index=len(passages) + 1,
                        extraction_method="spreadsheet_grid",
                        confidence=1.0,
                        metadata={
                            "workbook": workbook_name,
                            "sheet_name": sheet_name,
                            "cell_range": cell_range,
                            "column_headers": list(header_map.values()),
                            "row_number": r_idx,
                            "extraction_method": "spreadsheet_grid",
                        },
                    )
                )

        wb.close()
        status = "success" if total_chars > 0 else "empty_warning"
        if total_chars == 0:
            warnings.append("Spreadsheet contains no extractable text.")

        quality_report = ExtractionQualityReport(
            pages_processed=len(wb.sheetnames),
            native_text_pages=len(wb.sheetnames),
            total_characters=total_chars,
            quality_score=1.0 if total_chars > 0 else 0.0,
            warnings=warnings,
            extraction_methods=["spreadsheet_grid"] if passages else [],
            has_tables=True,
            has_ocr=False,
        )

        return ExtractionResult(
            passages=passages,
            total_characters=total_chars,
            status=status,
            warning_message=warnings[0] if warnings else None,
            quality_report=quality_report,
            metadata={"sheet_names": wb.sheetnames, "format": "xlsx", "filename": filename},
        )
    except Exception as exc:
        logger.error("XLSX extraction failed: %s", str(exc))
        fail_msg = f"Failed to parse XLSX document: {str(exc)}"
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=fail_msg,
            quality_report=ExtractionQualityReport(
                pages_processed=0,
                quality_score=0.0,
                warnings=[fail_msg],
            ),
            metadata={"format": "xlsx"},
        )


def extract_document_text(
    file_type: str,
    file_bytes: bytes,
    filename: Optional[str] = None,
    ocr_adapter: Optional[OCRAdapter] = None,
) -> ExtractionResult:
    """Extract text from supported document types based on extension with OCR and table intelligence."""
    norm_type = file_type.lower().lstrip(".")
    if norm_type == "pdf":
        return extract_pdf(file_bytes, filename=filename, ocr_adapter=ocr_adapter)
    elif norm_type == "docx":
        return extract_docx(file_bytes, filename=filename)
    elif norm_type == "xlsx":
        return extract_xlsx(file_bytes, filename=filename)
    else:
        err = f"Unsupported format '{file_type}' for text extraction."
        return ExtractionResult(
            passages=[],
            total_characters=0,
            status="failed",
            warning_message=err,
            quality_report=ExtractionQualityReport(
                pages_processed=0,
                quality_score=0.0,
                warnings=[err],
            ),
            metadata={"format": norm_type},
        )


def generate_extraction_preview(
    file_type: str,
    file_bytes: bytes,
    filename: str = "document",
    ocr_adapter: Optional[OCRAdapter] = None,
) -> DocumentExtractionPreviewResponse:
    """Generate admin preview of extracted content, coordinates, and quality metrics before indexing."""
    result = extract_document_text(file_type, file_bytes, filename=filename, ocr_adapter=ocr_adapter)

    preview_passages = [
        DocumentPassageRead(
            location=p.location,
            text=p.text,
            passage_index=p.passage_index,
            extraction_method=p.extraction_method,
            confidence=p.confidence,
            metadata=p.metadata,
        )
        for p in result.passages
    ]

    detected_tables = result.metadata.get("table_count", 0)
    detected_sheets = result.metadata.get("sheet_names", [])

    return DocumentExtractionPreviewResponse(
        title=filename,
        file_type=file_type.lower().lstrip("."),
        file_size_bytes=len(file_bytes),
        quality_report=result.quality_report,
        passages=preview_passages,
        total_passages=len(preview_passages),
        detected_tables=detected_tables,
        detected_sheets=detected_sheets,
    )
