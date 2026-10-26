# AegisRAG - Implementation Log

This log tracks architectural decisions, completed phases, verification commands, test outcomes, and git commits.

---

## Phase 0: Scope, Requirements, and Architecture
- **Date**: 2026-10-24
- **Completed Deliverables**:
  - `docs/requirements.md`: Defined problem statement, user personas (`employee`, `department_manager`, `admin`), permission matrix, supported document types (PDF, DOCX, XLSX with 20MB limit), and acceptance criteria.
  - `docs/architecture.md`: Documented modular monolith design, PostgreSQL as single source of truth, two-tier authorization filter (pre-search + post-search revalidation), data models, and trust boundaries.
  - `docs/threat-model.md`: Detailed STRIDE security analysis, privilege escalation scenarios, indirect prompt injection defense, and pre-deployment security checklist.
  - `evals/questions.jsonl` & `evals/README.md`: Created 20 synthetic evaluation questions covering allowed/denied departments, manager-only documents, abstention cases, and adversarial prompt injection attempts.
- **Outcomes**: MVP scope clearly specified; no out-of-scope microservices or complexity added.

---

## Phase 1: Tooling, Repo, and Development Workflow
- **Date**: 2026-10-24
- **Completed Deliverables**:
  - Verified local environment:
    - Git: `2.49.0.windows.1`
    - Python: `3.12.4` (using `py -3.12`)
    - Node.js: `v22.14.0`
    - npm: `10.9.2`
  - `.gitignore`: Configured to exclude `.env`, virtual environments (`.venv/`, `backend/venv/`), `node_modules/`, local upload storage, ChromaDB files, logs, and secrets.
  - `.env.example`: Added configuration template with placeholders only for backend, PostgreSQL, ChromaDB, HuggingFace embeddings, Groq/OpenAI LLM, and Vite frontend.
  - `AGENTS.md`: Established project guardrails, security rules (default-deny, untrusted document content, no hardcoded secrets), directory layout, and standard commands.
  - `README.md`: Comprehensive documentation with architecture diagram, prerequisites, local setup instructions, test commands, and implementation roadmap.
- **Verification Commands Run**:
  - `git --version` -> `git version 2.49.0.windows.1`
  - `py --version` -> `Python 3.12.4`
  - `node --version` -> `v22.14.0`
  - `npm --version` -> `10.9.2`
- **Next Step**: Phase 2 — Build backend skeleton and configuration.

---

## Phase 2: Backend Skeleton and Configuration
- **Date**: 2026-10-24
- **Completed Deliverables**:
  - `backend/pyproject.toml`: Configured package metadata, dependencies (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `httpx`), and test configuration.
  - `backend/app/main.py`: FastAPI application factory with Request ID middleware, CORS middleware, global error handlers, and router registration.
  - `backend/app/core/config.py`: Typed settings using `pydantic-settings` with fail-fast validation for production environments (disabling debug, enforcing minimum 32-character secret key).
  - `backend/app/core/logging.py`: Structured logging configuration injecting request ID context into every log entry.
  - `backend/app/core/errors.py`: Global exception handlers ensuring unhandled errors return generic, client-safe messages while recording full traces in protected server logs.
  - `backend/app/api/routes/health.py`: Zero-leakage liveness (`GET /health/live`) and readiness (`GET /health/ready`) endpoints.
  - `backend/tests/`: Comprehensive test suite (`test_config.py`, `test_health.py`, `conftest.py`) covering settings validation, production fail-closed security, health probes, request IDs, and unhandled error sanitization.
- **Verification Commands Run**:
  - `py -3.12 -m venv backend/venv` -> Created virtual environment
  - `pip install -e "backend[dev]"` -> Successfully installed dependencies
  - `pytest backend/tests -v` -> 12 passed in 0.33s
  - `uvicorn app.main:app --app-dir backend --port 8000` -> Server started and responded:
    - `GET /health/live` -> 200 OK, `{"status":"live"}` with `X-Request-ID`
    - `GET /health/ready` -> 200 OK, `{"status":"ready","checks":{"configuration":"healthy","storage":"healthy"}}` (zero path/credential leakage)
- **Next Step**: Phase 3 — Database, authentication, and RBAC model.

---

