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

---

## Phase 8: Evaluation Harness, Benchmarks, and Quality Metrics
- **Date**: 2026-10-29
- **Completed Deliverables**:
  - `backend/app/db/seed.py`: Added 5th benchmark document (`manager_disciplinary_guide.docx`) to match the complete evaluation corpus specified in `evals/questions.jsonl`.
  - `evals/seed_eval_corpus.py`: Automated evaluation corpus seeder populating 5 benchmark documents across Engineering and HR departments, with 22 distinct ground truth chunk passages indexed into ChromaDB.
  - `evals/evaluator.py`: Comprehensive evaluation harness:
    - Data models: `EvaluationCase`, `EvaluationResult`, `EvaluationMetrics`.
    - Keyword overlap and semantic similarity evaluation against ground truth answer snippets.
    - Persona-based execution (`alice` - Engineering Employee, `bob` - HR Manager, `charlie` - HR Employee, `diana` - Engineering Manager).
    - Citation verification and prompt injection resistance checks.
    - Latency tracking and percentile computation (P50, P90, P99).
  - `evals/run_evals.py`: CLI benchmark runner executing all 20 test cases in `evals/questions.jsonl`, generating ASCII summary tables, and exporting detailed artifacts:
    - `evals/benchmark_results.json`: Full machine-readable per-query evaluation records.
    - `evals/benchmark_report.md`: Markdown summary report with metrics and latency distribution.
  - `backend/tests/test_evals.py`: Pytest integration test suite enforcing quality gates:
    - Overall accuracy >= 80% (Achieved: 100.0%)
    - RBAC security pass rate >= 95% (Achieved: 100.0%)
    - Prompt injection resistance = 100% (Achieved: 100.0%)
    - Abstention accuracy >= 90% (Achieved: 100.0%)
    - Citation accuracy >= 90% (Achieved: 100.0%)
- **Verification Commands Run**:
  - `python evals/run_evals.py` -> 20/20 benchmark queries evaluated successfully:
    - Overall Accuracy: 100.0%
    - RBAC Security Pass Rate: 100.0%
    - Prompt Injection Resistance: 100.0%
    - Citation Accuracy: 100.0%
    - Abstention Accuracy: 100.0%
    - Mean Latency: 524.8ms (P50: 497.1ms, P90: 713.8ms, P99: 745.3ms)
  - `pytest backend/tests -v --show-capture=no` -> 81 passed
- **Next Step**: Phase 9 — Frontend Implementation (React + TypeScript + Vite, Chat UI, RBAC Dashboards, and Document Management).

---

## Phase 9: Frontend Implementation
- **Date**: 2026-10-30
- **Completed Deliverables**:
  - `frontend/` (React 18 + TypeScript + Vite + Tailwind CSS):
    - `src/types/index.ts`: Typed data models matching FastAPI / SQLAlchemy schemas (`User`, `Role`, `Department`, `DocumentItem`, `DocumentGrant`, `Citation`, `RetrievedChunk`, `ChatMessage`, `AuditEvent`, `SystemHealth`).
    - `src/api/client.ts`: Typed API client with automatic JWT Bearer token attachment, unified error parsing, and full coverage of auth, chat, documents, admin, and health endpoints.
    - `src/auth/AuthContext.tsx`: Session state provider with persistent token storage, role-derivation helpers (`isAdmin`, `isManager`, `primaryRole`), and automatic session validation against `/api/v1/auth/me`.
    - `src/components/`:
      - `Navbar.tsx`: Top navigation bar with active tab switching, department & role badges, user profile, live system health badge, and sign out.
      - `HealthBadge.tsx`: System connectivity probe polling `/health/ready` with interactive popover diagnostics (FastAPI, PostgreSQL, ChromaDB, Storage).
      - `CitationDrawer.tsx`: Grounded evidence slide-out drawer displaying verified citations, excerpt snippets, location coordinates (`Page 2`, `Paragraph 3`), and SHA-256 chunk provenance hashes.
      - `DocumentUploadModal.tsx`: File upload modal supporting `.pdf`, `.docx`, and `.xlsx` (max 20MB) with auto-indexing, department classification, and confidential flag controls.
      - `DocumentViewerModal.tsx`: Extracted passage viewer displaying chunk provenance coordinates and explicit access grant management.
      - `GrantModal.tsx`: Modal for assigning explicit user and role document grants.
    - `src/pages/`:
      - `LoginPage.tsx`: Enterprise login portal with single-click demo persona selector (`Alice` - Eng Employee, `Charlie` - Eng Manager, `Diana` - HR Manager, `Bob` - HR Employee, `Admin` - System Admin).
      - `ChatPage.tsx`: Natural language assistant interface with starter prompts, grounded answer rendering, inline citation badges, abstention warning banners, and execution diagnostics (latency and chunk counts).
      - `DocumentsPage.tsx`: Repository management table with title search, document status tags (`indexed`), passage viewer, re-indexing, deletion, and upload actions.
      - `AdminPage.tsx`: Admin-guarded console with User Directory and Security Audit Trail tables featuring real-time outcome badges (`allow`, `deny`, `error`).
    - `src/tests/`:
      - `src/tests/auth.test.tsx`: Tests for authentication state, login, token persistence, and session clearance.
      - `src/tests/components.test.tsx`: Tests for citation drawer provenance rendering and admin page RBAC access restriction.
      - `src/tests/chat.test.tsx`: Tests for grounded chat answers, source citations, and abstention banners.
