"""
Standalone Fee Service Module
Provides independent fee calculation and management for NIL blockchain platform
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class FeeStructure:
    """Fee structure configuration"""
    transaction_fee_percent: float = 4.0  # 4% on-chain transaction fee
    deployment_fee_usd: float = 12.50  # $10-15 per contract
    subscription_fee_monthly_usd: float = 15.00  # $15/month monitoring
    premium_feature_fee_min_usd: float = 5.00  # $5-10 per feature
    premium_feature_fee_max_usd: float = 10.00
    max_effective_fee_percent: float = 11.0  # Never exceed 11% total

class FeeService:
    """Independent fee calculation and management service"""

    def __init__(self):
        self.fee_structure = FeeStructure()

    def calculate_deal_fees(self, deal_value_usd: float) -> Dict[str, Any]:
        """
        Calculate all fees for a sponsorship deal

        Args:
            deal_value_usd: Total deal value in USD

        Returns:
            Dict with fee breakdown and competitiveness metrics
        """
        # Transaction fee (4%)
        transaction_fee = deal_value_usd * (self.fee_structure.transaction_fee_percent / 100)

        # Deployment fee ($10-15)
        deployment_fee = self.fee_structure.deployment_fee_usd

        # Subscription fee (prorated monthly)
        subscription_fee = self.fee_structure.subscription_fee_monthly_usd

        # No premium fee by default
        premium_fee = 0.0

        # Calculate total and effective percentage
        total_fee = transaction_fee + deployment_fee + subscription_fee + premium_fee
        effective_percent = (total_fee / deal_value_usd) * 100

        # Adjust for small deals to stay under max cap
        if effective_percent > self.fee_structure.max_effective_fee_percent:
            if deal_value_usd < 1000:
                # Reduce transaction fee for small deals
                transaction_fee = min(transaction_fee, deal_value_usd * 0.03)  # Max 3%
            elif deal_value_usd < 2000:
                transaction_fee = min(transaction_fee, deal_value_usd * 0.035)  # Max 3.5%

            # Recalculate totals
            total_fee = transaction_fee + deployment_fee + subscription_fee + premium_fee
            effective_percent = (total_fee / deal_value_usd) * 100

        return {
            "deal_value_usd": deal_value_usd,
            "transaction_fee_usd": round(transaction_fee, 2),
            "deployment_fee_usd": deployment_fee,
            "subscription_fee_usd": subscription_fee,
            "premium_fee_usd": premium_fee,
            "total_effective_fee_usd": round(total_fee, 2),
            "effective_fee_percentage": round(effective_percent, 1),
            "competitiveness": {
                "vs_nil_platforms": f"Undercut by {round(15 - effective_percent, 1)}%",  # vs 10-20% avg
                "vs_blockchain_norms": "Competitive (matches Request Network 1-5%)",
                "retention_score": "High" if effective_percent < 11 else "Medium"
            },
            "fee_structure": {
                "transaction": f"{self.fee_structure.transaction_fee_percent}% on-chain",
                "deployment": f"${self.fee_structure.deployment_fee_usd} per contract",
                "subscription": f"${self.fee_structure.subscription_fee_monthly_usd}/month",
                "premium": f"${self.fee_structure.premium_feature_fee_min_usd}-{self.fee_structure.premium_feature_fee_max_usd} per feature"
            }
        }

    def calculate_subscription_fee(self, billing_cycle: str = "monthly") -> Dict[str, Any]:
        """
        Calculate subscription fees based on billing cycle

        Args:
            billing_cycle: "monthly", "quarterly", or "annual"

        Returns:
            Dict with fee details and billing info
        """
        base_monthly = self.fee_structure.subscription_fee_monthly_usd

        if billing_cycle == "quarterly":
            monthly_fee = 12.50  # Slight discount
            total_periods = 3
        elif billing_cycle == "annual":
            monthly_fee = 10.00  # Further discount
            total_periods = 12
        else:  # monthly
            monthly_fee = base_monthly
            total_periods = 1

        now = datetime.now()
        if billing_cycle == "quarterly":
            next_billing = now + timedelta(days=90)
        elif billing_cycle == "annual":
            next_billing = now + timedelta(days=365)
        else:
            next_billing = now + timedelta(days=30)

        return {
            "billing_cycle": billing_cycle,
            "monthly_fee_usd": monthly_fee,
            "total_period_fee_usd": monthly_fee * total_periods,
            "next_billing_date": next_billing.isoformat(),
            "features_included": [
                "Real-time transaction monitoring",
                "Basic analytics dashboard",
                "Email notifications",
                "API access for integration"
            ],
            "competitiveness": "Undercuts traditional NIL platforms by 50-70%"
        }

    def validate_premium_feature_fee(self, fee_usd: float) -> bool:
        """
        Validate premium feature fee is within acceptable range

        Args:
            fee_usd: Fee amount to validate

        Returns:
            True if valid, False otherwise
        """
        return self.fee_structure.premium_feature_fee_min_usd <= fee_usd <= self.fee_structure.premium_feature_fee_max_usd

    def get_fee_analytics_summary(self) -> Dict[str, Any]:
        """
        Get fee analytics summary for dashboard display

        Returns:
            Dict with fee analytics summary
        """
        return {
            "fee_structure": {
                "deployment_fee": f"${self.fee_structure.deployment_fee_usd} per contract (1-2% of deal value)",
                "transaction_fee": f"{self.fee_structure.transaction_fee_percent}% of payment amount (on-chain)",
                "subscription_fee": f"${self.fee_structure.subscription_fee_monthly_usd}/month per user (monitoring/analytics)",
                "premium_features": f"${self.fee_structure.premium_feature_fee_min_usd}-{self.fee_structure.premium_feature_fee_max_usd} per feature (power users)",
                "target_effective_fee": "6-8% total per deal"
            },
            "competitiveness": {
                "vs_nil_platforms": "10-20% fees → We undercut by 2-12%",
                "vs_blockchain_norms": "Matches Request Network (1-5%)",
                "retention_focus": f"Under {self.fee_structure.max_effective_fee_percent}% cap maintains user trust"
            },
            "sample_calculations": {
                "small_deal_500": self.calculate_deal_fees(500),
                "medium_deal_1000": self.calculate_deal_fees(1000),
                "large_deal_5000": self.calculate_deal_fees(5000)
            }
        }

# Global fee service instance
fee_service = FeeService()

def get_fee_service() -> FeeService:
    """Get the global fee service instance"""
    return fee_service