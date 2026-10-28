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
- **Next Step**: Phase 5 — Chunking, embeddings, and vector indexing.

---

## Phase 5: Chunking, Embeddings, and ChromaDB Vector Indexing
- **Date**: 2026-10-27
- **Completed Deliverables**:
  - `backend/app/schemas/chunk.py`: Defined `Chunk`, `SearchResult`, and `DocumentChunkRead` models encapsulating deterministic identifiers, precise citation provenance (`Page 2`, `Paragraph 3`), RBAC metadata (`department_id`, `is_confidential`), and content hashes.
  - `backend/app/services/chunking.py`:
    - `split_text_with_overlap`: Deterministic boundary-aware chunking without breaking words mid-word.
    - `create_chunks_from_passages`: Converts extracted passages into chunk records with stable SHA-256 deduplication content hashes.
  - `backend/app/services/embeddings.py`:
    - `EmbeddingProvider` ABC with strict dimension enforcement (`validate_dimension`).
    - `ChromaDefaultEmbeddingProvider`: Default provider using Chroma's ONNX `all-MiniLM-L6-v2` (384 dimensions).
    - `DeterministicMockEmbeddingProvider`: Fast, unit-normalized, deterministic provider for offline test isolation.
    - `get_embedding_provider`: Factory selecting appropriate provider by environment.
  - `backend/app/services/vector_store.py`:
    - `VectorStore` abstract interface.
    - `ChromaVectorStore`: ChromaDB adapter supporting idempotent upserts (`add_chunks`), dimension mismatch validation, `get_by_document`, `delete_by_document`, `count`, and `health_check`.
    - Server-side pre-retrieval filtering via `where={"document_id": {"$in": allowed_document_ids}}`. Fail-closed on empty authorization list.
  - `backend/app/services/indexing.py`:
    - `index_document`: End-to-end orchestration reading storage, extracting text, chunking, generating embeddings, upserting to ChromaDB, and advancing document status to `"indexed"`.
    - `reindex_all_documents`: Batch reindexing for non-deleted documents.
  - `backend/app/api/routes/documents.py`:
    - `POST /api/v1/documents/upload`: Auto-triggers vector indexing upon upload.
    - `POST /api/v1/documents/{id}/index`: Explicit endpoint to re-index documents (requires manager/owner privileges).
    - `GET /api/v1/documents/{id}/chunks`: Endpoint returning indexed chunks with exact source provenance for authorized users.
    - `DELETE /api/v1/documents/{id}`: Purges document vectors from ChromaDB in addition to storage and database deletion.
  - `backend/app/api/routes/health.py`: Added vector store connectivity probe to `/health/ready`.
  - Comprehensive test suite:
    - `backend/tests/test_chunking.py`: Boundary verification, provenance retention, and SHA-256 stability.
    - `backend/tests/test_vector_store.py`: ChromaDB CRUD, pre-retrieval filtering, fail-closed enforcement, and dimension mismatch rejection.
    - `backend/tests/test_indexing.py`: End-to-end upload -> auto-indexing -> chunk inspection -> RBAC access control -> deletion vector cleanup.
- **Next Step**: Phase 6 — Hybrid retrieval, re-ranking, and server-side RBAC post-filtering.

---

