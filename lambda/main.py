"""
FastAPI wrapper for blockchain Lambda functions - Local Testing
"""
import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# AWS Lambda handler using Mangum
from mangum import Mangum

# Add lambda directory to path
sys.path.insert(0, '/app/lambda')

# Import blockchain handlers (with conditional imports)
try:
    from blockchain_handler import lambda_handler as blockchain_lambda
    BLOCKCHAIN_AVAILABLE = True
except ImportError as e:
    print(f"Warning: blockchain_handler not available: {e}")
    BLOCKCHAIN_AVAILABLE = False

try:
    from ipfs_handler import lambda_handler as ipfs_lambda
    IPFS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ipfs_handler not available: {e}")
    IPFS_AVAILABLE = False

try:
    from integration_handler import lambda_handler as integration_lambda, NILIntegrationService
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: integration_handler not available: {e}")
    INTEGRATION_AVAILABLE = False

try:
    from fee_service import get_fee_service
    FEE_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: fee_service not available: {e}")
    FEE_SERVICE_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Blockchain Service - Local Testing",
    description="Local testing environment for blockchain Lambda functions",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class NFTMintRequest(BaseModel):
    athlete_address: str
    recipient_address: str
    token_uri: str
    royalty_fee: int = 500

class SponsorshipTaskRequest(BaseModel):
    athlete_address: str
    description: str
    amount_eth: float

class TaskApprovalRequest(BaseModel):
    task_id: int

class DeployContractRequest(BaseModel):
    user_id: int
    user_type: str  # "athlete" or "sponsor"
    contract_type: str  # "sponsorship", "nft", "custom"
    fee_usd: float = 12.50  # $10-15 range
    payment_method: str = "stripe"  # "stripe", "crypto", "wallet"

class SubscribeRequest(BaseModel):
    user_id: int
    user_type: str  # "athlete" or "sponsor"
    plan_name: str = "monitoring"  # "monitoring", "analytics", "premium"
    billing_cycle: str = "monthly"  # "monthly", "quarterly", "annual"
    payment_method: str = "stripe"  # "stripe", "crypto"

class PremiumFeatureRequest(BaseModel):
    user_id: int
    user_type: str  # "athlete" or "sponsor"
    feature_name: str  # "custom_contract", "priority_oracle", "advanced_analytics", etc.
    feature_fee_usd: float  # $5-10 per feature
    payment_method: str = "stripe"  # "stripe", "crypto", "wallet"
    feature_config: Optional[Dict[str, Any]] = None

# Health check
@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "blockchain-local",
        "handlers": {
            "blockchain": BLOCKCHAIN_AVAILABLE,
            "ipfs": IPFS_AVAILABLE,
            "integration": INTEGRATION_AVAILABLE
        },
        "environment": {
            "db_host": os.getenv("DB_HOST", "localhost"),
            "chain_id": os.getenv("CHAIN_ID", "11155111"),
            "infura_configured": bool(os.getenv("INFURA_URL"))
        }
    }

# NFT Endpoints
@app.post("/mint-nft")
async def mint_nft(request: NFTMintRequest):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="Blockchain handler not available")
    
    # Convert to Lambda event format
    event = {
        "httpMethod": "POST",
        "path": "/mint-nft",
        "body": json.dumps(request.dict()),
        "headers": {"Content-Type": "application/json"}
    }
    
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}"))
        )
    except Exception as e:
        logger.error(f"NFT minting error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/athlete-nfts/{athlete_address}")
async def get_athlete_nfts(athlete_address: str):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="Blockchain handler not available")
    
    event = {
        "httpMethod": "GET", 
        "path": f"/athlete-nfts/{athlete_address}",
        "pathParameters": {"athlete_address": athlete_address}
    }
    
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}"))
        )
    except Exception as e:
        logger.error(f"Get athlete NFTs error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Sponsorship Endpoints
@app.post("/create-task")
async def create_sponsorship_task(request: SponsorshipTaskRequest):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="Blockchain handler not available")
    
    event = {
        "httpMethod": "POST",
        "path": "/create-task",
        "body": json.dumps(request.dict()),
        "headers": {"Content-Type": "application/json"}
    }
    
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}"))
        )
    except Exception as e:
        logger.error(f"Create task error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve-task")
