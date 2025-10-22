#!/bin/bash

# Manual Testing Script for Blockchain Service
# Run this after docker-compose up -d

echo "🧪 Blockchain Service Manual Tests"
echo "=================================="

BASE_URL="http://localhost:8002"

echo ""
echo "1. Health Check:"
curl -s "$BASE_URL/health" | jq '.' || echo "jq not available, showing raw response:" && curl -s "$BASE_URL/health"

echo ""
echo "2. Database Test:"
curl -s "$BASE_URL/test/database" | jq '.' || curl -s "$BASE_URL/test/database"

echo ""
echo "3. Test Athletes Data:"
curl -s "$BASE_URL/test/data/athletes" | jq '.athletes[0]' || curl -s "$BASE_URL/test/data/athletes"

echo ""
echo "4. Get Athlete NFTs (Michael Jordan):"
curl -s "$BASE_URL/athlete-nfts/0x70997970C51812dc3A010C7d01b50e0d17dc79C8" | jq '.' || curl -s "$BASE_URL/athlete-nfts/0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

echo ""
echo "5. Get Task #1:"
curl -s "$BASE_URL/task/1" | jq '.' || curl -s "$BASE_URL/task/1"

echo ""
echo "6. Test NFT Minting (if blockchain handler available):"
curl -X POST "$BASE_URL/mint-nft" \
  -H "Content-Type: application/json" \
  -d '{
    "athlete_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "recipient_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
    "token_uri": "ipfs://QmTest123",
    "royalty_fee": 750
  }' | jq '.' 2>/dev/null || echo "NFT minting test completed (check logs for details)"

echo ""
echo "=================================="
echo "Tests completed!"
echo ""
echo "Access points:"
echo "• Blockchain API: http://localhost:8002"
echo "• Database Admin: http://localhost:8081"
echo "• API Documentation: http://localhost:8002/docs"
echo ""
echo "Database access:"
echo "• Host: localhost:3307"
echo "• User: blockchain_user"
echo "• Pass: blockchain_pass"
echo "• DB: blockchain_test_db"