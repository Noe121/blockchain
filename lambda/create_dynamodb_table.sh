#!/bin/bash
# Create DynamoDB SmartContractData table for NIL blockchain platform

# Set AWS region
AWS_REGION=${AWS_REGION:-us-east-1}

echo "Creating SmartContractData table in region: $AWS_REGION"

# Create the table with single-table design
aws dynamodb create-table \
    --table-name SmartContractData \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
        AttributeName=GSI1PK,AttributeType=S \
        AttributeName=GSI1SK,AttributeType=S \
        AttributeName=GSI2PK,AttributeType=S \
        AttributeName=GSI2SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"GSI1\",
                \"KeySchema\": [
                    {\"AttributeName\": \"GSI1PK\", \"KeyType\": \"HASH\"},
                    {\"AttributeName\": \"GSI1SK\", \"KeyType\": \"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\": \"ALL\"},
                \"ProvisionedThroughput\": {
                    \"ReadCapacityUnits\": 5,
                    \"WriteCapacityUnits\": 5
                }
            },
            {
                \"IndexName\": \"GSI2\",
                \"KeySchema\": [
                    {\"AttributeName\": \"GSI2PK\", \"KeyType\": \"HASH\"},
                    {\"AttributeName\": \"GSI2SK\", \"KeyType\": \"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\": \"ALL\"},
                \"ProvisionedThroughput\": {
                    \"ReadCapacityUnits\": 5,
                    \"WriteCapacityUnits\": 5
                }
            }
        ]" \
    --billing-mode PAY_PER_REQUEST \
    --region $AWS_REGION

# Wait for table to be created
echo "Waiting for table creation..."
aws dynamodb wait table-exists --table-name SmartContractData --region $AWS_REGION

# Enable TTL for automatic data archiving
echo "Enabling TTL for created_at attribute..."
aws dynamodb update-table \
    --table-name SmartContractData \
    --time-to-live-specification \
        "Enabled=true,AttributeName=created_at" \
    --region $AWS_REGION

# Verify table creation
echo "Verifying table creation..."
aws dynamodb describe-table --table-name SmartContractData --region $AWS_REGION --query 'Table.[TableName,TableStatus,BillingModeSummary.BillingMode]'

echo "✅ SmartContractData table created successfully!"
echo ""
echo "Table Details:"
echo "- Name: SmartContractData"
echo "- Primary Key: PK (HASH), SK (RANGE)"
echo "- GSIs: GSI1 (wallet queries), GSI2 (time-based queries)"
echo "- Billing: PAY_PER_REQUEST"
echo "- TTL: Enabled on created_at (90 days retention)"
echo ""
echo "Next steps:"
echo "1. Update Lambda environment variables:"
echo "   DYNAMODB_TABLE=SmartContractData"
echo "   AWS_REGION=$AWS_REGION"
echo "2. Test the Lambda functions"
echo "3. Monitor CloudWatch for performance metrics"