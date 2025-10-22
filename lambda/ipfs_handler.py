import json
import requests
import logging
from typing import Dict, Any, Optional, List, Union

try:
    import boto3  # Available in AWS Lambda runtime
except ImportError:
    boto3 = None  # For local development

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class IPFSService:
    def __init__(self):
        self.pinata_api_key = self._get_secret('nilbx-ipfs-keys', 'PINATA_API_KEY')
        self.pinata_secret_key = self._get_secret('nilbx-ipfs-keys', 'PINATA_SECRET_KEY')
        self.pinata_base_url = "https://api.pinata.cloud"
        
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

    def upload_json_metadata(self, metadata: Dict[str, Any], name: Optional[str] = None) -> str:
        """Upload JSON metadata to IPFS via Pinata"""
        try:
            url = f"{self.pinata_base_url}/pinning/pinJSONToIPFS"
            
            headers = {
                'Content-Type': 'application/json',
                'pinata_api_key': self.pinata_api_key,
                'pinata_secret_api_key': self.pinata_secret_key
            }
            
            payload = {
                "pinataContent": metadata,
                "pinataMetadata": {
                    "name": name or f"NIL_NFT_Metadata_{metadata.get('name', 'unknown')}"
                }
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            ipfs_hash = result['IpfsHash']
            ipfs_url = f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
            
            logger.info(f"Metadata uploaded to IPFS: {ipfs_url}")
            return ipfs_url
            
        except Exception as e:
            logger.error(f"Error uploading to IPFS: {str(e)}")
            raise

    def create_nft_metadata(self, athlete_name: str, athlete_id: str, 
                           description: str, image_url: str,
                           attributes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Create standardized NFT metadata"""
        metadata = {
            "name": f"{athlete_name} Legacy NFT",
            "description": description,
            "image": image_url,
            "external_url": f"https://nilbx.com/athlete/{athlete_id}",
            "attributes": attributes or [
                {
                    "trait_type": "Athlete",
                    "value": athlete_name
                },
                {
                    "trait_type": "Type",
                    "value": "Legacy NFT"
                },
                {
                    "trait_type": "Platform",
                    "value": "NILbx"
                }
            ]
        }
        
        return metadata


def lambda_handler(event, context):
    """IPFS Lambda handler for uploading NFT metadata"""
    try:
        # Parse the request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        
        # Initialize IPFS service
        ipfs_service = IPFSService()
        
        if http_method == 'POST' and path == '/upload-metadata':
            # Create NFT metadata
            attributes_raw = body.get('attributes')
            attributes: Optional[List[Dict[str, Any]]] = attributes_raw if isinstance(attributes_raw, list) else None
            
            metadata = ipfs_service.create_nft_metadata(
                athlete_name=body['athlete_name'],
                athlete_id=body['athlete_id'],
                description=body['description'],
                image_url=body['image_url'],
                attributes=attributes
            )
            
            # Upload to IPFS
            ipfs_url = ipfs_service.upload_json_metadata(
                metadata=metadata,
                name=f"NIL_NFT_{body['athlete_name']}"
            )
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'ipfs_url': ipfs_url,
                    'metadata': metadata
                })
            }
            
        elif http_method == 'POST' and path == '/upload-json':
            # Direct JSON upload
            ipfs_url = ipfs_service.upload_json_metadata(
                metadata=body['data'],
                name=body.get('name', 'NIL_Data')
            )
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'ipfs_url': ipfs_url
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
        logger.error(f"IPFS Lambda handler error: {str(e)}")
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