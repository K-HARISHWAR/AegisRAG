"""Identity-aware sliding window rate limiter and daily quota controller."""

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.feature_flags import get_feature_flags
from app.models.user import User
from app.schemas.operations import QuotaStatusResponse

settings = get_settings()


class RateLimitExceeded(HTTPException):
    """Raised when an identity exceeds its allocated query rate or daily quota."""

    def __init__(self, limit: int, retry_after: int, reason: str = "rate_limit_exceeded") -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {reason}. Please retry after {retry_after} seconds.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )
        self.retry_after = retry_after
        self.limit = limit
        self.reason = reason


class RateLimitManager:
    """In-memory identity-aware rate limiter supporting sliding-window minutes and daily quotas."""

    def __init__(self) -> None:
        # Maps user_id -> deque of request timestamps in the last 60 seconds
        self._minute_windows: Dict[str, deque[float]] = defaultdict(deque)
        # Maps (user_id, date_str) -> integer count of queries executed today
        self._daily_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    def _get_user_limits(self, user: User) -> Tuple[int, int, str]:
        """Return (per_minute_limit, daily_quota, role_label) for user."""
        if user.is_admin:
            return settings.RATE_LIMIT_ADMIN_PER_MINUTE, settings.DAILY_QUOTA_ADMIN, "admin"
        if user.is_manager:
            return settings.RATE_LIMIT_MANAGER_PER_MINUTE, settings.DAILY_QUOTA_MANAGER, "department_manager"
        return settings.RATE_LIMIT_EMPLOYEE_PER_MINUTE, settings.DAILY_QUOTA_EMPLOYEE, "employee"

    def check_and_record(
        self,
        user: User,
        ip_address: Optional[str] = None,
    ) -> Dict[str, int]:
        """Check rate limits and daily quota. Increment counts if permitted; raise 429 if exceeded."""
        if not settings.ENABLE_RATE_LIMITING or not get_feature_flags().is_enabled("enable_rate_limiting"):
            return {"limit": 1000, "remaining": 1000, "reset": 60}

        now = time.time()
        user_key = str(user.id) if user and user.id else (ip_address or "anonymous")
        minute_limit, daily_quota, _ = self._get_user_limits(user)

        # 1. Check minute sliding window
        window = self._minute_windows[user_key]
        # Purge entries older than 60 seconds
        while window and window[0] <= now - 60.0:
            window.popleft()

        if len(window) >= minute_limit:
            oldest = window[0]
            retry_after = max(1, int(60.0 - (now - oldest)))
            raise RateLimitExceeded(limit=minute_limit, retry_after=retry_after, reason=f"Allowed {minute_limit} requests per minute")

        # 2. Check daily quota
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_key = (user_key, today_str)
        used_today = self._daily_counts[daily_key]

        if used_today >= daily_quota:
            # Seconds until midnight UTC
            now_dt = datetime.now(timezone.utc)
            midnight_ts = datetime(now_dt.year, now_dt.month, now_dt.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()
            retry_after = max(1, int(midnight_ts - now))
            raise RateLimitExceeded(limit=daily_quota, retry_after=retry_after, reason=f"Exceeded daily quota of {daily_quota} queries")

        # Record this request
        window.append(now)
        self._daily_counts[daily_key] += 1

        remaining = max(0, minute_limit - len(window))
        return {
            "limit": minute_limit,
            "remaining": remaining,
            "reset": 60,
        }

    def get_quota_status(self, user: User) -> QuotaStatusResponse:
        """Return user's quota and current usage status."""
        now = time.time()
        user_key = str(user.id)
        minute_limit, daily_quota, role_label = self._get_user_limits(user)

        window = self._minute_windows[user_key]
        while window and window[0] <= now - 60.0:
            window.popleft()

        remaining_minute = max(0, minute_limit - len(window))

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used_today = self._daily_counts.get((user_key, today_str), 0)
        remaining_today = max(0, daily_quota - used_today)

        # Calculate reset seconds
        now_dt = datetime.now(timezone.utc)
        midnight_ts = datetime(now_dt.year, now_dt.month, now_dt.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()
        reset_seconds = max(1, int(midnight_ts - now))

        return QuotaStatusResponse(
            user_id=user.id,
            email=user.email,
            role=role_label,
            rate_limit_per_minute=minute_limit,
            requests_remaining_minute=remaining_minute,
            daily_quota=daily_quota,
            daily_queries_used=used_today,
            daily_queries_remaining=remaining_today,
            reset_seconds=reset_seconds,
        )

    def reset_for_test(self) -> None:
        """Clear windows for test isolation."""
        self._minute_windows.clear()
        self._daily_counts.clear()


_global_rate_limiter: Optional[RateLimitManager] = None


def get_rate_limiter() -> RateLimitManager:
    """Return singleton rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimitManager()
    return _global_rate_limiter

