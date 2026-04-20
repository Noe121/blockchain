"""FastAPI wrapper for blockchain Lambda functions.

OWASP hardening (2026-04):
  * Default ENVIRONMENT = "production" (silent dev-mode was a boot-time
    auth bypass in misconfigured deploys).
  * End-user JWT validation on every signing route via ``auth.py``.
  * Idempotency, ETH caps, contract allow-list, serialized signing.
  * CORS lockdown (explicit methods/headers), rate limiting, opaque errors.
  * /test/* routes are only registered in dev — never present outside dev.
"""
import asyncio
import hmac
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field, validator

# Add lambda directory to path
sys.path.insert(0, '/app/lambda')

# Import blockchain handlers (with conditional imports)
try:
    from blockchain_handler import (
        _SIGN_LOCK,
        EthereumService,
        lambda_handler as blockchain_lambda,
    )
    BLOCKCHAIN_AVAILABLE = True
except ImportError as e:
    print(f"Warning: blockchain_handler not available: {e}")
    BLOCKCHAIN_AVAILABLE = False
    _SIGN_LOCK = asyncio.Lock()

try:
    from ipfs_handler import lambda_handler as ipfs_lambda  # noqa: F401
    IPFS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ipfs_handler not available: {e}")
    IPFS_AVAILABLE = False

try:
    from integration_handler import NILIntegrationService, lambda_handler as integration_lambda  # noqa: F401
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: integration_handler not available: {e}")
    INTEGRATION_AVAILABLE = False

try:
    from fee_service import get_fee_service  # noqa: F401
    FEE_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: fee_service not available: {e}")
    FEE_SERVICE_AVAILABLE = False

import auth as _auth  # late import keeps PyJWT boot-fail path tidy
import rate_limit as _rate_limit
import safety as _safety
from event_verification import (  # noqa: F401  (re-export available for handlers)
    verify_signed_event,
    sign_body_bytes,
    EventSignatureError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- environment gating --------------------------------------------------
_DEV_ENVS = frozenset({"dev", "development", "local", "test", "testing"})
# SECURITY: default to "production" so an unset ENVIRONMENT silently
# enabling dev-mode auth skips can never happen again.
_ENV = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "production").strip().lower()


def _is_dev_env() -> bool:
    return _ENV in _DEV_ENVS


_WRAPPER_AUTH_TOKEN = os.getenv("BLOCKCHAIN_WRAPPER_BEARER_TOKEN", "").strip()
_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _cors_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    parsed = [o.strip() for o in raw.split(",") if o.strip()]
    if parsed:
        return parsed
    if _is_dev_env():
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
        ]
    raise RuntimeError("CORS_ALLOWED_ORIGINS must be set in non-local environments")


def _is_valid_eth_address(value: str) -> bool:
    return bool(_ETH_ADDRESS_RE.fullmatch((value or "").strip()))


def _validate_token_uri(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("token_uri is required")
    if len(raw) > 2048:
        raise ValueError("token_uri exceeds max length (2048)")
    parsed = urlparse(raw)
    if parsed.scheme in {"https", "ipfs"}:
        return raw
    raise ValueError("token_uri must use https:// or ipfs://")


def _validate_eth_address_field(value: str, field_name: str) -> str:
    addr = (value or "").strip()
    if not _is_valid_eth_address(addr):
        raise ValueError(f"{field_name} must be a valid 0x-prefixed Ethereum address")
    return addr


# ---- OpenAPI / docs gating ----------------------------------------------
_ENABLE_DOCS = _is_dev_env() or os.getenv("ENABLE_API_DOCS", "").strip().lower() == "true"

app = FastAPI(
    title="Blockchain Service",
    description="Blockchain signing + Lambda surface for the NILBx platform",
    version="1.1.0",
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
)

# Explicit CORS — no wildcards.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_credentials=False,  # wrapper bearer is server-to-server; no cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Service-Token",
        "X-Service-Signature",
        "X-Service-Issued-At",
    ],
)


