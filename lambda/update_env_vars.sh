#!/bin/bash
# Update Lambda Environment Variables Script
# Updates environment variables for NIL blockchain Lambda functions

set -e

# Configuration
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-nil-blockchain-api}"
REGION="${AWS_REGION:-us-east-1}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-SmartContractData}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

echo "🔧 Updating Lambda Environment Variables"
echo "========================================"
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

# Check if Lambda function exists
if ! aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    echo "❌ Lambda function '$LAMBDA_FUNCTION_NAME' does not exist in region '$REGION'"
    echo "   Run deploy_lambda.sh first to create the function"
    exit 1
fi

# Update environment variables
echo "📝 Updating environment variables..."
aws lambda update-function-configuration \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --environment "Variables={
        DYNAMODB_TABLE=$DYNAMODB_TABLE,
        AWS_REGION=$REGION,
        ENVIRONMENT=$ENVIRONMENT
    }" \
    --region "$REGION"

echo "✅ Environment variables updated successfully"

# Verify the update
echo "🔍 Verifying environment variables..."
sleep 3

ENV_VARS=$(aws lambda get-function-configuration \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json)

echo "📋 Current Environment Variables:"
echo "$ENV_VARS" | jq -r 'to_entries[] | "  \(.key): \(.value)"'

echo
echo "🎉 Environment variables update completed!"
echo
echo "💡 Note: Lambda functions may take a few minutes to reflect environment variable changes"