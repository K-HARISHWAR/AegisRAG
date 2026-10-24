# AegisRAG - System Architecture & Design

## 1. Modular Monolith Architecture

AegisRAG is implemented as a modular monolith backend with a React SPA frontend. Keeping the backend unified within a single service simplifies local development, testing, transactional integrity, and authorization enforcement while avoiding distributed systems latency.

```
+-------------------------------------------------------------------------+
|                           Browser (React 18 + Vite)                     |
+-------------------------------------------------------------------------+
                                     |
                                     | HTTPS + JWT Bearer Token
                                     v
+-------------------------------------------------------------------------+
|                         FastAPI Backend Application                     |
|                                                                         |
|  +------------------+  +-------------------+  +-----------------------+ |
|  |  Auth & RBAC     |  |  Document Upload  |  |  Audit & Metrics      | |
|  |  (core/security) |  |  & Ingestion      |  |  (services/audit.py)  | |
|  +------------------+  +-------------------+  +-----------------------+ |
|            |                     |                        |             |
|  +------------------+  +-------------------+  +-----------------------+ |
|  |  DB Models       |  |  Parsers          |  |  Vector Store Adapter | |
|  |  (SQLAlchemy 2)  |  |  (PDF/DOCX/XLSX)  |  |  (ChromaDB)           | |
|  +------------------+  +-------------------+  +-----------------------+ |
|            |                     |                        |             |
|  +-------------------------------------------------------------------+  |
|  |  Secure Retrieval Pipeline (services/retrieval.py)                 |  |
|  |  [Pre-Search Filter] -> [ChromaDB Hit] -> [Post-Search Validate]   |  |
|  +-------------------------------------------------------------------+  |
|            |                                                            |
|  +-------------------------------------------------------------------+  |
|  |  LLM Provider Adapter (Groq / OpenAI-compatible with prompt shield)|  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
            |                        |                       |
            v                        v                       v
+-----------------------+  +--------------------+  +----------------------+
|  PostgreSQL Database  |  |  ChromaDB Store    |  |  Document Storage    |
|  (Source of Truth)    |  |  (Vector Index)    |  |  (Local / S3)        |
+-----------------------+  +--------------------+  +----------------------+
```

---

## 2. Source of Truth Principle

**Key Rule**: PostgreSQL is the sole authority for users, roles, departments, document metadata, and access grants.
- Vector store metadata in ChromaDB stores chunk indices, document IDs, and access tags **strictly as an optimization index**.
- Candidate chunks returned by ChromaDB must be re-validated against current PostgreSQL permissions before they are formatted into the LLM context prompt.

---

## 3. Data Model (PostgreSQL)

| Model | Table Name | Purpose / Fields |
| :--- | :--- | :--- |
| **User** | `users` | `id` (UUID), `email`, `hashed_password`, `department_id`, `is_active`, `is_superuser`, `created_at` |
| **Role** | `roles` | `id` (UUID), `name` (`employee`, `department_manager`, `admin`), `description` |
| **UserRole** | `user_roles` | `user_id`, `role_id` (many-to-many relationship) |
| **Department** | `departments` | `id` (UUID), `name` (`Engineering`, `HR`), `description` |
| **Document** | `documents` | `id` (UUID), `owner_id`, `department_id`, `title`, `storage_key`, `file_type`, `file_size_bytes`, `checksum_sha256`, `is_confidential`, `status` (`uploaded`, `processing`, `indexed`, `failed`, `deleted`), `created_at`, `updated_at` |
| **DocumentGrant** | `document_grants` | `id` (UUID), `document_id`, `grantee_user_id` (optional), `grantee_role_id` (optional), `permission` (`read`, `manage`), `granted_by_user_id`, `created_at` |
| **AuditEvent** | `audit_events` | `id` (UUID), `actor_user_id`, `action`, `resource_id`, `resource_type`, `outcome` (`allow`, `deny`, `error`), `ip_address`, `request_id`, `timestamp` |

---

## 4. Trust Boundaries & Security Enclaves

1. **Client Boundary**: Browser client is considered untrusted. Role and department headers or body fields are ignored; user identity is derived strictly from verified JWT claims.
2. **Retrieval Boundary**: Vector search never executes without pre-computed user document IDs derived from active PostgreSQL permissions.
3. **Model Context Boundary**: Only chunks passing both pre-retrieval filtering and post-retrieval revalidation are included in the prompt. Document text is enclosed in strict delimiters to mitigate prompt injection.
4. **Storage Boundary**: Uploaded files are written with random UUID names into an unexposed local folder (or private S3 bucket with no public read permissions).

---

## 5. End-to-End Query Flow

```
1. User submits query ("What is the server deployment checklist?") with Bearer Token.
2. FastAPI validates JWT -> identifies user: Alice (Role: employee, Dept: Engineering).
3. Retrieval Service queries PostgreSQL:
   - Gets all documents Alice can access (Engineering public docs + explicit grants to Alice).
   - Generates list of allowed document_ids: [doc_uuid_1, doc_uuid_2].
4. ChromaDB queried:
   - Search query embedding with `where={"document_id": {"$in": [doc_uuid_1, doc_uuid_2]}}`.
   - Returns top-k candidate chunks.
5. Revalidation Step:
   - Verify each candidate chunk's `document_id` against current PostgreSQL permissions.
6. Context Assembly:
   - Format surviving chunks with citations ([Doc: engineering_runbook.pdf, Page: 4]).
7. LLM Adapter:
   - Calls LLM with injection defense prompt + formatted context.
8. Response:
   - Returns grounded answer + citation metadata to user.
   - Logs AuditEvent (action: "query", outcome: "allow", request_id: "...").
```
