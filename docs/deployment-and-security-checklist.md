# AegisRAG Production Deployment & Security Hardening Checklist

Prior to promoting any release to staging or production, verify all criteria in this checklist.

---

## 1. Secrets & Credentials Sanitization
- [x] **Zero Secrets in Git History**: No API keys (`gsk_...`, `sk-...`), bearer tokens, passwords, or private keys tracked in Git.
- [x] **Environment Separation**: Distinct configuration files for `development`, `staging`, `production`, and `test`.
- [x] **Secret Injection**: All credentials loaded strictly via environment variables or managed secrets stores (e.g. AWS Secrets Manager, HashiCorp Vault).
- [x] **Sanitized Outputs**: Traces, health endpoints, audit logs, and error responses never output secrets, auth headers, or raw document content.

---

## 2. Server-Side RBAC & Security Boundaries
- [x] **PostgreSQL is Authoritative**: Department, roles, document grants, and lifecycle states derived exclusively on the server from verified database records.
- [x] **Two-Stage Authorization Filtering**:
  1. *Pre-retrieval*: Vector search candidates pre-filtered to user-authorized document IDs computed from PostgreSQL.
  2. *Post-retrieval*: Every candidate chunk re-verified against PostgreSQL before entering LLM context.
- [x] **Default-Deny Policy**: Missing or indeterminate access check results fail closed with `HTTP 403 Forbidden`.
- [x] **Prompt Injection Delimitation**: Untrusted document context strictly wrapped in XML tags with neutralizing replacements (`&lt;/context&gt;`).

---

## 3. Infrastructure & Container Hardening
- [x] **Non-Root Execution**: Docker images run as dedicated non-root user (`appuser`, UID `10001`).
- [x] **No Public Exposure of Database/Vector Stores**:
  - PostgreSQL port `5432` binds to `127.0.0.1` or remains internal to Docker network (`expose` only).
  - ChromaDB ports are never exposed to the public internet.
- [x] **Readiness & Liveness Probes**:
  - `/health/live`: Unauthenticated process check.
  - `/health/ready`: Deep dependency checks (database, vector store, storage, providers) returning 200 or 503 without leaking paths or secrets.
- [x] **Resource Constraints**: CPU and memory limits defined in deployment templates.

---

## 4. Resilience & Observability
- [x] **Bounded Retries & Timeouts**: LLM provider calls bounded by `LLM_TIMEOUT_SECONDS=15.0` with exponential backoff, abstaining gracefully on timeout.
- [x] **Identity-Aware Rate Limiting**: Sliding-window minute limits and daily quotas enforced per user identity.
- [x] **Safe Scoped Caching**: Cache keys scoped to `user_id` + `department_id` + `hash(roles)` + `hash(doc_versions)` + `hash(query)` with strict cross-user isolation.
- [x] **Disaster Recovery Tested**: Ability to completely wipe and rebuild vector store from authoritative PostgreSQL database records verified.

---

## 5. Verification Commands
```bash
# Backend pytest suite (100% pass required)
pytest backend/tests/ -v

# Continuous evaluation benchmark (100% pass required)
python evals/run_continuous_eval.py

# Frontend vitest suite (100% pass required)
npm --prefix frontend test -- --run

# Frontend production compile (zero TypeScript errors required)
npm --prefix frontend run build
```

