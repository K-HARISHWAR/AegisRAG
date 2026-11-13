"""Disaster recovery, automated database backups, and vector index rebuild service.

PostgreSQL is the single source of truth for users, roles, departments, document metadata,
and access grants. The vector store is an ephemeral index that can be completely wiped
and rebuilt on demand from authoritative PostgreSQL records and original stored files.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.audit import AuditEvent
from app.models.department import Department
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.role import Role
from app.models.user import User
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.cache import get_safe_cache
from app.services.indexing import index_document
from app.services.storage import StorageProvider, get_storage_provider
from app.services.vector_store import VectorStore, get_vector_store

logger = get_logger(__name__)
settings = get_settings()

BACKUP_DIR = Path("backend/data/backups")


def _compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hash over bytes."""
    return hashlib.sha256(content).hexdigest()


class DisasterRecoveryService:
    """Handles snapshot backups, integrity verification, and vector index rebuilding."""

    @staticmethod
    def get_backup_dir() -> Path:
        """Ensure and return the backup directory path."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        return BACKUP_DIR

    @staticmethod
    async def create_backup(
        db: AsyncSession,
        target_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a point-in-time snapshot of authoritative PostgreSQL database records."""
        start_time = time.perf_counter()
        backup_folder = Path(target_dir) if target_dir else DisasterRecoveryService.get_backup_dir()
        backup_folder.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"aegisrag_backup_{timestamp_str}.json"
        backup_path = backup_folder / backup_filename

        # Export core entity records
        departments = (await db.execute(select(Department))).scalars().all()
        roles = (await db.execute(select(Role))).scalars().all()
        users = (await db.execute(select(User).options(selectinload(User.roles)))).scalars().all()
        documents = (await db.execute(select(Document))).scalars().all()
        grants = (await db.execute(select(DocumentGrant))).scalars().all()
        audit_events = (await db.execute(select(AuditEvent))).scalars().all()

        backup_data: Dict[str, Any] = {
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tables": {
                "departments": [
                    {"id": str(d.id), "name": d.name, "description": d.description}
                    for d in departments
                ],
                "roles": [
                    {"id": str(r.id), "name": r.name, "description": r.description}
                    for r in roles
                ],
                "users": [
                    {
                        "id": str(u.id),
                        "email": u.email,
                        "department_id": str(u.department_id) if u.department_id else None,
                        "is_active": u.is_active,
                        "is_superuser": u.is_superuser,
                        "role_names": [r.name for r in u.roles],
                    }
                    for u in users
                ],
                "documents": [
                    {
                        "id": str(d.id),
                        "title": d.title,
                        "owner_id": str(d.owner_id),
                        "department_id": str(d.department_id),
                        "storage_key": d.storage_key,
                        "file_type": d.file_type,
                        "file_size_bytes": d.file_size_bytes,
                        "checksum_sha256": d.checksum_sha256,
                        "is_confidential": d.is_confidential,
                        "status": d.status,
                        "version": d.version,
                        "lifecycle_state": d.lifecycle_state,
                    }
                    for d in documents
                ],
                "grants": [
                    {
                        "id": str(g.id),
                        "document_id": str(g.document_id),
                        "grantee_user_id": str(g.grantee_user_id) if g.grantee_user_id else None,
                        "grantee_role_id": str(g.grantee_role_id) if g.grantee_role_id else None,
                        "permission": g.permission,
                    }
                    for g in grants
                ],
                "audit_events_count": len(audit_events),
            },
        }

        # Compute checksum over content without checksum field
        content_bytes = json.dumps(backup_data, indent=2).encode("utf-8")
        checksum = _compute_sha256(content_bytes)
        backup_data["checksum_sha256"] = checksum

        # Write to disk
        backup_path.write_bytes(json.dumps(backup_data, indent=2).encode("utf-8"))
        elapsed = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Created database backup snapshot %s (%d bytes, checksum=%s)",
            backup_filename,
            len(content_bytes),
            checksum[:12],
        )

        return {
            "filename": backup_filename,
            "filepath": str(backup_path),
            "created_at": backup_data["created_at"],
            "size_bytes": len(content_bytes),
            "checksum_sha256": checksum,
            "table_counts": {
                "departments": len(departments),
                "roles": len(roles),
                "users": len(users),
                "documents": len(documents),
                "grants": len(grants),
                "audit_events": len(audit_events),
            },
            "duration_ms": round(elapsed, 2),
        }

    @staticmethod
    def verify_backup_integrity(backup_path: Path) -> Dict[str, Any]:
        """Validate integrity and schema format of a backup file."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found at {backup_path}")

        raw_bytes = backup_path.read_bytes()
        data = json.loads(raw_bytes.decode("utf-8"))

        expected_checksum = data.get("checksum_sha256")
        verify_dict = dict(data)
        verify_dict.pop("checksum_sha256", None)
        computed_checksum = _compute_sha256(json.dumps(verify_dict, indent=2).encode("utf-8"))

        is_valid = expected_checksum is not None and expected_checksum == computed_checksum
        return {
            "filename": backup_path.name,
            "is_valid": is_valid,
            "expected_checksum": expected_checksum,
            "computed_checksum": computed_checksum,
            "created_at": data.get("created_at"),
            "table_counts": {k: len(v) if isinstance(v, list) else v for k, v in data.get("tables", {}).items()},
        }

    @staticmethod
    async def rebuild_vector_store_from_database(
        db: AsyncSession,
        storage: Optional[StorageProvider] = None,
        vector_store: Optional[VectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> Dict[str, Any]:
        """Completely wipe and rebuild vector store indexes from authoritative PostgreSQL records and original files."""
        start_time = time.perf_counter()

        if storage is None:
            storage = get_storage_provider()
        if vector_store is None:
            vector_store = get_vector_store()
        if embedding_provider is None:
            embedding_provider = get_embedding_provider()

        # 1. Reset vector store index and clear response cache completely
        vector_store.reset()
        get_safe_cache().clear()

        # 2. Query active documents from PostgreSQL
        doc_stmt = (
            select(Document)
            .where(
                Document.status != "deleted",
                Document.lifecycle_state == "active",
            )
        )
        docs_res = await db.execute(doc_stmt)
        active_docs = docs_res.scalars().all()

        total_chunks_indexed = 0
        docs_processed = 0

        for doc in active_docs:
            chunks_indexed = await index_document(
                document=doc,
                db=db,
                storage=storage,
                vector_store=vector_store,
                embedding_provider=embedding_provider,
            )
            total_chunks_indexed += chunks_indexed
            docs_processed += 1

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Vector store index rebuilt successfully: %d documents, %d chunks in %.2fms",
            docs_processed,
            total_chunks_indexed,
            elapsed,
        )

        return {
            "status": "rebuilt",
            "documents_processed": docs_processed,
            "chunks_indexed": total_chunks_indexed,
            "duration_ms": round(elapsed, 2),
            "vector_store_healthy": vector_store.health_check(),
        }

    @staticmethod
    async def get_status(
        db: AsyncSession,
        vector_store: Optional[VectorStore] = None,
    ) -> Dict[str, Any]:
        """Return disaster recovery health, recent backups, and database-vector synchronization."""
        if vector_store is None:
            vector_store = get_vector_store()

        # Count active documents in PostgreSQL
        doc_count_stmt = (
            select(func.count(Document.id))
            .where(
                Document.status != "deleted",
                Document.lifecycle_state == "active",
            )
        )
        pg_doc_count = (await db.execute(doc_count_stmt)).scalar() or 0

        # Backups list
        backup_folder = DisasterRecoveryService.get_backup_dir()
        backup_files = sorted(backup_folder.glob("aegisrag_backup_*.json"), key=os.path.getmtime, reverse=True)

        recent_backups = []
        for bf in backup_files[:5]:
            recent_backups.append({
                "filename": bf.name,
                "size_bytes": bf.stat().st_size,
                "modified_at": datetime.fromtimestamp(bf.stat().st_mtime, timezone.utc).isoformat(),
            })

        return {
            "database_active_chunks": pg_doc_count,
            "vector_store_healthy": vector_store.health_check(),
            "recent_backups_count": len(backup_files),
            "recent_backups": recent_backups,
            "backup_directory": str(backup_folder),
        }
