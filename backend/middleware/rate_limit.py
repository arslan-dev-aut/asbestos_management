"""Lightweight per-IP rate limiting for unauthenticated endpoints.

Fixed-window counter keyed by client IP. This is process-local: under multiple
replicas each instance enforces its own window, so the effective global limit is
``limit * replica_count``. For strict global limiting move the counter to Redis.
It still defends a single instance against token enumeration / scraping bursts.
"""

from __future__ import annotations

import time
from collections import OrderedDict

from fastapi import Request

from backend.config import get_settings
from backend.database.exceptions import DomainError


class RateLimitedError(DomainError):
    status_code = 429


# key -> (window_start_epoch_minute, count)
_WINDOWS: OrderedDict[str, tuple[int, int]] = OrderedDict()
_MAX_KEYS = 10_000
_WINDOW_SECONDS = 60


def _client_ip(request: Request) -> str:
    # Honour the first hop in X-Forwarded-For when behind a proxy/ingress.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def public_rate_limit(request: Request) -> None:
    """FastAPI dependency: throttle a caller to N requests per minute."""
    limit = get_settings().public_rate_limit_per_minute
    window = int(time.time() // _WINDOW_SECONDS)
    ip = _client_ip(request)
    key = f"{ip}:{window}"

    start, count = _WINDOWS.get(key, (window, 0))
    if count >= limit:
        raise RateLimitedError("Too many requests. Please slow down and try again shortly.")
    _WINDOWS[key] = (start, count + 1)
    _WINDOWS.move_to_end(key)

    # Bound memory: drop the oldest entries once we exceed the cap.
    while len(_WINDOWS) > _MAX_KEYS:
        _WINDOWS.popitem(last=False)
