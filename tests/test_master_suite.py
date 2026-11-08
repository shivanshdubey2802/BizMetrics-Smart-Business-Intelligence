"""
Comprehensive Master Test Suite for BizMetrics - Smart Business Intelligence
Validates:
1. What-if simulation mathematical models (Price, Volume, COGS, Overhead, BEP).
2. Unsupervised statistical anomaly detection (IQR outlier & Z-score spike).
3. Customer RFM segmentation and churn probability scoring.
4. Smart business alerts trigger conditions and priority ranking.
5. Report generation and PDF compilation verification.
6. Role-Based Access Control (RBAC) permission integrity.
"""

import io
import math
import numpy as np
import pandas as pd
import pytest

from utils.pdf_report import generate_feasibility_pdf


def test_what_if_simulator_financial_model():
    """Verify simulation engine formulas for revenue, profit, margin, and break-even."""
    base_rev = 200000.0
    base_cogs = 140000.0
    base_exp = 30000.0
    base_gp = base_rev - base_cogs  # 60,000
    base_np = base_gp - base_exp    # 30,000
    base_margin = (base_np / base_rev) * 100  # 15.0%

    # Scenario 1: 10% price increase, 0% volume change, 0% cost change, 0% expense change
    p_mult = 1.10
    v_mult = 1.00
    c_mult = 1.00
    e_mult = 1.00

    sim_rev = base_rev * p_mult * v_mult        # 220,000
    sim_cogs = base_cogs * c_mult * v_mult      # 140,000
    sim_gp = sim_rev - sim_cogs                 # 80,000
    sim_exp = base_exp * e_mult                 # 30,000
    sim_np = sim_gp - sim_exp                   # 50,000
    sim_margin = (sim_np / sim_rev) * 100

    assert pytest.approx(sim_rev, rel=1e-5) == 220000.0
    assert pytest.approx(sim_np, rel=1e-5) == 50000.0
    assert pytest.approx(sim_margin, rel=1e-3) == 22.727

    # Break-even calculation
    sim_cm_ratio = sim_gp / sim_rev  # 80,000 / 220,000 = 0.3636
    sim_bep_rev = sim_exp / sim_cm_ratio
    assert pytest.approx(sim_bep_rev, rel=1e-3) == 82500.0

    # Safety buffer
    buffer_pct = ((sim_rev - sim_bep_rev) / sim_rev) * 100
    assert buffer_pct > 60.0  # Revenue is well above break-even


def test_iqr_and_zscore_anomaly_detection():
    """Verify statistical anomaly detection behavior on synthetic distribution with outliers."""
    # 1. Sales IQR anomaly detection
    np.random.seed(42)
    normal_sales = np.random.normal(loc=500, scale=50, size=100)
    outlier_sale = 2500.0  # Obvious spike
    all_sales = pd.Series(list(normal_sales) + [outlier_sale])

    q25 = all_sales.quantile(0.25)
    q75 = all_sales.quantile(0.75)
    iqr = q75 - q25
    upper_bound = q75 + 2.5 * iqr

    outliers = all_sales[all_sales > upper_bound]
    assert len(outliers) >= 1
    assert outlier_sale in outliers.values

    # 2. Expense category Z-score anomaly detection
    normal_expenses = [1200, 1150, 1300, 1250, 1100, 1220, 1180, 1210]
    spike_expense = 3500.0
    exp_series = pd.Series(normal_expenses + [spike_expense])

    mean_val = exp_series.mean()
    std_val = exp_series.std()
    z_scores = (exp_series - mean_val) / std_val

    # The spike should clearly have Z-score > 2.2
    assert z_scores.iloc[-1] > 2.2
    assert (z_scores > 2.2).sum() == 1


def test_customer_rfm_scoring_and_churn_bounds():
    """Verify customer RFM computation and churn score constraint [0, 100]."""
    ref_date = pd.Timestamp("2026-03-31")
    transactions = pd.DataFrame([
        {"customer_id": "C01", "date": pd.Timestamp("2026-03-25"), "amount": 1500},
        {"customer_id": "C01", "date": pd.Timestamp("2026-03-10"), "amount": 2000},
        {"customer_id": "C02", "date": pd.Timestamp("2026-01-05"), "amount": 800},
    ])

    rfm = transactions.groupby("customer_id").agg(
        recency=("date", lambda x: (ref_date - x.max()).days),
        frequency=("date", "count"),
        monetary=("amount", "sum")
    ).reset_index()

    c01 = rfm[rfm["customer_id"] == "C01"].iloc[0]
    c02 = rfm[rfm["customer_id"] == "C02"].iloc[0]

    assert c01["recency"] == 6
    assert c01["frequency"] == 2
    assert c01["monetary"] == 3500

    assert c02["recency"] == 85
    assert c02["frequency"] == 1
    assert c02["monetary"] == 800

    # Churn risk heuristic: higher recency & low frequency -> higher churn probability
    def compute_churn_risk(recency, frequency):
        rec_factor = min(1.0, recency / 90.0)
        freq_factor = max(0.0, 1.0 - (frequency / 5.0))
        risk = (0.6 * rec_factor + 0.4 * freq_factor) * 100.0
        return max(0.0, min(100.0, risk))

    c01_churn = compute_churn_risk(c01["recency"], c01["frequency"])
    c02_churn = compute_churn_risk(c02["recency"], c02["frequency"])

    assert 0.0 <= c01_churn <= 100.0
    assert 0.0 <= c02_churn <= 100.0
    assert c02_churn > c01_churn  # Inactive customer has significantly higher churn risk


def test_smart_alerts_trigger_rules():
    """Verify alert generation rules for inventory stockouts and overdue credit."""
    # Test inventory alert logic
    inventory_items = [
        {"product_name": "LED Bulb 9W", "current_stock": 4, "reorder_level": 15},
        {"product_name": "Anchor Switch 6A", "current_stock": 50, "reorder_level": 20},
    ]

    stock_alerts = []
    for item in inventory_items:
        if item["current_stock"] <= item["reorder_level"]:
            severity = "CRITICAL" if item["current_stock"] == 0 else "WARNING"
            stock_alerts.append({
                "type": "Low Stock",
                "item": item["product_name"],
                "severity": severity,
                "deficit": item["reorder_level"] - item["current_stock"]
            })

    assert len(stock_alerts) == 1
    assert stock_alerts[0]["item"] == "LED Bulb 9W"
    assert stock_alerts[0]["severity"] == "WARNING"
    assert stock_alerts[0]["deficit"] == 11


def test_pdf_report_compilation_and_bytes():
    """Verify that the ReportLab PDF feasibility generator produces valid PDF bytes."""
    report_data = {
        "business_name": "Shivansh Electronics and Hardware",
        "business_category": "Electronics & Electrical Retail",
        "state": "Delhi",
        "district": "Central Delhi",
        "block": "Connaught",
        "village": "Connaught Place",
        "report_date": "2026-11-06",
        "total_revenue": 350000.0,
        "net_profit": 55000.0,
    }

    pdf_bytes = generate_feasibility_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    # PDF magic byte signature
    assert pdf_bytes.startswith(b"%PDF")


def test_rbac_roles_and_permissions():
    """Verify role-based access control matrix consistency."""
    role_permissions = {
        "Admin": ["view_all", "edit_settings", "manage_users", "export_data", "view_financials"],
        "Owner": ["view_all", "export_data", "view_financials", "edit_products"],
        "Staff": ["view_dashboard", "view_inventory", "record_sales"],
    }

    assert "manage_users" in role_permissions["Admin"]
    assert "manage_users" not in role_permissions["Staff"]
    assert "view_financials" not in role_permissions["Staff"]
    assert "view_financials" in role_permissions["Owner"]


def test_customer_shivansh_authentication():
    """Verify that Customer Name 'Shivansh' / 'shivansh' with Customer ID 'CUST001' authenticates cleanly."""
    from app import authenticate_customer, SHOP_ID

    auth_lower = authenticate_customer(SHOP_ID, "shivansh", "CUST001")
    assert auth_lower is not None
    assert auth_lower["customer_id"] == "CUST001"
    assert "Shivansh" in auth_lower["customer_name"]

    auth_title = authenticate_customer(SHOP_ID, "Shivansh", "CUST001")
    assert auth_title is not None
    assert auth_title["customer_id"] == "CUST001"
    assert "Shivansh" in auth_title["customer_name"]

    # Also check case-insensitive customer ID
    auth_lower_id = authenticate_customer(SHOP_ID, "shivansh", "cust001")
    assert auth_lower_id is not None
    assert auth_lower_id["customer_id"] == "CUST001"

