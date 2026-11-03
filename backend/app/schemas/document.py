"""Document and Grant Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentGrantRead(BaseModel):
    """Document grant representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    grantee_user_id: uuid.UUID | None = None
    grantee_role_id: uuid.UUID | None = None
    permission: str
    granted_by_user_id: uuid.UUID
    created_at: datetime


class DocumentGrantCreate(BaseModel):
    """Grant creation payload."""

    grantee_user_id: uuid.UUID | None = None
    grantee_role_id: uuid.UUID | None = None
    permission: str = "read"

    @model_validator(mode="after")
    def validate_grantee_provided(self) -> "DocumentGrantCreate":
        if self.grantee_user_id is None and self.grantee_role_id is None:
            raise ValueError("Either grantee_user_id or grantee_role_id must be provided")
        return self


class DocumentRead(BaseModel):
    """Document metadata representation for API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    logical_document_id: uuid.UUID
    title: str
    owner_id: uuid.UUID
    department_id: uuid.UUID
    file_type: str
    file_size_bytes: int
    checksum_sha256: str
    is_confidential: bool
    status: str
    version: int
    lifecycle_state: str = "active"
    supersedes_id: uuid.UUID | None = None
    effective_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    grants: list[DocumentGrantRead] = []


class DocumentCreate(BaseModel):
    """Document creation payload for metadata registration."""

    title: str
    department_id: uuid.UUID
    file_type: str
    file_size_bytes: int
    checksum_sha256: str
    is_confidential: bool = False


class ExtractionQualityReport(BaseModel):
    """Quality and provenance metrics from structured document extraction and OCR."""

    pages_processed: int = 0
    ocr_pages: int = 0
    native_text_pages: int = 0
    empty_pages: int = 0
    total_characters: int = 0
    quality_score: float = 1.0  # 0.0 to 1.0
    warnings: list[str] = Field(default_factory=list)
    extraction_methods: list[str] = Field(default_factory=list)
    has_tables: bool = False
    has_ocr: bool = False
    is_quarantined: bool = False
    quarantine_reason: str | None = None


class DocumentPassageRead(BaseModel):
    """Passage location, coordinates, and provenance representation."""

    location: str
    text: str
    passage_index: int
    extraction_method: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentContentResponse(BaseModel):
    """Extracted text passages and provenance for an authorized document."""

    document_id: uuid.UUID
    title: str
    passages: list[DocumentPassageRead]
    total_passages: int
    total_characters: int
    quality_report: ExtractionQualityReport | None = None


class DocumentUploadResponse(BaseModel):
    """Upload endpoint response including ingestion and extraction status."""

    document: DocumentRead
    extraction_status: str
    total_passages: int
    warning_message: str | None = None
    quality_report: ExtractionQualityReport | None = None


class DocumentExtractionPreviewResponse(BaseModel):
    """Detailed preview of extracted content and quality report before indexing."""

    title: str
    file_type: str
    file_size_bytes: int
    quality_report: ExtractionQualityReport
    passages: list[DocumentPassageRead]
    total_passages: int
    detected_tables: int = 0
    detected_sheets: list[str] = Field(default_factory=list)


class DocumentRevisionHistoryItem(BaseModel):
    """Document revision record in history timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    logical_document_id: uuid.UUID
    version: int
    title: str
    lifecycle_state: str
    checksum_sha256: str
    file_type: str
    file_size_bytes: int
    owner_id: uuid.UUID
    supersedes_id: uuid.UUID | None = None
    effective_date: datetime | None = None
    created_at: datetime


class DocumentHistoryResponse(BaseModel):
    """Document version timeline response."""

    logical_document_id: uuid.UUID
    title: str
    active_version: int
    total_revisions: int
    revisions: list[DocumentRevisionHistoryItem]
