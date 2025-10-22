#!/bin/bash

# NILbx Blockchain Deployment Commands
# Run these commands in sequence after setting environment variables

echo "Setting up environment variables..."
export INFURA_URL="https://sepolia.infura.io/v3/YOUR_PROJECT_ID"
export PRIVATE_KEY="your_ethereum_private_key"
export PINATA_API_KEY="your_pinata_api_key"
export PINATA_SECRET_KEY="your_pinata_secret_key"

echo "1. Deploy smart contracts..."
cd contracts
npm install
npx hardhat run scripts/deploy.js --network sepolia

echo "2. Package Lambda functions..."
cd ../lambda
./package_lambdas.sh

echo "3. Deploy AWS infrastructure..."
cd ../terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

echo "4. Configure secrets..."
echo "Please manually configure AWS Secrets Manager with:"
echo "  - nilbx-ethereum-keys"
echo "  - nilbx-contract-abis"
echo "  - nilbx-ipfs-keys"

echo "5. Test endpoints..."
echo "Use the test requests in test_requests.json"
