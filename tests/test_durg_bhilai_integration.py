import pytest
import pandas as pd
from pathlib import Path
from utils.database import (
    get_local_businesses_df,
    get_local_demographics_df,
    get_local_economic_indicators_df,
    get_local_geographic_nodes_df,
    get_dataset_sources_df,
    import_durg_bhilai_datasets,
    init_database,
)
from utils.hyperlocal_intelligence import query_osm_businesses, haversine_km

def test_durg_bhilai_database_tables_populated():
    """Verify that all Durg-Bhilai SQLite tables exist and have authentic records."""
    init_database()
    
    # 1. Demographics
    df_demo = get_local_demographics_df()
    assert not df_demo.empty, "Local demographics table should not be empty."
    assert len(df_demo) >= 10, f"Expected at least 10 demographic records, got {len(df_demo)}"
    assert "total_population" in df_demo.columns
    assert "census_year" in df_demo.columns
    # Mandatory requirement: verify Census Reference Year is explicitly 2011
    assert (df_demo["census_year"] == 2011).all(), "All demographic records must be labeled with Census Reference Year 2011."
    
    # Verify specific key cities
    area_names = df_demo["area_name"].tolist()
    assert "Durg District" in area_names
    assert "Bhilai Nagar" in area_names
    assert "Durg" in area_names
    assert "Bhilai Charoda" in area_names
    assert "Risali" in area_names
    assert "Jamul" in area_names
    assert "Kumhari" in area_names
    assert "Ahiwara" in area_names

    # 2. Geographic nodes
    df_geo = get_local_geographic_nodes_df()
    assert not df_geo.empty, "Local geographic nodes table should not be empty."
    assert len(df_geo) >= 15, f"Expected at least 15 geographic nodes, got {len(df_geo)}"
    assert "latitude" in df_geo.columns
    assert "longitude" in df_geo.columns

    # 3. Business Directory (OSM)
    df_biz = get_local_businesses_df()
    assert not df_biz.empty, "Local business directory should not be empty."
    assert len(df_biz) >= 30, f"Expected at least 30 verified OSM businesses, got {len(df_biz)}"
    assert "osm_id" in df_biz.columns
    assert "business_name" in df_biz.columns
    assert "category" in df_biz.columns
    # Ensure all businesses have real lat/lons in the Durg bounding box (lat ~21.1 to 21.4, lon ~81.1 to 81.6)
    assert ((df_biz["latitude"] >= 21.0) & (df_biz["latitude"] <= 21.6)).all()
    assert ((df_biz["longitude"] >= 81.1) & (df_biz["longitude"] <= 81.6)).all()

    # 4. Economic Indicators
    df_econ = get_local_economic_indicators_df()
    assert not df_econ.empty, "Economic indicators table should not be empty."
    assert len(df_econ) >= 7, f"Expected at least 7 economic indicators, got {len(df_econ)}"
    indicator_names = " ".join(df_econ["indicator_name"].tolist())
    assert "Bhilai Steel Plant" in indicator_names
    assert "Credit-Deposit" in indicator_names
    assert "Udyam MSME" in indicator_names
    assert "Mandi" in indicator_names

    # 5. Dataset Sources & Provenance
    df_src = get_dataset_sources_df()
    assert not df_src.empty, "Dataset sources table should not be empty."
    assert len(df_src) >= 4, f"Expected at least 4 source citations, got {len(df_src)}"
    licenses = " ".join(df_src["license"].tolist())
    assert "ODbL" in licenses
    assert "Government Open Data License" in licenses or "GODL" in licenses


def test_osm_query_for_durg_and_bhilai():
    """Verify that query_osm_businesses retrieves authentic local businesses."""
    # Test Durg city center query
    res_durg = query_osm_businesses(city="Durg", radius_km=5.0)
    assert res_durg is not None
    competitors = res_durg.get("competitors", [])
    assert len(competitors) > 0, "Durg should have mapped OSM competitors within 5 km."
    first_comp = competitors[0]
    assert "name" in first_comp
    assert "osm_id" in first_comp
    assert "dist" in first_comp
    assert first_comp["dist"] <= 5.0, "Competitor distance should be within the specified radius."

    # Test Bhilai center query
    res_bhilai = query_osm_businesses(city="Bhilai", radius_km=5.0)
    assert res_bhilai is not None
    bhilai_comps = res_bhilai.get("competitors", [])
    assert len(bhilai_comps) > 0, "Bhilai should have mapped OSM competitors within 5 km."


def test_import_idempotency():
    """Verify that re-importing datasets does not produce errors or duplicate records."""
    stats = import_durg_bhilai_datasets()
    assert stats["demographics"] >= 10
    assert stats["businesses"] >= 30
    assert stats["economic"] >= 7
    
    # Query again and check record counts remain consistent
    df_demo = get_local_demographics_df()
    df_biz = get_local_businesses_df()
    assert len(df_demo) == 10
    assert len(df_biz) == 32


def test_haversine_accuracy():
    """Verify haversine distance calculation between known Durg and Bhilai landmarks."""
    # Durg City Center: 21.1904, 81.2849
    # Bhilai Civic Center: 21.1938, 81.3509
    dist = haversine_km(21.1904, 81.2849, 21.1938, 81.3509)
    # The straight line distance is approximately 6.8 - 7.0 km
    assert 6.0 <= dist <= 7.5, f"Expected distance between Durg and Bhilai Civic Center to be ~6.8 km, got {dist:.2f} km"

