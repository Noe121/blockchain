"""On-chain safety primitives for the blockchain service.

Implements (all OWASP P0):
  1. Trusted-contract allow-list (per chain_id).
  2. Per-task + per-user-daily ETH spend caps.
  3. Idempotency-Key header dedupe (DynamoDB conditional put).

These are intentionally side-effecting at module load so missing/invalid
env configuration boot-fails the Lambda cold start rather than silently
accepting untrusted inputs at runtime.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_DEV_ENVS = frozenset({"dev", "development", "local", "test", "testing"})


def _is_dev() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return env in _DEV_ENVS


# -------------------------------------------------------------------------
# Trusted-contract allow-list
# -------------------------------------------------------------------------
_TRUSTED_CONTRACTS: Dict[int, Set[str]] = {}


def _load_trusted_contracts() -> Dict[int, Set[str]]:
    raw = (os.getenv("TRUSTED_CONTRACTS") or "").strip()
    if not raw:
        if _is_dev():
            logger.warning(
                "TRUSTED_CONTRACTS is empty — allow-list disabled in dev. "
                "Set TRUSTED_CONTRACTS JSON outside dev."
            )
            return {}
        # Fail closed outside dev.
        raise RuntimeError(
            "TRUSTED_CONTRACTS env var is required outside dev — provide a "
            'JSON like {"11155111": ["0x..."], "1": ["0x..."]}'
        )
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"TRUSTED_CONTRACTS is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("TRUSTED_CONTRACTS must be a JSON object")
    result: Dict[int, Set[str]] = {}
    for chain_id_raw, addresses in parsed.items():
        try:
            chain_id = int(chain_id_raw)
        except Exception as exc:
            raise RuntimeError(
                f"TRUSTED_CONTRACTS key {chain_id_raw!r} must be int-castable"
            ) from exc
        if not isinstance(addresses, list):
            raise RuntimeError(
                f"TRUSTED_CONTRACTS[{chain_id}] must be a list of addresses"
            )
        # Normalize to lower-hex for comparison; checksum validation happens
        # at EthereumService init.
        result[chain_id] = {str(a).strip().lower() for a in addresses if a}
    return result


_TRUSTED_CONTRACTS = _load_trusted_contracts()


def trusted_addresses_for(chain_id: int) -> Set[str]:
    return _TRUSTED_CONTRACTS.get(int(chain_id), set())


def assert_contract_trusted(chain_id: int, address: str, name: str) -> None:
    """Raise RuntimeError if ``address`` isn't in the allow-list for chain."""
    trusted = trusted_addresses_for(chain_id)
    addr_lower = (address or "").strip().lower()
    if not trusted:
        # Dev-mode warning already emitted at load; do not reject.
        if _is_dev():
            return
        raise RuntimeError(
            f"No TRUSTED_CONTRACTS entry for chain_id={chain_id}; refusing to "
            f"load {name}."
        )
    if addr_lower not in trusted:
        raise RuntimeError(
            f"{name}={address} is not in TRUSTED_CONTRACTS[{chain_id}]; "
            f"refusing to initialize."
        )


# -------------------------------------------------------------------------
# ETH amount caps
# -------------------------------------------------------------------------
def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception as exc:
        raise RuntimeError(f"{name} must be int-castable (got {raw!r})") from exc


MAX_ETH_PER_TASK_WEI = _env_int("MAX_ETH_PER_TASK_WEI", 5 * 10**18)
MAX_DAILY_ETH_PER_USER_WEI = _env_int(
    "MAX_DAILY_ETH_PER_USER_WEI", 20 * 10**18
)


class AmountCapExceeded(Exception):
    def __init__(self, code: str, limit_wei: int, attempted_wei: int):
        super().__init__(code)
        self.code = code
        self.limit_wei = limit_wei
        self.attempted_wei = attempted_wei


def check_per_task_cap(amount_wei: int) -> None:
    if amount_wei > MAX_ETH_PER_TASK_WEI:
        raise AmountCapExceeded(
            "amount_above_per_task_cap", MAX_ETH_PER_TASK_WEI, amount_wei
        )


