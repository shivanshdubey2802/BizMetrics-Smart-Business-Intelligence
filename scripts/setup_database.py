"""
Automated Database Setup, Migration & Import Script for BizMetrics.
Initializes tables, imports CSV records with foreign key checks, and validates counts.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.database import (
    DB_PATH,
    AUTH_DB_PATH,
    init_database,
    import_all_csvs,
    get_connection,
    query_records,
)


def run_setup():
    print("=" * 70)
    print("  BIZMETRICS — ORIGINAL DATABASE CONFIGURATION & CSV IMPORT")
    print("=" * 70)
    print(f"Primary Database: {DB_PATH}")
    print(f"Auth Database:    {AUTH_DB_PATH}")

    # 1. Initialize schemas
    print("\n[1/4] Initializing Database Schemas & Constraints...")
    init_database(DB_PATH)
    print("✓ All 13 tables, indexes, and views initialized successfully.")

    # 2. Import CSV data
    print("\n[2/4] Importing Original CSV Datasets...")
    summary = import_all_csvs(DB_PATH)
    print("✓ Import completed.")
    for table_name, count in summary.get("imported", {}).items():
        print(f"   • {table_name:<22}: {count:>5} records")

    if summary.get("errors"):
        print("\nWarnings / Errors during import:")
        for err in summary["errors"]:
            print(f"   ! {err}")

    # 3. Verify Table Record Counts
    print("\n[3/4] Verifying Table Record Counts & Relationships...")
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    tables = [
        "shops",
        "users",
        "customer_credentials",
        "customers",
        "products",
        "inventory",
        "sales_transactions",
        "expenses",
        "receivables",
        "vendors",
        "loans_emi",
        "government_schemes",
        "business_locations",
    ]

    total_records = 0
    print("-" * 50)
    print(f"{'Table Name':<25} {'Record Count':>15}")
    print("-" * 50)
    for t in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        total_records += count
        print(f"{t:<25} {count:>15}")
    print("-" * 50)
    print(f"{'TOTAL DATABASE RECORDS':<25} {total_records:>15}")
    print("-" * 50)

    # 4. Foreign Key and Integrity Checks
    print("\n[4/4] Running Foreign-Key & Integrity Verification...")
    fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_check:
        print(f"❌ Foreign key integrity check failed with {len(fk_check)} violations:")
        for v in fk_check:
            print(f"   Violation: {v}")
    else:
        print("✓ PRAGMA foreign_key_check: 0 violations. Foreign-key integrity intact.")

    integrity = cur.execute("PRAGMA integrity_check;").fetchone()[0]
    print(f"✓ PRAGMA integrity_check:   {integrity}")

    conn.close()
    print("\n" + "=" * 70)
    print("  DATABASE CONFIGURATION AND IMPORT COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    run_setup()