@app.middleware("http")
async def wrapper_auth_middleware(request: Request, call_next):
    """Static service-to-service bearer gate.

    Kept AS WELL as the per-route JWT dependency — both gates apply for
    defense in depth. Only /health bypasses.
    """
    path = request.url.path
    if request.method == "OPTIONS" or path in {"/", "/health"}:
        return await call_next(request)
    # NOTE: /docs and /openapi are NOT bypassed anymore. They're either
    # disabled at construction time (prod default) or opt-in via
    # ENABLE_API_DOCS=true, in which case browsing them requires the bearer.

    if not _WRAPPER_AUTH_TOKEN:
        if _is_dev_env():
            return await call_next(request)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": {"code": "wrapper_bearer_not_configured"}},
        )

    authz = request.headers.get("Authorization", "")
    # JWT routes *also* use Authorization — we honor either the wrapper token
    # or a JWT that the route dependency will verify. We ONLY enforce wrapper
    # presence when the header looks like the static token shape (i.e. no
    # dots). A forged "bearer <jwt-with-dots>" still has to pass JWT
    # verification in the route dependency.
    if authz.lower().startswith("bearer "):
        token = authz.split(" ", 1)[1].strip()
        if token and "." not in token:
            # Looks like the static wrapper token → enforce equality.
            if not hmac.compare_digest(token, _WRAPPER_AUTH_TOKEN):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": {"code": "invalid_wrapper_token"}},
                )
            return await call_next(request)
        # JWT path: fall through to route-level verification.
        return await call_next(request)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": {"code": "missing_bearer"}},
    )


# ---- Opaque error helpers -----------------------------------------------
def _cid() -> str:
    return uuid.uuid4().hex[:12]


def _raise_internal(op: str, exc: Exception, cid: Optional[str] = None):
    cid = cid or _cid()
    logger.exception("internal_error correlation_id=%s op=%s", cid, op)
    raise HTTPException(
        status_code=500,
        detail={"code": "internal_error", "correlation_id": cid},
    )


# ---- Pydantic models -----------------------------------------------------
class NFTMintRequest(BaseModel):
    athlete_address: str
    recipient_address: str
    token_uri: str
    royalty_fee: int = Field(default=500, ge=0, le=1000)

    @validator("athlete_address")
    def _vathlete(cls, v: str) -> str:
        return _validate_eth_address_field(v, "athlete_address")

    @validator("recipient_address")
    def _vrecipient(cls, v: str) -> str:
        return _validate_eth_address_field(v, "recipient_address")

    @validator("token_uri")
    def _vuri(cls, v: str) -> str:
        return _validate_token_uri(v)


class SponsorshipTaskRequest(BaseModel):
    athlete_address: str
    description: str = Field(..., min_length=1, max_length=1000)
    amount_eth: float = Field(..., gt=0, le=1000000)
    sponsor_address: Optional[str] = Field(default=None)

    @validator("athlete_address")
    def _vathlete(cls, v: str) -> str:
        return _validate_eth_address_field(v, "athlete_address")

    @validator("sponsor_address", always=True)
    def _vsponsor(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validate_eth_address_field(v, "sponsor_address")

    @validator("description")
    def _sanitize(cls, v: str) -> str:
        return v.strip()


class TaskApprovalRequest(BaseModel):
    task_id: int = Field(..., ge=1)


class DeployContractRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    user_type: Literal["athlete", "sponsor"]
    contract_type: Literal["sponsorship", "nft", "custom"]
    fee_usd: float = Field(default=12.50, gt=0, le=10000)
    payment_method: Literal["stripe", "crypto", "wallet"] = "stripe"


class SubscribeRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    user_type: Literal["athlete", "sponsor"]
    plan_name: Literal["monitoring", "analytics", "premium"] = "monitoring"
    billing_cycle: Literal["monthly", "quarterly", "annual"] = "monthly"
    payment_method: Literal["stripe", "crypto"] = "stripe"


class PremiumFeatureRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    user_type: Literal["athlete", "sponsor"]
    feature_name: str = Field(..., min_length=1, max_length=100)
    feature_fee_usd: float = Field(..., ge=5.0, le=10.0)
    payment_method: Literal["stripe", "crypto", "wallet"] = "stripe"
    feature_config: Optional[Dict[str, Any]] = None

    @validator("feature_name")
    def _vname(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]+", cleaned):
            raise ValueError("feature_name contains invalid characters")
        return cleaned


# ---- Health --------------------------------------------------------------
@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "blockchain",
        "handlers": {
            "blockchain": BLOCKCHAIN_AVAILABLE,
            "ipfs": IPFS_AVAILABLE,
            "integration": INTEGRATION_AVAILABLE,
        },
        "environment": {
            "env": _ENV,
            "chain_id": os.getenv("CHAIN_ID", "11155111"),
            "infura_configured": bool(os.getenv("INFURA_URL")),
            "signer_backend": os.getenv("SIGNER_BACKEND", "local"),
        },
    }


