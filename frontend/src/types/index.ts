/**
 * AegisRAG TypeScript Data Definitions
 * Mapped directly to server-verified FastAPI & SQLAlchemy schemas.
 */

export interface Role {
  id: string;
  name: string;
  description?: string | null;
}

export interface Department {
  id: string;
  name: string;
  description?: string | null;
}

export interface User {
  id: string;
  email: string;
  department_id?: string | null;
  department?: Department | null;
  roles: Role[];
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface DocumentGrant {
  id: string;
  document_id: string;
  grantee_user_id?: string | null;
  grantee_role_id?: string | null;
  permission: string;
  granted_by_user_id: string;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  owner_id: string;
  department_id: string;
  file_type: string;
  file_size_bytes: number;
  checksum_sha256: string;
  is_confidential: boolean;
  status: 'uploaded' | 'processing' | 'indexed' | 'failed' | 'deleted' | string;
  version: number;
  logical_document_id?: string;
  supersedes_id?: string | null;
  lifecycle_state?: 'active' | 'superseded' | 'archived' | 'quarantined' | 'deleted' | string;
  effective_date?: string | null;
  created_at: string;
  updated_at: string;
  grants: DocumentGrant[];
}

export interface ExtractionQualityReport {
  pages_processed: number;
  ocr_pages: number;
  native_text_pages: number;
  empty_pages: number;
  total_characters: number;
  quality_score: number;
  warnings: string[];
  extraction_methods: string[];
  has_tables: boolean;
  has_ocr: boolean;
  is_quarantined: boolean;
  quarantine_reason?: string | null;
}

export interface DocumentContentPassage {
  index: number;
  location: string;
  text: string;
  extraction_method?: string | null;
  confidence?: number | null;
  metadata?: Record<string, any>;
}

export interface DocumentContentResponse {
  document_id: string;
  title: string;
  total_passages: number;
  status: string;
  passages: DocumentContentPassage[];
  quality_report?: ExtractionQualityReport | null;
}

export interface DocumentExtractionPreviewResponse {
  title: string;
  file_type: string;
  file_size_bytes: number;
  quality_report: ExtractionQualityReport;
  passages: DocumentContentPassage[];
  total_passages: number;
  detected_tables: number;
  detected_sheets: string[];
}

export interface Citation {
  document_id: string;
  document_title: string;
  document_version?: number;
  location: string;
  content_hash: string;
  snippet: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  document_id: string;
  document_title: string;
  document_version?: number;
  location: string;
  content_hash: string;
  text: string;
  dense_score: number;
  sparse_score: number;
  combined_score: number;
  channel?: string;
  dense_rank?: number | null;
  sparse_rank?: number | null;
  rerank_score?: number | null;
  rerank_rank?: number | null;
}

export interface DocumentRevisionHistoryItem {
  id: string;
  logical_document_id: string;
  version: number;
  title: string;
  lifecycle_state: string;
  checksum_sha256: string;
  file_type: string;
  file_size_bytes: number;
  owner_id: string;
  supersedes_id?: string | null;
  effective_date?: string | null;
  created_at: string;
}

export interface DocumentHistoryResponse {
  logical_document_id: string;
  title: string;
  active_version: number;
  total_revisions: number;
  revisions: DocumentRevisionHistoryItem[];
}

export interface EvidenceDiagnostics {
  retrieval_relevance: 'high' | 'medium' | 'low';
  faithfulness_score: number;
  supported_claims_count: number;
  total_claims_count: number;
  conflicts_detected: boolean;
  citation_integrity_verified: boolean;
  unsupported_claims: string[];
}

export interface ChatQueryResponse {
  query: string;
  answer: string;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
  abstained: boolean;
  evidence_level?: 'strong' | 'limited' | 'insufficient';
  abstention_reason?: string | null;
  evidence_diagnostics?: EvidenceDiagnostics | null;
  execution_time_ms: number;
  query_id?: string;
  model_version?: string;
  prompt_version?: string;
  retrieved_document_versions?: Record<string, number>;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  citations?: Citation[];
  retrievedChunks?: RetrievedChunk[];
  abstained?: boolean;
  evidenceLevel?: 'strong' | 'limited' | 'insufficient';
  abstentionReason?: string | null;
  evidenceDiagnostics?: EvidenceDiagnostics | null;
  executionTimeMs?: number;
  error?: boolean;
  queryId?: string;
  modelVersion?: string;
  promptVersion?: string;
  retrievedDocumentVersions?: Record<string, number>;
  userQueryText?: string;
  feedbackGiven?: 'positive' | 'negative';
}

export type ReviewStatus =
  | 'pending_review'
  | 'in_review'
  | 'reviewed'
  | 'resolved'
  | 'dismissed'
  | 'not_required';

export interface FeedbackItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  user_department?: string | null;
  query_id?: string | null;
  request_id?: string | null;
  query_text: string;
  answer_text: string;
  rating: 'positive' | 'negative';
  reason_tags: string[];
  comment?: string | null;
  model_version?: string | null;
  prompt_version?: string | null;
  retrieved_document_versions?: Record<string, number>;
  evidence_level?: string | null;
  created_at: string;
  review_status: ReviewStatus;
  reviewer_user_id?: string | null;
  reviewer_email?: string | null;
  reviewer_notes?: string | null;
  reviewed_at?: string | null;
}

export interface FeedbackCreateRequest {
  query_id?: string | null;
  request_id?: string | null;
  query_text: string;
  answer_text: string;
  rating: 'positive' | 'negative';
  reason_tags?: string[];
  comment?: string | null;
  model_version?: string | null;
  prompt_version?: string | null;
  retrieved_document_versions?: Record<string, number>;
  evidence_level?: string | null;
}

export interface FeedbackStats {
  total_feedback: number;
  positive_count: number;
  negative_count: number;
  satisfaction_rate: number;
  failure_categories: Record<string, number>;
  pending_reviews_count: number;
  in_review_count: number;
  resolved_reviews_count: number;
}

export interface AuditEvent {
  id: string;
  actor_user_id?: string | null;
  action: string;
  resource_id?: string | null;
  resource_type?: string | null;
  outcome: 'allow' | 'deny' | 'error' | string;
  policy_reason_code?: string | null;
  sequence_number?: number | null;
  previous_event_hash?: string | null;
  event_hash?: string | null;
  details?: string | null;
  ip_address?: string | null;
  request_id?: string | null;
  timestamp: string;
}

export interface AuditIntegrityReport {
  is_valid: boolean;
  total_events_checked: number;
  tampered_event_ids: string[];
  error_details: string[];
  genesis_hash: string;
  chain_head_hash?: string | null;
  verified_at: string;
}

export interface RoleReviewItem {
  role_id: string;
  role_name: string;
  description?: string | null;
  users_count: number;
  permissions: string[];
}

export interface GrantReviewItem {
  grant_id: string;
  document_id: string;
  document_title: string;
  department_name: string;
  grantee_type: 'user' | 'role' | string;
  grantee_id: string;
  grantee_label: string;
  permission: string;
  created_at: string;
}

export interface DenialReviewItem {
  timestamp: string;
  action: string;
  actor_user_id?: string | null;
  policy_reason_code?: string | null;
  resource_id?: string | null;
  safe_explanation?: string | null;
}

export interface AccessReviewReport {
  roles_summary: RoleReviewItem[];
  explicit_grants: GrantReviewItem[];
  recent_denials: DenialReviewItem[];
  privilege_anomalies: string[];
  generated_at: string;
}

export interface AuditExportResponse {
  export_id: string;
  exported_at: string;
  exported_by_user_id: string;
  total_events: number;
  chain_head_hash?: string | null;
  events: AuditEvent[];
}

export interface PolicyDecisionExplanation {
  allowed: boolean;
  policy_reason_code: string;
  safe_explanation: string;
  resource_id?: string | null;
  evaluated_at: string;
}

export interface SystemHealth {
  status: string;
  checks?: {
    configuration?: string;
    storage?: string;
    database?: string;
    vector_store?: string;
  };
}

