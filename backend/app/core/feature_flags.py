"""Server-side dynamic runtime feature flags controller.

Enables gradual rollout, Canary testing, and instant operational kill-switches.
SECURITY INVARIANT:
Feature flags can NEVER disable, bypass, or weaken PostgreSQL-backed RBAC authorization.
"""

from typing import Any, Dict, Optional
import threading

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.feature_flags import FeatureFlagsState, FeatureFlagsUpdate

logger = get_logger(__name__)
settings = get_settings()


class FeatureFlagsManager:
    """Thread-safe runtime feature flags registry with fallback to Settings defaults."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags: Dict[str, bool] = {
            "enable_hybrid_retrieval": getattr(settings, "ENABLE_HYBRID_RETRIEVAL", True),
            "enable_reranking": getattr(settings, "ENABLE_RERANKING", True),
            "enable_evidence_validation": getattr(settings, "ENABLE_EVIDENCE_VALIDATION", True),
            "enable_scoped_cache": getattr(settings, "ENABLE_SCOPED_CACHE", True),
            "enable_rate_limiting": getattr(settings, "ENABLE_RATE_LIMITING", True),
            "enable_tracing": getattr(settings, "ENABLE_TRACING", True),
            "enable_workflows": True,
            "enable_ocr": getattr(settings, "ENABLE_OCR", True),
        }

    def is_enabled(self, flag_name: str) -> bool:
        """Check whether a given feature flag is active."""
        with self._lock:
            return self._flags.get(flag_name, True)

    def get_state(self) -> FeatureFlagsState:
        """Return snapshot of current feature flags."""
        with self._lock:
            return FeatureFlagsState(**self._flags)

    def update_flags(self, updates: FeatureFlagsUpdate) -> FeatureFlagsState:
        """Update runtime flags state."""
        with self._lock:
            update_dict = updates.model_dump(exclude_unset=True)
            for key, val in update_dict.items():
                if val is not None and key in self._flags:
                    old_val = self._flags[key]
                    self._flags[key] = bool(val)
                    logger.info("FeatureFlag '%s' toggled: %s -> %s", key, old_val, val)
            return FeatureFlagsState(**self._flags)

    def reset_to_defaults(self) -> FeatureFlagsState:
        """Reset all flags to their system default configuration."""
        with self._lock:
            self._flags = {
                "enable_hybrid_retrieval": getattr(settings, "ENABLE_HYBRID_RETRIEVAL", True),
                "enable_reranking": getattr(settings, "ENABLE_RERANKING", True),
                "enable_evidence_validation": getattr(settings, "ENABLE_EVIDENCE_VALIDATION", True),
                "enable_scoped_cache": getattr(settings, "ENABLE_SCOPED_CACHE", True),
                "enable_rate_limiting": getattr(settings, "ENABLE_RATE_LIMITING", True),
                "enable_tracing": getattr(settings, "ENABLE_TRACING", True),
                "enable_workflows": True,
                "enable_ocr": getattr(settings, "ENABLE_OCR", True),
            }
            logger.info("Feature flags reset to system defaults")
            return FeatureFlagsState(**self._flags)


_global_flags_manager: Optional[FeatureFlagsManager] = None


def get_feature_flags() -> FeatureFlagsManager:
    """Return singleton feature flags manager instance."""
    global _global_flags_manager
    if _global_flags_manager is None:
        _global_flags_manager = FeatureFlagsManager()
    return _global_flags_manager

