#!/bin/bash

# Consolidated Blockchain Deployment Script
# Handles all deployment aspects in a single script

set -e

# Configuration
ENVIRONMENT=${1:-"development"}
AWS_REGION=${2:-"us-east-1"}

echo "🚀 Starting Consolidated Blockchain Deployment for $ENVIRONMENT..."

# Load environment configuration
if [ -f "config/$ENVIRONMENT.env" ]; then
    source "config/$ENVIRONMENT.env"
    echo "✅ Loaded $ENVIRONMENT configuration"
else
    echo "❌ Configuration file config/$ENVIRONMENT.env not found"
    exit 1
fi

# Function to check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose not found. Please install Docker Compose"
        exit 1
    fi
    
    # Check AWS CLI (for production)
    if [ "$ENVIRONMENT" = "production" ] && ! command -v aws &> /dev/null; then
        echo "❌ AWS CLI not found. Please install AWS CLI"
        exit 1
    fi
    
    echo "✅ Prerequisites check completed"
}

# Function to deploy development environment
deploy_development() {
    echo "🛠️ Deploying development environment..."
    
    # Copy development config
    cp config/development.env .env
    
    # Start Docker services
    docker-compose down -v 2>/dev/null || true
    docker-compose up -d --build
    
    # Wait for services
    echo "⏳ Waiting for services to start..."
    sleep 30
    
    # Run tests
    if [ -f "tests/test_docker_setup.sh" ]; then
        chmod +x tests/test_docker_setup.sh
        ./tests/test_docker_setup.sh
    fi
    
    echo "✅ Development environment deployed successfully"
    echo "🌐 Access points:"
    echo "  • Blockchain API: http://localhost:8002"
    echo "  • Database Admin: http://localhost:8081"
    echo "  • API Documentation: http://localhost:8002/docs"
}

# Function to deploy production environment
deploy_production() {
    echo "☁️ Deploying production environment..."
    
    # Check AWS credentials
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        echo "❌ AWS credentials not configured"
        exit 1
    fi
    
    # Deploy infrastructure (if terraform exists)
    if [ -d "../NILbx-env" ]; then
        echo "🏗️ Deploying infrastructure via NILbx-env..."
        cd ../NILbx-env
        terraform init
        terraform apply -auto-approve
        cd -
        echo "✅ Infrastructure deployed"
    else
        echo "⚠️ NILbx-env not found, skipping infrastructure deployment"
    fi
    
    # Deploy contracts (if contracts directory exists and configured)
    if [ -d "contracts" ] && [ -n "$INFURA_URL" ] && [ -n "$PRIVATE_KEY" ]; then
        echo "🔗 Deploying smart contracts..."
        cd contracts
        npm install
        npx hardhat run scripts/deploy.js --network mainnet
        cd -
        echo "✅ Smart contracts deployed"
    else
        echo "⚠️ Skipping smart contract deployment (missing configuration or contracts)"
    fi
    
    echo "✅ Production deployment completed"
}

# Function to cleanup resources
cleanup() {
    echo "🧹 Cleaning up resources..."
    
    if [ "$ENVIRONMENT" = "development" ]; then
        docker-compose down -v
        echo "✅ Docker containers stopped and removed"
    fi
}

# Main deployment logic
main() {
    check_prerequisites
    
    case $ENVIRONMENT in
        "development")
            deploy_development
            ;;
        "production")
            deploy_production
            ;;
        *)
            echo "❌ Invalid environment: $ENVIRONMENT"
            echo "Usage: $0 [development|production] [aws-region]"
            exit 1
            ;;
    esac
    
    echo "🎉 Deployment completed successfully!"
}

# Trap cleanup on exit
trap cleanup EXIT

# Run main function
main