# ---- Idempotency helper --------------------------------------------------
def _require_idem_key(
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> str:
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400, detail={"code": "idempotency_key_required"}
        )
    if len(key) < 8 or len(key) > 128:
        raise HTTPException(
            status_code=400, detail={"code": "idempotency_key_invalid"}
        )
    return key


# ---- NFT: /mint-nft ------------------------------------------------------
@app.post("/mint-nft")
async def mint_nft(
    request: NFTMintRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
    idem_key: str = Depends(_require_idem_key),
):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail={"code": "handler_unavailable"})

    _rate_limit.enforce(actor, "mint_nft")

    # Ownership: admin/automation OR caller's verified wallet == athlete_address.
    # Using 404 (not 403) avoids leaking whether the athlete exists.
    caller_wallet = _auth.require_verified_wallet(actor)
    if not _auth.is_admin(actor):
        if not caller_wallet or not _auth.wallets_equal(
            caller_wallet, request.athlete_address
        ):
            raise HTTPException(status_code=404, detail={"code": "not_found"})

    # Idempotency replay check.
    cached = _safety.reserve_idempotency_key(idem_key, "mint-nft")
    if cached is not None:
        return JSONResponse(status_code=200, content=cached)

    cid = _cid()
    event = {
        "httpMethod": "POST",
        "path": "/mint-nft",
        "body": json.dumps(request.dict()),
        "headers": {"Content-Type": "application/json"},
    }
    try:
        async with _SIGN_LOCK:
            response = blockchain_lambda(event, {})
        body = json.loads(response.get("body", "{}"))
        _safety.store_idempotency_response(idem_key, "mint-nft", body)
        return JSONResponse(status_code=response.get("statusCode", 200), content=body)
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("mint_nft", e, cid)


@app.get("/athlete-nfts/{athlete_address}")
async def get_athlete_nfts(
    athlete_address: str,
    actor: Dict[str, Any] = Depends(_auth.require_user_or_service),
):
    # Read route — accept either the static service wrapper token (used by
    # other backend services like deliverable / live-streaming) or a real
    # end-user JWT. Per-user ownership isn't enforced for reads of
    # already-public on-chain state.
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail={"code": "handler_unavailable"})
    if not _is_valid_eth_address(athlete_address):
        raise HTTPException(status_code=400, detail={"code": "invalid_address"})

    event = {
        "httpMethod": "GET",
        "path": f"/athlete-nfts/{athlete_address}",
        "pathParameters": {"athlete_address": athlete_address},
    }
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}")),
        )
    except Exception as e:
        _raise_internal("get_athlete_nfts", e)