# -------------------------------------------------------------------------
# DynamoDB-backed daily spend tracker + idempotency
# -------------------------------------------------------------------------
_IDEMP_TTL_SECONDS = 24 * 60 * 60


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _dynamo_table():
    """Return the shared nilbx blockchain DynamoDB table or None in dev."""
    try:
        from dynamodb_service import get_dynamodb_service  # type: ignore

        return get_dynamodb_service().table
    except Exception as exc:
        logger.warning("DynamoDB unavailable for safety ops: %s", exc)
        return None


def check_and_record_daily_spend(user_id: str, amount_wei: int) -> None:
    """Atomically add ``amount_wei`` to today's user bucket; refuse if cap hit.

    PK = ``USER_DAILY_SPEND#<user_id>#<YYYY-MM-DD>``
    SK = ``METADATA``
    Uses ``UpdateItem ADD`` + a conditional expression guard.
    """
    table = _dynamo_table()
    if table is None:
        # Dev fallback: skip persistence but still apply per-task cap.
        return
    pk = f"USER_DAILY_SPEND#{user_id}#{_today_key()}"
    sk = "METADATA"
    try:
        # First read the current bucket to evaluate cap BEFORE writing.
        existing = table.get_item(Key={"PK": pk, "SK": sk}).get("Item") or {}
        current = int(existing.get("amount_wei", 0))
        if current + amount_wei > MAX_DAILY_ETH_PER_USER_WEI:
            raise AmountCapExceeded(
                "amount_above_daily_cap",
                MAX_DAILY_ETH_PER_USER_WEI,
                current + amount_wei,
            )
        # Atomic increment.
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="ADD amount_wei :amt SET updated_at = :ts, user_id = :uid, day_key = :day",
            ExpressionAttributeValues={
                ":amt": amount_wei,
                ":ts": int(time.time()),
                ":uid": str(user_id),
                ":day": _today_key(),
            },
        )
    except AmountCapExceeded:
        raise
    except Exception as exc:
        logger.exception("daily_spend_update_failed user_id=%s: %s", user_id, exc)
        # Fail closed on infra errors outside dev.
        if not _is_dev():
            raise


class IdempotencyConflict(Exception):
    """A prior request body with the same Idempotency-Key exists."""

    def __init__(self, cached_response: Dict[str, Any]):
        super().__init__("idempotent_replay")
        self.cached_response = cached_response