async def approve_task(request: TaskApprovalRequest):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="Blockchain handler not available")
    
    event = {
        "httpMethod": "POST",
        "path": "/approve-task",
        "body": json.dumps(request.dict()),
        "headers": {"Content-Type": "application/json"}
    }
    
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}"))
        )
    except Exception as e:
        logger.error(f"Approve task error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy-contract")
async def deploy_contract(request: DeployContractRequest):
    """Deploy a smart contract with fee collection"""
    try:
        # Deploy contract with fee recording
        integration_handler = NILIntegrationService()
        result = integration_handler.record_deployment_fee(
            request.user_id, request.user_type, request.contract_type, request.fee_usd
        )
        
        return {
            "success": True,
            "deployment_fee_usd": request.fee_usd,
            "contract_type": request.contract_type,
            "competitiveness": result.get('competitiveness', 'Competitive deployment fees'),
            "fee_breakdown": {
                "deployment_fee": request.fee_usd,
                "effective_percentage": f"{(request.fee_usd / 1000) * 100:.1f}%"  # Assuming $1000 deal
            }
        }
        
    except Exception as e:
        logger.error(f"Deploy contract error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deployment fee processing failed: {str(e)}")

@app.post("/subscribe")
async def subscribe_user(request: SubscribeRequest):
    """Subscribe user to monitoring/analytics service ($15/month)"""
    try:
        # Calculate billing dates
        from datetime import datetime, timedelta
        
        now = datetime.now()
        if request.billing_cycle == "monthly":
            next_billing = now + timedelta(days=30)
            monthly_fee = 15.00
        elif request.billing_cycle == "quarterly":
            next_billing = now + timedelta(days=90)
            monthly_fee = 12.50  # Slight discount for longer commitment
        elif request.billing_cycle == "annual":
            next_billing = now + timedelta(days=365)
            monthly_fee = 10.00  # Further discount for annual
        else:
            monthly_fee = 15.00
            next_billing = now + timedelta(days=30)
        
        # Record subscription fee using integration handler
        integration_handler = NILIntegrationService()
        result = integration_handler.record_subscription_fee(
            request.user_id, request.user_type, request.plan_name, monthly_fee
        )
        
        return {
            "success": True,
            "user_id": request.user_id,
            "user_type": request.user_type,
            "plan_name": request.plan_name,
            "monthly_fee_usd": monthly_fee,
            "billing_cycle": request.billing_cycle,
            "payment_method": request.payment_method,
            "next_billing_date": next_billing.isoformat(),
            "subscription_status": "active",
            "competitiveness": result.get('competitiveness', 'Competitive subscription pricing'),
            "message": f"Subscription activated for ${monthly_fee}/month. Next billing: {next_billing.strftime('%Y-%m-%d')}",
            "features_included": [
                "Real-time transaction monitoring",
                "Basic analytics dashboard",
                "Email notifications",
                "API access for integration"
            ] + (["Advanced analytics", "Custom reports"] if request.plan_name == "premium" else [])
        }
        
    except Exception as e:
        logger.error(f"Subscribe user error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription processing failed: {str(e)}")

@app.post("/premium-feature")
async def purchase_premium_feature(request: PremiumFeatureRequest):
    """Purchase premium feature ($5-10 per feature)"""
    try:
        # Validate feature fee is within acceptable range
        if not 5.00 <= request.feature_fee_usd <= 10.00:
            raise HTTPException(
                status_code=400, 
                detail="Premium feature fee must be between $5 and $10"
            )
        
        # Record premium feature fee using integration handler
        integration_handler = NILIntegrationService()
        result = integration_handler.record_premium_fee(
            request.user_id, request.user_type, request.feature_name, request.feature_fee_usd
        )
        
        return {
            "success": True,
            "user_id": request.user_id,
            "user_type": request.user_type,
            "feature_name": request.feature_name,
            "feature_fee_usd": request.feature_fee_usd,
            "payment_method": request.payment_method,
            "payment_status": "pending",
            "feature_config": request.feature_config,
            "competitiveness": result.get('competitiveness', 'Flexible premium features'),
            "message": f"Premium feature '{request.feature_name}' purchase initiated for ${request.feature_fee_usd}. Complete payment to activate.",
            "estimated_activation_time": "2-5 minutes after payment confirmation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Premium feature purchase error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Premium feature purchase failed: {str(e)}")

