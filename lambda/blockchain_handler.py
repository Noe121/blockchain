import asyncio
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

# Conditional imports for AWS Lambda dependencies
try:
    import boto3  # Available in AWS Lambda runtime
except ImportError:
    boto3 = None  # For local development

try:
    from web3 import Web3  # Available when web3 package is installed
except ImportError:
    Web3 = None  # For local development without web3

try:
    from eth_account import Account  # noqa: F401 (kept for back-compat imports)
except ImportError:
    Account = None  # type: ignore

from safety import assert_contract_trusted
from kms_signer import build_signer, SignerBase

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Process-local lock serializing the build+sign+send sequence. Two concurrent
# signings on the same process would otherwise race on the nonce and only one
# would broadcast successfully.
_SIGN_LOCK = asyncio.Lock()


class EthereumService:
    def __init__(self):
        # Check for required dependencies
        if Web3 is None:
            raise ImportError("web3 package is required but not installed")
        if boto3 is None:
            raise ImportError("boto3 package is required but not installed")

        self.infura_url = os.environ.get('INFURA_URL')
        self.chain_id = int(os.environ.get('CHAIN_ID', '11155111'))  # Sepolia testnet
        self.nft_contract_address = os.environ.get('NFT_CONTRACT_ADDRESS')
        self.sponsorship_contract_address = os.environ.get('SPONSORSHIP_CONTRACT_ADDRESS')
        self.anchor_contract_address = os.environ.get('ANCHOR_CONTRACT_ADDRESS')

        # Fail closed if contract addresses are missing, malformed, or
        # not in the trusted allow-list for the configured chain_id. This
        # prevents a stale/env-typo contract redirect from signing anything.
        for name, addr in (
            ("NFT_CONTRACT_ADDRESS", self.nft_contract_address),
            ("SPONSORSHIP_CONTRACT_ADDRESS", self.sponsorship_contract_address),
            ("ANCHOR_CONTRACT_ADDRESS", self.anchor_contract_address),
        ):
            if not addr:
                raise RuntimeError(f"{name} is required")
            if not Web3.is_checksum_address(addr):
                raise RuntimeError(
                    f"{name}={addr} is not a valid checksum address"
                )
            assert_contract_trusted(self.chain_id, addr, name)

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.infura_url))

        # Signer abstraction (local Secrets Manager now; KMS swap via env).
        self._signer: SignerBase = build_signer(
            lambda: self._get_secret('nilbx-ethereum-keys', 'PRIVATE_KEY')
        )

        # Load contract ABIs from Secrets Manager
        self.nft_abi = json.loads(self._get_secret('nilbx-contract-abis', 'NFT_ABI'))
        self.sponsorship_abi = json.loads(
            self._get_secret('nilbx-contract-abis', 'SPONSORSHIP_ABI')
        )

        # Load anchor ABI
        self.anchor_abi = json.loads(
            self._get_secret('nilbx-contract-abis', 'ANCHOR_ABI')
        )

        # Initialize contracts
        self.nft_contract = self.w3.eth.contract(
            address=self.nft_contract_address, abi=self.nft_abi
        )
        self.sponsorship_contract = self.w3.eth.contract(
            address=self.sponsorship_contract_address, abi=self.sponsorship_abi
        )
        self.anchor_contract = self.w3.eth.contract(
            address=self.anchor_contract_address, abi=self.anchor_abi
        )

    # Backwards-compat shim: some legacy callers accessed .account directly.
    @property
    def account(self):  # pragma: no cover
        return self._signer

    @property
    def signer_address(self) -> str:
        return self._signer.address

    def _get_secret(self, secret_name: str, key: str) -> str:
        try:
            if boto3 is None:
                raise ImportError("boto3 is not available")
            secrets_client = boto3.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId=secret_name)
            secrets = json.loads(response['SecretString'])
            return secrets[key]
        except Exception as e:
            logger.error(f"Error getting secret {secret_name}:{key}: {str(e)}")
            raise

    def _build_transaction(
        self, contract_function, value: int = 0
    ) -> Dict[str, Any]:
        """Build a transaction; use 'pending' nonce so locally-queued txns are seen."""
        try:
            return contract_function.build_transaction({
                'from': self._signer.address,
                'value': value,
                'gas': 2000000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(
                    self._signer.address, 'pending'
                ),
                'chainId': self.chain_id,
            })
        except Exception as e:
            logger.error(f"Error building transaction: {str(e)}")
            raise

    def _send_transaction(self, transaction: Dict[str, Any]) -> str:
        try:
            signed_txn = self._signer.sign_transaction(transaction)
            raw = getattr(signed_txn, "rawTransaction", None) or getattr(
                signed_txn, "raw_transaction", None
            )
            tx_hash = self.w3.eth.send_raw_transaction(raw)
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Error sending transaction: {str(e)}")
            raise

    # -------- NFT ---------------------------------------------------------
    def mint_legacy_nft(
        self,
        athlete_address: str,
        recipient_address: str,
        token_uri: str,
        royalty_fee: int,
    ) -> str:
        try:
            if Web3 is None:
                raise ImportError("Web3 is not available")
            if not Web3.is_address(athlete_address):
                raise ValueError("Invalid athlete address")
            if not Web3.is_address(recipient_address):
                raise ValueError("Invalid recipient address")
            if royalty_fee > 1000:
                raise ValueError("Royalty fee too high")

            contract_function = self.nft_contract.functions.mintLegacyNFT(
                athlete_address, recipient_address, token_uri, royalty_fee
            )
            transaction = self._build_transaction(contract_function)
            tx_hash = self._send_transaction(transaction)
            logger.info("NFT minted tx=%s", tx_hash)
            return tx_hash
        except Exception as e:
            logger.error("Error minting NFT: %s", e)
            raise

    # -------- Sponsorship -------------------------------------------------
    def create_sponsorship_task(
        self, athlete_address: str, description: str, amount_eth: float
    ) -> str:
        try:
            if Web3 is None:
                raise ImportError("Web3 is not available")
            if not Web3.is_address(athlete_address):
                raise ValueError("Invalid athlete address")
            if amount_eth <= 0:
                raise ValueError("Amount must be positive")

            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            contract_function = self.sponsorship_contract.functions.createTask(
                athlete_address, description
            )
            transaction = self._build_transaction(contract_function, value=amount_wei)
            tx_hash = self._send_transaction(transaction)
            logger.info("Sponsorship task created tx=%s", tx_hash)
            return tx_hash
        except Exception as e:
            logger.error("Error creating sponsorship task: %s", e)
            raise

    def approve_task(self, task_id: int) -> str:
        try:
            contract_function = self.sponsorship_contract.functions.approveTask(task_id)
            transaction = self._build_transaction(contract_function)
            tx_hash = self._send_transaction(transaction)
            logger.info("Task %s approved tx=%s", task_id, tx_hash)
            return tx_hash
        except Exception as e:
            logger.error("Error approving task: %s", e)
            raise

    def get_task_details(self, task_id: int) -> Dict[str, Any]:
        try:
            task = self.sponsorship_contract.functions.getTask(task_id).call()
            return {
                'taskId': task[0],
                'sponsor': task[1],
                'athlete': task[2],
                'amount': str(task[3]),
                'description': task[4],
                'status': task[5],
                'createdAt': task[6],
                'completedAt': task[7],
                'deliverableHash': task[8].hex() if task[8] != b'\x00' * 32 else None,
            }
        except Exception as e:
            logger.error("Error getting task details: %s", e)
            raise

    def get_task_onchain(
        self, task_id: int
    ) -> Tuple[str, str, int, Any]:
        """Return ``(sponsor, athlete, amount_wei, status)`` straight from chain.

        Used by /approve-task to verify the caller is the on-chain sponsor
        before signing an approval. Case-preserved checksum address.
        """
        task = self.sponsorship_contract.functions.getTask(task_id).call()
        sponsor = task[1]
        athlete = task[2]
        amount_wei = int(task[3])
        status = task[5]
        return sponsor, athlete, amount_wei, status

    # -------- Contract Anchoring -------------------------------------------
    async def anchor_contract_hash(
        self, terms_hash: str, contract_id: int
    ) -> Dict[str, Any]:
        """Anchor a contract terms hash on-chain via ContractAnchor.

        Args:
            terms_hash: SHA-256 hex string of the contract terms (64 chars).
            contract_id: NILBx platform contract instance ID.

        Returns:
            Dict with tx_hash, block_number, chain_id, contract_address.
        """
        async with _SIGN_LOCK:
            try:
                # Convert hex string to bytes32
                if terms_hash.startswith("0x"):
                    hash_bytes = bytes.fromhex(terms_hash[2:])
                else:
                    hash_bytes = bytes.fromhex(terms_hash)

                if len(hash_bytes) != 32:
                    raise ValueError(
                        f"terms_hash must be 32 bytes, got {len(hash_bytes)}"
                    )

                contract_function = self.anchor_contract.functions.anchorContract(
                    hash_bytes, contract_id
                )

                # Estimate gas before sending (fail fast if too expensive)
                gas_limit = int(os.environ.get("ANCHOR_GAS_LIMIT", "100000"))
                estimated = contract_function.estimate_gas(
                    {"from": self._signer.address}
                )
                if estimated > gas_limit:
                    raise RuntimeError(
                        f"Gas estimate {estimated} exceeds limit {gas_limit}"
                    )

                transaction = self._build_transaction(contract_function)
                tx_hash = self._send_transaction(transaction)

                # Wait for receipt to get block number
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=120
                )

                logger.info(
                    "Contract anchored: contract_id=%s tx=%s block=%s",
                    contract_id, tx_hash, receipt.blockNumber,
                )
                return {
                    "tx_hash": tx_hash,
                    "block_number": receipt.blockNumber,
                    "chain_id": str(self.chain_id),
                    "contract_address": self.anchor_contract_address,
                }
            except Exception as e:
                logger.error(
                    "Error anchoring contract %s: %s", contract_id, e
                )
                raise

    async def anchor_proof_hash(
        self, proof_hash: str, deliverable_id: int
    ) -> Dict[str, Any]:
        """Anchor a deliverable proof hash on-chain via ContractAnchor.

        Args:
            proof_hash: SHA-256 hex string of the proof metadata.
            deliverable_id: NILBx platform deliverable ID.

        Returns:
            Dict with tx_hash, block_number, chain_id, contract_address.
        """
        async with _SIGN_LOCK:
            try:
                if proof_hash.startswith("0x"):
                    hash_bytes = bytes.fromhex(proof_hash[2:])
                else:
                    hash_bytes = bytes.fromhex(proof_hash)

                if len(hash_bytes) != 32:
                    raise ValueError(
                        f"proof_hash must be 32 bytes, got {len(hash_bytes)}"
                    )

                contract_function = self.anchor_contract.functions.anchorProof(
                    hash_bytes, deliverable_id
                )

                gas_limit = int(os.environ.get("ANCHOR_GAS_LIMIT", "100000"))
                estimated = contract_function.estimate_gas(
                    {"from": self._signer.address}
                )
                if estimated > gas_limit:
                    raise RuntimeError(
                        f"Gas estimate {estimated} exceeds limit {gas_limit}"
                    )

                transaction = self._build_transaction(contract_function)
                tx_hash = self._send_transaction(transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=120
                )

                logger.info(
                    "Proof anchored: deliverable_id=%s tx=%s block=%s",
                    deliverable_id, tx_hash, receipt.blockNumber,
                )
                return {
                    "tx_hash": tx_hash,
                    "block_number": receipt.blockNumber,
                    "chain_id": str(self.chain_id),
                    "contract_address": self.anchor_contract_address,
                }
            except Exception as e:
                logger.error(
                    "Error anchoring proof %s: %s", deliverable_id, e
                )
                raise

    def verify_contract_anchor(self, terms_hash: str) -> Dict[str, Any]:
        """Verify a contract anchor on-chain (view function, no gas cost)."""
        if terms_hash.startswith("0x"):
            hash_bytes = bytes.fromhex(terms_hash[2:])
        else:
            hash_bytes = bytes.fromhex(terms_hash)

        exists, timestamp, block_number, contract_id = (
            self.anchor_contract.functions.verifyContractAnchor(hash_bytes).call()
        )
        return {
            "exists": exists,
            "timestamp": timestamp,
            "block_number": block_number,
            "contract_id": contract_id,
        }

    def get_athlete_nfts(self, athlete_address: str) -> List[Dict[str, Any]]:
        try:
            if Web3 is None:
                raise ImportError("Web3 is not available")
            if not Web3.is_address(athlete_address):
                raise ValueError("Invalid athlete address")
            token_ids = self.nft_contract.functions.tokensOfOwner(athlete_address).call()
            nfts = []
            for token_id in token_ids:
                try:
                    token_uri = self.nft_contract.functions.tokenURI(token_id).call()
                    nfts.append({'tokenId': token_id, 'tokenURI': token_uri, 'owner': athlete_address})
                except Exception:
                    continue
            return nfts
        except Exception as e:
            logger.error("Error getting athlete NFTs: %s", e)
            raise


