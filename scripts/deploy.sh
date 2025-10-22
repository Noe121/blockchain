#!/bin/bash

# Deploy NILbx Blockchain Smart Contracts and Lambda Functions
# This script handles contract deployment and Lambda function setup

set -e

echo "🚀 Starting NILbx Blockchain Deployment..."

# Configuration
NETWORK=${1:-"sepolia"}
AWS_REGION=${2:-"us-east-1"}
PROJECT_ROOT="/Users/nicolasvalladares/NIL"
BLOCKCHAIN_DIR="$PROJECT_ROOT/blockchain"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check if required directories exist
for dir in "contracts" "lambda" "terraform"; do
    if [ ! -d "$BLOCKCHAIN_DIR/$dir" ]; then
        echo "❌ Directory $BLOCKCHAIN_DIR/$dir not found"
        exit 1
    fi
done

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure'"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not installed. Please install Terraform"
    exit 1
fi

# Check if Node.js/npm is available for Hardhat (if needed)
if ! command -v npm &> /dev/null; then
    echo "⚠️  NPM not found. Smart contract deployment will be skipped"
    SKIP_CONTRACTS=true
fi

echo "✅ Prerequisites check completed"

# Step 1: Prepare Lambda deployment packages
echo "📦 Preparing Lambda deployment packages..."

cd "$BLOCKCHAIN_DIR/lambda"

# Create deployment packages
for handler in "blockchain_handler" "ipfs_handler" "integration_handler"; do
    echo "  📦 Packaging $handler..."
    
    # Create temporary directory
    mkdir -p "temp_$handler"
    
    # Copy handler file
    cp "${handler}.py" "temp_$handler/"
    
    # Copy requirements and install dependencies
    if [ -f "requirements.txt" ]; then
        cp "requirements.txt" "temp_$handler/"
        cd "temp_$handler"
        
        # Install dependencies
        pip install -r requirements.txt -t .
        
        # Create zip file
        zip -r "../${handler}.zip" .
        
        cd ..
        
        # Clean up
        rm -rf "temp_$handler"
    else
        cd "temp_$handler"
        zip -r "../${handler}.zip" .
        cd ..
        rm -rf "temp_$handler"
    fi
    
    echo "  ✅ $handler packaged successfully"
done

# Step 2: Deploy smart contracts (if not skipped)
if [ "$SKIP_CONTRACTS" != "true" ]; then
    echo "🔗 Deploying smart contracts to $NETWORK..."
    
    cd "$BLOCKCHAIN_DIR/contracts"
    
    # Initialize Hardhat project if needed
    if [ ! -f "package.json" ]; then
        echo "  📦 Initializing Hardhat project..."
        npm init -y
        npm install --save-dev hardhat @nomiclabs/hardhat-ethers ethers @openzeppelin/contracts
        
        # Create basic Hardhat config
        cat > hardhat.config.js << EOF
require("@nomiclabs/hardhat-ethers");

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000000";
const INFURA_URL = process.env.INFURA_URL || "https://sepolia.infura.io/v3/YOUR_PROJECT_ID";

module.exports = {
  solidity: "0.8.19",
  networks: {
    sepolia: {
      url: INFURA_URL,
      accounts: [PRIVATE_KEY]
    }
  }
};
EOF
    fi
    
    # Create deployment script
    mkdir -p scripts
    cat > scripts/deploy.js << EOF
const hre = require("hardhat");

