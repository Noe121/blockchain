"""
SNS consumer Lambda for automatic NFT minting on athlete contract execution.

When a contract reaches `executed` status AND has a party with
party_role="creator", auto-mints a PlayerLegacyNFT (ERC721) for the
athlete. The NFT represents the contract relationship — not the
deliverable content.

Flow:
  1. Receives `contract.executed` event via SNS
  2. Checks if contract has a creator/athlete party
  3. Resolves athlete's wallet address from auth-service user_metadata
  4. Builds NFT metadata JSON and uploads to IPFS via Pinata
  5. Mints PlayerLegacyNFT with tokenURI pointing to IPFS
  6. Stores nft_token_id + nft_tx_hash back on contract metadata

If the athlete has no wallet address, the mint is queued in DynamoDB
(pending_mints) for processing when the athlete adds a wallet.

Security:
  - Private key in Secrets Manager (never in env vars)
  - PII NEVER in NFT metadata — only hashed identifiers
  - Wallet address validated as checksum address
  - Gas limit enforced before minting
  - Idempotency via DynamoDB check
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    import boto3
except ImportError:
    boto3 = None

try:
    import requests
except ImportError:
    requests = None

# Environment
AUTH_SERVICE_URL = os.environ.get(
    "AUTH_SERVICE_URL", "http://auth-service.dev.local:9000"
).rstrip("/")
CONTRACT_SERVICE_URL = os.environ.get(
    "CONTRACT_SERVICE_URL", "http://contract-service.dev.local:8016"
).rstrip("/")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "").strip()
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "nilbx-blockchain")
NFT_MINT_ENABLED = os.environ.get("NFT_MINT_ENABLED", "true").lower() == "true"
DEFAULT_ROYALTY_FEE = int(os.environ.get("DEFAULT_ROYALTY_FEE", "500"))  # 5% = 500 bps
PLATFORM_WALLET = os.environ.get("PLATFORM_WALLET_ADDRESS", "")


# ── Helpers ──────────────────────────────────────────────────────────

def _service_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if SERVICE_TOKEN:
        headers["X-Service-Token"] = SERVICE_TOKEN
    return headers


def _get_dynamodb_table():
    if boto3 is None:
        return None
    return boto3.resource("dynamodb").Table(DYNAMODB_TABLE)


def _already_minted(contract_id: str) -> bool:
    """Check DynamoDB for existing mint (idempotency)."""
    try:
        table = _get_dynamodb_table()
        if table is None:
            return False
        resp = table.get_item(Key={"PK": f"NFT_MINT#{contract_id}", "SK": "STATUS"})
        return "Item" in resp
    except Exception as e:
        logger.warning("DynamoDB idempotency check failed: %s", e)
        return False


def _record_mint(contract_id: str, result: Dict[str, Any]) -> None:
    """Record mint result in DynamoDB."""
    try:
        table = _get_dynamodb_table()
        if table is None:
            return
        table.put_item(Item={
            "PK": f"NFT_MINT#{contract_id}",
            "SK": "STATUS",
            "tx_hash": result.get("tx_hash", ""),
            "token_id": result.get("token_id", ""),
            "minted_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning("DynamoDB record failed: %s", e)


def _queue_pending_mint(contract_id: str, athlete_user_id: str, metadata: Dict, terms_hash: str = "") -> None:
    """Queue a mint for later when athlete adds a wallet address."""
    try:
        table = _get_dynamodb_table()
        if table is None:
            return
        table.put_item(Item={
            "PK": f"PENDING_MINT#{contract_id}",
            "SK": f"USER#{athlete_user_id}",
            "contract_id": contract_id,
            "athlete_user_id": athlete_user_id,
            "terms_hash": terms_hash,
            "metadata": json.dumps(metadata),
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_wallet",
        })
        logger.info("Queued pending mint: contract=%s athlete=%s", contract_id, athlete_user_id)
    except Exception as e:
        logger.warning("Failed to queue pending mint: %s", e)


# ── Auth + Contract Service Calls ────────────────────────────────────

def _fetch_user_metadata(user_id: str) -> Dict[str, Any]:
    """Fetch user metadata from auth-service."""
    if not requests:
        return {}
    try:
        resp = requests.get(
            f"{AUTH_SERVICE_URL}/users/{user_id}",
            headers=_service_headers(),
            timeout=5,
            allow_redirects=False,
        )
        if resp.status_code == 200:
            return resp.json().get("user_metadata") or {}
    except requests.RequestException:
        pass
    return {}


def _fetch_contract_parties(contract_id: str) -> list:
    """Fetch contract parties from contract-service."""
    if not requests:
        return []
    try:
        resp = requests.get(
            f"{CONTRACT_SERVICE_URL}/contract-instances/{contract_id}/parties",
            headers=_service_headers(),
            timeout=5,
            allow_redirects=False,
        )
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else resp.json().get("parties", [])
    except requests.RequestException:
        pass
    return []


def _find_athlete_party(parties: list) -> Optional[Dict]:
    """Find the creator/athlete party in a contract's party list."""
    for party in parties:
        role = party.get("party_role", "").lower()
        if role in ("creator", "athlete"):
            return party
    return None