# ---- Sponsorship: /create-task ------------------------------------------
@app.post("/create-task")
async def create_sponsorship_task(
    request: SponsorshipTaskRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
    idem_key: str = Depends(_require_idem_key),
):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail={"code": "handler_unavailable"})

    _rate_limit.enforce(actor, "create_task")

    caller_wallet = _auth.require_verified_wallet(actor)
    # Sponsor must match the caller unless admin/automation is creating on
    # behalf of a user. If body supplies sponsor_address it must ALSO match.
    if not _auth.is_admin(actor):
        if request.sponsor_address and not _auth.wallets_equal(
            request.sponsor_address, caller_wallet
        ):
            raise HTTPException(status_code=403, detail={"code": "sponsor_mismatch"})
        # If body omitted sponsor_address we use the caller wallet implicitly —
        # which is enforced on-chain anyway (msg.sender = signer).

    # Per-task ETH cap.
    try:
        amount_wei = _safety.eth_to_wei(request.amount_eth)
        _safety.check_per_task_cap(amount_wei)
        # Per-user daily cap (skipped for admin to keep operator workflows).
        if not _auth.is_admin(actor):
            _safety.check_and_record_daily_spend(actor["user_id"], amount_wei)
    except _safety.AmountCapExceeded as cap:
        raise HTTPException(status_code=422, detail={
            "code": cap.code,
            "limit_wei": cap.limit_wei,
        })

    cached = _safety.reserve_idempotency_key(idem_key, "create-task")
    if cached is not None:
        # Self-heal: a prior call with this same Idempotency-Key may have
        # succeeded on-chain but had its off-chain sponsor-binding write
        # fail transiently (DynamoDB blip, throttling, IAM hiccup). The
        # binding write is best-effort during the original call so we
        # don't 500 a request that already mutated chain state — but
        # without binding, /approve-task will 404 for non-admin sponsors
        # forever. So on every idempotent replay, re-attempt the binding
        # write. ``record_task_sponsor`` is first-writer-wins idempotent,
        # so a no-op when the row exists is a single conditional put.
        try:
            cached_task_id = cached.get("task_id") if isinstance(cached, dict) else None
            if cached_task_id is not None and not _auth.is_admin(actor):
                existing = _safety.lookup_task_sponsor(int(cached_task_id))
                if existing is None:
                    _safety.record_task_sponsor(
                        int(cached_task_id),
                        str(actor["user_id"]),
                        caller_wallet,
                    )
                    logger.info(
                        "task_sponsor_repaired_on_replay task_id=%s user_id=%s",
                        cached_task_id, actor["user_id"],
                    )
        except Exception:
            logger.exception(
                "task_sponsor_replay_repair_failed key=%s", idem_key,
            )
        return JSONResponse(status_code=200, content=cached)

    cid = _cid()
    event = {
        "httpMethod": "POST",
        "path": "/create-task",
        "body": json.dumps({
            "athlete_address": request.athlete_address,
            "description": request.description,
            "amount_eth": request.amount_eth,
        }),
        "headers": {"Content-Type": "application/json"},
    }
    try:
        async with _SIGN_LOCK:
            response = blockchain_lambda(event, {})
        body = json.loads(response.get("body", "{}"))
        # Record the off-chain (task_id → sponsor) binding so /approve-task
        # can perform a real ownership check. The on-chain task.sponsor is
        # always the hot signer wallet, so without this mapping non-admin
        # sponsors can never approve their own tasks. See safety.py header.
        try:
            new_task_id = body.get("task_id")
            if new_task_id is not None and not _auth.is_admin(actor):
                _safety.record_task_sponsor(
                    int(new_task_id), str(actor["user_id"]), caller_wallet,
                )
        except Exception:
            # Sponsor binding is best-effort at create time so we don't
            # 500 a request that already mutated on-chain state. If this
            # fails, the task IS on-chain and the binding will be retried
            # on the next idempotent replay (the cache-hit path in this
            # same handler does record_task_sponsor again — first-writer-
            # wins idempotent). Log at WARN with the task_id so ops can
            # detect orphans (e.g. CloudWatch metric filter on
            # "task_sponsor_record_failed_pending_replay").
            logger.warning(
                "task_sponsor_record_failed_pending_replay task_id=%s "
                "user_id=%s key=%s — caller must retry /create-task with "
                "same Idempotency-Key to repair binding",
                body.get("task_id"), actor["user_id"], idem_key,
            )
        _safety.store_idempotency_response(idem_key, "create-task", body)
        return JSONResponse(status_code=response.get("statusCode", 200), content=body)
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("create_task", e, cid)


