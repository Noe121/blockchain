# NIL Blockchain Fee System API Documentation

## Overview
The NIL blockchain fee system provides a comprehensive, non-custodial fee structure that achieves 6-8% total effective fees while maintaining competitiveness in the NIL sponsorship market.

## Fee Structure
- **Transaction Fee**: 4% (on-chain, automated via smart contract)
- **Deployment Fee**: $10-15 per contract (off-chain service fee)
- **Subscription Fee**: $15/month (monitoring/analytics service)
- **Premium Features**: $5-10 per feature (flexible add-ons)

## API Endpoints

### Base URL
```
http://localhost:8000  (local development)
https://api.nil-blockchain.com  (production)
```

### Authentication
All endpoints require authentication via JWT token in Authorization header:
```
Authorization: Bearer <jwt_token>
```

---

## 1. Deploy Contract with Fee Collection

**Endpoint:** `POST /deploy-contract`

**Description:** Deploy a smart contract with automatic fee collection and recording.

**Request Body:**
```json
{
  "user_id": 123,
  "user_type": "athlete",
  "contract_type": "sponsorship",
  "fee_usd": 12.50,
  "payment_method": "stripe"
}
```

**Response:**
```json
{
  "success": true,
  "deployment_fee_usd": 12.50,
  "contract_type": "sponsorship",
  "competitiveness": "Undercuts traditional deployment costs by 60-80%",
  "fee_breakdown": {
    "deployment_fee": 12.50,
    "effective_percentage": "1.3%"
  }
}
```

**Frontend Integration:**
```javascript
const deployContract = async (contractData) => {
  const response = await fetch('/deploy-contract', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify(contractData)
  });

  const result = await response.json();
  if (result.success) {
    showSuccessMessage(`Contract deployed! Fee: $${result.deployment_fee_usd}`);
    updateFeeAnalytics(result.fee_breakdown);
  }
};
```

---

## 2. Subscribe to Monitoring Service

**Endpoint:** `POST /subscribe`

**Description:** Subscribe user to monitoring/analytics service ($15/month).

**Request Body:**
```json
{
  "user_id": 123,
  "user_type": "athlete",
  "plan_name": "monitoring",
  "billing_cycle": "monthly",
  "payment_method": "stripe"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": 123,
  "user_type": "athlete",
  "plan_name": "monitoring",
  "monthly_fee_usd": 15.00,
  "billing_cycle": "monthly",
  "payment_method": "stripe",
  "next_billing_date": "2025-11-21T10:30:00",
  "subscription_status": "active",
  "competitiveness": "Undercuts traditional NIL platforms by 50-70%",
  "message": "Subscription activated for $15.00/month. Next billing: 2025-11-21",
  "features_included": [
    "Real-time transaction monitoring",
    "Basic analytics dashboard",
    "Email notifications",
    "API access for integration"
  ]
}
```

**Frontend Integration:**
```javascript
const subscribeUser = async (subscriptionData) => {
  const response = await fetch('/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify(subscriptionData)
  });

  const result = await response.json();
  if (result.success) {
    showSuccessMessage(result.message);
    updateSubscriptionStatus(result);
  }
};
```

---

## 3. Purchase Premium Feature

**Endpoint:** `POST /premium-feature`

**Description:** Purchase premium feature ($5-10 per feature).

**Request Body:**
```json
{
  "user_id": 123,
  "user_type": "athlete",
  "feature_name": "custom_contract",
  "feature_fee_usd": 7.50,
  "payment_method": "stripe",
  "feature_config": {
    "template": "sponsorship_v2",
    "custom_fields": ["social_media_links", "performance_metrics"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "user_id": 123,
  "user_type": "athlete",
  "feature_name": "custom_contract",
  "feature_fee_usd": 7.50,
  "payment_method": "stripe",
  "payment_status": "pending",
  "feature_config": {
    "template": "sponsorship_v2",
    "custom_fields": ["social_media_links", "performance_metrics"]
  },
  "competitiveness": "Flexible premium features undercutting enterprise solutions",
  "message": "Premium feature 'custom_contract' purchase initiated for $7.50. Complete payment to activate.",
  "estimated_activation_time": "2-5 minutes after payment confirmation"
}
```

**Frontend Integration:**
```javascript
const purchasePremiumFeature = async (featureData) => {
  const response = await fetch('/premium-feature', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify(featureData)
  });

  const result = await response.json();
  if (result.success) {
    showSuccessMessage(result.message);
    updatePremiumFeatures(result);
  }
};
```

---

## 4. Get Fee Analytics

