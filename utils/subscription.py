"""
BizMetrics Subscription & License Management Engine
Manages Free, Basic, and Premium subscription tiers, validates feature allowances,
and verifies payment gateway integrations without fabricating transactions.
"""
from __future__ import annotations

import os
from typing import Any, Optional
import streamlit as st
from utils.database import get_db_cursor, DEFAULT_SHOP_ID

PLANS = {
    "Free": {
        "name": "Community / Free",
        "price_inr": 0,
        "billing": "Forever Free",
        "badge": "Free Tier",
        "limits": {
            "max_shops": 1,
            "max_monthly_tx": 100,
            "max_customers": 50,
            "ai_advisor": False,
            "hyperlocal_gis": False,
            "scheduled_reports": False,
            "custom_export": False,
        },
        "description": "Essential single-branch bookkeeping and basic financial P&L reporting."
    },
    "Basic": {
        "name": "Professional / Basic",
        "price_inr": 999,
        "billing": "₹999 / month",
        "badge": "Active Plan",
        "limits": {
            "max_shops": 3,
            "max_monthly_tx": 5000,
            "max_customers": 500,
            "ai_advisor": True,
            "hyperlocal_gis": True,
            "scheduled_reports": True,
            "custom_export": True,
        },
        "description": "Full MSME ERP intelligence, ML demand forecasting, receivables risk radar, and customer self-service portal."
    },
    "Premium": {
        "name": "Enterprise / Premium",
        "price_inr": 2499,
        "billing": "₹2,499 / month",
        "badge": "Enterprise Tier",
        "limits": {
            "max_shops": 999,
            "max_monthly_tx": 999999,
            "max_customers": 999999,
            "ai_advisor": True,
            "hyperlocal_gis": True,
            "scheduled_reports": True,
            "custom_export": True,
        },
        "description": "Unlimited branch networking, multi-role RBAC, custom spatial GIS catchments, and priority AI intelligence."
    }
}


def get_current_subscription(shop_id: str = DEFAULT_SHOP_ID) -> dict[str, Any]:
    """Retrieve the active subscription status for the enterprise."""
    plan_key = st.session_state.get("active_subscription_plan", "Basic")
    plan_info = PLANS.get(plan_key, PLANS["Basic"])

    # Count real usage from database
    with get_db_cursor(commit=False) as cur:
        tx_count = cur.execute("SELECT count(*) FROM sales_transactions").fetchone()[0]
        cust_count = cur.execute("SELECT count(*) FROM customers").fetchone()[0]
        shop_count = cur.execute("SELECT count(*) FROM shops").fetchone()[0]

    gateway_status = check_payment_gateway_status()

    return {
        "plan_key": plan_key,
        "plan_name": plan_info["name"],
        "price_inr": plan_info["price_inr"],
        "billing": plan_info["billing"],
        "status": "Active",
        "valid_until": "2026-12-01",
        "limits": plan_info["limits"],
        "description": plan_info["description"],
        "usage": {
            "shops": shop_count,
            "max_shops": plan_info["limits"]["max_shops"],
            "transactions": tx_count,
            "max_monthly_tx": plan_info["limits"]["max_monthly_tx"],
            "customers": cust_count,
            "max_customers": plan_info["limits"]["max_customers"],
        },
        "gateway": gateway_status
    }


def set_subscription_plan(new_plan: str) -> bool:
    """Update active plan in session for demo purposes."""
    if new_plan in PLANS:
        st.session_state["active_subscription_plan"] = new_plan
        from utils.audit_logger import log_audit_event
        log_audit_event(
            username="Shivansh G",
            action_type="ADMIN",
            entity_type="SUBSCRIPTION",
            entity_id=new_plan,
            details=f"Switched subscription tier to {new_plan}"
        )
        return True
    return False


def check_payment_gateway_status() -> dict[str, Any]:
    """Inspect whether live payment gateway credentials are configured."""
    razor_key = os.environ.get("RAZORPAY_KEY_ID")
    razor_secret = os.environ.get("RAZORPAY_KEY_SECRET")

    if razor_key and razor_secret:
        return {
            "configured": True,
            "gateway": "Razorpay Payments",
            "mode": "Live Production / Test API Active",
            "message": "Payment gateway configured for automated recurring billing."
        }
    return {
        "configured": False,
        "gateway": "Razorpay / Stripe",
        "mode": "Enterprise Local Mode",
        "message": "Payment credentials not configured in .env. Platform operates in self-hosted license mode."
    }