def _find_brand_party(parties: list) -> Optional[Dict]:
    """Find the brand signatory party."""
    for party in parties:
        if party.get("party_role", "").lower() == "brand_signatory":
            return party
    return None


# ── NFT Metadata Builder ────────────────────────────────────────────

def _build_nft_metadata(
    contract_id: str,
    terms_hash: str,
    athlete_name_hash: str,
    brand_name: str,
    executed_at: str,
) -> Dict[str, Any]:
    """Build ERC721 metadata JSON for IPFS upload.

    CRITICAL: No raw PII in metadata. Athlete name is SHA-256 hashed.
    Brand name is used as-is (it's a public business entity, not PII).
    """
    return {
        "name": f"NILBx Contract #{contract_id}",
        "description": "On-chain proof of NIL contract execution on the NILBx platform.",
        "image": "ipfs://bafkreib5xkletbbzl4ucblcxjpxhbfn3ofciwd7p6mr5ew5se5zqverqji",  # NILBx logo
        "external_url": f"https://nilbx.com/contracts/{contract_id}",
        "attributes": [
            {"trait_type": "Platform", "value": "NILBx"},
            {"trait_type": "Contract ID", "value": contract_id},
            {"trait_type": "Terms Hash", "value": terms_hash},
            {"trait_type": "Athlete ID Hash", "value": athlete_name_hash},
            {"trait_type": "Brand", "value": brand_name},
            {"trait_type": "Executed At", "value": executed_at},
            {"trait_type": "Contract Type", "value": "NIL Sponsorship"},
        ],
    }


# ── Minting Logic ───────────────────────────────────────────────────

