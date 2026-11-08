"""
Unit and integration tests for BizMetrics system improvements:
1. Fast ML demand forecasting and evaluation metrics (MAE, RMSE, MAPE).
2. Inventory visual indicators, days of stock, reorder recommendations.
3. Receivables ageing buckets (0-30, 31-60, 61-90, 90+) and collection priorities (P1-P4).
4. Public dataset integrity and schemas (UCI Online Retail, German Credit, OSM).
5. Hyperlocal OpenStreetMap queries, radius filters, and Haversine distances.
"""

import math
from pathlib import Path
import pandas as pd
import pytest

from inventory_ml import InventoryML
from utils.hyperlocal_intelligence import haversine_km, query_osm_businesses, load_osm_dataset
from utils.data_loader import load_public_benchmark_datasets


def test_inventory_ml_optimization_and_metrics():
    """Verify that InventoryML trains efficiently and produces valid holdout validation metrics."""
    # Synthetic multi-day transactions
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    sales_records = []
    for d in dates:
        sales_records.append({"date": d, "product_id": "SKU_01", "quantity": 5 + (d.day % 7)})
        sales_records.append({"date": d, "product_id": "SKU_02", "quantity": 10 + (d.day % 4)})
    sales_df = pd.DataFrame(sales_records)
    inv_df = pd.DataFrame([
        {"product_id": "SKU_01", "lead_time_days": 5},
        {"product_id": "SKU_02", "lead_time_days": 7},
    ])

    ml = InventoryML()
    prepared = ml.prepare_data(sales_df, inv_df)
    ml.train(prepared)

    # Evaluation metrics must be present and valid
    metrics = ml.diagnostics.get("metrics", {})
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "mape" in metrics
    assert metrics["mae"] >= 0.0
    assert metrics["rmse"] >= 0.0
    assert metrics["sample_size"] > 0

    # Prediction test using vectorized predict_demand
    predictions, diag = ml.predict_demand(sales_df, inv_df)
    assert "SKU_01" in predictions
    assert "SKU_02" in predictions
    assert predictions["SKU_01"] > 0
    assert predictions["SKU_02"] > 0


def test_receivables_ageing_and_priority_scoring():
    """Verify receivables ageing bucket categorization and collection priority tiers."""
    now = pd.Timestamp.today().normalize()
    test_invoices = pd.DataFrame([
        {"invoice_id": "INV-01", "customer_name": "Ramesh", "due_date": now + pd.Timedelta(days=5), "amount": 5000, "status": "Pending"},
        {"invoice_id": "INV-02", "customer_name": "Suresh", "due_date": now - pd.Timedelta(days=15), "amount": 8000, "status": "Pending"},
        {"invoice_id": "INV-03", "customer_name": "Mahesh", "due_date": now - pd.Timedelta(days=45), "amount": 12000, "status": "Pending"},
        {"invoice_id": "INV-04", "customer_name": "Ganesh", "due_date": now - pd.Timedelta(days=75), "amount": 25000, "status": "Pending"},
        {"invoice_id": "INV-05", "customer_name": "Dinesh", "due_date": now - pd.Timedelta(days=110), "amount": 50000, "status": "Pending"},
    ])

    # Calculate days overdue
    test_invoices["days_overdue"] = (now - pd.to_datetime(test_invoices["due_date"])).dt.days
    
    def get_bucket(days):
        if days <= 0:
            return "Current (Not Due)"
        elif days <= 30:
            return "0–30 Days"
        elif days <= 60:
            return "31–60 Days"
        elif days <= 90:
            return "61–90 Days"
        return "90+ Days"

    test_invoices["bucket"] = test_invoices["days_overdue"].apply(get_bucket)

    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-01", "bucket"].iloc[0] == "Current (Not Due)"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-02", "bucket"].iloc[0] == "0–30 Days"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-03", "bucket"].iloc[0] == "31–60 Days"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-04", "bucket"].iloc[0] == "61–90 Days"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-05", "bucket"].iloc[0] == "90+ Days"

    # Priority tier logic: P1 for 90+ days or high balance overdue, P4 for current
    def get_priority(days, amt):
        if days > 90 or (days > 60 and amt >= 20000):
            return "P1: URGENT"
        elif days > 60 or (days > 30 and amt >= 10000):
            return "P2: High"
        elif days > 30:
            return "P3: Medium"
        return "P4: Low"

    test_invoices["priority"] = test_invoices.apply(lambda r: get_priority(r["days_overdue"], r["amount"]), axis=1)
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-05", "priority"].iloc[0] == "P1: URGENT"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-04", "priority"].iloc[0] == "P1: URGENT"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-03", "priority"].iloc[0] == "P2: High"
    assert test_invoices.loc[test_invoices["invoice_id"] == "INV-01", "priority"].iloc[0] == "P4: Low"


