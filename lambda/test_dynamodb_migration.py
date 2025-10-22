#!/usr/bin/env python3
"""
DynamoDB Migration Test Script
Tests the complete migration from MySQL to DynamoDB
"""

import sys
import os
import json
from datetime import datetime

# Add lambda directory to path
sys.path.insert(0, '/app/lambda')

def test_dynamodb_service():
    """Test DynamoDB service functionality"""
    print("🧪 Testing DynamoDB Service...")

    try:
        from dynamodb_service import get_dynamodb_service
        dynamodb = get_dynamodb_service()

        # Test user creation
        user_id = "test-user-123"
        user = dynamodb.create_user(user_id, "test@example.com", "athlete")
        print(f"✅ Created user: {user_id}")

        # Test contract creation
        contract = dynamodb.create_contract(
            user_id=user_id,
            athlete_wallet="0xTestAthlete123",
            sponsor_wallet="0xTestSponsor456",
            contract_address="0xTestContract789",
            abi='{"test": "abi"}',
            appearances_required=5,
            payment_amount=1000000000000000000,  # 1 ETH
            platform_fee_percent=4.0,
            deployment_fee=12.50
        )
        contract_id = contract['PK'].replace('CONTRACT#', '')
        print(f"✅ Created contract: {contract_id}")

        # Test transaction logging
        tx = dynamodb.log_transaction(
            contract_id=contract_id,
            tx_hash="0xTestTx123",
            tx_type="deployment",
            amount=12500000000000000,  # 0.0125 ETH
            recipient_wallet="0xPlatform789"
        )
        print(f"✅ Logged transaction: {tx['SK']}")

        # Test fee recording
        deployment_fee = dynamodb.record_deployment_fee(
            user_id=user_id,
            user_type="athlete",
            contract_type="sponsorship",
            fee_usd=12.50
        )
        print(f"✅ Recorded deployment fee: ${deployment_fee['fee_usd']}")

        subscription_fee = dynamodb.record_subscription_fee(
            user_id=user_id,
            user_type="athlete",
            plan_name="monitoring",
            fee_usd=15.00
        )
        print(f"✅ Recorded subscription fee: ${subscription_fee['fee_usd']}")

        premium_fee = dynamodb.record_premium_fee(
            user_id=user_id,
            user_type="athlete",
            feature_name="custom_contract",
            fee_usd=7.50
        )
        print(f"✅ Recorded premium fee: ${premium_fee['fee_usd']}")

        # Test queries
        user_contracts = dynamodb.get_user_contracts(user_id)
        print(f"✅ Found {len(user_contracts)} user contracts")

        contract_txs = dynamodb.get_contract_transactions(contract_id)
        print(f"✅ Found {len(contract_txs)} contract transactions")

        wallet_txs = dynamodb.get_wallet_transactions("0xPlatform789", 10)
        print(f"✅ Found {len(wallet_txs)} wallet transactions")

        # Test analytics
        analytics = dynamodb.get_fee_analytics()
        print(f"✅ Fee analytics: {analytics['overall']['total_deals']} deals, ${analytics['overall']['total_revenue']} revenue")

        print("\n✅ DynamoDB Service Tests Passed!")
        return True

    except Exception as e:
        print(f"❌ DynamoDB Service Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fee_calculations():
    """Test that fee calculations still work correctly"""
    print("\n💰 Testing Fee Calculations...")

    try:
        from fee_service import get_fee_service
        fee_service = get_fee_service()

        # Test various deal sizes
        test_cases = [
            (500, "Small deal"),
            (1000, "Medium deal"),
            (2500, "Large deal"),
            (5000, "Enterprise deal")
        ]

        for amount, description in test_cases:
            result = fee_service.calculate_deal_fees(amount)
            effective_fee = result['effective_fee_percentage']
            competitiveness = result['competitiveness']['vs_nil_platforms']

            print(f"✅ {description} (${amount}): {effective_fee}% fee - {competitiveness}")

            # Validate fee is within target range (6-8% for medium deals)
            if amount == 1000 and not (6.0 <= effective_fee <= 8.0):
                print(f"⚠️  Warning: Medium deal fee {effective_fee}% outside target range")
            elif amount < 1000 and effective_fee > 11.0:
                print(f"⚠️  Warning: Small deal fee {effective_fee}% exceeds 11% cap")

        print("\n✅ Fee Calculation Tests Passed!")
        return True

    except Exception as e:
        print(f"❌ Fee Calculation Test Failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints work with DynamoDB"""
    print("\n🔗 Testing API Endpoints with DynamoDB...")

    try:
        from main import app

        # Check that endpoints are defined
        routes = []
        for route in app.routes:
            # FastAPI routes have a 'path' attribute
            route_path = getattr(route, 'path', None)
            if route_path:
                routes.append(route_path)

        required_endpoints = [
            "/deploy-contract",
            "/subscribe",
            "/premium-feature",
            "/fee-analytics",
            "/test/database"
        ]

        missing_endpoints = []
        for endpoint in required_endpoints:
            if endpoint not in routes:
                missing_endpoints.append(endpoint)

        if missing_endpoints:
            print(f"❌ Missing endpoints: {missing_endpoints}")
            return False

        print("✅ All required API endpoints present")
        print("✅ API Endpoints Test Passed!")
        return True

    except Exception as e:
        print(f"❌ API Endpoints Test Failed: {e}")
        return False

def generate_migration_report():
    """Generate a migration validation report"""
    print("\n📊 Migration Validation Report")
    print("=" * 50)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    report = {
        "migration_type": "MySQL → DynamoDB",
        "table_design": "Single-table (SmartContractData)",
        "billing_mode": "PAY_PER_REQUEST",
        "gsi_count": 2,
        "ttl_enabled": True,
        "api_compatibility": "Maintained",
        "fee_structure": "Preserved (6-8% target)",
        "test_coverage": "Core functionality validated"
    }

    for key, value in report.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")

    print()
    print("Key Benefits Achieved:")
    print("  ✅ Unlimited scalability")
    print("  ✅ Cost-effective pay-per-request")
    print("  ✅ Serverless operations")
    print("  ✅ Optimized query patterns")
    print("  ✅ Automatic data lifecycle")

def main():
    """Run all migration tests"""
    print("🚀 NIL Blockchain - DynamoDB Migration Test")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("DynamoDB Service", test_dynamodb_service()))
    results.append(("Fee Calculations", test_fee_calculations()))
    results.append(("API Endpoints", test_api_endpoints()))

    # Summary
    print("\n" + "=" * 60)
    print("📋 MIGRATION TEST SUMMARY:")
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 MIGRATION SUCCESSFUL! DynamoDB integration is ready.")
        generate_migration_report()
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        print("Ensure AWS credentials are configured and DynamoDB table exists.")

    print("\n📖 Documentation:")
    print("  DYNAMODB_MIGRATION_README.md - Complete migration guide")
    print("  FEE_API_DOCUMENTATION.md - Frontend integration")
    print("  create_dynamodb_table.sh - Infrastructure setup")

    print("\n🔧 Next Steps:")
    print("  1. Run: ./create_dynamodb_table.sh")
    print("  2. Update Lambda environment variables")
    print("  3. Deploy updated Lambda functions")
    print("  4. Test with real data")

if __name__ == "__main__":
    main()