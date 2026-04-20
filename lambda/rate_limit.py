"""In-process sliding-window rate limiter for signing routes.

Mirrors ``marketing-materials-service/src/rate_limit.py``. Single-replica
only — move to Redis/ElastiCache when the blockchain service scales past
one active instance (or when KMS signing is live, since a single KMS key
caps effective signing throughput anyway).
"""
from __future__ import annotations

import collections
import threading
import time
from dataclasses import dataclass
from typing import Deque, Dict, Tuple

from fastapi import HTTPException

WINDOW_SECONDS = 60


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._buckets: Dict[Tuple[str, str], Deque[float]] = {}
        self._lock = threading.Lock()

    def check(
        self,
        identity: str,
        endpoint: str,
        limit: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        if now is None:
            now = time.monotonic()
        key = (identity or "_anon", endpoint)
        cutoff = now - WINDOW_SECONDS
        with self._lock:
            dq = self._buckets.setdefault(key, collections.deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            used = len(dq)
            if used >= limit:
                oldest = dq[0]
                retry_after = max(1, int(oldest + WINDOW_SECONDS - now) + 1)
                return RateLimitDecision(
                    allowed=False, limit=limit, remaining=0, retry_after=retry_after
                )
            dq.append(now)
            return RateLimitDecision(
                allowed=True, limit=limit, remaining=limit - len(dq), retry_after=0
            )

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


_limiter = SlidingWindowLimiter()


_LIMITS: Dict[str, int] = {
    "mint_nft": 10,
    "create_task": 20,
    "approve_task": 30,
    "deploy_contract": 20,
    "subscribe": 20,
    "premium_feature": 20,
}


def enforce(actor: dict, endpoint: str) -> None:
    """Raise 429 with Retry-After on breach."""
    limit = _LIMITS.get(endpoint, 30)
    identity = str(actor.get("user_id") or "anon")
    decision = _limiter.check(identity, endpoint, limit)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "limit": limit,
                "window_s": WINDOW_SECONDS,
            },
            headers={"Retry-After": str(decision.retry_after)},
        )
