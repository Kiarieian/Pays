"""
In-memory sliding window rate limiter.

Each limiter tracks requests per (key, window_start) and rejects
when the count exceeds the limit.

Scope: process-local. Does NOT provide distributed protection when
multiple API replicas are deployed behind a load balancer.

Limit classes are configured via environment variables (see config.py):
  PAYMENT_RATE_LIMIT, DISBURSEMENT_RATE_LIMIT, AUTH_RATE_LIMIT,
  GENERAL_API_RATE_LIMIT, ADMIN_RATE_LIMIT
"""
import hashlib
import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse

from app.config import get_settings

logger = logging.getLogger("daraja.rate_limit")

settings = get_settings()

# Sliding window: 60-second rolling window
WINDOW_SECONDS = 60


class SlidingWindowLimiter:
    """Thread-safe sliding window counter for a single limit class."""

    def __init__(self, max_requests: int, window: int = WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window = window
        self._counts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.time()
        cutoff = now - self.window

        with self._lock:
            timestamps = self._counts[key]
            self._counts[key] = [t for t in timestamps if t > cutoff]
            timestamps = self._counts[key]

            if len(timestamps) >= self.max_requests:
                return False

            timestamps.append(now)
            return True

    def remaining(self, key: str) -> int:
        """How many requests remain in the current window."""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            timestamps = [t for t in self._counts[key] if t > cutoff]
            return max(0, self.max_requests - len(timestamps))

    def reset(self, key: str) -> None:
        """Reset counter for a key (used in tests)."""
        with self._lock:
            self._counts.pop(key, None)


# Limiters per class — initialized once at import time from config
payment_limiter = SlidingWindowLimiter(settings.rate_limit.payment_per_minute)
disbursement_limiter = SlidingWindowLimiter(settings.rate_limit.disbursement_per_minute)
auth_limiter = SlidingWindowLimiter(settings.rate_limit.auth_per_minute)
general_api_limiter = SlidingWindowLimiter(settings.rate_limit.general_api_per_minute)
admin_limiter = SlidingWindowLimiter(settings.rate_limit.admin_per_minute)


def _client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _api_key_hash(request: Request) -> str:
    """Hash the API key for per-merchant rate limiting.
    Uses first 16 chars of SHA-256 for a stable but non-reversible key."""
    api_key = request.headers.get("x-api-key", "")
    if not api_key or len(api_key) < 12:
        return ""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _session_token_hash(request: Request) -> str:
    """Hash the Bearer session token for per-merchant dashboard rate limiting.
    Uses first 16 chars of SHA-256 for a stable but non-reversible key."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return ""
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        return ""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that applies per-merchant or per-IP rate limits.

    Route classification:
      - POST /pay                 → payment_limiter (by API key hash or session hash)
      - POST /disburse            → disbursement_limiter (by API key hash or session hash)
      - POST /generate_qr         → general_api_limiter (by API key hash or session hash)
      - POST /auth/*              → auth_limiter (by IP)
      - POST /merchants/*         → auth_limiter (by IP)
      - POST /admin/*             → admin_limiter (by IP)
      - GET/POST dashboard routes → general_api_limiter (by session hash, API key, or IP)
      - Callbacks (/api/payment/*) → NOT rate limited (Safaricom)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        method = request.method

        limiter, key = self._classify(method, path, request)

        if limiter is not None:
            if not limiter.is_allowed(key):
                logger.warning(
                    "Rate limit exceeded: %s %s key=%s remaining=%d",
                    method, path, key, limiter.remaining(key),
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please retry later."},
                    headers={
                        "Retry-After": str(WINDOW_SECONDS),
                        "X-RateLimit-Limit": str(limiter.max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

        response = await call_next(request)

        if limiter is not None:
            response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(limiter.remaining(key))

        return response

    def _classify(self, method: str, path: str, request: Request):
        """Return (limiter, key) for the given request, or (None, '') if no limit."""
        # Callbacks — from Safaricom, do NOT rate limit
        if path.startswith("/api/payment/"):
            return None, ""

        # Health check — no limit
        if path == "/health" or path == "/":
            return None, ""

        # Admin endpoints — keyed by IP
        if path.startswith("/admin/"):
            return admin_limiter, f"admin:{_client_ip(request)}"

        # Auth endpoints (login, logout) — keyed by IP
        if path.startswith("/auth/"):
            return auth_limiter, f"auth:{_client_ip(request)}"

        # Merchant signup/set-password — keyed by IP
        if path.startswith("/merchants/"):
            return auth_limiter, f"auth:{_client_ip(request)}"

        # Payment initiation — keyed by API key hash or session token hash
        if method == "POST" and path == "/pay":
            api_hash = _api_key_hash(request)
            if api_hash:
                return payment_limiter, f"pay:{api_hash}"
            sess_hash = _session_token_hash(request)
            if sess_hash:
                return payment_limiter, f"pay:sess:{sess_hash}"
            return payment_limiter, f"pay:ip:{_client_ip(request)}"

        # Disbursement — keyed by API key hash or session token hash
        if method == "POST" and path == "/disburse":
            api_hash = _api_key_hash(request)
            if api_hash:
                return disbursement_limiter, f"disb:{api_hash}"
            sess_hash = _session_token_hash(request)
            if sess_hash:
                return disbursement_limiter, f"disb:sess:{sess_hash}"
            return disbursement_limiter, f"disb:ip:{_client_ip(request)}"

        # QR generation — keyed by API key hash or session token hash
        if method == "POST" and path == "/generate_qr":
            api_hash = _api_key_hash(request)
            if api_hash:
                return general_api_limiter, f"api:{api_hash}"
            sess_hash = _session_token_hash(request)
            if sess_hash:
                return general_api_limiter, f"api:sess:{sess_hash}"
            return general_api_limiter, f"api:ip:{_client_ip(request)}"

        # Dashboard GET endpoints (payments, usage, profile) — by session hash or API key or IP
        api_hash = _api_key_hash(request)
        if api_hash:
            return general_api_limiter, f"api:{api_hash}"
        sess_hash = _session_token_hash(request)
        if sess_hash:
            return general_api_limiter, f"api:sess:{sess_hash}"
        return general_api_limiter, f"api:ip:{_client_ip(request)}"