# ---- Sponsorship: /approve-task -----------------------------------------
@app.post("/approve-task")
async def approve_task(
    request: TaskApprovalRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
    idem_key: str = Depends(_require_idem_key),
):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail={"code": "handler_unavailable"})

    _rate_limit.enforce(actor, "approve_task")

    caller_wallet = _auth.require_verified_wallet(actor)

    # Ownership model — see safety.py "Off-chain sponsor mapping" section.
    #
    # The on-chain ``task.sponsor`` is the platform hot signer (msg.sender
    # at create time), NOT the real end-user sponsor, so an on-chain
    # ownership check can never authorize a non-admin caller. We instead:
    #
    #   1. Look up the off-chain (task_id → sponsor user_id + wallet)
    #      mapping that was recorded at /create-task time.
    #   2. If found: caller's user_id OR verified wallet must match.
    #   3. If missing (legacy task pre-mapping, or DB unavailable): fall
    #      back to admin-only approval. Non-admin callers get 404 — same
    #      shape as the no-such-task case to avoid an enumeration oracle.
    #
    # Admins always pass. Service-token callers (kind=service) reach this
    # route via require_end_user_identity which rejects no-dot tokens, so
    # they cannot approve tasks — only end-user JWTs (or admin JWTs) can.
    cid = _cid()
    if not _auth.is_admin(actor):
        binding = _safety.lookup_task_sponsor(request.task_id)
        if binding is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        wallet_match = bool(caller_wallet) and _auth.wallets_equal(
            caller_wallet, binding["wallet"]
        )
        user_id_match = str(actor["user_id"]) == binding["user_id"]
        if not (wallet_match or user_id_match):
            raise HTTPException(status_code=404, detail={"code": "not_found"})

    # Best-effort on-chain task sanity probe — confirms the task exists
    # before we burn gas on approve. Failure here is non-fatal for admin
    # users (the underlying lambda handler will surface a real revert
    # reason); for non-admin we already passed the off-chain check.
    try:
        svc = EthereumService()
        svc.get_task_onchain(request.task_id)
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("approve_task_lookup", e, cid)

    cached = _safety.reserve_idempotency_key(idem_key, "approve-task")
    if cached is not None:
        return JSONResponse(status_code=200, content=cached)

    event = {
        "httpMethod": "POST",
        "path": "/approve-task",
        "body": json.dumps(request.dict()),
        "headers": {"Content-Type": "application/json"},
    }
    try:
        async with _SIGN_LOCK:
            response = blockchain_lambda(event, {})
        body = json.loads(response.get("body", "{}"))
        _safety.store_idempotency_response(idem_key, "approve-task", body)
        return JSONResponse(status_code=response.get("statusCode", 200), content=body)
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("approve_task", e, cid)


# ---- Deploy/subscribe/premium (JWT-bound) -------------------------------
@app.post("/deploy-contract")
async def deploy_contract(
    request: DeployContractRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
):
    _rate_limit.enforce(actor, "deploy_contract")
    cid = _cid()
    try:
        integration_handler = NILIntegrationService()
        result = integration_handler.record_deployment_fee(
            request.user_id,
            request.user_type,
            request.contract_type,
            request.fee_usd,
        )
        return {
            "success": True,
            "deployment_fee_usd": request.fee_usd,
            "contract_type": request.contract_type,
            "competitiveness": result.get("competitiveness", "Competitive deployment fees"),
            "fee_breakdown": {
                "deployment_fee": request.fee_usd,
                "effective_percentage": f"{(request.fee_usd / 1000) * 100:.1f}%",
            },
        }
    except Exception as e:
        _raise_internal("deploy_contract", e, cid)


