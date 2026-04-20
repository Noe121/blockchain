"""HMAC event signing + verification for the blockchain service.

Canonical form MUST be byte-identical to notification-service's
``event_verification.py``:

    to_sign = {k: v for k, v in payload.items() if k not in
               {"signature", "signature_alg", "signature_issued_at"}}
    canonical = json.dumps(to_sign, sort_keys=True, separators=(",",":"),
                           default=str)
    sig = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()

Used for:
  * Inbound events: refuse to process anything whose signature is missing
    or stale (>5 min).
  * Outbound api-service calls: attach ``X-Service-Signature`` /
    ``X-Service-Issued-At`` headers so api-service can verify us symmetrically
    once rollout is coordinated.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_DEV_ENVS = frozenset({"dev", "development", "local", "test", "testing"})
_MAX_AGE_SECONDS = 300  # 5-minute replay window


def _is_dev_environment() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return env in _DEV_ENVS


class EventSignatureError(Exception):
    """Raised when an event signature is missing, expired, or invalid."""


def require_event_hmac_key(var_name: str) -> str:
    """Load an HMAC key; boot-fail outside dev if missing."""
    key = (os.getenv(var_name) or "").strip()
    if not key:
        if _is_dev_environment():
            logger.warning(
                "%s is unset — event signature verification disabled in dev.",
                var_name,
            )
            return ""
        raise RuntimeError(
            f"{var_name} is required outside dev — upstream/downstream "
            f"HMAC rollout requires this key."
        )
    return key


def _canonical(payload: dict) -> str:
    to_sign = {
        k: v
        for k, v in payload.items()
        if k not in {"signature", "signature_alg", "signature_issued_at"}
    }
    return json.dumps(to_sign, sort_keys=True, separators=(",", ":"), default=str)


def sign_payload(payload: dict, key: str) -> Dict[str, str]:
    """Return HMAC metadata for ``payload``. Caller attaches to request."""
    if not key:
        raise EventSignatureError("event_key_unset")
    canonical = _canonical(payload)
    sig = hmac.new(
        key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    issued_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "signature": sig,
        "signature_alg": "HMAC-SHA256",
        "signature_issued_at": issued_at,
    }


def sign_body_bytes(body_bytes: bytes, key: str) -> Dict[str, str]:
    """Sign an already-serialized JSON body (for outbound HTTP)."""
    if not key:
        raise EventSignatureError("event_key_unset")
    sig = hmac.new(key.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    issued_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "X-Service-Signature": sig,
        "X-Service-Issued-At": issued_at,
    }


def verify_signed_event(
    payload: dict,
    key: str,
    *,
    source: str = "unknown",
    max_age_seconds: int = _MAX_AGE_SECONDS,
) -> None:
    """Verify a signed event; raise ``EventSignatureError`` on failure."""
    if not isinstance(payload, dict):
        raise EventSignatureError("event_not_dict")
    if not key:
        raise EventSignatureError("event_key_unset")

    sig = payload.get("signature")
    alg = payload.get("signature_alg")
    issued_at = payload.get("signature_issued_at")

    if not sig:
        raise EventSignatureError("signature_missing")
    if alg and str(alg).upper() not in {"HMAC-SHA256", "SHA256"}:
        raise EventSignatureError("alg_not_allowed")

    if issued_at:
        try:
            ts_str = str(issued_at).replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > max_age_seconds or age < -30:
                raise EventSignatureError("signature_expired")
        except EventSignatureError:
            raise
        except Exception as exc:
            raise EventSignatureError("signature_issued_at_malformed") from exc

    canonical = _canonical(payload)
    expected = hmac.new(
        key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(str(sig), expected):
        raise EventSignatureError("signature_mismatch")