**Endpoint:** `GET /fee-analytics`

**Description:** Get comprehensive fee analytics and performance metrics.

**Response:**
```json
{
  "success": true,
  "analytics": {
    "by_deal_size": [
      {
        "deal_size_range": "$0-1K",
        "total_deals": 25,
        "avg_deal_value": 650.00,
        "avg_total_fee": 44.25,
        "avg_fee_percentage": 6.8,
        "total_revenue": 1106.25
      }
    ],
    "overall": {
      "total_deals": 150,
      "avg_deal_value": 2500.00,
      "avg_total_fee": 165.00,
      "avg_fee_percentage": 6.6,
      "total_revenue": 24750.00,
      "min_fee_percentage": 5.2,
      "max_fee_percentage": 8.1
    },
    "top_users": [
      {
        "user_id": 123,
        "user_type": "athlete",
        "user_name": "John Doe",
        "total_deals": 5,
        "total_deal_value": 15000.00,
        "total_fees_paid": 975.00,
        "avg_fee_percentage": 6.5
      }
    ]
  },
  "fee_structure": {
    "deployment_fee": "$10-15 per contract (1-2% of deal value)",
    "transaction_fee": "4% of payment amount (on-chain)",
    "subscription_fee": "$15/month per user (monitoring/analytics)",
    "premium_features": "$5-10 per feature (power users)",
    "target_effective_fee": "6-8% total per deal"
  },
  "competitiveness": {
    "vs_nil_platforms": "10-20% fees → We undercut by 2-12%",
    "vs_blockchain_norms": "Matches Request Network (1-5%)",
    "retention_focus": "Under 11% cap maintains user trust"
  }
}
```

**Frontend Integration:**
```javascript
const loadFeeAnalytics = async () => {
  const response = await fetch('/fee-analytics', {
    headers: {
      'Authorization': `Bearer ${userToken}`
    }
  });

  const result = await response.json();
  if (result.success) {
    updateAnalyticsDashboard(result.analytics);
    displayCompetitivenessMetrics(result.competitiveness);
  }
};
```

---

## Fee Calculation Examples

### Small Deal ($500)
```javascript
// Frontend calculation preview
const feePreview = {
  deal_value: 500,
  transaction_fee: 500 * 0.04,     // $20
  deployment_fee: 12.50,           // $12.50
  subscription_fee: 15.00,         // $15
  total_fee: 47.50,                // $47.50
  effective_percentage: 9.5        // 9.5%
};
```

### Medium Deal ($1,000)
```javascript
const feePreview = {
  deal_value: 1000,
  transaction_fee: 40.00,          // $40
  deployment_fee: 12.50,           // $12.50
  subscription_fee: 15.00,         // $15
  total_fee: 67.50,                // $67.50
  effective_percentage: 6.8        // 6.8%
};
```

### Large Deal ($5,000)
```javascript
const feePreview = {
  deal_value: 5000,
  transaction_fee: 200.00,         // $200
  deployment_fee: 12.50,           // $12.50
  subscription_fee: 15.00,         // $15
  total_fee: 227.50,               // $227.50
  effective_percentage: 4.6        // 4.6%
};
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message description"
}
```

**Common HTTP Status Codes:**
- `200`: Success
- `400`: Bad Request (validation error)
- `401`: Unauthorized
- `500`: Internal Server Error

---

## Frontend Integration Checklist

- [ ] Implement authentication token management
- [ ] Create fee calculation preview components
- [ ] Add subscription management UI
- [ ] Implement premium feature purchase flow
- [ ] Build analytics dashboard
- [ ] Add error handling and user feedback
- [ ] Implement payment processing integration
- [ ] Add loading states and progress indicators

## Testing the API

### Start the service:
```bash
cd /Users/nicolasvalladares/NIL/blockchain/lambda
python3 main.py
```

### Test endpoints:
```bash
# Health check
curl http://localhost:8000/health

# Test database connection
curl http://localhost:8000/test/database

# Get fee analytics
curl http://localhost:8000/fee-analytics
```

---

## Deployment Notes

1. **Environment Variables Required:**
   - `DB_HOST`: Database host
   - `DB_PORT`: Database port
   - `DB_USERNAME`: Database username
   - `DB_PASSWORD`: Database password
   - `DB_NAME`: Database name

2. **Database Setup:**
   - Run `blockchain-extensions.sql` to create fee tables
   - Ensure MySQL 8.0+ with JSON support

3. **Dependencies:**
   - fastapi
   - uvicorn
   - pymysql
   - pydantic

The fee system is completely independent and can be integrated into any frontend application using standard REST API calls.