## Phase 6: Hybrid Retrieval, Re-ranking, and Server-Side RBAC Post-Filtering
- **Date**: 2026-10-28
- **Completed Deliverables**:
  - `backend/app/schemas/retrieval.py`: Defined `RetrievalQuery`, `RetrievedChunk`, and `RetrievalResponse` with granular source citations (`document_title`, `location`, `content_hash`, `dense_score`, `sparse_score`, `combined_score`).
  - `backend/app/schemas/__init__.py`: Exported retrieval models for unified package consumption.
  - `backend/app/services/retrieval.py`:
    - `BM25Scorer`: Tokenization and Okapi BM25 sparse keyword scoring with Robertson-Spärck Jones IDF over candidate passage texts.
    - `reciprocal_rank_fusion`: Normalized dense + sparse ranking fusion with standard $k_{rrf}=60$ parameter and configurable weighting.
    - `retrieve_context`: Full two-stage authorization retrieval orchestrator:
      - **Stage 1 (Pre-Retrieval Filter)**: Computes user-authorized document IDs from PostgreSQL; applies strict `where={"document_id": {"$in": ...}}` ChromaDB filter. **Fails closed** immediately if authorized set is empty.
      - **Stage 2 (Post-Retrieval Revalidation)**: Revalidates every candidate chunk against active PostgreSQL records (`can_read_document`), dropping any stale or mismatched candidates and verifying that document status is not `"deleted"`.
      - Attaches official document title from PostgreSQL records to prevent citation spoofing.
      - Persists audit events (`action="retrieval_query"` and `"post_retrieval_revalidation"`) with execution latency and outcome.
  - `backend/app/api/routes/retrieval.py`: Implemented `POST /api/v1/retrieval/query` endpoint with full request validation and authentication.
  - `backend/app/main.py`: Registered retrieval router in FastAPI application.
  - `backend/tests/test_retrieval.py`: 8 comprehensive integration and security tests:
    - BM25 unit scoring and RRF normalization verification.
    - Employee intra-department non-confidential retrieval.
    - Cross-department pre-retrieval isolation (Stage 1 pre-filter).
    - Confidential document isolation (hidden from regular employees, accessible to department manager).
    - Cross-department explicit `DocumentGrant` retrieval.
    - Stage 2 post-retrieval revalidation defense against vector store candidate leakage.
    - Audit event persistence.
- **Next Step**: Phase 7 — Generation, Prompt Delimitation, and Citation Grounding.

---

## Phase 7: Generation, Prompt Delimitation, and Citation Grounding
- **Date**: 2026-10-28
- **Completed Deliverables**:
  - `backend/app/schemas/generation.py`: Defined `ChatQueryRequest`, `Citation`, and `ChatQueryResponse` schemas with grounded citation models and abstention indicators.
  - `backend/app/schemas/__init__.py`: Exported generation schemas.
  - `backend/app/services/llm.py`:
    - `LLMProvider` ABC.
    - `GroqLLMProvider`: Async HTTP integration with Groq's high-speed completion API (`llama-3.3-70b-versatile`).
    - `OpenAILLMProvider`: OpenAI-compatible chat completion provider.
    - `MockLLMProvider`: Deterministic, offline, citation-aware mock provider for isolated testing.
    - `get_llm_provider`: Dynamic factory falling back to mock provider in test or unconfigured environments.
  - `backend/app/services/generation.py`:
    - `sanitize_delimiters`: Neutralizes XML and delimiter escape injection attacks (`</context>`, `<document>`) inside untrusted chunk texts.
    - `build_grounded_prompt`: Wraps retrieved context in strict `<context>` boundaries with system guardrails enforcing factual grounding, strict abstention on insufficient evidence, and instruction-override resistance.
    - `extract_grounded_citations`: Extracts and links citations directly to verified PostgreSQL document IDs, locations, and content hashes.
    - `generate_answer`: Full RAG generation orchestrator integrating two-stage retrieval, delimited prompt generation, and structured audit logging (`action="rag_generation"`).
  - `backend/app/api/routes/chat.py`: Implemented `POST /api/v1/chat/query` endpoint with full authentication and validation.
  - `backend/app/main.py`: Registered chat router.
  - `backend/tests/test_generation.py`: 7 comprehensive tests:
    - Grounded generation with exact citation markers (`[Doc: ..., Page 1]`).
    - Strict abstention guarantee (`"The available documentation does not contain sufficient information to answer this question."`) on unanswerable questions.
    - Cross-department RBAC query isolation resulting in abstention.
    - Confidential document isolation (abstention for regular employee, grounded answer for manager).
    - Indirect prompt injection defense neutralizing embedded system overrides.
    - Delimiter escape sanitization.
    - Audit event persistence.
- **Verification Commands Run**:
  - `pytest backend/tests -v --show-capture=no` -> 80 passed in 54.77s
- **Next Step**: Phase 8 — Evaluation harness, benchmarks, and quality metrics.




