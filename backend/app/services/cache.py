"""Safe policy-scoped cache for RAG generation responses.

Guarantees strict multi-tenant and cross-user isolation:
- Cache key is strictly scoped to:
  user_id + department_id + roles_hash + doc_versions_hash + query_hash
- User A's cache can NEVER be served to User B (cross-user isolation).
- Invalidation occurs automatically whenever documents are created, updated,
  superseded, or rolled back because doc_versions_hash changes.
- In-memory bounded cache with TTL and LRU eviction.
"""

from collections import OrderedDict
import hashlib
import time
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)
settings = get_settings()


class SafeScopedCache:
    """In-memory safe scoped cache with cryptographic key scoping, TTL, and LRU eviction."""

    def __init__(self, max_entries: int = 1000, default_ttl_seconds: int = 300) -> None:
        self.max_entries = max_entries
        self.default_ttl = default_ttl_seconds
        # Maps cache_key -> (expiry_time, cached_payload)
        self._cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()

    @staticmethod
    def compute_doc_versions_hash(doc_versions: Dict[str, int]) -> str:
        """Deterministically hash the set of authorized document IDs and versions."""
        if not doc_versions:
            return "empty"
        sorted_pairs = sorted(f"{str(k)}:v{v}" for k, v in doc_versions.items())
        raw = "|".join(sorted_pairs)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def compute_cache_key(
        user: User,
        doc_versions_hash: str,
        query: str,
    ) -> str:
        """Compute strict policy-scoped cache key containing user identity, roles, and document versions."""
        role_names = sorted([r.name for r in (user.roles or [])])
        roles_str = ",".join(role_names)
        user_id_str = str(user.id)
        dept_id_str = str(user.department_id) if user.department_id else "nodept"
        norm_query = query.strip().lower()
        query_hash = hashlib.sha256(norm_query.encode("utf-8")).hexdigest()[:16]

        raw_identifier = (
            f"uid={user_id_str};dept={dept_id_str};roles={roles_str};"
            f"docs={doc_versions_hash};q={query_hash}"
        )
        return hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if present and not expired."""
        if not settings.ENABLE_SCOPED_CACHE:
            return None

        if cache_key not in self._cache:
            return None

        expiry, payload = self._cache[cache_key]
        now = time.time()
        if now > expiry:
            del self._cache[cache_key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        return dict(payload)

    def set(
        self,
        cache_key: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store response in cache with TTL and LRU eviction."""
        if not settings.ENABLE_SCOPED_CACHE:
            return

        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl

        # Evict oldest entry if at capacity
        if len(self._cache) >= self.max_entries and cache_key not in self._cache:
            self._cache.popitem(last=False)

        self._cache[cache_key] = (expiry, payload)
        self._cache.move_to_end(cache_key)

    def clear(self) -> int:
        """Purge all entries from the cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cleared %d entries from SafeScopedCache", count)
        return count

    def size(self) -> int:
        """Return number of currently cached entries."""
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """Return cache health and capacity metrics."""
        return {
            "entries_count": len(self._cache),
            "max_entries": self.max_entries,
            "default_ttl_seconds": self.default_ttl,
            "enabled": settings.ENABLE_SCOPED_CACHE,
        }


_global_cache: Optional[SafeScopedCache] = None


def get_safe_cache() -> SafeScopedCache:
    """Return singleton safe scoped cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = SafeScopedCache(
            max_entries=settings.CACHE_MAX_ENTRIES,
            default_ttl_seconds=settings.CACHE_TTL_SECONDS,
        )
    return _global_cache
