"""
One-time backfill script for anchoring existing executed contracts.

Queries all contract instances in `executed` status where
chain_tx_hash IS NULL, then anchors each one via the ContractAnchor
smart contract. Rate-limited to avoid gas spikes.

Usage:
  # Dry run (list contracts that would be anchored)
  python backfill_anchoring.py --dry-run

  # Anchor up to 50 contracts
  python backfill_anchoring.py --limit 50

  # Full backfill with 5-second delay between anchors
  python backfill_anchoring.py --delay 5

Environment variables:
  CONTRACT_SERVICE_URL — contract-service base URL
  SERVICE_TOKEN — inter-service auth token
  INFURA_URL, CHAIN_ID, ANCHOR_CONTRACT_ADDRESS — blockchain config
  NFT_CONTRACT_ADDRESS, SPONSORSHIP_CONTRACT_ADDRESS — required by EthereumService

Security:
  - Uses SERVICE_TOKEN for contract-service auth
  - Private key from Secrets Manager (never in env)
  - Gas limit enforced per anchor
  - Rate-limited to prevent gas spikes
  - Idempotent (checks chain_tx_hash before anchoring)
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    logger.error("requests package required: pip install requests")
    sys.exit(1)

# Configuration
CONTRACT_SERVICE_URL = os.environ.get(
    "CONTRACT_SERVICE_URL", "http://localhost:8016"
).rstrip("/")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "").strip()
DEFAULT_DELAY_SECONDS = 3
DEFAULT_LIMIT = 100


def _service_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if SERVICE_TOKEN:
        headers["X-Service-Token"] = SERVICE_TOKEN
    return headers


def fetch_unanchored_contracts(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch executed contracts that haven't been anchored yet."""
    try:
        # Use contract-service list endpoint with status filter
        resp = requests.get(
            f"{CONTRACT_SERVICE_URL}/contract-instances",
            headers=_service_headers(),
            params={"status": "executed", "limit": limit},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error("Failed to fetch contracts: %s %s", resp.status_code, resp.text[:200])
            return []

        contracts = resp.json()
        if isinstance(contracts, dict):
            contracts = contracts.get("items", contracts.get("instances", []))

        # Filter to only those without chain_tx_hash
        unanchored = [
            c for c in contracts
            if not c.get("chain_tx_hash")
        ]
        return unanchored
    except Exception as e:
        logger.error("Error fetching contracts: %s", e)
        return []


def anchor_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Anchor a single contract on-chain."""
    contract_id = contract.get("id", contract.get("instance_id", ""))
    terms_hash = contract.get("terms_hash", "")

    if not terms_hash:
        return {"status": "skipped", "reason": "no_terms_hash", "id": contract_id}

    try:
        # Add lambda dir to path for imports
        lambda_dir = os.path.join(os.path.dirname(__file__), "..", "lambda")
        if lambda_dir not in sys.path:
            sys.path.insert(0, lambda_dir)

        from blockchain_handler import EthereumService
        eth = EthereumService()
        # contract_id must be uint256; derive a stable int from the string ID via SHA-256
        import hashlib as _hl
        contract_id_int = (
            int(contract_id) if isinstance(contract_id, int)
            else int(_hl.sha256(str(contract_id).encode()).hexdigest()[:8], 16)
        )
        result = asyncio.run(
            eth.anchor_contract_hash(terms_hash, contract_id_int)
        )

        # Store result back via callback
        try:
            callback_resp = requests.post(
                f"{CONTRACT_SERVICE_URL}/contract-instances/{contract_id}/anchor-result",
                headers=_service_headers(),
                json={
                    "chain_tx_hash": result["tx_hash"],
                    "chain_contract_address": result["contract_address"],
                    "chain_id": result["chain_id"],
                    "chain_block_number": result["block_number"],
                },
                timeout=10,
            )
            logger.info(
                "Callback: contract=%s status=%s",
                contract_id, callback_resp.status_code,
            )
        except Exception as e:
            logger.warning("Callback failed for %s: %s", contract_id, e)

        return {"status": "anchored", "id": contract_id, **result}

    except Exception as e:
        logger.error("Anchoring failed for contract %s: %s", contract_id, e)
        return {"status": "error", "id": contract_id, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Backfill blockchain anchoring for existing executed contracts"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List contracts that would be anchored without actually anchoring",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Maximum number of contracts to process (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds to wait between anchors (default: {DEFAULT_DELAY_SECONDS})",
    )
    args = parser.parse_args()

    logger.info("=== Blockchain Anchoring Backfill ===")
    logger.info("Contract service: %s", CONTRACT_SERVICE_URL)
    logger.info("Limit: %d, Delay: %.1fs, Dry run: %s", args.limit, args.delay, args.dry_run)
    logger.info("")

    # Fetch unanchored contracts
    contracts = fetch_unanchored_contracts(limit=args.limit)
    logger.info("Found %d unanchored executed contracts", len(contracts))

    if not contracts:
        logger.info("Nothing to backfill.")
        return

    if args.dry_run:
        logger.info("--- DRY RUN (no anchoring) ---")
        for c in contracts:
            cid = c.get("id", c.get("instance_id", "?"))
            terms = c.get("terms_hash", "none")[:16]
            logger.info("  Would anchor: id=%s terms_hash=%s...", cid, terms)
        logger.info("Total: %d contracts would be anchored", len(contracts))
        return

    # Process
    anchored = 0
    failed = 0
    skipped = 0

    for i, contract in enumerate(contracts):
        cid = contract.get("id", contract.get("instance_id", "?"))
        logger.info("[%d/%d] Anchoring contract %s...", i + 1, len(contracts), cid)

        result = anchor_contract(contract)
        status = result.get("status")

        if status == "anchored":
            anchored += 1
            logger.info("  ✅ Anchored: tx=%s block=%s", result.get("tx_hash", "?")[:16], result.get("block_number"))
        elif status == "skipped":
            skipped += 1
            logger.info("  ⏭️  Skipped: %s", result.get("reason"))
        else:
            failed += 1
            logger.error("  ❌ Failed: %s", result.get("error", result.get("reason", "unknown")))

        # Rate limit
        if i < len(contracts) - 1 and args.delay > 0:
            time.sleep(args.delay)

    logger.info("")
    logger.info("=== Backfill Complete ===")
    logger.info("Anchored: %d, Skipped: %d, Failed: %d, Total: %d", anchored, skipped, failed, len(contracts))


if __name__ == "__main__":
    main()
