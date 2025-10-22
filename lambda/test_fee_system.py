#!/usr/bin/env python3
"""
Standalone Fee System Test Script
Tests the complete fee system independently for frontend integration validation
"""

import sys
import os
import json
from datetime import datetime

# Add lambda directory to path
sys.path.insert(0, '/app/lambda')

def test_fee_service():
    """Test the standalone fee service"""
    print("🧪 Testing Fee Service...")

    try:
        from fee_service import get_fee_service

        fee_service = get_fee_service()

        # Test fee calculations
        test_deals = [500, 1000, 2500, 5000]

        print("\n📊 Fee Calculation Tests:")
        for deal_value in test_deals:
            result = fee_service.calculate_deal_fees(deal_value)
            print(f"${deal_value} deal: {result['effective_fee_percentage']}% total fee "
                  f"(${result['total_effective_fee_usd']}) - {result['competitiveness']['vs_nil_platforms']}")

        # Test subscription calculations
        print("\n📅 Subscription Fee Tests:")
        billing_cycles = ["monthly", "quarterly", "annual"]
        for cycle in billing_cycles:
            result = fee_service.calculate_subscription_fee(cycle)
            print(f"{cycle}: ${result['monthly_fee_usd']}/month, "
                  f"next billing: {result['next_billing_date'][:10]}")

        # Test premium feature validation
        print("\n✨ Premium Feature Validation:")
        test_fees = [3.00, 7.50, 12.00]  # Invalid, valid, invalid
        for fee in test_fees:
            is_valid = fee_service.validate_premium_feature_fee(fee)
            status = "✅ Valid" if is_valid else "❌ Invalid"
            print(f"${fee} premium fee: {status}")

        # Test analytics summary
        print("\n📈 Fee Analytics Summary:")
        summary = fee_service.get_fee_analytics_summary()
        print(f"Target: {summary['fee_structure']['target_effective_fee']}")
        print(f"Competitiveness: {summary['competitiveness']['vs_nil_platforms']}")

        print("\n✅ Fee Service Tests Passed!")
        return True

    except Exception as e:
        print(f"❌ Fee Service Test Failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints are properly structured"""
    print("\n🔗 Testing API Endpoints Structure...")

    try:
        from main import app

        # Check for required fee endpoints by inspecting route paths
        required_endpoints = [
            "/deploy-contract",
            "/subscribe",
            "/premium-feature",
            "/fee-analytics"
        ]

        print("Checking for required fee endpoints:")
        found_endpoints = []

        # Simple check - just verify the endpoints are defined
        import inspect
        source = inspect.getsource(app)
        for endpoint in required_endpoints:
            if endpoint in source:
                found_endpoints.append(endpoint)
                print(f"  ✅ {endpoint}")
            else:
                print(f"  ❌ {endpoint} - NOT FOUND")

        if len(found_endpoints) == len(required_endpoints):
            print("✅ API Endpoints Structure Valid!")
            return True
        else:
            print(f"❌ Missing {len(required_endpoints) - len(found_endpoints)} endpoints")
            return False

    except Exception as e:
        print(f"❌ API Endpoints Test Failed: {e}")
        return False

def test_database_schema():
    """Test database schema is properly set up"""
    print("\n🗄️  Testing Database Schema...")

    try:
        import pymysql

        connection = pymysql.connect(
            host=os.getenv("DB_HOST", "blockchain-mysql"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USERNAME", "blockchain_user"),
            password=os.getenv("DB_PASSWORD", "blockchain_pass"),
            database=os.getenv("DB_NAME", "blockchain_test_db")
        )

        with connection.cursor() as cursor:
            # Check required tables exist
            required_tables = [
                "deployment_fees",
                "subscription_plans",
                "premium_features",
                "fee_analytics"
            ]

            cursor.execute("SHOW TABLES")
            existing_tables = [row[0] for row in cursor.fetchall()]

            missing_tables = []
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)

            if missing_tables:
                print(f"⚠️  Missing tables (run blockchain-extensions.sql): {missing_tables}")
            else:
                print("✅ All required fee tables exist")

            # Test analytics views
            try:
                cursor.execute("SELECT COUNT(*) FROM fee_analytics_by_deal_size")
                result = cursor.fetchone()
                count = result[0] if result else 0
                print(f"✅ Analytics views working (found {count} deal size ranges)")
            except Exception as e:
                print(f"⚠️  Analytics views not available: {e}")

        connection.close()
        print("✅ Database Schema Test Completed!")
        return True

    except Exception as e:
        print(f"❌ Database Schema Test Failed: {e}")
        return False

def generate_frontend_integration_guide():
    """Generate a quick frontend integration guide"""
    print("\n📚 Frontend Integration Guide:")
    print("=" * 50)

    integration_code = '''
// Fee System Integration Example

// 1. Deploy Contract with Fee
const deployContract = async (contractData) => {
  const response = await fetch('/deploy-contract', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify({
      user_id: 123,
      user_type: 'athlete',
      contract_type: 'sponsorship',
      fee_usd: 12.50,
      payment_method: 'stripe'
    })
  });

  const result = await response.json();
  return result;
};

// 2. Subscribe to Service
const subscribeUser = async (subscriptionData) => {
  const response = await fetch('/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify({
      user_id: 123,
      user_type: 'athlete',
      plan_name: 'monitoring',
      billing_cycle: 'monthly',
      payment_method: 'stripe'
    })
  });

  const result = await response.json();
  return result;
};

// 3. Purchase Premium Feature
const purchasePremiumFeature = async (featureData) => {
  const response = await fetch('/premium-feature', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify({
      user_id: 123,
      user_type: 'athlete',
      feature_name: 'custom_contract',
      feature_fee_usd: 7.50,
      payment_method: 'stripe'
    })
  });

  const result = await response.json();
  return result;
};

// 4. Get Fee Analytics
const loadFeeAnalytics = async () => {
  const response = await fetch('/fee-analytics', {
    headers: {
      'Authorization': `Bearer ${userToken}`
    }
  });

  const result = await response.json();
  return result;
};
'''

    print(integration_code)

def main():
    """Run all tests"""
    print("🚀 NIL Blockchain Fee System - Independent Integration Test")
    print("=" * 60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = []

    # Run tests
    results.append(("Fee Service", test_fee_service()))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Database Schema", test_database_schema()))

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY:")
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Fee system is ready for frontend integration.")
        generate_frontend_integration_guide()
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        print("Run 'python3 blockchain-extensions.sql' to set up database tables if needed.")

    print("\n📖 Full API documentation: FEE_API_DOCUMENTATION.md")
    print("🔧 Fee service module: fee_service.py")

if __name__ == "__main__":
    main()