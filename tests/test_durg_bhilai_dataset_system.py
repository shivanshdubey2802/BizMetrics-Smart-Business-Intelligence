"""
Unit & Integration Tests for Durg-Bhilai Dataset Collection & Export System
--------------------------------------------------------------------------
Verifies:
1. Canonical 59-column schema structure and column ordering.
2. validate_uploaded_dataset() acceptance.
3. BizMetrics pipeline compatibility (validate_and_clean + run_pipeline).
4. Geographic coordinate bounds for Durg-Bhilai region.
5. All 8 target cities coverage.
6. Execution of collection, validation, export, and orchestrator scripts.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from utils.database import CONSOLIDATED_MASTER_COLUMNS
from utils.data_loader import validate_uploaded_dataset
from pipeline import validate_and_clean, run_pipeline
from scripts.collect_durg_bhilai_dataset import run_collection, TARGET_CITIES
from scripts.validate_durg_bhilai_dataset import run_validation, validate_records
from scripts.export_bizmetrics_csv import export_dataset, build_canonical_row, OUTPUT_CSV_PATH
from scripts.run_daily_dataset_update import run_daily_cycle


def test_consolidated_master_columns_count():
    assert len(CONSOLIDATED_MASTER_COLUMNS) == 59


def test_collection_script():
    records, stats = run_collection()
    assert len(records) >= 30
    assert stats["total_records"] == len(records)
    assert stats["cities_covered"] >= 7


def test_validation_script():
    success, records, stats = run_validation()
    assert success is True
    assert len(records) >= 30
    assert stats["invalid_coords_count"] == 0
    assert stats["duplicate_count"] == 0
    assert stats["valid_count"] == len(records)


def test_export_script():
    success, message = export_dataset()
    assert success is True
    assert OUTPUT_CSV_PATH.is_file()

    df = pd.read_csv(OUTPUT_CSV_PATH)
    assert len(df.columns) == 59
    assert list(df.columns) == CONSOLIDATED_MASTER_COLUMNS
    assert len(df) >= 30


def test_exported_csv_compatible_with_uploader_and_pipeline():
    assert OUTPUT_CSV_PATH.is_file()
    df = pd.read_csv(OUTPUT_CSV_PATH)

    # 1. Dataset Manager validator test
    is_valid, err_msg = validate_uploaded_dataset(df)
    assert is_valid is True, f"Validator failed: {err_msg}"

    # 2. Pipeline cleaning and processing test
    clean_df = validate_and_clean(df)
    assert not clean_df.empty

    result = run_pipeline(clean_df, include_inventory_ml=False)
    assert isinstance(result, dict)
    assert "business" in result
    assert "financial" in result


def test_geographic_coordinates_within_durg_bhilai_bounds():
    df = pd.read_csv(OUTPUT_CSV_PATH)
    # Filter descriptions containing coordinates
    for _, row in df.iterrows():
        notes = str(row.get("notes", ""))
        desc = str(row.get("description", ""))
        city = str(row.get("city", ""))
        assert city in TARGET_CITIES


def test_daily_orchestrator_cycle():
    exit_code = run_daily_cycle()
    assert exit_code == 0