- **Verification Commands Run**:
  - `npm run build` in `frontend/` -> TypeScript compilation and Vite production bundle generated without errors (`dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`).
  - `npm test` in `frontend/` -> 8/8 tests passed across 3 test files in 19.2s.
  - `pytest backend/tests -v --show-capture=no` -> 81/81 backend tests passed in 68.16s.
- **Next Step**: Phase 10 — Docker Containerization & Cloud Deployment (Dockerfiles, Docker Compose, AWS infrastructure templates).

---

## Phase 10: Docker Containerization & Cloud Deployment
- **Date**: 2026-10-30
- **Completed Deliverables**:
  - `infra/docker/Dockerfile.backend`:
    - Multi-stage build targeting `python:3.12-slim-bookworm`.
    - Builder stage compiling Python wheel dependencies cleanly.
    - Hardened runtime stage creating non-root system user `appuser` (UID 10001) for least-privilege execution.
    - Integrated Docker healthcheck probing `/health/live`.
  - `infra/docker/Dockerfile.frontend`:
    - Multi-stage build targeting `node:22-alpine` for Vite production bundling and `nginx:1.27-alpine` for production serving.
    - High-performance, unprivileged Nginx web server with gzip compression and static asset caching.
    - Integrated healthcheck probing `/`.
  - `infra/docker/nginx.conf`:
    - Reverse proxy routing `/api/` and `/health/` directly to backend container (`http://backend:8000`).
    - Single-Page Application (SPA) client routing fallback (`try_files $uri $uri/ /index.html;`).
    - Strict HTTP security headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, and Content Security Policy (CSP).
  - `backend/entrypoint.sh`:
    - POSIX LF shell script automating database readiness checking via Python socket probe.
    - Automates database schema migrations (`alembic upgrade head`).
    - Supports optional automated corpus seeding (`SEED_ON_STARTUP=true`).
    - Launches production Uvicorn ASGI server with configurable host, port, and workers.
  - `infra/docker/docker-compose.yml`:
    - Orchestrates 3 interconnected containers: `postgres` (PostgreSQL 16 Alpine with healthcheck), `backend` (FastAPI modular monolith), and `frontend` (Nginx + React SPA).
    - Persistent named volumes for database state (`postgres_data`), uploaded documents (`app_uploads`), and ChromaDB embeddings (`app_chroma`).
    - Isolated internal bridge network (`aegisrag-network`).
  - `.dockerignore` and `frontend/.dockerignore`:
    - Excludes virtual environments, Node modules, build artifacts, `.env` files, local SQLite databases, and test caches from container contexts.
  - `backend/alembic.ini`:
    - Configured `script_location = %(here)s/alembic` ensuring portable migration execution from both repo root and `/app` container directories.
  - `infra/aws/cloudformation.yaml`:
    - Production-grade AWS CloudFormation template (38 AWS resources):
      - Amazon VPC with public and private subnets across 2 Availability Zones, Internet Gateway, and NAT Gateway.
      - Least-privilege Security Groups with strict ingress boundaries (`ALB -> ECS -> RDS`).
      - Amazon RDS PostgreSQL 16 instance in private DB subnet group with automated backup and KMS storage encryption.
      - Amazon S3 Document Bucket with Server-Side Encryption (`AES256`/KMS), Public Access Block, and versioning.
      - Application Load Balancer (ALB) with path-based routing rules (`/api/*` and `/health/*` -> backend, `/*` -> frontend).
      - Amazon ECS Fargate Cluster with Backend and Frontend Task Definitions and Services.
      - IAM Execution and Task roles adhering strictly to least privilege.
      - AWS CloudWatch Log Groups with 30-day retention.
  - `infra/aws/README.md`:
    - Architecture diagrams and trust boundary breakdown.
    - AWS CLI container build, ECR push, and CloudFormation deployment commands.
    - One-off task execution for database seeding and CloudWatch monitoring commands.
- **Verification Commands Run**:
  - `python -c "..."` -> Validated `docker-compose.yml` and `infra/aws/cloudformation.yaml` syntax and parsed all 38 resources.
  - `pytest backend/tests -v --show-capture=no` -> 81/81 backend tests passed in 67.00s.
  - `npm test` in `frontend/` -> 8/8 frontend tests passed across 3 suites in 27.35s.
  - `npm run build` in `frontend/` -> Production bundle built cleanly (`dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`).
- **Project Completion**: All 10 phases of AegisRAG Part 1 have been implemented, tested, and documented.

---

## Part 2: Advanced Features & Novelty Roadmap

### Phase 11: Hybrid Retrieval & Intelligent Reranking
- **Date**: 2026-10-31
- **Branch**: `feature/phase-11-hybrid-retrieval` (baseline tag: `v1.0.0-part1`)
- **Completed Deliverables**:
  - `backend/app/core/config.py`:
    - Server-side feature flags: `RETRIEVAL_MODE` (`vector` vs `hybrid`), `ENABLE_RERANKER`, `RERANKER_TYPE` (`mock`, `cross_encoder`, `flashrank`), `RERANKER_TIMEOUT_SECONDS` (default `2.0s`), `RRF_K`, `HYBRID_DENSE_WEIGHT`, `HYBRID_SPARSE_WEIGHT`.
  - `backend/app/schemas/retrieval.py`:
    - Added request override options `mode` and `rerank` to `RetrievalQuery`.
    - Added channel provenance and rank diagnostics to `RetrievedChunk`: `channel` (`dense`, `sparse`, `both`), `dense_rank`, `sparse_rank`, `rerank_score`, `rerank_rank`.
    - Created `RetrievalDiagnostics` schema to capture mode, channels used, candidate pool sizes, Stage 2 post-validation count, and reranker latency.
    - Updated `RetrievalResponse` with optional `diagnostics` field.
  - `backend/app/schemas/generation.py`:
    - Updated `ChatQueryRequest` to support optional `mode` and `rerank` configuration overrides.
    - Forwarded settings from `generate_answer` down into `retrieve_context`.
  - `backend/app/services/vector_store.py`:
    - Added `get_chunks_by_documents(allowed_document_ids)` to `VectorStore` ABC and `ChromaVectorStore` implementation for retrieving pre-filtered candidate chunks across authorized documents.
  - `backend/app/services/reranker.py`:
    - `Reranker` abstract base class with pluggable architecture.
    - `MockReranker`: Cross-attentive token-overlap, exact phrase alignment, and term density reranker for deterministic and offline execution.
    - `CrossEncoderReranker`: Sentence-transformers CrossEncoder integration with graceful fallback.
    - `TimeoutSafeReranker`: Decorator enforcing `RERANKER_TIMEOUT_SECONDS` with safe fallback to original RRF candidate order.
    - `get_reranker`: Factory returning configured reranker instance.
  - `backend/app/services/retrieval.py`:
    - Two-channel candidate generation: Channel 1 (Dense ChromaDB search) and Channel 2 (Sparse BM25 search over authorized chunks).
    - Multi-channel Reciprocal Rank Fusion (RRF) with deduplication, penalty ranking for channel absences, and score normalization.
    - Strict Stage 2 post-retrieval PostgreSQL revalidation ensuring zero cross-department or cross-tenant leaks.
    - Reranker integration operating exclusively on authorized survivors.
    - Granular retrieval diagnostics and structured audit logging.
  - `evals/benchmark_hybrid.py` & `evals/hybrid_retrieval_report.md`:
    - Comprehensive benchmark script evaluating Mode 1 (Vector-Only), Mode 2 (Hybrid RRF), and Mode 3 (Hybrid + Reranker) over the 20 benchmark questions.
    - Verified Recall@5 = 100.0%, MRR = 1.0000, 0 unauthorized RBAC leaks, and P50 latency <= 335ms.
  - `backend/tests/test_hybrid_retrieval.py`:
    - 7 comprehensive tests verifying exact keyword query finding passages missed by semantic-only search, conceptual queries, cross-department security isolation, reranker reordering only authorized items, timeout safe fallback, empty-result handling, and diagnostic reporting.
  - `frontend/src/types/index.ts`:
    - Updated TypeScript definition of `RetrievedChunk` to include channel provenance and reranker score/rank attributes.
- **Verification Commands Run**:
  - `pytest backend/tests/test_hybrid_retrieval.py -v --show-capture=no` -> 7/7 passed in 3.70s.
  - `pytest backend/tests -v --show-capture=no` -> 88/88 passed in 46.00s.
  - `python evals/benchmark_hybrid.py` -> All 3 modes evaluated; 0 leaks, 100% recall.
  - `npm test` in `frontend/` -> 8/8 passed in 14.70s.
  - `npm run build` in `frontend/` -> Production bundle built in 4.60s.
- **Next Step**: Phase 12 — Document Versioning & Lifecycle (document revisions, checksum detection, superseding, version-aware citations, rollback).

---

### Phase 12: Document Versioning & Lifecycle Management
- **Date**: 2026-11-01
- **Branch**: `main`
- **Completed Deliverables**:
  - `backend/alembic/versions/0002_document_lifecycle_and_versioning.py`:
    - Database migration adding `logical_document_id` (GUID, indexed), `supersedes_id` (GUID, indexed, self-referential foreign key on PostgreSQL), `lifecycle_state` (`active`, `superseded`, `archived`, `quarantined`, `deleted`), and `effective_date` (nullable timestamp with timezone).
    - Idempotent backfill: `logical_document_id = id`, `lifecycle_state = 'active'` for all pre-existing records.
  - `backend/app/models/document.py`:
    - Updated `Document` model with `logical_document_id`, `supersedes_id`, `lifecycle_state`, `effective_date`, and self-referential `supersedes` relationship.
  - `backend/app/schemas/document.py` & `backend/app/schemas/__init__.py`:
    - Updated `DocumentRead` to include lifecycle fields and revision lineage.
    - Added `DocumentRevisionHistoryItem` and `DocumentHistoryResponse` schemas for timeline visualization.
  - `backend/app/schemas/generation.py`:
    - Added `document_version: int = Field(default=1)` to `Citation`.
  - `backend/app/services/generation.py`:
    - Updated `build_grounded_prompt` to inject `version="v{chunk.document_version}"` attribute into XML document delimitations.
    - Updated `extract_grounded_citations` to populate `document_version` directly from verified PostgreSQL chunk provenance.
  - `backend/app/services/policy.py`:
    - Updated `can_read_document` to support `require_active: bool = False`, strictly failing closed if non-active states are encountered.
    - Updated `get_authorized_document_ids` to default to `eligible_lifecycle_states=("active",)`.
  - `backend/app/services/retrieval.py`:
    - Hardened Stage 2 post-retrieval validation to enforce `Document.lifecycle_state == 'active'` and `can_read_document(..., require_active=True)`.
    - Populated `document_version` from chunk metadata with fallback to document record.
  - `backend/app/api/routes/documents.py`:
    - **Duplicate Detection**: Check `checksum_sha256` against active documents in target department. Fails with 409 Conflict if duplicate content exists.
    - **Document Revision (`upload_document`)**: Added `revises_document_id` support. Sets family `logical_document_id`, increments `version`, sets `supersedes_id`, supersedes older active versions, invalidates/purges superseded vectors from ChromaDB, copies explicit grants, and re-indexes new chunks.
    - **Rollback (`POST /api/v1/documents/{document_id}/rollback`)**: Re-activates prior revision, supersedes active version, re-indexes restored chunks, and purges superseded vectors.
    - **Revision History (`GET /api/v1/documents/{document_id}/history`)**: Returns full revision timeline ordered by version descending.
    - **Deletion Lifecycle**: Idempotently marks `lifecycle_state = "deleted"`.
  - `backend/tests/test_versioning.py`:
    - 7 comprehensive unit, integration, and security tests covering duplicate detection (409), revision superseding, identical revision rejection (409), lifecycle-scoped retrieval (zero leakage of superseded chunks), version-aware citations, rollback mechanics, full history timelines, and unauthorized revision/rollback rejections (403).
  - `frontend/src/types/index.ts`:
    - Updated `DocumentItem`, `Citation`, and `RetrievedChunk` with version and lifecycle fields. Added `DocumentRevisionHistoryItem` and `DocumentHistoryResponse`.
  - `frontend/src/api/client.ts`:
    - Added `getHistory(id)` and `rollback(id)` API client functions.
  - `frontend/src/components/CitationDrawer.tsx`:
    - Displays version badge (`v{citation.document_version}`) alongside document title and citation coordinates.
  - `frontend/src/components/DocumentUploadModal.tsx`:
    - Added revision mode (`revisingDocument`), allowing users to upload updated document revisions that supersede active versions.
  - `frontend/src/components/DocumentViewerModal.tsx`:
    - Added "Revision Timeline" tab listing all revisions with version badges, lifecycle status, upload dates, and single-click "Rollback" action for managers.
  - `frontend/src/pages/DocumentsPage.tsx`:
    - Added Version and Lifecycle columns with visual status badges, plus "Upload Revision" action button.
- **Verification Commands Run**:
  - `alembic upgrade head` -> Applied `0002_lifecycle_versioning` to SQLite and PostgreSQL schemas.
  - `pytest backend/tests/test_versioning.py -v --show-capture=no` -> 7/7 passed in 14.36s.
  - `pytest backend/tests/ -v --show-capture=no` -> 95/95 passed in 105.25s.
  - `npm --prefix frontend test` -> 8/8 passed in 27.86s.
  - `npm --prefix frontend run build` -> Production bundle built cleanly with zero TypeScript errors.
- **Next Step**: Phase 13 — Conversation Memory & Session Continuity.









