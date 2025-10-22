"""
DynamoDB Service Layer for NIL Blockchain Platform
Provides comprehensive CRUD operations for blockchain fee management
"""

import os
import json
import logging
import boto3  # type: ignore
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr  # type: ignore

logger = logging.getLogger(__name__)

class DynamoDBService:
    """DynamoDB service for NIL blockchain data management"""

    def __init__(self):
        self.table_name = os.getenv('DYNAMODB_TABLE', 'SmartContractData')
        self.dynamodb = boto3.resource('dynamodb',
                                     region_name=os.getenv('AWS_REGION', 'us-east-1'))
        self.table = self.dynamodb.Table(self.table_name)

    def _generate_id(self) -> str:
        """Generate a unique ID for entities"""
        import uuid
        return str(uuid.uuid4())

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat()

    # User Management
    def create_user(self, user_id: str, email: str, role: str) -> Dict[str, Any]:
        """Create a new user in DynamoDB"""
        item = {
            'PK': f'USER#{user_id}',
            'SK': 'METADATA',
            'email': email,
            'role': role,
            'created_at': self._get_timestamp(),
            'updated_at': self._get_timestamp()
        }

        self.table.put_item(Item=item)
        logger.info(f"Created user {user_id}")
        return item

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        response = self.table.get_item(
            Key={'PK': f'USER#{user_id}', 'SK': 'METADATA'}
        )
        return response.get('Item')

    # Contract Management
    def create_contract(self, user_id: str, athlete_wallet: str, sponsor_wallet: str,
                       contract_address: str, abi: str, appearances_required: int,
                       payment_amount: int, platform_fee_percent: float,
                       deployment_fee: float) -> Dict[str, Any]:
        """Create a new smart contract record"""
        contract_id = self._generate_id()
        created_at = self._get_timestamp()

        item = {
            'PK': f'CONTRACT#{contract_id}',
            'SK': 'METADATA',
            'user_id': user_id,
            'athlete_wallet': athlete_wallet,
            'sponsor_wallet': sponsor_wallet,
            'address': contract_address,
            'abi': abi,
            'appearances_required': appearances_required,
            'payment_amount': payment_amount,
            'platform_fee_percent': platform_fee_percent,
            'deployment_fee': deployment_fee,
            'created_at': created_at,
            'updated_at': created_at,
            'status': 'active',
            # GSIs
            'GSI1PK': f'WALLET#{athlete_wallet}',
            'GSI1SK': f'CONTRACT#{created_at}',
            'GSI2PK': 'CONTRACT',
            'GSI2SK': created_at
        }

        self.table.put_item(Item=item)
        logger.info(f"Created contract {contract_id}")
        return item

    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Get contract by ID"""
        response = self.table.get_item(
            Key={'PK': f'CONTRACT#{contract_id}', 'SK': 'METADATA'}
        )
        return response.get('Item')

    def get_user_contracts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contracts for a user"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('CONTRACT')
        )
        return response.get('Items', [])

    # Transaction Management
    def log_transaction(self, contract_id: str, tx_hash: str, tx_type: str,
                       amount: int, recipient_wallet: str) -> Dict[str, Any]:
        """Log a blockchain transaction"""
        tx_id = self._generate_id()
        created_at = self._get_timestamp()

        item = {
            'PK': f'CONTRACT#{contract_id}',
            'SK': f'TX#{tx_id}',
            'tx_hash': tx_hash,
            'type': tx_type,
            'amount': amount,
            'recipient_wallet': recipient_wallet,
            'created_at': created_at,
            # GSIs for fee tracking
            'GSI1PK': f'WALLET#{recipient_wallet}',
            'GSI1SK': f'TX#{created_at}',
            'GSI2PK': 'TX',
            'GSI2SK': created_at
        }

        self.table.put_item(Item=item)
        logger.info(f"Logged transaction {tx_id} for contract {contract_id}")
        return item

    def get_contract_transactions(self, contract_id: str) -> List[Dict[str, Any]]:
        """Get all transactions for a contract"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CONTRACT#{contract_id}') & Key('SK').begins_with('TX#')
        )
        return response.get('Items', [])

    def get_wallet_transactions(self, wallet_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transactions for a wallet using GSI1"""
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'WALLET#{wallet_address}') & Key('GSI1SK').begins_with('TX#'),
            ScanIndexForward=False,  # Most recent first
            Limit=limit
        )
        return response.get('Items', [])

    # Fee Management (replacing MySQL fee tables)
    def record_deployment_fee(self, user_id: str, user_type: str, contract_type: str, fee_usd: float) -> Dict[str, Any]:
        """Record deployment fee payment"""
        fee_id = self._generate_id()
        created_at = self._get_timestamp()

        item = {
            'PK': f'FEE#{fee_id}',
            'SK': 'DEPLOYMENT',
            'user_id': user_id,
            'user_type': user_type,
            'contract_type': contract_type,
            'fee_usd': Decimal(str(fee_usd)),
            'status': 'completed',
            'created_at': created_at,
            # GSIs
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'FEE#{created_at}',
            'GSI2PK': 'FEE',
            'GSI2SK': created_at
        }

        self.table.put_item(Item=item)
        logger.info(f"Recorded deployment fee {fee_id} for user {user_id}")
        return item

    def record_subscription_fee(self, user_id: str, user_type: str, plan_name: str, fee_usd: float) -> Dict[str, Any]:
        """Record subscription fee payment"""
        sub_id = self._generate_id()
        created_at = self._get_timestamp()

        # Calculate billing dates
        now = datetime.utcnow()
        if plan_name == 'quarterly':
            end_date = now + timedelta(days=90)
        elif plan_name == 'annual':
            end_date = now + timedelta(days=365)
        else:  # monthly
            end_date = now + timedelta(days=30)

        item = {
            'PK': f'USER#{user_id}',
            'SK': f'SUB#{sub_id}',
            'plan': plan_name,
            'fee_usd': Decimal(str(fee_usd)),
            'start_date': created_at,
            'end_date': end_date.isoformat(),
            'status': 'active',
            'created_at': created_at,
            # GSIs
            'GSI2PK': 'SUB',
            'GSI2SK': created_at
        }

        self.table.put_item(Item=item)
        logger.info(f"Recorded subscription {sub_id} for user {user_id}")
        return item

    def record_premium_fee(self, user_id: str, user_type: str, feature_name: str, fee_usd: float) -> Dict[str, Any]:
        """Record premium feature fee payment"""
        feature_id = self._generate_id()
        created_at = self._get_timestamp()

        item = {
            'PK': f'USER#{user_id}',
            'SK': f'PREMIUM#{feature_id}',
            'feature_name': feature_name,
            'fee_usd': Decimal(str(fee_usd)),
            'status': 'active',
            'created_at': created_at,
            # GSIs
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'PREMIUM#{created_at}',
            'GSI2PK': 'PREMIUM',
            'GSI2SK': created_at
        }

        self.table.put_item(Item=item)
        logger.info(f"Recorded premium fee {feature_id} for user {user_id}")
        return item

    # Analytics and Reporting
    def get_fee_analytics(self) -> Dict[str, Any]:
        """Get comprehensive fee analytics"""
        analytics = {
            'by_deal_size': [],
            'overall': {},
            'top_users': []
        }

        # Get transactions by date range for analytics
        # Note: In production, you'd use more sophisticated queries
        # This is a simplified version

        try:
            # Get all fee-related items
            response = self.table.scan(
                FilterExpression=Attr('PK').begins_with('FEE#') | Attr('GSI2PK').eq('SUB') | Attr('GSI2PK').eq('PREMIUM')
            )

            items = response.get('Items', [])
            total_fees = 0
            fee_count = 0

            for item in items:
                if 'fee_usd' in item:
                    total_fees += float(item['fee_usd'])
                    fee_count += 1

            analytics['overall'] = {
                'total_deals': fee_count,
                'total_revenue': round(total_fees, 2),
                'avg_fee': round(total_fees / fee_count, 2) if fee_count > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting fee analytics: {e}")

        return analytics

    def get_transactions_by_date_range(self, start_date: str, end_date: str, entity_type: str = 'TX') -> List[Dict[str, Any]]:
        """Get transactions within a date range using GSI2"""
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(entity_type) & Key('GSI2SK').between(start_date, end_date)
        )
        return response.get('Items', [])

    # NIL Compliance Reporting
    def get_contract_for_compliance(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Get contract data for NIL compliance reporting"""
        contract = self.get_contract(contract_id)
        if contract:
            # Get associated transactions
            transactions = self.get_contract_transactions(contract_id)
            contract['transactions'] = transactions
        return contract

# Global DynamoDB service instance
dynamodb_service = DynamoDBService()

def get_dynamodb_service() -> DynamoDBService:
    """Get the global DynamoDB service instance"""
    return dynamodb_service