export interface ThreadSummary {
  id: string;
  user_id: string;
  title: string;
  is_archived: boolean;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ThreadMessage {
  id: string;
  thread_id: string;
  sender: 'user' | 'assistant';
  text: string;
  citations: Citation[];
  abstained: boolean;
  evidence_level?: string | null;
  abstention_reason?: string | null;
  query_id?: string | null;
  created_at: string;
}

export interface ThreadBookmark {
  id: string;
  thread_id: string;
  user_id: string;
  document_id: string;
  title: string;
  location: string;
  snippet: string;
  content_hash: string;
  notes?: string | null;
  created_at: string;
}

export interface ThreadDetails {
  id: string;
  user_id: string;
  title: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  messages: ThreadMessage[];
  bookmarks: ThreadBookmark[];
}

export interface ThreadCreateRequest {
  title?: string;
}

export interface ThreadUpdateRequest {
  title?: string;
  is_archived?: boolean;
}

export interface ThreadMessageCreateRequest {
  query: string;
  top_k?: number;
  hybrid?: boolean;
  temperature?: number;
}

export interface ThreadBookmarkCreateRequest {
  document_id: string;
  title: string;
  location: string;
  snippet: string;
  content_hash: string;
  notes?: string;
}

// --- Knowledge Workflows (Phase 18) ---

export interface WorkflowStepTrace {
  step_name: string;
  tool_name: string;
  status: string;
  duration_ms: number;
  details: Record<string, any>;
}

export interface ClauseDiffItem {
  clause_type: 'added' | 'removed' | 'modified';
  source_text?: string | null;
  target_text?: string | null;
  source_citation?: string | null;
  target_citation?: string | null;
  policy_impact: string;
  severity_or_importance: 'low' | 'medium' | 'high';
}

export interface VersionComparisonResponse {
  workflow_id: string;
  source_document: {
    id: string;
    title: string;
    version: number;
    department_id: string;
  };
  target_document: {
    id: string;
    title: string;
    version: number;
    department_id: string;
  };
  executive_summary: string;
  diff_items: ClauseDiffItem[];
  total_added: number;
  total_removed: number;
  total_modified: number;
  citations: string[];
  steps: WorkflowStepTrace[];
  total_duration_ms: number;
}

export interface DocumentSummaryItem {
  document_id: string;
  title: string;
  version: number;
  key_takeaways: string[];
  citations: string[];
}

export interface ThematicFinding {
  theme: string;
  summary: string;
  points: string[];
}

export interface CollectionSummaryResponse {
  workflow_id: string;
  collection_title: string;
  total_documents_analyzed: number;
  excluded_restricted_count: number;
  executive_summary: string;
  thematic_findings: ThematicFinding[];
  document_breakdowns: DocumentSummaryItem[];
  citations: string[];
  steps: WorkflowStepTrace[];
  total_duration_ms: number;
}

export interface ExtractedField {
  field_name: string;
  value: any;
  confidence: number;
  citation: string;
  notes?: string | null;
}

export interface ExtractedRisk {
  risk_title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  mitigation?: string | null;
  citation: string;
}

export interface StructuredExtractionResponse {
  workflow_id: string;
  document_id: string;
  title: string;
  version: number;
  owner?: ExtractedField | null;
  effective_date?: ExtractedField | null;
  deadline_or_cycle?: ExtractedField | null;
  requirements: ExtractedField[];
  risks: ExtractedRisk[];
  compliance_obligations: ExtractedField[];
  citations: string[];
  steps: WorkflowStepTrace[];
  total_duration_ms: number;
}

export interface WorkflowExecutionRead {
  id: string;
  workflow_type: string;
  status: string;
  title: string;
  total_duration_ms: number;
  created_at: string;
  steps?: WorkflowStepTrace[] | null;
  result_data?: Record<string, any> | null;
}

export interface ToolAllowlistInfo {
  is_read_only: boolean;
  allowed_tools: string[];
  disallowed_tools_sample: string[];
  default_deny: boolean;
  external_write_actions_permitted: boolean;
}