async function main() {
  console.log("Deploying contracts to", hre.network.name);

  // Deploy PlayerLegacyNFT
  const PlayerLegacyNFT = await hre.ethers.getContractFactory("PlayerLegacyNFT");
  const nftContract = await PlayerLegacyNFT.deploy();
  await nftContract.deployed();
  console.log("PlayerLegacyNFT deployed to:", nftContract.address);

  // Deploy SponsorshipContract
  const SponsorshipContract = await hre.ethers.getContractFactory("SponsorshipContract");
  const sponsorshipContract = await SponsorshipContract.deploy();
  await sponsorshipContract.deployed();  
  console.log("SponsorshipContract deployed to:", sponsorshipContract.address);

  // Save deployment info
  const fs = require('fs');
  const deploymentInfo = {
    network: hre.network.name,
    PlayerLegacyNFT: nftContract.address,
    SponsorshipContract: sponsorshipContract.address,
    timestamp: new Date().toISOString()
  };
  
  fs.writeFileSync('deployment.json', JSON.stringify(deploymentInfo, null, 2));
  console.log("Deployment info saved to deployment.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
EOF
    
    # Deploy contracts
    if [ -n "$PRIVATE_KEY" ] && [ -n "$INFURA_URL" ]; then
        echo "  🚀 Deploying to $NETWORK..."
        npx hardhat run scripts/deploy.js --network $NETWORK
        
        # Read deployment addresses
        if [ -f "deployment.json" ]; then
            NFT_ADDRESS=$(node -p "require('./deployment.json').PlayerLegacyNFT")
            SPONSORSHIP_ADDRESS=$(node -p "require('./deployment.json').SponsorshipContract")
            echo "  ✅ Contracts deployed successfully"
            echo "    NFT Contract: $NFT_ADDRESS"
            echo "    Sponsorship Contract: $SPONSORSHIP_ADDRESS"
        fi
    else
        echo "  ⚠️  PRIVATE_KEY and INFURA_URL environment variables required for deployment"
        echo "  📝 Please set these variables and run: npx hardhat run scripts/deploy.js --network $NETWORK"
    fi
else
    echo "⏭️  Skipping smart contract deployment"
fi

# Step 3: Deploy AWS infrastructure with Terraform
echo "☁️  Deploying AWS infrastructure..."

cd "$BLOCKCHAIN_DIR/terraform"

# Copy Lambda packages to terraform directory
cp ../lambda/*.zip .

# Initialize Terraform
terraform init

# Create terraform.tfvars if it doesn't exist
if [ ! -f "terraform.tfvars" ]; then
    cat > terraform.tfvars << EOF
# Network Configuration
infura_url = "$INFURA_URL"
chain_id = "11155111"

# Contract Addresses (update after deployment)
nft_contract_address = "${NFT_ADDRESS:-}"
sponsorship_contract_address = "${SPONSORSHIP_ADDRESS:-}"

# Service URLs (update for production)
auth_service_url = "http://localhost:3001"
api_service_url = "http://localhost:3000"
company_api_url = "http://localhost:3002"
EOF
    echo "  📝 Created terraform.tfvars - please update with your values"
fi

# Plan and apply
echo "  📋 Planning Terraform deployment..."
terraform plan

echo "  🚀 Applying Terraform configuration..."
terraform apply -auto-approve

# Get outputs
BLOCKCHAIN_API_URL=$(terraform output -raw blockchain_api_url 2>/dev/null || echo "")
IPFS_API_URL=$(terraform output -raw ipfs_api_url 2>/dev/null || echo "")
INTEGRATION_API_URL=$(terraform output -raw integration_api_url 2>/dev/null || echo "")

echo "✅ AWS infrastructure deployed successfully"

# Step 4: Setup AWS Secrets
echo "🔐 Setting up AWS Secrets Manager..."

# Note: These commands require manual input for security
echo "  📝 Please manually configure the following secrets in AWS Secrets Manager:"
echo "    1. nilbx-ethereum-keys: Add your PRIVATE_KEY"
echo "    2. nilbx-contract-abis: Add contract ABIs (extract from Hardhat artifacts)"
echo "    3. nilbx-ipfs-keys: Add PINATA_API_KEY and PINATA_SECRET_KEY"

# Create example secret values
cat > "$BLOCKCHAIN_DIR/example-secrets.json" << EOF
{
  "ethereum-keys": {
    "PRIVATE_KEY": "your_ethereum_private_key_here"
  },
  "contract-abis": {
    "NFT_ABI": "[]",
    "SPONSORSHIP_ABI": "[]"
  },
  "ipfs-keys": {
    "PINATA_API_KEY": "your_pinata_api_key",
    "PINATA_SECRET_KEY": "your_pinata_secret_key"
  }
}
EOF

echo "  📄 Example secrets saved to $BLOCKCHAIN_DIR/example-secrets.json"

# Step 5: Generate integration documentation
echo "📚 Generating integration documentation..."

cat > "$BLOCKCHAIN_DIR/DEPLOYMENT_SUMMARY.md" << EOF
# NILbx Blockchain Deployment Summary

## 🎯 Deployment Status

- **Date**: $(date)
- **Network**: $NETWORK
- **AWS Region**: $AWS_REGION

## 📡 API Endpoints

- **Blockchain API**: $BLOCKCHAIN_API_URL
- **IPFS API**: $IPFS_API_URL  
- **Integration API**: $INTEGRATION_API_URL

## 🔗 Smart Contracts

- **NFT Contract**: ${NFT_ADDRESS:-"Not deployed"}
- **Sponsorship Contract**: ${SPONSORSHIP_ADDRESS:-"Not deployed"}

## 🔐 Required Secrets

Configure these in AWS Secrets Manager:

1. **nilbx-ethereum-keys**
   - PRIVATE_KEY: Your Ethereum private key

2. **nilbx-contract-abis**
   - NFT_ABI: PlayerLegacyNFT contract ABI
   - SPONSORSHIP_ABI: SponsorshipContract contract ABI

3. **nilbx-ipfs-keys**
   - PINATA_API_KEY: Your Pinata API key
   - PINATA_SECRET_KEY: Your Pinata secret key

## 🛠️ Integration Examples

### Mint NFT
\`\`\`bash
curl -X POST $BLOCKCHAIN_API_URL/mint-nft \\
  -H "Content-Type: application/json" \\
  -d '{
    "athlete_address": "0x...",
    "recipient_address": "0x...",
    "token_uri": "https://ipfs.io/ipfs/...",
    "royalty_fee": 500
  }'
\`\`\`

### Create Sponsorship Task
\`\`\`bash
curl -X POST $BLOCKCHAIN_API_URL/create-task \\
  -H "Content-Type: application/json" \\
  -d '{
    "athlete_address": "0x...",
    "description": "Social media promotion",
    "amount_eth": 0.1
  }'
\`\`\`

### Upload Metadata to IPFS
\`\`\`bash
curl -X POST $IPFS_API_URL/upload-metadata \\
  -H "Content-Type: application/json" \\
  -d '{
    "athlete_name": "John Doe",
    "athlete_id": "123",
    "description": "Legacy NFT for athlete",
    "image_url": "https://example.com/image.jpg"
  }'
\`\`\`

## 🔄 Next Steps

1. Update contract addresses in terraform.tfvars
2. Configure AWS Secrets Manager
3. Test API endpoints
4. Integrate with existing NIL services
5. Update frontend to use blockchain features

## 📞 Support

For issues or questions, check the logs:
- CloudWatch Logs: /aws/lambda/nilbx-*
- API Gateway logs in AWS Console
EOF

echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Summary:"
echo "  - Lambda functions: ✅ Deployed"
echo "  - Smart contracts: ${NFT_ADDRESS:+✅ Deployed}${NFT_ADDRESS:-⏭️ Skipped}"
echo "  - AWS infrastructure: ✅ Deployed"
echo "  - Documentation: ✅ Generated"
echo ""
echo "📖 See $BLOCKCHAIN_DIR/DEPLOYMENT_SUMMARY.md for integration details"
echo "🔧 Configure AWS Secrets Manager to complete setup"