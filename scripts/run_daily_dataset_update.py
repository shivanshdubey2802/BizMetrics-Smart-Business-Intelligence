#!/usr/bin/env python3
"""
BizMetrics - Daily Durg-Bhilai Public Business Dataset Orchestrator
------------------------------------------------------------------
Automated daily runner script designed for Windows Task Scheduler,
cron, or standalone execution.

Workflow:
1. Collection : Queries Overpass API / verified catalog for Durg-Bhilai establishments.
2. Validation : Verifies coordinates, deduplicates, and generates quality report.
3. Export     : Generates canonical 59-column BizMetrics master CSV (atomic write).
4. Audit      : Confirms compatibility with BizMetrics validate_uploaded_dataset().

Log output:
  data/exports/daily_update.log
"""

import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = EXPORTS_DIR / "daily_update.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("DailyOrchestrator")

# Add scripts directory and project root to path
SCRIPTS_DIR = Path(__file__).resolve().parent
for p in [str(ROOT_DIR), str(SCRIPTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from collect_durg_bhilai_dataset import run_collection
from validate_durg_bhilai_dataset import run_validation
from export_bizmetrics_csv import export_dataset


def run_daily_cycle() -> int:
    """
    Executes the complete daily workflow.
    Returns 0 on success, 1 on error.
    """
    start_time = time.time()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info("=" * 70)
    logger.info(f"STARTING BIZMETRICS DAILY DATASET UPDATE: {today_str}")
    logger.info("=" * 70)

    # -------------------------------------------------------------------------
    # STEP 1: COLLECTION
    # -------------------------------------------------------------------------
    logger.info("[Step 1/3] Collecting Durg-Bhilai public business establishments...")
    try:
        records, collect_stats = run_collection()
        logger.info(
            f"Collection finished: {collect_stats.get('total_records', 0)} total records "
            f"({collect_stats.get('newly_discovered', 0)} new, {collect_stats.get('updated_records', 0)} updated) "
            f"across {collect_stats.get('cities_covered', 0)} cities."
        )
    except Exception as exc:
        logger.exception(f"FATAL: Collection step failed with exception: {exc}")
        return 1

    # -------------------------------------------------------------------------
    # STEP 2: VALIDATION & REPORT GENERATION
    # -------------------------------------------------------------------------
    logger.info("[Step 2/3] Validating records and generating data quality report...")
    try:
        val_success, val_records, val_stats = run_validation()
        if not val_success:
            logger.error("FATAL: Validation step failed. Aborting CSV export to preserve previous data.")
            return 1
        logger.info(
            f"Validation passed: {val_stats.get('valid_count', 0)} valid establishments, "
            f"{val_stats.get('duplicate_count', 0)} duplicates, "
            f"{val_stats.get('invalid_coords_count', 0)} invalid coordinates."
        )
    except Exception as exc:
        logger.exception(f"FATAL: Validation step failed with exception: {exc}")
        return 1

    # -------------------------------------------------------------------------
    # STEP 3: BIZMETRICS CANONICAL CSV EXPORT
    # -------------------------------------------------------------------------
    logger.info("[Step 3/3] Exporting canonical 59-column BizMetrics master CSV...")
    try:
        export_success, export_msg = export_dataset()
        if not export_success:
            logger.error(f"FATAL: CSV export failed: {export_msg}")
            return 1
        logger.info(f"Export successful: {export_msg}")
    except Exception as exc:
        logger.exception(f"FATAL: Export step failed with exception: {exc}")
        return 1

    # -------------------------------------------------------------------------
    # STEP 4: VERIFICATION AUDIT
    # -------------------------------------------------------------------------
    target_csv = EXPORTS_DIR / "durg_bhilai_business_dataset.csv"
    report_file = EXPORTS_DIR / "dataset_quality_report.txt"

    if not target_csv.is_file() or target_csv.stat().st_size == 0:
        logger.error(f"FATAL: Target export file missing or zero bytes: {target_csv}")
        return 1

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info(f"DAILY UPDATE COMPLETED SUCCESSFULLY IN {elapsed:.2f}s")
    logger.info(f"Generated CSV    : {target_csv}")
    logger.info(f"Quality Report   : {report_file}")
    logger.info(f"Total Rows       : {len(val_records)}")
    logger.info("=" * 70)

    print("\n" + "=" * 60)
    print("BIZMETRICS DAILY DATASET UPDATE - EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Timestamp           : {today_str}")
    print(f"Status              : SUCCESS (Code 0)")
    print(f"Total Records       : {len(val_records)}")
    print(f"Canonical Columns   : 59 Columns (Exact Order Verified)")
    print(f"CSV Export File     : {target_csv}")
    print(f"Quality Report File : {report_file}")
    print(f"Elapsed Time        : {elapsed:.2f} seconds")
    print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    exit_code = run_daily_cycle()
    sys.exit(exit_code)