@app.get("/fee-analytics")
async def get_fee_analytics():
    """Get fee analytics and total effective fee calculations from DynamoDB"""
    try:
        from dynamodb_service import get_dynamodb_service
        dynamodb = get_dynamodb_service()

        analytics = dynamodb.get_fee_analytics()

        # Get fee service summary if available
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
            "fee_structure": fee_summary.get('fee_structure', {
                "deployment_fee": "$10-15 per contract (1-2% of deal value)",
                "transaction_fee": "4% of payment amount (on-chain)",
                "subscription_fee": "$15/month per user (monitoring/analytics)",
                "premium_features": "$5-10 per feature (power users)",
                "target_effective_fee": "6-8% total per deal"
            }),
            "competitiveness": fee_summary.get('competitiveness', {
                "vs_nil_platforms": "10-20% fees → We undercut by 2-12%",
                "vs_blockchain_norms": "Matches Request Network (1-5%)",
                "retention_focus": "Under 11% cap maintains user trust"
            }),
            "sample_calculations": fee_summary.get('sample_calculations', {})
        }

    except Exception as e:
        logger.error(f"Fee analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fee analytics retrieval failed: {str(e)}")

@app.get("/task/{task_id}")
async def get_task(task_id: int):
    if not BLOCKCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="Blockchain handler not available")
    
    event = {
        "httpMethod": "GET",
        "path": f"/task/{task_id}",
        "pathParameters": {"task_id": str(task_id)}
    }
    
    try:
        response = blockchain_lambda(event, {})
        return JSONResponse(
            status_code=response.get("statusCode", 200),
            content=json.loads(response.get("body", "{}"))
        )
    except Exception as e:
        logger.error(f"Get task error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Database endpoints for testing
@app.get("/test/database")
async def test_database():
    """Test DynamoDB connectivity"""
    try:
        import boto3  # type: ignore
        from dynamodb_service import get_dynamodb_service
        dynamodb = get_dynamodb_service()

        # Test basic connectivity by trying to get table description
        try:
            table_desc = dynamodb.table.meta.client.describe_table(TableName=dynamodb.table_name)
            table_status = table_desc['Table']['TableStatus']
        except Exception as e:
            table_status = f"Error: {str(e)}"

        # Get some basic counts using scan (not efficient for production)
        try:
            # Count users
            user_response = dynamodb.table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('PK').begins_with('USER#') & boto3.dynamodb.conditions.Attr('SK').eq('METADATA')
            )
            user_count = len(user_response.get('Items', []))

            # Count contracts
            contract_response = dynamodb.table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('SK').eq('METADATA') & boto3.dynamodb.conditions.Attr('PK').begins_with('CONTRACT#')
            )
            contract_count = len(contract_response.get('Items', []))

            # Count transactions
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
            "counts": {
                "users": user_count,
                "contracts": contract_count,
                "transactions": tx_count
            },
            "region": os.getenv('AWS_REGION', 'us-east-1'),
            "billing_mode": "PAY_PER_REQUEST"
        }
    except Exception as e:
        logger.error(f"DynamoDB test error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"DynamoDB connection failed: {str(e)}")

# Test data endpoints
@app.get("/test/data/athletes")
async def get_test_athletes():
    """Get test athlete data from DynamoDB"""
    try:
        from dynamodb_service import get_dynamodb_service
        dynamodb = get_dynamodb_service()

        # Scan for user items (simplified - in production use more specific queries)
        import boto3  # type: ignore
        response = dynamodb.table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('PK').begins_with('USER#') & boto3.dynamodb.conditions.Attr('SK').eq('METADATA')
        )

        athletes = []
        for item in response.get('Items', []):
            if item.get('role') == 'athlete':
                athletes.append({
                    'user_id': item['PK'].replace('USER#', ''),
                    'email': item.get('email', ''),
                    'role': item.get('role', ''),
                    'created_at': item.get('created_at', '')
                })

        return {"athletes": athletes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# AWS Lambda handler using Mangum
handler = Mangum(app)

# Alternative simple Lambda handler for testing
def lambda_handler(event, context):
    """Simple Lambda handler that can handle both direct calls and API Gateway events"""
    try:
        # Check if it's an API Gateway event (has requestContext)
        if 'requestContext' in event or 'httpMethod' in event:
            # Use Mangum for API Gateway events
            return handler(event, context)
        
        # Direct Lambda call (simple JSON)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'healthy',
                'service': 'nil-blockchain-api',
                'message': 'Lambda function is working',
                'environment': os.getenv('ENVIRONMENT', 'unknown'),
                'dynamodb_table': os.getenv('DYNAMODB_TABLE', 'unknown')
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }
