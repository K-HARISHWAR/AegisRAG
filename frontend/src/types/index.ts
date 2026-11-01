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

export interface DocumentContentPassage {
  index: number;
  location: string;
  text: string;
}

export interface DocumentContentResponse {
  document_id: string;
  title: string;
  total_passages: number;
  status: string;
  passages: DocumentContentPassage[];
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
}

export interface AuditEvent {
  id: string;
  actor_user_id?: string | null;
  action: string;
  resource_id?: string | null;
  resource_type?: string | null;
  outcome: 'allow' | 'deny' | 'error' | string;
  details?: string | null;
  ip_address?: string | null;
  request_id?: string | null;
  timestamp: string;
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

