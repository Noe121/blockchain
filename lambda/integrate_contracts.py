#!/usr/bin/env python3
"""
Contract Integration Script
Integrates compiled smart contracts with Lambda functions
"""

import json
import os
import shutil
from pathlib import Path

def load_contract_artifacts():
    """Load compiled contract artifacts (ABI and bytecode)"""
    contracts_dir = Path("../contracts/artifacts/contracts")
    lambda_dir = Path("./")
    
    artifacts = {}
    
    # Load PlayerLegacyNFT
    nft_artifact_file = contracts_dir / "PlayerLegacyNFT.sol" / "PlayerLegacyNFT.json"
    if nft_artifact_file.exists():
        with open(nft_artifact_file, 'r') as f:
            nft_data = json.load(f)
            artifacts['PlayerLegacyNFT'] = {
                'abi': nft_data['abi'],
                'bytecode': nft_data['bytecode']
            }
        print("✅ Loaded PlayerLegacyNFT artifact")
    
    # Load SponsorshipContract
    sponsorship_artifact_file = contracts_dir / "SponsorshipContract.sol" / "SponsorshipContract.json"
    if sponsorship_artifact_file.exists():
        with open(sponsorship_artifact_file, 'r') as f:
            sponsorship_data = json.load(f)
            artifacts['SponsorshipContract'] = {
                'abi': sponsorship_data['abi'],
                'bytecode': sponsorship_data['bytecode']
            }
        print("✅ Loaded SponsorshipContract artifact")
    
    # Save artifacts to Lambda directory
    artifacts_file = lambda_dir / "contract_artifacts.json"
    with open(artifacts_file, 'w') as f:
        json.dump(artifacts, f, indent=2)
    
    print(f"📄 Contract artifacts saved to {artifacts_file}")
    return artifacts

def load_deployment_info():
    """Load deployment information"""
    deployment_file = Path("../contracts/deployment.json")
    lambda_dir = Path("./")
    
    if deployment_file.exists():
        with open(deployment_file, 'r') as f:
            deployment_data = json.load(f)
        
        # Save to Lambda directory
        lambda_deployment_file = lambda_dir / "deployment_config.json"
        with open(lambda_deployment_file, 'w') as f:
            json.dump(deployment_data, f, indent=2)
        
        print(f"📄 Deployment config saved to {lambda_deployment_file}")
        return deployment_data
    else:
        print("⚠️ No deployment.json found. Run contract deployment first.")
        return None

def update_lambda_config():
    """Update Lambda function configuration with contract addresses"""
    config = {
        "ethereum": {
            "network": "sepolia",  # Change to mainnet for production
            "rpc_url_param": "/nilbx/ethereum/rpc_url",
            "private_key_param": "/nilbx/ethereum/private_key"
        },
        "contracts": {
            "player_legacy_nft": {
                "address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",  # Update with real deployment
                "abi_key": "PlayerLegacyNFT"
            },
            "sponsorship_contract": {
                "address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",  # Update with real deployment
                "abi_key": "SponsorshipContract"
            }
        },
        "ipfs": {
            "pinata_api_key_param": "/nilbx/ipfs/pinata_api_key",
            "pinata_secret_param": "/nilbx/ipfs/pinata_secret",
            "gateway_url": "https://gateway.pinata.cloud/ipfs/"
        },
        "aws": {
            "region": "us-east-1",
            "lambda_timeout": 300,
            "memory_size": 512
        }
    }
    
    config_file = Path("./lambda_config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"📄 Lambda configuration saved to {config_file}")
    return config

def create_requirements_file():
    """Create requirements.txt for Lambda deployment"""
    requirements = [
        "web3==6.12.0",
        "boto3==1.34.34",
        "requests==2.31.0",
        "eth-account==0.10.0",
        "typing-extensions==4.9.0"
    ]
    
    with open("requirements.txt", 'w') as f:
        f.write('\n'.join(requirements))
    
    print("📄 Requirements.txt created")

def main():
    """Main integration function"""
    print("🔧 Integrating smart contracts with Lambda functions...")
    
    # Create necessary files
    artifacts = load_contract_artifacts()
    deployment = load_deployment_info()
    config = update_lambda_config()
    create_requirements_file()
    
    print("\n✅ Integration complete!")
    print("\nNext steps:")
    print("1. Update contract addresses in lambda_config.json with real deployment addresses")
    print("2. Configure AWS Parameter Store with:")
    print("   - /nilbx/ethereum/rpc_url (Infura/Alchemy endpoint)")
    print("   - /nilbx/ethereum/private_key (Deployer private key)")
    print("   - /nilbx/ipfs/pinata_api_key")
    print("   - /nilbx/ipfs/pinata_secret")
    print("3. Deploy Lambda functions using AWS SAM or Serverless")
    print("4. Test the integration with your NIL application")

if __name__ == "__main__":
    main()