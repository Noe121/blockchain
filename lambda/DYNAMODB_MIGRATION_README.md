# NIL Blockchain - DynamoDB Migration

## Overview
The NIL blockchain platform has been migrated from MySQL to DynamoDB to leverage AWS serverless architecture, improve scalability, and reduce costs while maintaining the same API interfaces for seamless frontend integration.

## Architecture Changes

### Before (MySQL)
- Multiple relational tables: `deployment_fees`, `subscription_plans`, `premium_features`, `fee_analytics`
- Complex JOIN queries for analytics
- Vertical scaling limitations
- Fixed infrastructure costs

### After (DynamoDB)
- Single-table design: `SmartContractData`
- Serverless scaling with pay-per-request billing
- Optimized query patterns using PK/SK and GSIs
- Cost-effective for variable workloads

## DynamoDB Schema

### Table: SmartContractData
- **Primary Key**: PK (HASH), SK (RANGE)
- **GSI1**: Wallet-based queries (GSI1PK, GSI1SK)
- **GSI2**: Time-based analytics (GSI2PK, GSI2SK)
- **Billing**: PAY_PER_REQUEST
- **TTL**: 90 days on `created_at`

### Data Patterns

#### Users
```
PK: USER#{user_id}
SK: METADATA
Attributes: email, role, created_at
```

#### Contracts
```
PK: CONTRACT#{contract_id}
SK: METADATA
Attributes: user_id, athlete_wallet, sponsor_wallet, address, abi, appearances_required, payment_amount, platform_fee_percent, deployment_fee, created_at
GSI1PK: WALLET#{athlete_wallet}
GSI1SK: CONTRACT#{created_at}
GSI2PK: CONTRACT
GSI2SK: {created_at}
```

#### Transactions
```
PK: CONTRACT#{contract_id}
SK: TX#{tx_id}
Attributes: tx_hash, type, amount, recipient_wallet, created_at
GSI1PK: WALLET#{recipient_wallet}
GSI1SK: TX#{created_at}
GSI2PK: TX
GSI2SK: {created_at}
```

#### Fees (Deployment, Subscription, Premium)
```
PK: FEE#{fee_id} | USER#{user_id}
SK: DEPLOYMENT | SUB#{sub_id} | PREMIUM#{feature_id}
Attributes: user_id, fee_usd, status, created_at
GSI1PK: USER#{user_id}
GSI1SK: FEE#{created_at} | SUB#{created_at} | PREMIUM#{created_at}
GSI2PK: FEE | SUB | PREMIUM
GSI2SK: {created_at}
```

## Migration Benefits

### Cost Efficiency
- **Pay-per-request**: ~$1.25/million writes vs. RDS fixed costs
- **No over-provisioning**: Scales automatically with usage
- **TTL archiving**: Automatic data lifecycle management

### Performance
- **Single-digit millisecond responses** for most queries
- **Global Secondary Indexes** for efficient wallet and time-based queries
- **Parallel scans** for analytics workloads

### Scalability
- **Unlimited throughput** with pay-per-request
- **Global tables** support for multi-region deployment
- **No storage limits** (scales to petabytes)

### Operational
- **Serverless**: No infrastructure management
- **High availability**: 99.99% SLA
- **Automatic backups** and point-in-time recovery

## API Compatibility

All existing API endpoints remain unchanged:
- `POST /deploy-contract` - Contract deployment with fees
- `POST /subscribe` - User subscriptions ($15/month)
- `POST /premium-feature` - Premium features ($5-10)
- `GET /fee-analytics` - Comprehensive analytics

## Implementation Files

### Core Services
- `dynamodb_service.py` - DynamoDB operations layer
- `fee_service.py` - Fee calculation logic (unchanged)
- `integration_handler.py` - Updated to use DynamoDB
- `main.py` - API endpoints (DynamoDB integration)

### Infrastructure
- `create_dynamodb_table.sh` - Table creation script
- `FEE_API_DOCUMENTATION.md` - Frontend integration guide

## Setup Instructions

### 1. Create DynamoDB Table
```bash
cd /Users/nicolasvalladares/NIL/blockchain/lambda
chmod +x create_dynamodb_table.sh
./create_dynamodb_table.sh
```

### 2. Update Environment Variables
```bash
# Lambda environment variables
DYNAMODB_TABLE=SmartContractData
AWS_REGION=us-east-1
```

### 3. Deploy Lambda Functions
The Lambda functions will automatically use DynamoDB instead of MySQL.

### 4. Test Migration
```bash
# Test database connectivity
curl http://localhost:8000/test/database

# Test fee analytics
curl http://localhost:8000/fee-analytics
```

## Query Patterns

### Get User Contracts
```python
# Query: PK=USER#{user_id}, SK begins_with CONTRACT
response = dynamodb.query(
    KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('CONTRACT')
)
```

### Track Platform Fees
```python
# Query GSI1: GSI1PK=WALLET#{platform_wallet}, GSI1SK begins_with TX
response = dynamodb.query(
    IndexName='GSI1',
    KeyConditionExpression=Key('GSI1PK').eq(f'WALLET#{platform_wallet}') & Key('GSI1SK').begins_with('TX')
)
```

### Analytics by Date Range
```python
# Query GSI2: GSI2PK=TX, GSI2SK between start_date and end_date
response = dynamodb.query(
    IndexName='GSI2',
    KeyConditionExpression=Key('GSI2PK').eq('TX') & Key('GSI2SK').between(start_date, end_date)
)
```

## Monitoring & Optimization

### CloudWatch Metrics
- **ConsumedReadCapacityUnits**
- **ConsumedWriteCapacityUnits**
- **ThrottledRequests**
- **SuccessfulRequestLatency**

### Cost Optimization
- Use GSI sparingly for write-heavy patterns
- Implement TTL for historical data
- Batch writes where possible
- Use parallel scans for analytics

### Performance Tuning
- Monitor hot partitions
- Use write sharding for high-throughput patterns
- Implement exponential backoff for throttled requests

## Migration Validation

### Fee Structure Maintained
- Transaction Fee: 4% (on-chain)
- Deployment Fee: $10-15 per contract
- Subscription Fee: $15/month
- Premium Features: $5-10 per feature
- Target: 6-8% effective fees

### API Compatibility
- All endpoints return identical response formats
- Frontend integration requires no changes
- Error handling preserved

### Data Integrity
- All fee calculations remain accurate
- Analytics queries provide same insights
- NIL compliance reporting maintained

## Cost Comparison

| Metric | MySQL (RDS) | DynamoDB |
|--------|-------------|----------|
| Base Cost | $0.10/hour (~$73/month) | $0 |
| Storage | $0.115/GB/month | $0.25/GB/month |
| I/O | Included | Pay-per-request |
| Scaling | Vertical limits | Unlimited |
| Backup | Additional cost | Included |

For 10,000 transactions/month:
- **MySQL**: ~$100/month (fixed) + I/O costs
- **DynamoDB**: ~$0.25/month (pay-per-request)

## Next Steps

1. **Monitor Performance**: Track CloudWatch metrics for 2-4 weeks
2. **Optimize Queries**: Fine-tune GSI usage based on access patterns
3. **Implement Caching**: Add DAX for frequently accessed data
4. **Global Expansion**: Consider global tables for multi-region deployment
5. **Advanced Analytics**: Implement DynamoDB Streams for real-time processing

The migration maintains full API compatibility while providing superior scalability, cost efficiency, and performance for the NIL blockchain platform.