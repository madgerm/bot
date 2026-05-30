"""Einfaches In-Memory-Rate-Limiting (Login, Webhooks)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = [t for t in self._hits[key] if t > cutoff]
            if len(bucket) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Zu viele Anfragen — bitte später erneut versuchen",
                )
            bucket.append(now)
            self._hits[key] = bucket


def client_key(request: Request, suffix: str = "") -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        host = forwarded.split(",")[0].strip()
    else:
        host = request.client.host if request.client else "unknown"
    return f"{host}:{suffix}" if suffix else host


def login_rate_limiter() -> RateLimiter:
    attempts = int(os.environ.get("BOT_LOGIN_RATE_LIMIT", "10"))
    window = float(os.environ.get("BOT_LOGIN_RATE_WINDOW", "300"))
    return RateLimiter(max_attempts=attempts, window_seconds=window)


def webhook_rate_limiter() -> RateLimiter:
    return RateLimiter(max_attempts=60, window_seconds=60.0)