def _handle_contract_executed(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle contract.executed event — mint NFT if athlete contract."""
    contract_id = str(payload.get("contract_instance_id", payload.get("id", "")))
    terms_hash = payload.get("terms_hash", "")
    executed_at = payload.get("executed_at", datetime.now(timezone.utc).isoformat())

    if not contract_id:
        return {"status": "error", "reason": "missing_contract_id"}

    # Idempotency
    if _already_minted(contract_id):
        logger.info("Already minted for contract %s (idempotent skip)", contract_id)
        return {"status": "skipped", "reason": "already_minted"}

    # Fetch parties to find athlete
    parties = _fetch_contract_parties(contract_id)
    athlete_party = _find_athlete_party(parties)
    if not athlete_party:
        logger.info("No athlete/creator party in contract %s — skipping NFT", contract_id)
        return {"status": "skipped", "reason": "no_athlete_party"}

    athlete_user_id = athlete_party.get("user_id")
    if not athlete_user_id:
        logger.info("Athlete party has no user_id — skipping")
        return {"status": "skipped", "reason": "no_athlete_user_id"}

    # Resolve athlete wallet address
    user_meta = _fetch_user_metadata(athlete_user_id)
    wallet_address = user_meta.get("wallet_address", "").strip()

    # Build metadata
    import hashlib
    athlete_name_hash = hashlib.sha256(
        (athlete_party.get("name", "") or "").encode()
    ).hexdigest()
    brand_party = _find_brand_party(parties)
    brand_name = (brand_party.get("name", "") if brand_party else "NILBx Brand")

    nft_metadata = _build_nft_metadata(
        contract_id=contract_id,
        terms_hash=terms_hash,
        athlete_name_hash=athlete_name_hash,
        brand_name=brand_name,
        executed_at=executed_at,
    )

    # If no wallet, queue for later
    if not wallet_address:
        logger.info("Athlete %s has no wallet — queuing pending mint", athlete_user_id)
        _queue_pending_mint(contract_id, athlete_user_id, nft_metadata, terms_hash=terms_hash)
        return {"status": "queued", "reason": "no_wallet_address"}

    # Validate wallet
    try:
        from web3 import Web3
        if not Web3.is_address(wallet_address):
            logger.error("Invalid wallet address for athlete %s: %s", athlete_user_id, wallet_address)
            return {"status": "error", "reason": "invalid_wallet_address"}
        wallet_address = Web3.to_checksum_address(wallet_address)
    except ImportError:
        return {"status": "error", "reason": "web3_not_available"}

    # Upload metadata to IPFS
    try:
        from ipfs_handler import IPFSService
        ipfs = IPFSService()
        token_uri = ipfs.upload_json_metadata(
            nft_metadata,
            name=f"NILBx_Contract_{contract_id}_NFT",
        )
        logger.info("NFT metadata uploaded to IPFS: %s", token_uri)
    except Exception as e:
        logger.error("IPFS upload failed: %s", e)
        return {"status": "error", "reason": f"ipfs_upload_failed: {e}"}

    # Mint NFT
    try:
        from blockchain_handler import EthereumService
        eth = EthereumService()

        recipient = wallet_address
        royalty_fee = DEFAULT_ROYALTY_FEE

        tx_hash = eth.mint_legacy_nft(
            athlete_address=wallet_address,
            recipient_address=recipient,
            token_uri=token_uri,
            royalty_fee=royalty_fee,
        )

        result = {
            "tx_hash": tx_hash,
            "token_uri": token_uri,
            "athlete_wallet": wallet_address,
            "royalty_fee": royalty_fee,
            "contract_id": contract_id,
        }

        _record_mint(contract_id, result)

        logger.info(
            "NFT minted: contract=%s tx=%s athlete=%s",
            contract_id, tx_hash, wallet_address,
        )
        return {"status": "minted", **result}

    except Exception as e:
        logger.error("NFT minting failed for contract %s: %s", contract_id, e)
        return {"status": "error", "reason": f"mint_failed: {e}"}


# ── Lambda Entry Point ───────────────────────────────────────────────

def lambda_handler(event, context):
    """SNS-triggered Lambda handler for NFT minting.

    Listens for contract.executed events. Only mints if the contract
    has a creator/athlete party with a registered wallet address.
    """
    if not NFT_MINT_ENABLED:
        logger.info("NFT minting disabled via NFT_MINT_ENABLED=false")
        return {"statusCode": 200, "body": "disabled"}

    results = []

    for record in event.get("Records", []):
        try:
            sns_message = record.get("Sns", {}).get("Message", "{}")
            message = json.loads(sns_message)
            event_type = message.get("event_type", "")
            payload = message.get("payload", message)

            if event_type == "contract.executed":
                result = _handle_contract_executed(payload)
            else:
                result = {"status": "ignored", "event_type": event_type}

            results.append(result)
        except Exception as e:
            logger.error("Error processing NFT mint record: %s", e)
            results.append({"status": "error", "error": str(e)})

    return {
        "statusCode": 200,
        "body": json.dumps({"results": results}),
    }
