"""
Scheduled processor for pending NFT mints.

Runs periodically (via CloudWatch Events / EventBridge) to check if
athletes who had no wallet at contract execution time have since added
one. If so, processes the queued mint.

Can also be triggered by a `user.wallet_added` event from auth-service
for real-time processing.

DynamoDB schema for pending mints:
  PK: PENDING_MINT#{contract_id}
  SK: USER#{athlete_user_id}
  status: pending_wallet | processing | minted | failed
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    import boto3
    from boto3.dynamodb.conditions import Key, Attr
except ImportError:
    boto3 = None

try:
    import requests
except ImportError:
    requests = None

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service.dev.local:9000").rstrip("/")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "").strip()
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "nilbx-blockchain")
MAX_BATCH_SIZE = int(os.environ.get("PENDING_MINT_BATCH_SIZE", "10"))


def _service_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if SERVICE_TOKEN:
        headers["X-Service-Token"] = SERVICE_TOKEN
    return headers


def _get_pending_mints() -> List[Dict]:
    """Fetch all pending mints from DynamoDB."""
    if boto3 is None:
        return []
    try:
        table = boto3.resource("dynamodb").Table(DYNAMODB_TABLE)
        # Scan for PENDING_MINT items with status=pending_wallet
        # In production, use a GSI on status for efficiency
        resp = table.scan(
            FilterExpression=Attr("PK").begins_with("PENDING_MINT#") & Attr("status").eq("pending_wallet"),
            Limit=MAX_BATCH_SIZE,
        )
        return resp.get("Items", [])
    except Exception as e:
        logger.error("Failed to fetch pending mints: %s", e)
        return []


def _check_wallet(user_id: str) -> str:
    """Check if user has added a wallet address."""
    if not requests:
        return ""
    try:
        resp = requests.get(
            f"{AUTH_SERVICE_URL}/users/{user_id}",
            headers=_service_headers(),
            timeout=5,
            allow_redirects=False,
        )
        if resp.status_code == 200:
            meta = resp.json().get("user_metadata") or {}
            return meta.get("wallet_address", "").strip()
    except requests.RequestException:
        pass
    return ""


def _process_pending_mint(item: Dict) -> Dict[str, Any]:
    """Process a single pending mint if wallet is now available."""
    contract_id = item.get("contract_id", "")
    athlete_user_id = item.get("athlete_user_id", "")

    wallet = _check_wallet(athlete_user_id)
    if not wallet:
        return {"status": "still_pending", "contract_id": contract_id}

    # Wallet found — trigger the mint
    try:
        from nft_handler import _handle_contract_executed

        result = _handle_contract_executed({
            "contract_instance_id": contract_id,
            "terms_hash": item.get("terms_hash", ""),
            "executed_at": item.get("queued_at", ""),
        })

        # Update DynamoDB status
        if boto3 and result.get("status") == "minted":
            table = boto3.resource("dynamodb").Table(DYNAMODB_TABLE)
            table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #s = :s, minted_at = :t, tx_hash = :tx",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "minted",
                    ":t": datetime.now(timezone.utc).isoformat(),
                    ":tx": result.get("tx_hash", ""),
                },
            )

        return {"status": "processed", "contract_id": contract_id, "result": result}
    except Exception as e:
        logger.error("Failed to process pending mint %s: %s", contract_id, e)
        return {"status": "error", "contract_id": contract_id, "error": str(e)}


def lambda_handler(event, context):
    """Scheduled handler to process pending NFT mints.

    Can be triggered by:
      - CloudWatch Events (every 15 minutes)
      - user.wallet_added event (real-time)
    """
    # Check if this is a targeted event (user added wallet)
    if event.get("event_type") == "user.wallet_added":
        user_id = event.get("user_id", "")
        logger.info("Processing wallet-added event for user %s", user_id)
        # Could filter pending mints by this user_id for efficiency

    pending = _get_pending_mints()
    logger.info("Found %d pending mints to process", len(pending))

    results = []
    for item in pending:
        result = _process_pending_mint(item)
        results.append(result)

    minted = sum(1 for r in results if r.get("status") == "processed")
    logger.info("Processed %d/%d pending mints", minted, len(pending))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "total_pending": len(pending),
            "processed": minted,
            "results": results,
        }),
    }
