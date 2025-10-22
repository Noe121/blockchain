#!/bin/bash
# NIL Blockchain Lambda Deployment Script
# Automates deployment of Lambda functions with DynamoDB integration

set -e

# Configuration
LAMBDA_FUNCTION_NAME="nil-blockchain-api"
REGION="${AWS_REGION:-us-east-1}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-SmartContractData}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

echo "🚀 Deploying NIL Blockchain Lambda Functions"
echo "=========================================="
echo "Function: $LAMBDA_FUNCTION_NAME"
echo "Region: $REGION"
echo "DynamoDB Table: $DYNAMODB_TABLE"
echo "Environment: $ENVIRONMENT"
echo

# Check AWS CLI configuration
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Create deployment package
echo "📦 Creating deployment package..."
cd "$(dirname "$0")"

# Clean up any existing package
rm -f lambda-deployment.zip
rm -rf package/

# Create package directory
mkdir -p package

# Install dependencies
echo "📦 Installing dependencies..."
python3 -m pip install -r requirements.txt -t package/

# Copy source files
cp dynamodb_service.py integration_handler.py main.py fee_service.py requirements.txt pyrightconfig.json package/

# Create zip package
cd package
zip -r ../lambda-deployment.zip . -x "*.pyc" "__pycache__/*" "*.git*" "*test*" "*.log"

echo "✅ Deployment package created"

# Check if Lambda function exists
if aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    echo "🔄 Updating existing Lambda function..."

    # Update function code
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --zip-file fileb://lambda-deployment.zip \
        --region "$REGION"

    echo "✅ Function code updated"

    # Update environment variables
    aws lambda update-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --environment "Variables={
            DYNAMODB_TABLE=$DYNAMODB_TABLE,
            ENVIRONMENT=$ENVIRONMENT
        }" \
        --region "$REGION"

    echo "✅ Environment variables updated"

else
    echo "🆕 Creating new Lambda function..."

    # Create IAM role for Lambda (if it doesn't exist)
    ROLE_NAME="nil-blockchain-lambda-role"
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "")

    if [ -z "$ROLE_ARN" ]; then
        echo "🔧 Creating IAM role for Lambda..."

        # Create trust policy
        cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

        # Create role
        aws iam create-role \
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document file://trust-policy.json

        # Attach basic execution role
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

        # Attach DynamoDB policy
        cat > dynamodb-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:$REGION:*:table/$DYNAMODB_TABLE",
                "arn:aws:dynamodb:$REGION:*:table/$DYNAMODB_TABLE/index/*"
            ]
        }
    ]
}
EOF

        aws iam put-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-name "DynamoDBAccess" \
            --policy-document file://dynamodb-policy.json

        # Wait for role to propagate
        echo "⏳ Waiting for IAM role to propagate..."
        sleep 10

        ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
    fi

    # Create Lambda function
    aws lambda create-function \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --runtime python3.9 \
        --role "$ROLE_ARN" \
        --handler main.app \
        --zip-file fileb://lambda-deployment.zip \
        --environment "Variables={
            DYNAMODB_TABLE=$DYNAMODB_TABLE,
            ENVIRONMENT=$ENVIRONMENT
        }" \
        --timeout 30 \
        --memory-size 256 \
        --region "$REGION"

    echo "✅ Lambda function created"
fi

# Verify deployment
echo "🔍 Verifying deployment..."
sleep 5

# Get function configuration
FUNCTION_INFO=$(aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --region "$REGION")

# Extract environment variables
ENV_VARS=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Environment.Variables')

echo "📋 Deployment Summary:"
echo "  Function Name: $LAMBDA_FUNCTION_NAME"
echo "  Runtime: $(echo "$FUNCTION_INFO" | jq -r '.Configuration.Runtime')"
echo "  Handler: $(echo "$FUNCTION_INFO" | jq -r '.Configuration.Handler')"
echo "  Memory: $(echo "$FUNCTION_INFO" | jq -r '.Configuration.MemorySize')MB"
echo "  Timeout: $(echo "$FUNCTION_INFO" | jq -r '.Configuration.Timeout')s"
echo "  Environment Variables:"
echo "$ENV_VARS" | jq -r 'to_entries[] | "    \(.key): \(.value)"'

# Test function (optional)
read -p "🧪 Do you want to test the Lambda function? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Testing Lambda function..."

    # Test payload
    TEST_PAYLOAD='{"test": "deployment"}'
    echo "$TEST_PAYLOAD" > test-payload.json

    # Invoke function
    aws lambda invoke \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --payload file://test-payload.json \
        --region "$REGION" \
        response.json

    echo "📄 Test response:"
    cat response.json
    rm test-payload.json response.json
fi

# Clean up
rm -f lambda-deployment.zip trust-policy.json dynamodb-policy.json
rm -rf package/

echo
echo "🎉 Lambda deployment completed successfully!"
echo
echo "📖 Next Steps:"
echo "  1. Update API Gateway to point to this Lambda function"
echo "  2. Run seed_data.py to populate initial data (optional)"
echo "  3. Test all endpoints with real data"
echo
echo "🔗 Useful Commands:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME --payload '{\"test\": \"hello\"}' response.json --region $REGION"
echo "  aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $REGION"