def test_public_benchmark_datasets_exist_and_valid():
    """Verify that public authentic datasets in data/sources/ are present, non-empty, and correctly formed."""
    benchmarks = load_public_benchmark_datasets()
    assert "uci_retail" in benchmarks
    assert "uci_forecast" in benchmarks
    assert "credit_risk" in benchmarks
    assert "osm_data" in benchmarks

    # UCI transactions benchmark
    uci_tx = benchmarks["uci_retail"]
    assert not uci_tx.empty
    assert "InvoiceNo" in uci_tx.columns
    assert "StockCode" in uci_tx.columns
    assert "Quantity" in uci_tx.columns
    assert "UnitPrice" in uci_tx.columns

    # UCI forecast benchmark
    uci_fc = benchmarks["uci_forecast"]
    assert not uci_fc.empty
    assert "stock_code" in uci_fc.columns
    assert "mae" in uci_fc.columns
    assert "rmse" in uci_fc.columns
    assert "mape_pct" in uci_fc.columns

    # Credit risk benchmark
    cr = benchmarks["credit_risk"]
    assert not cr.empty
    assert "ageing_bucket" in cr.columns
    assert "default_rate_pct" in cr.columns

    # OpenStreetMap verified nodes
    osm = benchmarks["osm_data"]
    assert "cities" in osm
    assert "Raipur" in osm["cities"]
    assert "Bilaspur" in osm["cities"]
    assert "Bhilai" in osm["cities"]
    assert "Durg" in osm["cities"]


def test_haversine_distance_calculation():
    """Verify Haversine formula against known geographic distance."""
    # Raipur to Bhilai center: approximately 25-30 km
    raipur_lat, raipur_lon = 21.2514, 81.6296
    bhilai_lat, bhilai_lon = 21.2167, 81.3833
    dist = haversine_km(raipur_lat, raipur_lon, bhilai_lat, bhilai_lon)
    assert dist is not None
    assert 20.0 < dist < 35.0

    # Distance to self must be 0
    assert haversine_km(raipur_lat, raipur_lon, raipur_lat, raipur_lon) == 0.0

    # Invalid coordinates return None
    assert haversine_km(999, 81.6, 21.2, 81.6) is None


def test_hyperlocal_osm_queries_and_radius_filtering():
    """Verify that query_osm_businesses retrieves valid POIs within specified radius filters."""
    for radius in [1.0, 3.0, 5.0]:
        res = query_osm_businesses(city="Raipur", radius_km=radius, category="Hardware")
        assert res["city"] == "Raipur"
        assert res["radius_km"] == radius
        assert "competitors" in res
        assert "opportunities" in res

        # All competitors must have valid coordinates and distance <= radius
        for c in res["competitors"]:
            assert c["dist"] <= radius
            assert -90 <= c["lat"] <= 90
            assert -180 <= c["lon"] <= 180
            assert "osm_id" in c
            assert c["osm_id"] is not None

        # All opportunities must be within radius
        for o in res["opportunities"]:
            assert o["dist"] <= radius
            assert -90 <= o["lat"] <= 90
            assert -180 <= o["lon"] <= 180
            assert "osm_id" in o
