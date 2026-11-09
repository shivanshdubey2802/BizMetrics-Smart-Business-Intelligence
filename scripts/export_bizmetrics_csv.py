#!/usr/bin/env python3
"""
BizMetrics - Durg-Bhilai Public Business Dataset CSV Exporter
------------------------------------------------------------
Exports validated Durg-Bhilai public business establishments into the exact
canonical 59-column BizMetrics master CSV format.

Guarantees:
- Exactly 59 columns in exact canonical order
- Atomic export: Never overwrites last valid export with invalid/empty data
- Backup preservation: data/exports/durg_bhilai_business_dataset.csv.bak
- Direct verification against validate_uploaded_dataset() and pipeline.validate_and_clean()
"""

import os
import sys
import json
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "durg_bhilai" / "processed"
EXPORTS_DIR = ROOT_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV_PATH = EXPORTS_DIR / "durg_bhilai_business_dataset.csv"
BACKUP_CSV_PATH = EXPORTS_DIR / "durg_bhilai_business_dataset.csv.bak"
TEMP_CSV_PATH = EXPORTS_DIR / "durg_bhilai_business_dataset.csv.tmp"
VALIDATED_JSON_PATH = PROCESSED_DIR / "validated_businesses.json"
LOG_FILE = EXPORTS_DIR / "daily_update.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("DurgBhilaiExporter")

# Add project root to sys.path to import project modules
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from utils.database import CONSOLIDATED_MASTER_COLUMNS
except ImportError:
    CONSOLIDATED_MASTER_COLUMNS = [
        "record_type", "product_id", "product_name", "category", "sector", "unit",
        "purchase_price", "selling_price", "current_stock", "minimum_stock",
        "maximum_stock", "reorder_level", "status", "description", "supplier_id",
        "lead_time_days", "sale_id", "business_id", "date", "customer_id",
        "quantity", "discount_percent", "total_amount", "payment_mode",
        "payment_status", "credit_amount", "notes", "expense_id", "amount",
        "is_fixed", "customer_name", "business_name", "contact_number", "email",
        "city", "customer_type", "registration_date", "customer_rating",
        "outstanding_amount", "vendor_id", "vendor_name", "material_type",
        "total_ordered_amount", "total_paid_amount", "outstanding_balance",
        "next_payment_date", "credit_days_allowed", "loan_id", "loan_provider",
        "principal_amount", "interest_rate", "tenure_months", "monthly_emi",
        "outstanding_principal", "start_date", "next_due_date", "loan_type",
        "due_date", "mobile_number",
    ]

SECTOR_MAP = {
    "Hardware": "Industrial & Trade",
    "Electronics": "Consumer Retail",
    "Electronics & Electricals": "Commercial & Retail",
    "Grocery / Kirana": "FMCG & Provisions",
    "Medical Store": "Healthcare Retail",
    "Hospital / Clinic": "Healthcare Services",
    "Bank / ATM": "Financial Services",
    "Bank / Financial": "Financial Services",
    "Restaurant / Cafe": "Food & Hospitality",
    "Industrial & Commercial": "Manufacturing & Heavy Engineering",
    "Agriculture Supplies": "Agribusiness & Implements",
    "Automobile & Spare Parts": "Automotive & Logistics",
    "Retail Shops": "Retail Merchandising",
    "Educational Institution": "Education & Research",
}


def build_canonical_row(item: Dict[str, Any], today_str: str) -> Dict[str, Any]:
    """
    Maps a public establishment record into the exact 59-column BizMetrics master schema.
    Unavailable private business, financial, and inventory fields are left blank.
    Zero fabricated numbers or transactions.
    """
    cat = item.get("category", "Retail Shops")
    sector = SECTOR_MAP.get(cat, "Commercial Trade")
    locality = item.get("locality", "")
    address = item.get("address", "")
    lat = item.get("latitude", "")
    lon = item.get("longitude", "")
    desc = f"{address or locality} (Coordinates: {lat}, {lon})" if lat and lon else (address or locality)

    source = item.get("source", "OpenStreetMap (ODbL 1.0)")
    osm_id = item.get("osm_id", "")
    v_status = item.get("verification_status", "Public Contributed (OSM Unverified)")
    sub_cat = item.get("sub_category", "")
    ward = item.get("ward", "")
    website = item.get("website", "")

    notes_parts = [
        f"Source: {source}",
        f"RecordID: {item.get('business_id', '')}",
        f"Status: {v_status}",
    ]
    if osm_id:
        notes_parts.append(f"OSM_ID: {osm_id}")
    if sub_cat:
        notes_parts.append(f"SubCategory: {sub_cat}")
    if ward:
        notes_parts.append(f"Ward: {ward}")
    if website:
        notes_parts.append(f"Website: {website}")

    notes_str = " | ".join(notes_parts)
    contact = str(item.get("contact_info", "")).strip()
    if contact.lower() in ["nan", "none"]:
        contact = ""

    ref_year = item.get("reference_year", 2024)
    reg_date = f"{ref_year}-01-01"

    row = {col: "" for col in CONSOLIDATED_MASTER_COLUMNS}
    row["record_type"] = "Business"
    row["business_id"] = str(item.get("business_id", "")).strip()
    row["business_name"] = str(item.get("business_name", "")).strip()
    row["category"] = cat
    row["sector"] = sector
    row["status"] = "Active"
    row["description"] = desc
    row["date"] = item.get("collection_date", today_str)
    row["notes"] = notes_str
    row["contact_number"] = contact
    row["mobile_number"] = contact
    row["email"] = ""
    row["city"] = str(item.get("city", "Durg")).strip()
    row["customer_type"] = ""
    row["registration_date"] = reg_date

    return row


