# AegisRAG Backup, Restoration & Disaster Recovery Runbook

## 1. Architectural Philosophy: PostgreSQL is the Sole Authority

In AegisRAG, **PostgreSQL is the single source of truth** for all identities, departments, document metadata, lifecycle versions, access grants, and audit events.
The vector database (ChromaDB / in-memory vector store) is an **ephemeral cache/index**. If the vector database is corrupted, lost, or compromised, it can be completely wiped and rebuilt from scratch on demand using authoritative records and original uploaded documents stored in PostgreSQL and secure storage.

---

## 2. Automated Point-in-Time Database Snapshots

### 2.1 Triggering a Backup via API
System administrators can trigger an on-demand verified database snapshot at any time:
```bash
curl -X POST http://localhost:8000/api/v1/operations/disaster-recovery/backup \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Response Format**:
```json
{
  "filename": "aegisrag_backup_20261113_165000.json",
  "filepath": "backend/data/backups/aegisrag_backup_20261113_165000.json",
  "created_at": "2026-11-13T11:20:00.000000+00:00",
  "size_bytes": 104520,
  "checksum_sha256": "4f53cda...",
  "table_counts": {
    "departments": 3,
    "roles": 3,
    "users": 4,
    "documents": 12,
    "grants": 5,
    "chunks": 48,
    "audit_events": 120
  },
  "duration_ms": 142.5
}
```

### 2.2 Native PostgreSQL Production Backup Command
For production deployments using managed PostgreSQL:
```bash
# Export compressed binary database dump
pg_dump -h <DB_HOST> -U <DB_USER> -d aegisrag -Fc -f aegisrag_prod_$(date +%Y%m%d_%H%M%S).dump

# Verify backup integrity
pg_restore --list aegisrag_prod_*.dump > /dev/null && echo "Backup integrity verified"
```

---

## 3. Database Restoration Procedure

### 3.1 Restoring from Native Dump
To restore PostgreSQL from a point-in-time snapshot:
```bash
# 1. Stop backend service to prevent write conflicts during restoration
docker compose stop backend

# 2. Drop existing connections and restore database
pg_restore -h <DB_HOST> -U <DB_USER> -d aegisrag --clean --if-exists aegisrag_prod_<TIMESTAMP>.dump

# 3. Apply any pending Alembic migrations
alembic upgrade head

# 4. Restart backend service
docker compose start backend
```

---

## 4. Vector Store Disaster Recovery: Complete Index Rebuild

If ChromaDB or vector storage is lost, corrupted, or experiencing embedding drift:

### 4.1 Triggering Index Rebuild via Admin Console
1. Navigate to **Admin Console -> Operations & Performance**.
2. Locate the **Disaster Recovery & Vector Store Synchronization** panel.
3. Click **"Rebuild Vector Index from PostgreSQL Authority"**.

### 4.2 Triggering Index Rebuild via API
```bash
curl -X POST http://localhost:8000/api/v1/operations/disaster-recovery/rebuild-index \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Rebuild Workflow Executed**:
1. Completely wipes existing vector collections (`vector_store.reset()`).
2. Queries all active, non-deleted `Chunk` and `Document` records from PostgreSQL.
3. Computes fresh embeddings using the configured `EmbeddingProvider`.
4. Indexes all chunks into vector store with authoritative RBAC metadata (`document_id`, `department_id`, `is_confidential`, `document_version`).
5. Validates vector count matches PostgreSQL active chunks.

---

## 5. Disaster Recovery Status Check

To verify database-vector synchronization and backup health:
```bash
curl -X GET http://localhost:8000/api/v1/operations/disaster-recovery/status \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```
