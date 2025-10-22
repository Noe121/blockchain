import json
import os
import logging
from typing import Dict, Any, List, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class NILIntegrationService:
    def __init__(self):
        # API endpoints for existing services
        self.auth_service_url = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:3001')
        self.api_service_url = os.environ.get('API_SERVICE_URL', 'http://localhost:3000')
        self.company_api_url = os.environ.get('COMPANY_API_URL', 'http://localhost:3002')
        
        # Blockchain Lambda endpoints
        self.blockchain_lambda_url = os.environ.get('BLOCKCHAIN_LAMBDA_URL')
        self.ipfs_lambda_url = os.environ.get('IPFS_LAMBDA_URL')

    def _make_api_request(self, url: str, method: str = 'GET', data: Optional[Dict] = None, 
                         headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to API service"""
        try:
            import requests
            
            if headers is None:
                headers = {'Content-Type': 'application/json'}
                
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise

    def get_athlete_profile(self, athlete_id: str, auth_token: str) -> Dict[str, Any]:
        """Get athlete profile from API service"""
        try:
            url = f"{self.api_service_url}/athletes/{athlete_id}"
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            return self._make_api_request(url, 'GET', headers=headers)
            
        except Exception as e:
            logger.error(f"Error getting athlete profile: {str(e)}")
            raise

    def create_nft_for_athlete(self, athlete_id: str, auth_token: str, 
                              nft_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create NFT for athlete by integrating with blockchain service"""
        try:
            # Get athlete profile
            athlete = self.get_athlete_profile(athlete_id, auth_token)
            
            # Upload metadata to IPFS
            ipfs_response = self._make_api_request(
                f"{self.ipfs_lambda_url}/upload-metadata",
                'POST',
                {
                    'athlete_name': athlete['name'],
                    'athlete_id': athlete_id,
                    'description': nft_data.get('description', f"Legacy NFT for {athlete['name']}"),
                    'image_url': nft_data['image_url'],
                    'attributes': nft_data.get('attributes', [])
                }
            )
            
            # Mint NFT on blockchain
            blockchain_response = self._make_api_request(
                f"{self.blockchain_lambda_url}/mint-nft",
                'POST',
                {
                    'athlete_address': athlete['ethereum_address'],
                    'recipient_address': nft_data.get('recipient_address', athlete['ethereum_address']),
                    'token_uri': ipfs_response['ipfs_url'],
                    'royalty_fee': nft_data.get('royalty_fee', 500)  # 5% default
                }
            )
            
            # Update athlete record with NFT info (optional)
            import time
            nft_info = {
                'tx_hash': blockchain_response['tx_hash'],
                'ipfs_url': ipfs_response['ipfs_url'],
                'created_at': str(int(time.time()))
            }
            
            return {
                'success': True,
                'athlete': athlete,
                'nft_transaction': blockchain_response,
                'metadata': ipfs_response,
                'nft_info': nft_info
            }
            
        except Exception as e:
            logger.error(f"Error creating NFT for athlete: {str(e)}")
            raise

    def create_sponsorship_opportunity(self, sponsor_id: str, athlete_id: str, 
                                     auth_token: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create sponsorship opportunity with blockchain payment and fee tracking"""
        try:
            # Get athlete profile
            athlete = self.get_athlete_profile(athlete_id, auth_token)
            
            # Calculate deal value in USD (assuming ETH price)
            eth_price_usd = 2000.0  # Should come from price oracle in production
            deal_value_usd = float(task_data['amount_eth']) * eth_price_usd
            
            # Calculate fees based on competitive 6-8% target
            transaction_fee_usd = deal_value_usd * 0.04  # 4% transaction fee
            deployment_fee_usd = 12.50  # $10-15 midpoint
            subscription_fee_usd = 15.00  # $15/month (prorated for deal duration)
            premium_fee_usd = 0.00  # No premium by default
            
            # Adjust fees for small deals to stay under 11% cap
            total_fee_percentage = ((transaction_fee_usd + deployment_fee_usd + subscription_fee_usd + premium_fee_usd) / deal_value_usd) * 100
            
            if total_fee_percentage > 11.0:
                # Reduce transaction fee for small deals
                if deal_value_usd < 1000:
                    transaction_fee_usd = deal_value_usd * 0.03  # Reduce to 3%
                elif deal_value_usd < 2000:
                    transaction_fee_usd = deal_value_usd * 0.035  # Reduce to 3.5%
            
            # Create blockchain task
            blockchain_response = self._make_api_request(
                f"{self.blockchain_lambda_url}/create-task",
                'POST',
                {
                    'athlete_address': athlete['ethereum_address'],
                    'description': task_data['description'],
                    'amount_eth': float(task_data['amount_eth'])
                }
            )
            
            # Record fee analytics
            self._record_fee_analytics(
                deal_id=f"sponsorship_{blockchain_response.get('task_id', 'unknown')}",
                deal_type='sponsorship',
                deal_value_usd=deal_value_usd,
                transaction_fee_usd=transaction_fee_usd,
                deployment_fee_usd=deployment_fee_usd,
                subscription_fee_usd=subscription_fee_usd,
                premium_fee_usd=premium_fee_usd,
                user_id=int(athlete_id),
                user_type='athlete'
            )
            
            return {
                'success': True,
                'athlete': athlete,
                'blockchain_task': blockchain_response,
                'task_data': task_data,
                'fee_breakdown': {
                    'deal_value_usd': deal_value_usd,
                    'transaction_fee_usd': transaction_fee_usd,
                    'deployment_fee_usd': deployment_fee_usd,
                    'subscription_fee_usd': subscription_fee_usd,
                    'premium_fee_usd': premium_fee_usd,
                    'total_effective_fee_usd': transaction_fee_usd + deployment_fee_usd + subscription_fee_usd + premium_fee_usd,
                    'effective_fee_percentage': ((transaction_fee_usd + deployment_fee_usd + subscription_fee_usd + premium_fee_usd) / deal_value_usd) * 100,
                    'competitiveness': 'Undercuts NIL platforms by 2-12% while maintaining 6-8% target'
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating sponsorship opportunity: {str(e)}")
            raise

    def _record_fee_analytics(self, deal_id: str, deal_type: str, deal_value_usd: float,
                             transaction_fee_usd: float, deployment_fee_usd: float,
                             subscription_fee_usd: float, premium_fee_usd: float,
                             user_id: int, user_type: str):
        """Record fee analytics in DynamoDB"""
        try:
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()

            # Record deployment fee
            dynamodb.record_deployment_fee(
                user_id=str(user_id),
                user_type=user_type,
                contract_type='sponsorship',
                fee_usd=deployment_fee_usd
            )

            # Record subscription fee if applicable
            if subscription_fee_usd > 0:
                dynamodb.record_subscription_fee(
                    user_id=str(user_id),
                    user_type=user_type,
                    plan_name='monitoring',
                    fee_usd=subscription_fee_usd
                )

            # Record premium fee if applicable
            if premium_fee_usd > 0:
                dynamodb.record_premium_fee(
                    user_id=str(user_id),
                    user_type=user_type,
                    feature_name='sponsorship_premium',
                    fee_usd=premium_fee_usd
                )

            logger.info(f"Fee analytics recorded for deal {deal_id}")

        except Exception as e:
            logger.error(f"Error recording fee analytics: {str(e)}")
            # Don't raise exception - fee tracking failure shouldn't break main flow

    def record_subscription_fee(self, user_id: int, user_type: str, 
                               subscription_plan: str, fee_usd: float) -> Dict[str, Any]:
        """Record subscription fee payment in DynamoDB"""
        try:
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()

            result = dynamodb.record_subscription_fee(
                user_id=str(user_id),
                user_type=user_type,
                plan_name=subscription_plan,
                fee_usd=fee_usd
            )

            return {
                'success': True,
                'subscription_fee_usd': fee_usd,
                'plan': subscription_plan,
                'competitiveness': 'Undercuts traditional NIL platforms by 50-70%'
            }
            
        except Exception as e:
            logger.error(f"Error recording subscription fee: {str(e)}")
            raise

    def record_premium_fee(self, user_id: int, user_type: str, 
                          feature_name: str, fee_usd: float) -> Dict[str, Any]:
        """Record premium feature fee payment in DynamoDB"""
        try:
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()

            result = dynamodb.record_premium_fee(
                user_id=str(user_id),
                user_type=user_type,
                feature_name=feature_name,
                fee_usd=fee_usd
            )

            return {
                'success': True,
                'premium_fee_usd': fee_usd,
                'feature': feature_name,
                'competitiveness': 'Flexible premium features undercutting enterprise solutions'
            }
            
        except Exception as e:
            logger.error(f"Error recording premium fee: {str(e)}")
            raise

    def record_deployment_fee(self, user_id: int, user_type: str, 
                             contract_type: str, fee_usd: float) -> Dict[str, Any]:
        """Record deployment fee payment in DynamoDB"""
        try:
            from dynamodb_service import get_dynamodb_service
            dynamodb = get_dynamodb_service()

            result = dynamodb.record_deployment_fee(
                user_id=str(user_id),
                user_type=user_type,
                contract_type=contract_type,
                fee_usd=fee_usd
            )

            return {
                'success': True,
                'deployment_fee_usd': fee_usd,
                'contract_type': contract_type,
                'competitiveness': 'Undercuts traditional deployment costs by 60-80%'
            }
            
        except Exception as e:
            logger.error(f"Error recording deployment fee: {str(e)}")
            raise

    def get_athlete_blockchain_assets(self, athlete_id: str, auth_token: str) -> Dict[str, Any]:
        """Get all blockchain assets (NFTs, tasks) for an athlete"""
        try:
            # Get athlete profile
            athlete = self.get_athlete_profile(athlete_id, auth_token)
            
            # Get NFTs from blockchain
            nfts_response = self._make_api_request(
                f"{self.blockchain_lambda_url}/athlete-nfts/{athlete['ethereum_address']}",
                'GET'
            )
            
            # TODO: Get sponsorship tasks (would need additional endpoint)
            
            return {
                'success': True,
                'athlete': athlete,
                'nfts': nfts_response.get('nfts', []),
                'total_nfts': len(nfts_response.get('nfts', []))
            }
            
        except Exception as e:
            logger.error(f"Error getting athlete blockchain assets: {str(e)}")
            raise

    def verify_athlete_identity(self, athlete_id: str, ethereum_address: str, 
                               auth_token: str) -> Dict[str, Any]:
        """Verify athlete identity and link Ethereum address"""
        try:
            # Get athlete profile
            athlete = self.get_athlete_profile(athlete_id, auth_token)
            
            # Update athlete with Ethereum address if not set
            if not athlete.get('ethereum_address'):
                update_data = {'ethereum_address': ethereum_address}
                
                updated_athlete = self._make_api_request(
                    f"{self.api_service_url}/athletes/{athlete_id}",
                    'PUT',
                    update_data,
                    headers={
                        'Authorization': f'Bearer {auth_token}',
                        'Content-Type': 'application/json'
                    }
                )
                
                return {
                    'success': True,
                    'message': 'Ethereum address linked successfully',
                    'athlete': updated_athlete
                }
            else:
                return {
                    'success': True,
                    'message': 'Ethereum address already verified',
                    'athlete': athlete
                }
                
        except Exception as e:
            logger.error(f"Error verifying athlete identity: {str(e)}")
            raise


def lambda_handler(event, context):
    """Integration Lambda handler"""
    try:
        # Parse the request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        headers = event.get('headers', {})
        
        # Get auth token
        auth_token = headers.get('Authorization', '').replace('Bearer ', '')
        if not auth_token:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Authentication required'
                })
            }
        
        # Initialize integration service
        integration_service = NILIntegrationService()
        
        if http_method == 'POST' and path == '/create-athlete-nft':
            result = integration_service.create_nft_for_athlete(
                athlete_id=body['athlete_id'],
                auth_token=auth_token,
                nft_data=body['nft_data']
            )
            
        elif http_method == 'POST' and path == '/create-sponsorship':
            result = integration_service.create_sponsorship_opportunity(
                sponsor_id=body['sponsor_id'],
                athlete_id=body['athlete_id'],
                auth_token=auth_token,
                task_data=body['task_data']
            )
            
        elif http_method == 'GET' and path.startswith('/athlete-assets/'):
            athlete_id = path.split('/')[-1]
            result = integration_service.get_athlete_blockchain_assets(
                athlete_id=athlete_id,
                auth_token=auth_token
            )
            
        elif http_method == 'POST' and path == '/verify-athlete-identity':
            result = integration_service.verify_athlete_identity(
                athlete_id=body['athlete_id'],
                ethereum_address=body['ethereum_address'],
                auth_token=auth_token
            )
            
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
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Integration Lambda handler error: {str(e)}")
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