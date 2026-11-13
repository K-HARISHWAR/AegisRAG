# AegisRAG Rollback & Provider Outage Mitigation Runbook

## 1. Upstream Provider Outage Mitigation

### 1.1 Outage Symptoms
- LLM or embedding provider requests timing out (`LLM provider timeout (attempt X/Y)`).
- Traces indicate high `generation` or `retrieval` stage latencies (>2500ms).
- Increased responsible abstention rate with reason `provider_timeout`.

### 1.2 Graceful Failover Behavior
AegisRAG implements bounded retries (`LLM_MAX_RETRIES=2`) with exponential backoff and explicit timeouts (`LLM_TIMEOUT_SECONDS=15.0`).
When an upstream provider (Groq or OpenAI) goes down:
1. AegisRAG **fails closed and abstains gracefully** (`abstention_reason = "provider_timeout"`).
2. The server does NOT hang or crash.
3. Client receives standard abstention message:
   `"The available documentation does not contain sufficient information to answer this question."`
4. Audit event is logged with `PolicyReasonCode.PROVIDER_TIMEOUT`.

### 1.3 Emergency Provider Switch
To switch to an alternative LLM provider or offline mock provider without downtime:
1. Update environment configuration:
   ```bash
   # Switch to offline mock provider or secondary API
   LLM_PROVIDER=mock
   ```
2. Restart backend container:
   ```bash
   docker compose restart backend
   ```

---

## 2. Emergency Feature Flag Kill-Switches

If any auxiliary subsystem causes degraded performance or an unexpected incident, system administrators can instantly disable that specific subsystem without restarting containers:

### 2.1 Available Runtime Kill-Switches
- `enable_hybrid_retrieval`: Disables sparse BM25 retrieval, falling back strictly to pure vector search.
- `enable_reranking`: Disables cross-encoder reranking, using direct similarity scores.
- `enable_evidence_validation`: Disables post-generation claim checking, returning direct model output.
- `enable_scoped_cache`: Disables response caching, forcing fresh pipeline generation.
- `enable_rate_limiting`: Disables sliding-window query throttling.
- `enable_workflows`: Disables multi-step knowledge workflows (`/api/v1/workflows` returns 503).
- `enable_ocr`: Disables OCR extraction for uploaded scanned documents.

### 2.2 Toggling a Kill-Switch via API
```bash
# Example: Disable hybrid search and reranker during high load
curl -X PATCH http://localhost:8000/api/v1/operations/feature-flags \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"enable_hybrid_retrieval": false, "enable_reranking": false}'
```

### 2.3 Resetting Flags to System Defaults
```bash
curl -X POST http://localhost:8000/api/v1/operations/feature-flags/reset \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

---

## 3. Deployment Rollback Procedures

### 3.1 Container Version Rollback (Blue/Green or Docker Compose)
If a newly deployed image exhibits unforeseen issues:

1. Identify prior stable image tag or Git commit:
   ```bash
   git log --oneline -n 5
   ```
2. Revert to previous image or checkout stable commit:
   ```bash
   git checkout <PREVIOUS_COMMIT_TAG>
   ```
3. Re-build and re-launch containers:
   ```bash
   docker compose build backend frontend
   docker compose up -d
   ```
4. Verify readiness:
   ```bash
   curl -f http://localhost:8000/health/ready || exit 1
   ```

### 3.2 Database Migration Rollback (Alembic)
If a database migration needs to be rolled back to a previous revision:
```bash
# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision (e.g. 0006_workflow_executions)
alembic downgrade 0006
```