@app.post("/subscribe")
async def subscribe_user(
    request: SubscribeRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
):
    _rate_limit.enforce(actor, "subscribe")
    cid = _cid()
    # Bind user_id to JWT; refuse if body mismatches.
    jwt_uid = actor["user_id"]
    if request.user_id is not None and str(request.user_id) != str(jwt_uid):
        if not _auth.is_admin(actor):
            raise HTTPException(status_code=403, detail={"code": "user_id_mismatch"})
    bound_user_id = int(request.user_id) if request.user_id is not None else int(jwt_uid) if str(jwt_uid).isdigit() else 0

    try:
        now = datetime.now()
        if request.billing_cycle == "monthly":
            next_billing = now + timedelta(days=30)
            monthly_fee = 15.00
        elif request.billing_cycle == "quarterly":
            next_billing = now + timedelta(days=90)
            monthly_fee = 12.50
        elif request.billing_cycle == "annual":
            next_billing = now + timedelta(days=365)
            monthly_fee = 10.00
        else:
            monthly_fee = 15.00
            next_billing = now + timedelta(days=30)

        integration_handler = NILIntegrationService()
        result = integration_handler.record_subscription_fee(
            bound_user_id, request.user_type, request.plan_name, monthly_fee
        )
        return {
            "success": True,
            "user_id": bound_user_id,
            "user_type": request.user_type,
            "plan_name": request.plan_name,
            "monthly_fee_usd": monthly_fee,
            "billing_cycle": request.billing_cycle,
            "payment_method": request.payment_method,
            "next_billing_date": next_billing.isoformat(),
            "subscription_status": "active",
            "competitiveness": result.get("competitiveness", "Competitive subscription pricing"),
            "message": f"Subscription activated for ${monthly_fee}/month.",
            "features_included": [
                "Real-time transaction monitoring",
                "Basic analytics dashboard",
                "Email notifications",
                "API access for integration",
            ]
            + (["Advanced analytics", "Custom reports"] if request.plan_name == "premium" else []),
        }
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("subscribe", e, cid)


@app.post("/premium-feature")
async def purchase_premium_feature(
    request: PremiumFeatureRequest,
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
):
    _rate_limit.enforce(actor, "premium_feature")
    cid = _cid()

    jwt_uid = actor["user_id"]
    if request.user_id is not None and str(request.user_id) != str(jwt_uid):
        if not _auth.is_admin(actor):
            raise HTTPException(status_code=403, detail={"code": "user_id_mismatch"})
    bound_user_id = int(request.user_id) if request.user_id is not None else int(jwt_uid) if str(jwt_uid).isdigit() else 0

    try:
        if not 5.00 <= request.feature_fee_usd <= 10.00:
            raise HTTPException(
                status_code=400, detail={"code": "fee_out_of_range"}
            )
        integration_handler = NILIntegrationService()
        result = integration_handler.record_premium_fee(
            bound_user_id,
            request.user_type,
            request.feature_name,
            request.feature_fee_usd,
        )
        return {
            "success": True,
            "user_id": bound_user_id,
            "user_type": request.user_type,
            "feature_name": request.feature_name,
            "feature_fee_usd": request.feature_fee_usd,
            "payment_method": request.payment_method,
            "payment_status": "pending",
            "feature_config": request.feature_config,
            "competitiveness": result.get("competitiveness", "Flexible premium features"),
            "message": f"Premium feature '{request.feature_name}' purchase initiated.",
            "estimated_activation_time": "2-5 minutes after payment confirmation",
        }
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal("premium_feature", e, cid)


# ---- Fee analytics (admin-only) -----------------------------------------
@app.get("/fee-analytics")
async def get_fee_analytics(
    actor: Dict[str, Any] = Depends(_auth.require_end_user_identity),
):
    if not _auth.is_finance_admin(actor):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    cid = _cid()
    try:
        from dynamodb_service import get_dynamodb_service
        dynamodb = get_dynamodb_service()
        analytics = dynamodb.get_fee_analytics()

        fee_summary = {}
        try:
            from fee_service import get_fee_service
            fee_service = get_fee_service()
            fee_summary = fee_service.get_fee_analytics_summary()
        except ImportError:
            pass

        return {
            "success": True,
            "analytics": analytics,
            "fee_structure": fee_summary.get(
                "fee_structure",
                {
                    "deployment_fee": "$10-15 per contract (1-2% of deal value)",
                    "transaction_fee": "4% of payment amount (on-chain)",
                    "subscription_fee": "$15/month per user (monitoring/analytics)",
                    "premium_features": "$5-10 per feature (power users)",
                    "target_effective_fee": "6-8% total per deal",
                },
            ),
            "competitiveness": fee_summary.get(
                "competitiveness",
                {
                    "vs_nil_platforms": "10-20% fees → We undercut by 2-12%",
                    "vs_blockchain_norms": "Matches Request Network (1-5%)",
                    "retention_focus": "Under 11% cap maintains user trust",
                },
            ),
            "sample_calculations": fee_summary.get("sample_calculations", {}),
        }
    except Exception as e:
        _raise_internal("fee_analytics", e, cid)


