/**
 * AegisRAG Typed API Client
 * Interfaces with FastAPI endpoints with automatic Bearer token injection.
 */

import {
  AccessReviewReport,
  AuditExportResponse,
  AuditIntegrityReport,
  AuthResponse,
  AuditEvent,
  ChatQueryResponse,
  DocumentContentResponse,
  DocumentExtractionPreviewResponse,
  DocumentHistoryResponse,
  DocumentItem,
  FeedbackCreateRequest,
  FeedbackItem,
  FeedbackStats,
  PolicyDecisionExplanation,
  SystemHealth,
  ThreadBookmark,
  ThreadBookmarkCreateRequest,
  ThreadCreateRequest,
  ThreadDetails,
  ThreadMessage,
  ThreadMessageCreateRequest,
  ThreadSummary,
  ThreadUpdateRequest,
  User,
  VersionComparisonResponse,
  CollectionSummaryResponse,
  StructuredExtractionResponse,
  WorkflowExecutionRead,
  ToolAllowlistInfo,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export { ApiError };

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('aegis_token');
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    ...getAuthHeader(),
    ...(options.headers || {}),
  } as Record<string, string>;

  // Don't set Content-Type if sending FormData (browser sets boundary automatically)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorData = null;
    try {
      errorData = await response.json();
      if (errorData && errorData.detail) {
        errorDetail = errorData.detail;
      }
    } catch {
      // Non-JSON response
    }
    throw new ApiError(errorDetail, response.status, errorData);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Authentication
  auth: {
    async login(email: string, password: string): Promise<AuthResponse> {
      return request<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
    },

    async getMe(): Promise<User> {
      return request<User>('/api/v1/auth/me');
    },
  },

  // RAG Chat & Generation
  chat: {
    async query(payload: {
      query: string;
      top_k?: number;
      hybrid?: boolean;
      temperature?: number;
    }): Promise<ChatQueryResponse> {
      return request<ChatQueryResponse>('/api/v1/chat/query', {
        method: 'POST',
        body: JSON.stringify({
          query: payload.query,
          top_k: payload.top_k ?? 5,
          hybrid: payload.hybrid ?? true,
          temperature: payload.temperature ?? 0.0,
        }),
      });
    },
  },

  // Document Management & Ingestion
  documents: {
    async list(includeSuperseded: boolean = false): Promise<DocumentItem[]> {
      const q = includeSuperseded ? '?include_superseded=true' : '';
      return request<DocumentItem[]>(`/api/v1/documents${q}`);
    },

    async get(id: string): Promise<DocumentItem> {
      return request<DocumentItem>(`/api/v1/documents/${id}`);
    },

    async getContent(id: string): Promise<DocumentContentResponse> {
      return request<DocumentContentResponse>(`/api/v1/documents/${id}/content`);
    },

    async upload(formData: FormData): Promise<{ message: string; document: DocumentItem }> {
      return request<{ message: string; document: DocumentItem }>('/api/v1/documents/upload', {
        method: 'POST',
        body: formData,
      });
    },

    async reindex(id: string): Promise<{ message: string; indexed_chunks: number }> {
      return request<{ message: string; indexed_chunks: number }>(`/api/v1/documents/${id}/index`, {
        method: 'POST',
      });
    },

    async delete(id: string): Promise<{ message: string }> {
      return request<{ message: string }>(`/api/v1/documents/${id}`, {
        method: 'DELETE',
      });
    },

    async createGrant(
      documentId: string,
      grant: {
        grantee_user_id?: string;
        grantee_role_id?: string;
        permission?: string;
      }
    ): Promise<any> {
      return request<any>(`/api/v1/documents/${documentId}/grants`, {
        method: 'POST',
        body: JSON.stringify(grant),
      });
    },

    async getHistory(id: string): Promise<DocumentHistoryResponse> {
      return request<DocumentHistoryResponse>(`/api/v1/documents/${id}/history`);
    },

    async rollback(id: string): Promise<DocumentItem> {
      return request<DocumentItem>(`/api/v1/documents/${id}/rollback`, {
        method: 'POST',
      });
    },

    async getExtractionPreview(id: string): Promise<DocumentExtractionPreviewResponse> {
      return request<DocumentExtractionPreviewResponse>(`/api/v1/documents/${id}/extraction-preview`);
    },

    async previewUpload(formData: FormData): Promise<DocumentExtractionPreviewResponse> {
      return request<DocumentExtractionPreviewResponse>('/api/v1/documents/preview', {
        method: 'POST',
        body: formData,
      });
    },

    async explainAccess(id: string): Promise<PolicyDecisionExplanation> {
      return request<PolicyDecisionExplanation>(`/api/v1/documents/${id}/explain-access`);
    },
  },

  // Administrative Endpoints (Phase 17 Governance & Audit)
  admin: {
    async listUsers(): Promise<User[]> {
      return request<User[]>('/api/v1/admin/users');
    },

    async listAuditLogs(params?: {
      limit?: number;
      offset?: number;
      action?: string;
      outcome?: string;
      policy_reason_code?: string;
    }): Promise<AuditEvent[]> {
      const q = new URLSearchParams();
      if (params?.limit !== undefined) q.set('limit', String(params.limit));
      else q.set('limit', '50');
      if (params?.offset !== undefined) q.set('offset', String(params.offset));
      if (params?.action) q.set('action', params.action);
      if (params?.outcome) q.set('outcome', params.outcome);
      if (params?.policy_reason_code) q.set('policy_reason_code', params.policy_reason_code);
      return request<AuditEvent[]>(`/api/v1/admin/audit-logs?${q.toString()}`);
    },

    async verifyAuditIntegrity(): Promise<AuditIntegrityReport> {
      return request<AuditIntegrityReport>('/api/v1/admin/audit/integrity');
    },

    async getAccessReview(): Promise<AccessReviewReport> {
      return request<AccessReviewReport>('/api/v1/admin/access-review');
    },

    async exportAudit(limit: number = 500, offset: number = 0): Promise<AuditExportResponse> {
      return request<AuditExportResponse>(`/api/v1/admin/audit/export?limit=${limit}&offset=${offset}`);
    },
  },

  // Feedback & Quality Analytics (Phase 14)
  feedback: {
    async submit(payload: FeedbackCreateRequest): Promise<FeedbackItem> {
      return request<FeedbackItem>('/api/v1/feedback', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async list(params?: {
      rating?: string;
      review_status?: string;
      limit?: number;
      offset?: number;
    }): Promise<FeedbackItem[]> {
      const q = new URLSearchParams();
      if (params?.rating) q.set('rating', params.rating);
      if (params?.review_status) q.set('review_status', params.review_status);
      if (params?.limit) q.set('limit', String(params.limit));
      if (params?.offset) q.set('offset', String(params.offset));
      const queryString = q.toString() ? `?${q.toString()}` : '';
      return request<FeedbackItem[]>(`/api/v1/feedback${queryString}`);
    },

    async getStats(): Promise<FeedbackStats> {
      return request<FeedbackStats>('/api/v1/feedback/stats');
    },

    async updateReview(
      feedbackId: string,
      payload: { review_status: string; reviewer_notes?: string }
    ): Promise<FeedbackItem> {
      return request<FeedbackItem>(`/api/v1/feedback/${feedbackId}/review`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
  },

  // Conversation Workspaces & Controlled Memory (Phase 15)
  threads: {
    async create(payload?: ThreadCreateRequest): Promise<ThreadSummary> {
      return request<ThreadSummary>('/api/v1/threads', {
        method: 'POST',
        body: payload ? JSON.stringify(payload) : JSON.stringify({}),
      });
    },

    async list(includeArchived: boolean = false, limit: number = 50, offset: number = 0): Promise<ThreadSummary[]> {
      const q = new URLSearchParams();
      if (includeArchived) q.set('include_archived', 'true');
      if (limit) q.set('limit', String(limit));
      if (offset) q.set('offset', String(offset));
      const queryString = q.toString() ? `?${q.toString()}` : '';
      return request<ThreadSummary[]>(`/api/v1/threads${queryString}`);
    },

    async get(threadId: string): Promise<ThreadDetails> {
      return request<ThreadDetails>(`/api/v1/threads/${threadId}`);
    },

    async update(threadId: string, payload: ThreadUpdateRequest): Promise<ThreadSummary> {
      return request<ThreadSummary>(`/api/v1/threads/${threadId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },

    async delete(threadId: string): Promise<{ status: string; thread_id: string }> {
      return request<{ status: string; thread_id: string }>(`/api/v1/threads/${threadId}`, {
        method: 'DELETE',
      });
    },

    async sendMessage(threadId: string, payload: ThreadMessageCreateRequest): Promise<ThreadMessage> {
      return request<ThreadMessage>(`/api/v1/threads/${threadId}/messages`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async addBookmark(threadId: string, payload: ThreadBookmarkCreateRequest): Promise<ThreadBookmark> {
      return request<ThreadBookmark>(`/api/v1/threads/${threadId}/bookmarks`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async deleteBookmark(bookmarkId: string): Promise<{ status: string; bookmark_id: string }> {
      return request<{ status: string; bookmark_id: string }>(`/api/v1/threads/bookmarks/${bookmarkId}`, {
        method: 'DELETE',
      });
    },
  },

  // Knowledge Workflows (Phase 18)
  workflows: {
    async compare(payload: {
      source_document_id: string;
      target_document_id: string;
      focus?: string;
    }): Promise<VersionComparisonResponse> {
      return request<VersionComparisonResponse>('/api/v1/workflows/compare', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async summarizeCollection(payload: {
      document_ids?: string[];
      department_id?: string;
      collection_title?: string;
      focus_query?: string;
    }): Promise<CollectionSummaryResponse> {
      return request<CollectionSummaryResponse>('/api/v1/workflows/summarize-collection', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async extractFields(payload: {
      document_id: string;
      template_type?: string;
    }): Promise<StructuredExtractionResponse> {
      return request<StructuredExtractionResponse>('/api/v1/workflows/extract-fields', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async exportWorkflow(payload: {
      workflow_type: string;
      data: any;
      format: 'markdown' | 'pdf' | 'text';
      title?: string;
      workflow_id?: string;
    }): Promise<Blob> {
      const url = `${API_BASE}/api/v1/workflows/export`;
      const headers = {
        ...getAuthHeader(),
        'Content-Type': 'application/json',
      };
      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`Export failed with status ${res.status}`);
      }
      return res.blob();
    },

    async getHistory(limit: number = 20): Promise<WorkflowExecutionRead[]> {
      return request<WorkflowExecutionRead[]>(`/api/v1/workflows/history?limit=${limit}`);
    },

    async getTools(): Promise<ToolAllowlistInfo> {
      return request<ToolAllowlistInfo>('/api/v1/workflows/tools');
    },
  },

  // Health and System Diagnostics
  health: {
    async checkReady(): Promise<SystemHealth> {
      return request<SystemHealth>('/health/ready');
    },

    async checkLive(): Promise<{ status: string }> {
      return request<{ status: string }>('/health/live');
    },
  },
};

