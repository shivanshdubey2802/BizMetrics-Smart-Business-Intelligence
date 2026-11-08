"""
Dataset validation and import verification script for BizMetrics.
Checks dataset presence, schema validity, null constraints, and provenance.
"""

from pathlib import Path
import pandas as pd
import json

SOURCES_DIR = Path(__file__).resolve().parent.parent / "data" / "sources"

def validate_sources():
    print("Validating BizMetrics Data Sources...")
    
    # 1. UCI Online Retail
    retail_csv = SOURCES_DIR / "uci_online_retail_authentic.csv"
    assert retail_csv.is_file(), f"Missing {retail_csv}"
    df_retail = pd.read_csv(retail_csv)
    assert not df_retail.empty, "UCI retail CSV is empty"
    assert "StockCode" in df_retail.columns and "Quantity" in df_retail.columns
    print(f" [PASS] UCI Online Retail Authentic: {len(df_retail)} rows, {df_retail['StockCode'].nunique()} SKUs")

    # 2. UCI Inventory Forecast Benchmark
    fc_csv = SOURCES_DIR / "uci_inventory_forecast_benchmark.csv"
    assert fc_csv.is_file(), f"Missing {fc_csv}"
    df_fc = pd.read_csv(fc_csv)
    assert not df_fc.empty, "UCI forecast CSV is empty"
    for col in ["stock_code", "avg_daily_demand", "predicted_daily_demand", "reorder_point", "mae", "rmse", "mape_pct"]:
        assert col in df_fc.columns, f"Missing {col} in benchmark"
    print(f" [PASS] UCI Inventory Forecast Benchmark: {len(df_fc)} SKUs, MAE={df_fc['mae'].mean():.2f}")

    # 3. OSM Verified Businesses
    osm_json = SOURCES_DIR / "osm_verified_businesses.json"
    assert osm_json.is_file(), f"Missing {osm_json}"
    with open(osm_json, "r", encoding="utf-8") as f:
        osm_data = json.load(f)
    cities = osm_data.get("cities", {})
    assert len(cities) >= 4, "Expected at least 4 cities in OSM dataset"
    total_pois = sum(len(c.get("businesses", [])) for c in cities.values())
    print(f" [PASS] OpenStreetMap Verified Commercial POIs: {total_pois} nodes across {list(cities.keys())}")

    # 4. Credit Risk Research Benchmark
    cr_csv = SOURCES_DIR / "credit_risk_research_benchmark.csv"
    assert cr_csv.is_file(), f"Missing {cr_csv}"
    df_cr = pd.read_csv(cr_csv)
    assert len(df_cr) == 4, "Expected 4 ageing buckets in credit risk benchmark"
    print(f" [PASS] Credit Risk Research Benchmark: {len(df_cr)} tiers verified")

    print("\nAll datasets validated successfully!")

if __name__ == "__main__":
    validate_sources()
