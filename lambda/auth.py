"""End-user JWT validation for the blockchain service.

OWASP A01/A07: every signing endpoint must validate the caller's JWT and
bind the transaction to the caller's verified ``ethereum_address`` claim.
Static service-to-service bearer tokens (``BLOCKCHAIN_WRAPPER_BEARER_TOKEN``)
are kept as an ADDITIONAL gate — both must pass (defense in depth).

Upstream contract (auth-service):
    The signed JWT must contain:
      - ``sub`` or ``user_id`` (string/int)
      - ``role`` (string)
      - ``exp`` (required)
      - ``ethereum_address`` (0x-prefixed checksum or hex, OPTIONAL — but
        required for non-admin callers of any on-chain signing route).
    Callers without ``ethereum_address`` receive 403 ``wallet_not_verified``.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

try:
    import jwt as _pyjwt
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError(
        "PyJWT is required; add PyJWT>=2.8.0 to requirements.txt"
    ) from exc

logger = logging.getLogger(__name__)

_DEV_ENVS = frozenset({"dev", "development", "local", "test", "testing"})
_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_ADMIN_ROLES = frozenset(
    {
        "admin",
        "platform_admin",
        "automation",
        "platform_system_admin",
        "nilbx_admin",
    }
)
_FINANCE_ADMIN_ROLES = frozenset(
    {"admin", "platform_admin", "finance_admin", "nilbx_admin"}
)


def _is_dev_environment() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return env in _DEV_ENVS


_AUTH_SECRET_KEY = (os.getenv("AUTH_SECRET_KEY") or "").strip()
_MIN_KEY_LEN = 32

if not _AUTH_SECRET_KEY and not _is_dev_environment():
    raise RuntimeError("AUTH_SECRET_KEY is required outside dev environments.")
if (
    _AUTH_SECRET_KEY
    and len(_AUTH_SECRET_KEY) < _MIN_KEY_LEN
    and not _is_dev_environment()
):
    raise RuntimeError(
        f"AUTH_SECRET_KEY must be >= {_MIN_KEY_LEN} chars outside dev."
    )


def require_end_user_identity(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI dependency: parse + verify HS256 Bearer token.

    Returns ``{user_id, role, roles, ethereum_address}``.
    Raises 401 with an opaque ``code`` on every failure mode.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_bearer"})
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail={"code": "missing_bearer"})
    if not _AUTH_SECRET_KEY:
        raise HTTPException(status_code=401, detail={"code": "auth_not_configured"})
    try:
        header = _pyjwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "malformed_token"})
    if (header or {}).get("alg") != "HS256":
        raise HTTPException(status_code=401, detail={"code": "alg_not_allowed"})
    try:
        claims = _pyjwt.decode(
            token,
            _AUTH_SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp"]},
        )
    except _pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired"})
    except _pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    user_id = claims.get("user_id") or claims.get("sub") or claims.get("id")
    role = str(claims.get("role") or "")
    roles = claims.get("roles") or []
    eth_address = (claims.get("ethereum_address") or "").strip()
    if eth_address and not _ETH_ADDRESS_RE.fullmatch(eth_address):
        # Malformed address in claim → treat as missing (opaque).
        eth_address = ""

    if not user_id:
        raise HTTPException(
            status_code=401, detail={"code": "token_missing_subject"}
        )

    return {
        "user_id": str(user_id),
        "role": role,
        "roles": [str(r) for r in roles] if isinstance(roles, (list, tuple)) else [],
        "ethereum_address": eth_address or None,
    }


def require_user_or_service(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI dependency for READ routes that accept either:

      * a service-to-service static wrapper bearer (no dots in the token,
        already validated by ``wrapper_auth_middleware`` in main.py), OR
      * a real end-user JWT (has dots, validated here via the same path
        as ``require_end_user_identity``).

    Use this on read-only routes (``/task/{id}``, ``/athlete-nfts/{addr}``,
    etc.) to keep wrapper-token callers (other backend services) working
    without forcing them to mint and pass a user JWT they don't have.

    Use ``require_end_user_identity`` (this module) on WRITE routes — those
    must be bound to a real end-user identity for ownership checks.

    Returns one of:
        ``{kind: "service", user_id: None, role: "service", roles: [],
            ethereum_address: None}``  for wrapper-token callers.
        ``{kind: "user", user_id, role, roles, ethereum_address}``  for JWT.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_bearer"})
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail={"code": "missing_bearer"})

    # Static wrapper tokens are opaque random strings (no dots). JWTs have
    # at least two dots ("header.payload.sig"). The wrapper-bearer
    # middleware already verified the wrapper token's exact value before
    # this dep runs, so a no-dot token reaching this point is trusted as
    # a service caller.
    if "." not in token:
        return {
            "kind": "service",
            "user_id": None,
            "role": "service",
            "roles": [],
            "ethereum_address": None,
        }

    # JWT path — reuse the same validation as require_end_user_identity.
    actor = require_end_user_identity(authorization=authorization)
    actor["kind"] = "user"
    return actor


def is_service_caller(actor: Dict[str, Any]) -> bool:
    """True iff actor came from the static wrapper bearer (not a JWT)."""
    return (actor or {}).get("kind") == "service"


def is_admin(actor: Dict[str, Any]) -> bool:
    if actor.get("role") in _ADMIN_ROLES:
        return True
    return any(r in _ADMIN_ROLES for r in (actor.get("roles") or []))


def is_finance_admin(actor: Dict[str, Any]) -> bool:
    if actor.get("role") in _FINANCE_ADMIN_ROLES:
        return True
    return any(r in _FINANCE_ADMIN_ROLES for r in (actor.get("roles") or []))


def require_verified_wallet(actor: Dict[str, Any]) -> str:
    """Return the caller's verified wallet or raise 403 ``wallet_not_verified``.

    Admin/automation callers may operate without a bound wallet (they use the
    platform signing key directly), but any other role must have a JWT claim
    asserting their Ethereum address — signed by auth-service upstream.
    """
    addr = actor.get("ethereum_address")
    if addr:
        return addr
    if is_admin(actor):
        # Admin doesn't need a bound wallet — returns empty sentinel.
        return ""
    raise HTTPException(
        status_code=403, detail={"code": "wallet_not_verified"}
    )


def wallets_equal(a: str, b: str) -> bool:
    """Case-insensitive Ethereum address compare."""
    return (a or "").strip().lower() == (b or "").strip().lower()
