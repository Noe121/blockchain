"""
SNS consumer Lambda for contract anchoring.

Listens for contract lifecycle events and anchors terms hashes on-chain
via the ContractAnchor smart contract. Stores results back on the
contract-service via the /anchor-result callback endpoint.

Event types handled:
  - contract.executed      → anchor contract terms hash
  - deliverable.proof.verified → anchor proof hash (Phase 4)
  - property.construction.draw_approved → anchor draw hash (Phase 5)

Security:
  - Private key in Secrets Manager (never in env)
  - Gas cost control with configurable threshold
  - Idempotency via DynamoDB check before anchoring
  - Service-token auth on callback
  - PII NEVER stored on-chain — only SHA-256 hashes
"""
import asyncio
import hashlib
import json
import logging
import os
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
CONTRACT_SERVICE_URL = os.environ.get(
    "CONTRACT_SERVICE_URL", "http://contract-service.dev.local:8016"
).rstrip("/")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "").strip()
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "nilbx-blockchain")
ANCHOR_ENABLED = os.environ.get("ANCHOR_ENABLED", "true").lower() == "true"


def _get_dynamodb_table():
    if boto3 is None:
        return None
    return boto3.resource("dynamodb").Table(DYNAMODB_TABLE)


def _already_anchored(terms_hash: str) -> bool:
    """Check DynamoDB for existing anchor (idempotency)."""
    try:
        table = _get_dynamodb_table()
        if table is None:
            return False
        resp = table.get_item(
            Key={"PK": f"ANCHOR#{terms_hash}", "SK": "CONTRACT"},
        )
        return "Item" in resp
    except Exception as e:
        logger.warning("DynamoDB idempotency check failed: %s", e)
        return False


def _record_anchor(terms_hash: str, result: Dict[str, Any], event_type: str) -> None:
    """Record anchor result in DynamoDB for idempotency + audit."""
    try:
        table = _get_dynamodb_table()
        if table is None:
            return
        table.put_item(
            Item={
                "PK": f"ANCHOR#{terms_hash}",
                "SK": "CONTRACT" if "contract" in event_type else "PROOF",
                "tx_hash": result.get("tx_hash", ""),
                "block_number": result.get("block_number", 0),
                "chain_id": result.get("chain_id", ""),
                "event_type": event_type,
                "anchored_at": result.get("anchored_at", ""),
            }
        )
    except Exception as e:
        logger.warning("DynamoDB record failed: %s", e)


def _callback_anchor_result(
    contract_instance_id: int, result: Dict[str, Any]
) -> None:
    """Store anchor result back on the contract-service via callback."""
    if not requests or not SERVICE_TOKEN:
        logger.warning("Cannot callback: requests or SERVICE_TOKEN missing")
        return
    try:
        resp = requests.post(
            f"{CONTRACT_SERVICE_URL}/contract-instances/{contract_instance_id}/anchor-result",
            headers={
                "Content-Type": "application/json",
                "X-Service-Token": SERVICE_TOKEN,
            },
            json={
                "chain_tx_hash": result.get("tx_hash"),
                "chain_contract_address": result.get("contract_address"),
                "chain_id": result.get("chain_id"),
                "chain_block_number": result.get("block_number"),
            },
            timeout=10,
        )
        logger.info(
            "Callback to contract-service: status=%s id=%s",
            resp.status_code, contract_instance_id,
        )
    except Exception as e:
        logger.error("Callback failed for contract %s: %s", contract_instance_id, e)


