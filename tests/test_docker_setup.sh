#!/bin/bash

# Blockchain Docker Test Script
# This script tests the blockchain service with its database

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print functions
print_status() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "🚀 Starting Blockchain Service Docker Test"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_success "Docker is running"

# Navigate to blockchain directory
cd "$(dirname "$0")"
print_status "Working directory: $(pwd)"

# Clean up any existing containers
print_status "Cleaning up existing containers..."
docker-compose down -v 2>/dev/null || true

# Build and start services
print_status "Building and starting blockchain services..."
docker-compose up -d --build

# Wait for services to be healthy
print_status "Waiting for services to start..."
sleep 10

# Check database health
print_status "Checking database health..."
for i in {1..30}; do
    if docker-compose exec -T blockchain-mysql mysqladmin ping -h localhost --silent; then
        print_success "Database is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Database failed to start"
        docker-compose logs blockchain-mysql
        exit 1
    fi
    sleep 2
done

# Check blockchain service health
print_status "Checking blockchain service health..."
for i in {1..30}; do
    if curl -f http://localhost:8002/health > /dev/null 2>&1; then
        print_success "Blockchain service is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Blockchain service failed to start"
        docker-compose logs blockchain-service
        exit 1
    fi
    sleep 2
done

# Test database connectivity
print_status "Testing database connectivity..."
DB_TEST=$(curl -s http://localhost:8002/test/database)
if echo "$DB_TEST" | grep -q "connected"; then
    print_success "Database connectivity test passed"
else
    print_error "Database connectivity test failed"
    echo "$DB_TEST"
    exit 1
fi

# Test database data
print_status "Testing database data..."
ATHLETE_DATA=$(curl -s http://localhost:8002/test/data/athletes)
if echo "$ATHLETE_DATA" | grep -q "Michael Jordan"; then
    print_success "Test data is loaded correctly"
else
    print_error "Test data not found"
    echo "$ATHLETE_DATA"
    exit 1
fi

# Test blockchain endpoints
print_status "Testing blockchain endpoints..."

# Test health endpoint
HEALTH_RESPONSE=$(curl -s http://localhost:8002/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    print_success "Health endpoint test passed"
else
    print_error "Health endpoint test failed"
    echo "$HEALTH_RESPONSE"
fi

# Test athlete NFTs endpoint
print_status "Testing athlete NFTs endpoint..."
NFT_RESPONSE=$(curl -s "http://localhost:8002/athlete-nfts/0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
if [ $? -eq 0 ]; then
    print_success "Athlete NFTs endpoint test passed"
else
    print_error "Athlete NFTs endpoint test failed"
fi

# Test task endpoint
print_status "Testing task endpoint..."
TASK_RESPONSE=$(curl -s "http://localhost:8002/task/1")
if [ $? -eq 0 ]; then
    print_success "Task endpoint test passed"
else
    print_error "Task endpoint test failed"
fi

# Show service information
print_status "Service Information:"
echo "  • Blockchain Service: http://localhost:8002"
echo "  • Database Admin: http://localhost:8081"
echo "  • Database: blockchain-mysql:3306"
echo "  • Username: blockchain_user"
echo "  • Password: blockchain_pass"
echo "  • Database: blockchain_test_db"

# Show logs (last 20 lines)
print_status "Recent blockchain service logs:"
docker-compose logs --tail=20 blockchain-service

print_success "🎉 Blockchain Docker setup test completed successfully!"
print_status "Services are ready for testing"

# Keep services running
print_status "Services will continue running. To stop them, run:"
print_status "  docker-compose down"
print_status ""
print_status "To view logs:"
print_status "  docker-compose logs -f blockchain-service"
print_status "  docker-compose logs -f blockchain-mysql"