"""Pydantic schemas for read-only knowledge workflows."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStepTrace(BaseModel):
    """Step execution trace for workflow telemetry and auditing."""

    step_name: str = Field(description="Name of the workflow step")
    tool_name: str = Field(description="Allowlisted tool invoked for this step")
    status: str = Field(description="Status of step: success, failed, or skipped")
    duration_ms: float = Field(description="Execution latency in milliseconds")
    details: Dict[str, Any] = Field(default_factory=dict, description="Step metadata and context")


class SourceReference(BaseModel):
    """Source document provenance reference."""

    document_id: uuid.UUID
    title: str
    version: int
    location: str
    department_name: Optional[str] = None


# --- 1. Version Comparison Schemas ---

class VersionComparisonRequest(BaseModel):
    """Request payload to compare two document versions/revisions."""

    source_document_id: uuid.UUID = Field(description="ID of baseline document revision (v1)")
    target_document_id: uuid.UUID = Field(description="ID of target document revision (v2)")
    focus: Optional[str] = Field(None, description="Optional thematic focus (e.g., 'security', 'SLA', 'leaves')")


class ClauseDiffItem(BaseModel):
    """Individual clause or section difference between two document versions."""

    clause_type: str = Field(description="One of 'added', 'removed', or 'modified'")
    source_text: Optional[str] = Field(None, description="Clause text in source version")
    target_text: Optional[str] = Field(None, description="Clause text in target version")
    source_citation: Optional[str] = Field(None, description="Provenance citation in source version")
    target_citation: Optional[str] = Field(None, description="Provenance citation in target version")
    policy_impact: str = Field(description="Analysis of practical/operational impact of the change")
    severity_or_importance: str = Field(default="medium", description="Importance level: low, medium, or high")


class VersionComparisonResponse(BaseModel):
    """Result of multi-step version comparison workflow."""

    workflow_id: uuid.UUID
    source_document: Dict[str, Any]
    target_document: Dict[str, Any]
    executive_summary: str
    diff_items: List[ClauseDiffItem]
    total_added: int
    total_removed: int
    total_modified: int
    citations: List[str]
    steps: List[WorkflowStepTrace]
    total_duration_ms: float


# --- 2. Collection Summary Schemas ---

class CollectionSummaryRequest(BaseModel):
    """Request payload to synthesize an authorized collection of documents."""

    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Specific document IDs to synthesize")
    department_id: Optional[uuid.UUID] = Field(None, description="Department scope to summarize accessible documents")
    collection_title: Optional[str] = Field("Document Collection", description="Human-readable collection title")
    focus_query: Optional[str] = Field(None, description="Optional synthesis focus or specific questions")


class DocumentSummaryItem(BaseModel):
    """Individual document breakdown within a collection summary."""

    document_id: uuid.UUID
    title: str
    version: int
    key_takeaways: List[str]
    citations: List[str]


class CollectionSummaryResponse(BaseModel):
    """Result of multi-document authorized collection summary workflow."""

    workflow_id: uuid.UUID
    collection_title: str
    total_documents_analyzed: int
    excluded_restricted_count: int
    executive_summary: str
    thematic_findings: List[Dict[str, Any]]
    document_breakdowns: List[DocumentSummaryItem]
    citations: List[str]
    steps: List[WorkflowStepTrace]
    total_duration_ms: float


# --- 3. Structured Field Extraction Schemas ---

class StructuredExtractionRequest(BaseModel):
    """Request payload to extract structured fields and risk matrix from an authorized document."""

    document_id: uuid.UUID
    template_type: str = Field(default="general", description="Extraction template: general, policy, runbook, contract")


class ExtractedField(BaseModel):
    """Typed extracted metadata or policy requirement field."""

    field_name: str
    value: Any
    confidence: float
    citation: str
    notes: Optional[str] = None


class ExtractedRisk(BaseModel):
    """Typed risk extracted from document with severity classification."""

    risk_title: str
    description: str
    severity: str = Field(description="low, medium, high, or critical")
    mitigation: Optional[str] = None
    citation: str


class StructuredExtractionResponse(BaseModel):
    """Result of structured field and risk matrix extraction."""

    workflow_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    version: int
    owner: Optional[ExtractedField] = None
    effective_date: Optional[ExtractedField] = None
    deadline_or_cycle: Optional[ExtractedField] = None
    requirements: List[ExtractedField] = Field(default_factory=list)
    risks: List[ExtractedRisk] = Field(default_factory=list)
    compliance_obligations: List[ExtractedField] = Field(default_factory=list)
    citations: List[str]
    steps: List[WorkflowStepTrace]
    total_duration_ms: float


# --- 4. Export & Telemetry Schemas ---

class WorkflowExportRequest(BaseModel):
    """Request payload to export an authorized workflow result to Markdown, text, or PDF."""

    workflow_type: str = Field(description="'compare', 'collection_summary', or 'structured_extraction'")
    workflow_id: Optional[uuid.UUID] = None
    format: str = Field(default="markdown", description="'markdown', 'text', or 'pdf'")
    title: Optional[str] = None
    data: Dict[str, Any] = Field(description="Structured workflow output payload to export")


class WorkflowExecutionRead(BaseModel):
    """Serialized workflow execution record for history list and audit review."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_type: str
    status: str
    title: str
    total_duration_ms: int
    created_at: datetime
    steps: Optional[List[WorkflowStepTrace]] = None
    result_data: Optional[Dict[str, Any]] = None
