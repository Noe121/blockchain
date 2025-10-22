import json
import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

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
    from eth_account import Account  # Available when eth-account package is installed
except ImportError:
    Account = None  # For local development without eth-account

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class EthereumService:
    def __init__(self):
        # Check for required dependencies
        if Web3 is None:
            raise ImportError("web3 package is required but not installed")
        if Account is None:
            raise ImportError("eth-account package is required but not installed")
        if boto3 is None:
            raise ImportError("boto3 package is required but not installed")
            
        # Get configuration from environment variables
        self.infura_url = os.environ.get('INFURA_URL')
        self.chain_id = int(os.environ.get('CHAIN_ID', '11155111'))  # Sepolia testnet
        self.nft_contract_address = os.environ.get('NFT_CONTRACT_ADDRESS')
        self.sponsorship_contract_address = os.environ.get('SPONSORSHIP_CONTRACT_ADDRESS')
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.infura_url))
        
        # Get private key from Secrets Manager
        self.private_key = self._get_secret('nilbx-ethereum-keys', 'PRIVATE_KEY')
        self.account = Account.from_key(self.private_key)
        
        # Load contract ABIs from Secrets Manager
        self.nft_abi = json.loads(self._get_secret('nilbx-contract-abis', 'NFT_ABI'))
        self.sponsorship_abi = json.loads(self._get_secret('nilbx-contract-abis', 'SPONSORSHIP_ABI'))
        
        # Initialize contracts
        self.nft_contract = self.w3.eth.contract(
            address=self.nft_contract_address,
            abi=self.nft_abi
        )
        self.sponsorship_contract = self.w3.eth.contract(
            address=self.sponsorship_contract_address,
            abi=self.sponsorship_abi
        )

    def _get_secret(self, secret_name: str, key: str) -> str:
        """Get secret from AWS Secrets Manager"""
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

    def _build_transaction(self, contract_function, value: int = 0) -> Dict[str, Any]:
        """Build a transaction for a contract function"""
        try:
            return contract_function.build_transaction({
                'from': self.account.address,
                'value': value,
                'gas': 2000000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'chainId': self.chain_id
            })
        except Exception as e:
            logger.error(f"Error building transaction: {str(e)}")
            raise

    def _send_transaction(self, transaction: Dict[str, Any]) -> str:
        """Sign and send a transaction"""
        try:
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Error sending transaction: {str(e)}")
            raise

    def mint_legacy_nft(self, athlete_address: str, recipient_address: str, 
                       token_uri: str, royalty_fee: int) -> str:
        """Mint a legacy NFT for an athlete"""
        try:
            # Validate inputs
            if Web3 is None:
                raise ImportError("Web3 is not available")
            if not Web3.is_address(athlete_address):
                raise ValueError("Invalid athlete address")
            if not Web3.is_address(recipient_address):
                raise ValueError("Invalid recipient address")
            if royalty_fee > 1000:  # Max 10%
                raise ValueError("Royalty fee too high")

            # Build transaction
            contract_function = self.nft_contract.functions.mintLegacyNFT(
                athlete_address,
                recipient_address,
                token_uri,
                royalty_fee
            )
            
            transaction = self._build_transaction(contract_function)
            tx_hash = self._send_transaction(transaction)
            
            logger.info(f"NFT minted successfully. Tx hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error minting NFT: {str(e)}")
            raise

    def create_sponsorship_task(self, athlete_address: str, description: str, 
                               amount_eth: float) -> str:
        """Create a sponsorship task"""
        try:
            # Validate inputs
            if Web3 is None:
                raise ImportError("Web3 is not available")
            if not Web3.is_address(athlete_address):
                raise ValueError("Invalid athlete address")
            if amount_eth <= 0:
                raise ValueError("Amount must be positive")

            # Convert ETH to Wei
            amount_wei = self.w3.to_wei(amount_eth, 'ether')

            # Build transaction
            contract_function = self.sponsorship_contract.functions.createTask(
                athlete_address,
                description
            )
            
            transaction = self._build_transaction(contract_function, value=amount_wei)
            tx_hash = self._send_transaction(transaction)
            
            logger.info(f"Sponsorship task created successfully. Tx hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error creating sponsorship task: {str(e)}")
            raise

    def approve_task(self, task_id: int) -> str:
        """Approve a completed sponsorship task"""
        try:
            # Build transaction
            contract_function = self.sponsorship_contract.functions.approveTask(task_id)
            transaction = self._build_transaction(contract_function)
            tx_hash = self._send_transaction(transaction)
            
            logger.info(f"Task {task_id} approved successfully. Tx hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error approving task: {str(e)}")
            raise

    def get_task_details(self, task_id: int) -> Dict[str, Any]:
        """Get details of a sponsorship task"""
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
                'deliverableHash': task[8].hex() if task[8] != b'\x00' * 32 else None
            }
            
        except Exception as e:
            logger.error(f"Error getting task details: {str(e)}")
            raise

    def get_athlete_nfts(self, athlete_address: str) -> list:
        """Get all NFTs owned by an athlete"""
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
                    nfts.append({
                        'tokenId': token_id,
                        'tokenURI': token_uri,
                        'owner': athlete_address
                    })
                except:
                    # Skip if tokenURI fails
                    continue
                    
            return nfts
            
        except Exception as e:
            logger.error(f"Error getting athlete NFTs: {str(e)}")
            raise


def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        # Check for required dependencies before proceeding
        if Web3 is None or Account is None or boto3 is None:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Required dependencies (web3, eth-account, boto3) are not available'
                })
            }
            
        # Parse the request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        
        # Initialize Ethereum service
        eth_service = EthereumService()
        
        # Route the request
        if http_method == 'POST' and path == '/mint-nft':
            result = eth_service.mint_legacy_nft(
                athlete_address=body['athlete_address'],
                recipient_address=body['recipient_address'],
                token_uri=body['token_uri'],
                royalty_fee=body.get('royalty_fee', 500)  # Default 5%
            )
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'tx_hash': result,
                    'message': 'NFT minted successfully'
                })
            }
            
        elif http_method == 'POST' and path == '/create-task':
            result = eth_service.create_sponsorship_task(
                athlete_address=body['athlete_address'],
                description=body['description'],
                amount_eth=float(body['amount_eth'])
            )
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'tx_hash': result,
                    'message': 'Sponsorship task created successfully'
                })
            }
            
        elif http_method == 'POST' and path == '/approve-task':
            result = eth_service.approve_task(int(body['task_id']))
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'tx_hash': result,
                    'message': 'Task approved successfully'
                })
            }
            
        elif http_method == 'GET' and path.startswith('/task/'):
            task_id = int(path.split('/')[-1])
            result = eth_service.get_task_details(task_id)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'task': result
                })
            }
            
        elif http_method == 'GET' and path.startswith('/athlete-nfts/'):
            athlete_address = path.split('/')[-1]
            result = eth_service.get_athlete_nfts(athlete_address)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'nfts': result
                })
            }
            
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Endpoint not found'
                })
            }
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }