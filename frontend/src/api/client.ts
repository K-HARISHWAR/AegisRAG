/**
 * AegisRAG Typed API Client
 * Interfaces with FastAPI endpoints with automatic Bearer token injection.
 */

import {
  AuthResponse,
  AuditEvent,
  ChatQueryResponse,
  DocumentContentResponse,
  DocumentItem,
  SystemHealth,
  User,
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
    async list(): Promise<DocumentItem[]> {
      return request<DocumentItem[]>('/api/v1/documents');
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
  },

  // Administrative Endpoints
  admin: {
    async listUsers(): Promise<User[]> {
      return request<User[]>('/api/v1/admin/users');
    },

    async listAuditLogs(limit: number = 50, offset: number = 0): Promise<AuditEvent[]> {
      return request<AuditEvent[]>(`/api/v1/admin/audit-logs?limit=${limit}&offset=${offset}`);
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