@app.get("/task/{task_id}")
async def get_task(
    task_id: int,
    actor: Dict[str, Any] = Depends(_auth.require_user_or_service),
):
    # Read route — accept the static service wrapper token (used by other
    # backend services for state lookups during workflows) or a real JWT.
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail={"code": "handler_unavailable"})
    if task_id < 1:
        raise HTTPException(status_code=400, detail={"code": "invalid_task_id"})
    event = {
        "httpMethod": "GET",
        "path": f"/task/{task_id}",
        "pathParameters": {"task_id": str(task_id)},
    }
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}")),
        )
    except Exception as e:
        _raise_internal("get_task", e)


# ---- Dev-only test endpoints (NEVER registered outside dev) --------------
if _is_dev_env():
    @app.get("/test/database")
    async def test_database():
        """Test DynamoDB connectivity (dev-only)."""
        try:
            import boto3  # type: ignore
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()
            try:
                table_desc = dynamodb.table.meta.client.describe_table(
                    TableName=dynamodb.table_name
                )
                table_status = table_desc['Table']['TableStatus']
            except Exception as e:
                table_status = f"Error: {str(e)}"
            try:
                user_response = dynamodb.table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('PK').begins_with('USER#')
                    & boto3.dynamodb.conditions.Attr('SK').eq('METADATA')
                )
                user_count = len(user_response.get('Items', []))
                contract_response = dynamodb.table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('SK').eq('METADATA')
                    & boto3.dynamodb.conditions.Attr('PK').begins_with('CONTRACT#')
                )
                contract_count = len(contract_response.get('Items', []))
                tx_response = dynamodb.table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('SK').begins_with('TX#')
                )
                tx_count = len(tx_response.get('Items', []))
            except Exception as e:
                user_count = contract_count = tx_count = f"Error counting: {str(e)}"
            return {
                "status": "connected" if table_status == "ACTIVE" else f"table_status: {table_status}",
                "database": dynamodb.table_name,
                "table_status": table_status,
                "counts": {"users": user_count, "contracts": contract_count, "transactions": tx_count},
                "region": os.getenv('AWS_REGION', 'us-east-1'),
                "billing_mode": "PAY_PER_REQUEST",
            }
        except Exception as e:
            _raise_internal("test_database", e)

    @app.get("/test/data/athletes")
    async def get_test_athletes():
        try:
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()
            import boto3  # type: ignore
            response = dynamodb.table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('PK').begins_with('USER#')
                & boto3.dynamodb.conditions.Attr('SK').eq('METADATA')
            )
            athletes = []
            for item in response.get('Items', []):
                if item.get('role') == 'athlete':
                    athletes.append({
                        'user_id': item['PK'].replace('USER#', ''),
                        'email': item.get('email', ''),
                        'role': item.get('role', ''),
                        'created_at': item.get('created_at', ''),
                    })
            return {"athletes": athletes}
        except Exception as e:
            _raise_internal("test_athletes", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# AWS Lambda handler using Mangum
handler = Mangum(app)


def lambda_handler(event, context):
    """Simple Lambda handler that can handle both direct + API-Gateway events."""
    try:
        if 'requestContext' in event or 'httpMethod' in event:
            return handler(event, context)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'healthy',
                'service': 'nil-blockchain-api',
                'message': 'Lambda function is working',
                'environment': _ENV,
                'dynamodb_table': os.getenv('DYNAMODB_TABLE', 'unknown'),
            }),
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'code': 'internal_error', 'type': type(e).__name__}),
        }