def reserve_idempotency_key(key: str, route: str) -> Optional[Dict[str, Any]]:
    """Attempt to reserve an idempotency slot.

    Returns:
        None if the slot was freshly reserved and the caller must now do the
        work and then call ``store_idempotency_response``.
        A cached dict response if the slot already exists (caller returns it).
    """
    if not key:
        raise ValueError("idempotency key must be non-empty")
    table = _dynamo_table()
    if table is None:
        return None  # Dev fallback: no dedupe.
    pk = f"IDEMP#{key}"
    sk = f"ROUTE#{route}"
    ttl = int(time.time()) + _IDEMP_TTL_SECONDS
    try:
        table.put_item(
            Item={
                "PK": pk,
                "SK": sk,
                "created_at": int(time.time()),
                "ttl": ttl,
                "status": "in_flight",
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
        return None  # Freshly reserved.
    except Exception as exc:
        # ConditionalCheckFailed → slot exists; fetch cached response.
        msg = str(exc)
        if "ConditionalCheckFailed" not in msg and "ConditionalCheckFailedException" not in msg:
            logger.exception("idempotency_put_failed key=%s: %s", key, exc)
            if not _is_dev():
                raise
            return None
        existing = table.get_item(Key={"PK": pk, "SK": sk}).get("Item") or {}
        cached = existing.get("response")
        if isinstance(cached, str):
            try:
                cached = json.loads(cached)
            except Exception:
                cached = None
        if isinstance(cached, dict):
            return cached
        # In-flight or malformed — treat as replay with opaque code.
        return {"code": "idempotent_in_flight"}


def store_idempotency_response(
    key: str, route: str, response: Dict[str, Any]
) -> None:
    """Persist the completed response for future replay."""
    if not key:
        return
    table = _dynamo_table()
    if table is None:
        return
    pk = f"IDEMP#{key}"
    sk = f"ROUTE#{route}"
    ttl = int(time.time()) + _IDEMP_TTL_SECONDS
    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET #r = :r, #s = :s, #t = :t",
            ExpressionAttributeNames={"#r": "response", "#s": "status", "#t": "ttl"},
            ExpressionAttributeValues={
                ":r": json.dumps(response, default=str),
                ":s": "completed",
                ":t": ttl,
            },
        )
    except Exception as exc:
        logger.exception("idempotency_store_failed key=%s: %s", key, exc)


# -------------------------------------------------------------------------
# Off-chain sponsor mapping (workaround for SponsorshipContract design)
# -------------------------------------------------------------------------
# The on-chain SponsorshipContract records ``task.sponsor = msg.sender``.
# But ``msg.sender`` is ALWAYS the platform's hot signer wallet — the
# real end-user sponsor is invisible on-chain. So an ownership check on
# /approve-task that compares caller_wallet to ``getTask(id).sponsor``
# always fails for non-admin users.
#
# Until the contract is redeployed with an explicit sponsor parameter,
# we mirror the (task_id → sponsor user_id + wallet) mapping in DynamoDB
# at create-task time and consult it at approve-task time.
#
# PK = ``TASK_SPONSOR#<task_id>``  SK = ``METADATA``
# Item: { user_id, wallet, created_at }
# No TTL — we want this for the lifetime of the contract task.


def record_task_sponsor(task_id: int, user_id: str, wallet: str) -> None:
    """Persist the off-chain (task → sponsor) binding at create-task time.

    Idempotent via ``attribute_not_exists`` — first writer wins. A retry
    of the same /create-task request (same Idempotency-Key) re-derives
    the same task_id from the cached response and tries to record the
    same binding; the conditional put silently no-ops.
    """
    table = _dynamo_table()
    if table is None:
        return  # dev fallback
    if task_id is None or int(task_id) < 1:
        return
    pk = f"TASK_SPONSOR#{int(task_id)}"
    try:
        table.put_item(
            Item={
                "PK": pk,
                "SK": "METADATA",
                "user_id": str(user_id),
                "wallet": (wallet or "").lower(),
                "created_at": int(time.time()),
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
    except Exception as exc:
        msg = str(exc)
        if "ConditionalCheckFailed" in msg or "ConditionalCheckFailedException" in msg:
            # First-writer-wins; the existing record is authoritative.
            return
        logger.exception(
            "task_sponsor_record_failed task_id=%s user_id=%s: %s",
            task_id, user_id, exc,
        )
        if not _is_dev():
            raise


def lookup_task_sponsor(task_id: int) -> Optional[Dict[str, Any]]:
    """Return ``{user_id, wallet, created_at}`` for the off-chain sponsor
    binding, or ``None`` when there's no record (legacy task created
    before this mapping existed, or DB unavailable in dev)."""
    table = _dynamo_table()
    if table is None:
        return None
    if task_id is None or int(task_id) < 1:
        return None
    pk = f"TASK_SPONSOR#{int(task_id)}"
    try:
        item = table.get_item(Key={"PK": pk, "SK": "METADATA"}).get("Item")
        if not item:
            return None
        return {
            "user_id": str(item.get("user_id") or ""),
            "wallet": str(item.get("wallet") or "").lower(),
            "created_at": int(item.get("created_at") or 0),
        }
    except Exception as exc:
        logger.exception("task_sponsor_lookup_failed task_id=%s: %s", task_id, exc)
        return None


def extract_idempotency_key(headers: Dict[str, Any]) -> str:
    """Pull ``Idempotency-Key`` out of a header dict (case-insensitive)."""
    if not headers:
        return ""
    for k, v in headers.items():
        if str(k).lower() == "idempotency-key":
            return str(v or "").strip()
    return ""


# -------------------------------------------------------------------------
# Wei conversion helper (avoids re-importing web3 in callers)
# -------------------------------------------------------------------------
def eth_to_wei(amount_eth: float) -> int:
    # 1 ETH = 1e18 wei; guard against float precision drift.
    from decimal import Decimal, localcontext

    with localcontext() as ctx:
        ctx.prec = 40
        return int((Decimal(str(amount_eth)) * Decimal(10) ** 18).to_integral_value())