def _handle_contract_executed(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle contract.executed event — anchor terms hash on-chain."""
    contract_id = payload.get("contract_instance_id")
    terms_hash = payload.get("terms_hash")

    if not contract_id or not terms_hash:
        logger.error("Missing contract_instance_id or terms_hash in payload")
        return {"status": "error", "reason": "missing_fields"}

    # Idempotency check
    if _already_anchored(terms_hash):
        logger.info("Already anchored: %s (idempotent skip)", terms_hash)
        return {"status": "skipped", "reason": "already_anchored"}

    # Anchor on-chain — contract_id must be uint256; derive stable int from string ID
    contract_id_int = (
        contract_id if isinstance(contract_id, int)
        else int(hashlib.sha256(str(contract_id).encode()).hexdigest()[:8], 16)
    )
    from blockchain_handler import EthereumService
    eth = EthereumService()
    result = asyncio.run(
        eth.anchor_contract_hash(terms_hash, contract_id_int)
    )

    # Record in DynamoDB
    _record_anchor(terms_hash, result, "contract.executed")

    # Callback to contract-service
    _callback_anchor_result(contract_id, result)

    return {"status": "anchored", **result}


def _handle_proof_verified(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle deliverable.proof.verified — anchor proof hash on-chain."""
    deliverable_id = payload.get("deliverable_id")
    proof_data = payload.get("proof_data", {})

    if not deliverable_id or not proof_data:
        return {"status": "error", "reason": "missing_fields"}

    # Compute proof hash from metadata
    proof_str = json.dumps(proof_data, sort_keys=True)
    proof_hash = hashlib.sha256(proof_str.encode()).hexdigest()

    if _already_anchored(proof_hash):
        return {"status": "skipped", "reason": "already_anchored"}

    from blockchain_handler import EthereumService
    eth = EthereumService()
    result = asyncio.run(
        eth.anchor_proof_hash(proof_hash, deliverable_id)
    )

    _record_anchor(proof_hash, result, "deliverable.proof.verified")
    return {"status": "anchored", **result}


# ── Phase 5: Property Management Anchoring ───────────────────────────

def _handle_property_event(payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Anchor property management events on-chain.

    Supported events:
      - property.construction.draw_approved → anchor draw approval hash
      - property.lease.created → anchor lease terms hash
      - property.construction.lien_waiver_verified → anchor waiver hash

    All use ContractAnchor.anchorContract() with a computed SHA-256 hash
    of the event payload (no PII — only IDs, amounts, timestamps).
    """
    # Build a deterministic hash from the event payload
    # Strip any PII fields before hashing
    safe_payload = {
        k: v for k, v in payload.items()
        if k not in ("tenant_name", "tenant_email", "tenant_phone", "tenant_ssn",
                     "contact_name", "contact_email", "contact_phone")
    }
    payload_str = json.dumps(safe_payload, sort_keys=True, default=str)
    event_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    # Use a composite entity_id: hash of event_type + resource_id
    resource_id = (
        payload.get("milestone_id")
        or payload.get("lease_id")
        or payload.get("waiver_id")
        or payload.get("property_id")
        or 0
    )
    entity_id = int(resource_id) if isinstance(resource_id, (int, float)) else abs(hash(str(resource_id))) % (2**31)

    if _already_anchored(event_hash):
        return {"status": "skipped", "reason": "already_anchored", "event_type": event_type}

    from blockchain_handler import EthereumService
    eth = EthereumService()
    result = asyncio.run(
        eth.anchor_contract_hash(event_hash, entity_id)
    )

    _record_anchor(event_hash, result, event_type)

    logger.info(
        "Property event anchored: type=%s entity_id=%s tx=%s",
        event_type, entity_id, result.get("tx_hash"),
    )
    return {"status": "anchored", "event_type": event_type, **result}


# ── Lambda Entry Point ───────────────────────────────────────────────

# Event types routed to property anchoring
_PROPERTY_ANCHOR_EVENTS = {
    "property.construction.draw_approved",
    "property.construction.lien_waiver_verified",
    "property.lease.created",
    "property.lease.renewed",
    "property.lease.terminated",
}


def lambda_handler(event, context):
    """SNS-triggered Lambda handler for contract + property anchoring.

    Expects SNS message with JSON body containing:
      - event_type: contract.*, deliverable.*, or property.* events
      - payload: event-specific data
    """
    if not ANCHOR_ENABLED:
        logger.info("Anchoring disabled via ANCHOR_ENABLED=false")
        return {"statusCode": 200, "body": "disabled"}

    results = []

    for record in event.get("Records", []):
        try:
            sns_message = record.get("Sns", {}).get("Message", "{}")
            message = json.loads(sns_message)
            event_type = message.get("event_type", "")
            payload = message.get("payload", message)

            logger.info("Processing event: %s", event_type)

            if event_type == "contract.executed":
                result = _handle_contract_executed(payload)
            elif event_type == "deliverable.proof.verified":
                result = _handle_proof_verified(payload)
            elif event_type in _PROPERTY_ANCHOR_EVENTS:
                result = _handle_property_event(payload, event_type)
            else:
                logger.info("Ignoring event type: %s", event_type)
                result = {"status": "ignored", "event_type": event_type}

            results.append(result)

        except Exception as e:
            logger.error("Error processing record: %s", e)
            results.append({"status": "error", "error": str(e)})

    return {
        "statusCode": 200,
        "body": json.dumps({"results": results}),
    }
