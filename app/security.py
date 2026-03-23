"""
SATA security and resilience utilities.

Implements security hardening tasks sourced from accepted agent insights:
- API access control guardrails
- baseline rate limiting for abuse resistance
- audit trail logging for sensitive agent actions
- transport security headers
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Deque, Dict, Optional

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


@dataclass
class AuditEvent:
    event_type: str
    route: str
    method: str
    status: str
    timestamp: str
    actor: str = "unknown"
    detail: Optional[str] = None


class SecurityAuditLogger:
    """Append-only JSONL audit logger for sensitive endpoints."""

    def __init__(self, path: str = "tmp/security_audit.log"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


audit_logger = SecurityAuditLogger()


async def require_admin_token(x_sata_admin_token: str | None = Header(default=None)) -> bool:
    """
    Optional access control:
    - if SATA_ADMIN_TOKEN is configured, protected endpoints require matching header.
    - if not configured, endpoints remain open for local/dev usage.
    """
    expected = os.getenv("SATA_ADMIN_TOKEN")
    if expected and x_sata_admin_token != expected:
        raise HTTPException(status_code=403, detail="Admin token required for this operation")
    return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds conservative security headers for browser/API clients."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window in-memory rate limiter.
    Conservative defaults to reduce abuse and improve resilience.
    """

    def __init__(self, app, max_requests_per_minute: int = 120):
        super().__init__(app)
        self.max_requests = max_requests_per_minute
        self.window_seconds = 60
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        key = self._key(request)
        now = time.time()
        queue = self.requests[key]

        while queue and queue[0] <= now - self.window_seconds:
            queue.popleft()

        if len(queue) >= self.max_requests:
            audit_logger.log(
                AuditEvent(
                    event_type="rate_limit_block",
                    route=request.url.path,
                    method=request.method,
                    status="blocked",
                    timestamp=datetime.now(UTC).isoformat(),
                    actor=self._actor(request),
                    detail=f"max_requests={self.max_requests}/minute",
                )
            )
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        queue.append(now)
        return await call_next(request)

    @staticmethod
    def _actor(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    @classmethod
    def _key(cls, request: Request) -> str:
        first_segment = request.url.path.strip("/").split("/")[0] if request.url.path.strip("/") else "root"
        return f"{cls._actor(request)}:{first_segment}"