## Phase 3: Database, Authentication, and RBAC Model
- **Date**: 2026-10-26
- **Completed Deliverables**:
  - `backend/app/models/`: SQLAlchemy 2.0 ORM models with platform-independent GUID support:
    - `Department`: organizational units (`Engineering`, `HR`).
    - `Role` & `user_roles`: RBAC roles (`employee`, `department_manager`, `admin`).
    - `User`: server-verified identity, bcrypt hashed password, active/superuser flags, department association.
    - `Document`: title, owner, department, unique storage key, file metadata, SHA-256 checksum, confidentiality flag, lifecycle status.
    - `DocumentGrant`: explicit document access grants to user or role with check constraint.
    - `AuditEvent`: immutable audit trail recording actor, action, outcome, resource ID, IP address, and request ID.
  - `backend/app/core/security.py`: Salted bcrypt password hashing (`hash_password`, `verify_password`) and PyJWT token generation/decoding (`create_access_token`, `decode_access_token`).
  - `backend/app/services/policy.py`: Centralized default-deny authorization policies (`can_read_document`, `can_upload_document`, `can_manage_grants`, `can_manage_users`, `get_authorized_document_ids`).
  - `backend/app/services/audit.py`: Audit logging service with sensitive parameter sanitization.
  - `backend/app/api/deps.py`: Server-verified dependencies resolving authenticated user and active roles/department directly from database records.
  - `backend/app/api/routes/`:
    - `auth.py`: `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.
    - `documents.py`: `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `POST /api/v1/documents`, `POST /api/v1/documents/{id}/grants`.
    - `admin.py`: `GET /api/v1/admin/users`, `GET /api/v1/admin/audit-logs`.
  - `backend/alembic/`: Async migration configuration and `0001_initial_rbac_schema.py` initial migration.
  - `infra/docker/docker-compose.yml`: Container definitions for local PostgreSQL and backend services.
  - `backend/app/db/seed.py`: Seed data script populating synthetic departments, roles, users (`alice`, `bob`, `charlie`, `diana`, `admin`, `inactive`), documents, and grants.
  - `backend/tests/`: Comprehensive test suite with 38 unit and integration tests covering password security, JWT verification, policy logic, authentication routes, and RBAC access isolation.
- **Verification Commands Run**:
  - `pytest backend/tests -v` -> 38 passed in 31.62s
    - Cross-department access denied to unauthorized employees (HTTP 403)
    - Confidential document access denied within department without grant (HTTP 403)
    - Explicit document grant allows cross-department access (HTTP 200)
    - Manager can access own department confidential documents (HTTP 200)
    - Altered client-supplied role/department headers strictly ignored (server-verified authorization)
    - Inactive user rejected at authentication (HTTP 401)
    - Non-existent document returns HTTP 404
    - Audit event persisted for allowed and denied requests
- **Next Step**: Phase 4 — Document upload and safe text extraction.

---

## Phase 4: Document Upload and Safe Text Extraction
- **Date**: 2026-10-26
- **Completed Deliverables**:
  - `backend/app/services/storage.py`: Storage provider abstraction (`StorageProvider` ABC) and secure `LocalStorageProvider` with directory traversal defenses (`_resolve_safe_path`).
  - `backend/app/services/validation.py`: Strict file upload validation:
    - 20 MB size limit (HTTP 413)
    - Extension allowlist (`.pdf`, `.docx`, `.xlsx`)
    - Magic byte / content signature verification (`%PDF-`, `PK\x03\x04` with OpenXML package structure verification)
    - SHA-256 checksum calculation for integrity tracking
    - Filename sanitization to prevent path manipulation.
  - `backend/app/services/extraction.py`: Safe multi-format extractors preserving citation locations:
    - PDF: Page-by-page extraction (`Page {i}`), scanned/empty PDF detection returning `status="scanned_warning"`
    - DOCX: Paragraphs and table cell extraction (`Paragraph {i}`, `Table {i}, Row {j}`) without macro execution
    - XLSX: Sheet and cell coordinate preservation (`Sheet: {name}!Row {i}`) with `data_only=True` mode
    - `extract_document_text`: Unified dispatcher with safe exception handling.
  - `backend/app/api/routes/documents.py`:
    - `POST /api/v1/documents/upload`: Multipart upload with department RBAC enforcement, magic byte verification, storage persistence, and text extraction.
    - `GET /api/v1/documents/{id}/content`: Protected endpoint returning extracted passages with citation coordinates for authorized users.
    - `DELETE /api/v1/documents/{id}`: Idempotent document deletion removing stored binary and updating database status.
  - `backend/tests/test_extraction.py` & `backend/tests/test_document_upload.py`: 15 new tests covering extraction provenance, scanned PDF warnings, corrupt file handling, extension validation, magic byte verification, oversized limits, and idempotent deletion.
- **Verification Commands Run**:
  - `pytest backend/tests -v` -> 53 passed in 20.83s
- **Next Step**: Phase 5 — Chunking, embeddings, and vector indexing.