# --- Lambda handler (legacy event-shape routing) -------------------------
def lambda_handler(event, context):  # noqa: C901 - legacy shape kept
    try:
        if Web3 is None or boto3 is None:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Required dependencies (web3, boto3) are not available',
                }),
            }

        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}

        eth_service = EthereumService()

        if http_method == 'POST' and path == '/mint-nft':
            result = eth_service.mint_legacy_nft(
                athlete_address=body['athlete_address'],
                recipient_address=body['recipient_address'],
                token_uri=body['token_uri'],
                royalty_fee=body.get('royalty_fee', 500),
            )
            return _ok({'tx_hash': result, 'message': 'NFT minted successfully'})
        elif http_method == 'POST' and path == '/create-task':
            result = eth_service.create_sponsorship_task(
                athlete_address=body['athlete_address'],
                description=body['description'],
                amount_eth=float(body['amount_eth']),
            )
            return _ok({'tx_hash': result, 'message': 'Sponsorship task created'})
        elif http_method == 'POST' and path == '/approve-task':
            result = eth_service.approve_task(int(body['task_id']))
            return _ok({'tx_hash': result, 'message': 'Task approved'})
        elif http_method == 'GET' and path.startswith('/task/'):
            task_id = int(path.split('/')[-1])
            result = eth_service.get_task_details(task_id)
            return _ok({'task': result})
        elif http_method == 'GET' and path.startswith('/athlete-nfts/'):
            athlete_address = path.split('/')[-1]
            result = eth_service.get_athlete_nfts(athlete_address)
            return _ok({'nfts': result})
        return _err(404, 'Endpoint not found')
    except Exception as e:
        logger.exception("lambda_handler error")
        return _err(500, str(e))


def _ok(payload: Dict[str, Any]):
    body = {'success': True}
    body.update(payload)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body),
    }


def _err(code: int, msg: str):
    return {
        'statusCode': code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'success': False, 'error': msg}),
    }