def export_dataset() -> Tuple[bool, str]:
    """
    Executes the canonical CSV export pipeline with full atomic safety:
    1. Loads validated establishment records.
    2. Builds exact 59-column DataFrame in canonical order.
    3. Writes to a temporary CSV.
    4. Validates via validate_uploaded_dataset() and pipeline.validate_and_clean().
    5. Backs up previous export.
    6. Atomically moves temporary file to data/exports/durg_bhilai_business_dataset.csv.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("Starting Durg-Bhilai BizMetrics canonical CSV export...")

    if not VALIDATED_JSON_PATH.is_file():
        err = f"Validated dataset not found at {VALIDATED_JSON_PATH}. Run validation first."
        logger.error(err)
        return False, err

    with open(VALIDATED_JSON_PATH, "r", encoding="utf-8") as fp:
        records = json.load(fp)

    if not records:
        err = "Validated records list is empty. Aborting export to protect existing files."
        logger.error(err)
        return False, err

    rows = [build_canonical_row(item, today_str) for item in records]
    df = pd.DataFrame(rows)

    # Reorder columns explicitly to guarantee exact canonical 59-column order
    df = df[CONSOLIDATED_MASTER_COLUMNS]

    if len(df.columns) != 59:
        err = f"Column count mismatch: Expected 59, got {len(df.columns)}"
        logger.error(err)
        return False, err

    if list(df.columns) != CONSOLIDATED_MASTER_COLUMNS:
        err = "Column order mismatch with CONSOLIDATED_MASTER_COLUMNS"
        logger.error(err)
        return False, err

    # 1. Write to temporary CSV first
    df.to_csv(TEMP_CSV_PATH, index=False, encoding="utf-8")
    logger.info(f"Wrote temporary CSV with {len(df)} rows -> {TEMP_CSV_PATH}")

    # 2. Test reading back and validating against BizMetrics internal validator
    try:
        from utils.data_loader import validate_uploaded_dataset
        test_df = pd.read_csv(TEMP_CSV_PATH)
        is_valid, msg = validate_uploaded_dataset(test_df)
        if not is_valid:
            TEMP_CSV_PATH.unlink(missing_ok=True)
            err = f"Exported CSV failed validate_uploaded_dataset(): {msg}"
            logger.error(err)
            return False, err
        logger.info("Temporary export passed validate_uploaded_dataset() successfully.")
    except Exception as exc:
        TEMP_CSV_PATH.unlink(missing_ok=True)
        err = f"Validator execution error: {exc}"
        logger.error(err)
        return False, err

    # 3. Test through pipeline.validate_and_clean()
    try:
        from pipeline import validate_and_clean, run_pipeline
        clean_df = validate_and_clean(test_df)
        _ = run_pipeline(clean_df, include_inventory_ml=False)
        logger.info("Exported CSV passed full BizMetrics pipeline validation and execution.")
    except Exception as exc:
        TEMP_CSV_PATH.unlink(missing_ok=True)
        err = f"Pipeline execution test failed on exported CSV: {exc}"
        logger.error(err)
        return False, err

    # 4. Safe backup of existing file
    if OUTPUT_CSV_PATH.is_file():
        try:
            shutil.copy2(OUTPUT_CSV_PATH, BACKUP_CSV_PATH)
            logger.info(f"Backed up previous export to {BACKUP_CSV_PATH}")
        except Exception as exc:
            logger.warning(f"Could not backup existing file: {exc}")

    # 5. Atomically replace temporary file with official output file
    try:
        if os.name == "nt" and OUTPUT_CSV_PATH.is_file():
            # On Windows, replace requires removing target first if atomic rename fails
            OUTPUT_CSV_PATH.unlink(missing_ok=True)
        shutil.move(TEMP_CSV_PATH, OUTPUT_CSV_PATH)
        logger.info(f"Official canonical CSV successfully deployed: {OUTPUT_CSV_PATH} ({len(df)} rows, 59 columns)")
    except Exception as exc:
        err = f"Failed to finalize output file: {exc}"
        logger.error(err)
        return False, err

    return True, f"Successfully exported {len(df)} records with exact 59 columns to {OUTPUT_CSV_PATH}"


if __name__ == "__main__":
    success, message = export_dataset()
    if not success:
        sys.exit(1)
    print("\n--- Export Succeeded ---")
    print(f"Message:     {message}")
    print(f"Target File: {OUTPUT_CSV_PATH}")
    print(f"Columns:     59 (Exact Canonical Order)\n")
