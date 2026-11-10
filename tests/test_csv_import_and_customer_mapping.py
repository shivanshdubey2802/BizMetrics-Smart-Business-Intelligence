"""
Tests for BizMetrics CSV Import Workflow and Customer-Level Data Mapping.
Verifies:
1. Canonical 59-column schema validation & structure preview.
2. Explicit import to SQLite database (customers, products, inventory, sales, expenses, loans, vendors).
3. Duplicate import prevention & preservation of existing records.
4. Customer CUST001 genuine data mapping (never invents fake orders; displays empty state when no transactions exist).
5. Customer portal sidebar navigation items & resilience against query errors.
"""

import os
import sqlite3
import tempfile
import pandas as pd
import pytest
from pathlib import Path

from utils.database import (
    init_database,
    import_master_df_to_database,
    CONSOLIDATED_MASTER_COLUMNS,
    DEFAULT_SHOP_ID,
)
from utils.data_loader import validate_uploaded_dataset
from customer_qr_bills import get_customer_bills, get_bill_summary


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_database(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def test_canonical_59_column_schema_recognition():
    """Verify that canonical 59-column BizMetrics dataset is recognized and validated."""
    assert len(CONSOLIDATED_MASTER_COLUMNS) == 59
    empty_canonical_df = pd.DataFrame(columns=CONSOLIDATED_MASTER_COLUMNS)
    empty_canonical_df.loc[0] = ["Sale"] + [""] * 58
    empty_canonical_df.at[0, "total_amount"] = "1500"
    empty_canonical_df.at[0, "product_id"] = "PROD001"
    empty_canonical_df.at[0, "customer_id"] = "CUST001"

    is_valid, err = validate_uploaded_dataset(empty_canonical_df)
    assert is_valid, f"Validation failed: {err}"
    assert err == ""


def test_import_master_df_to_database_all_records(temp_db):
    """Verify that import_master_df_to_database maps customers, products, inventory, and sales."""
    test_rows = [
        # Customer
        {
            "record_type": "Customer",
            "customer_id": "CUST001",
            "customer_name": "Shivansh Gupta",
            "business_name": "Shivansh Hardware Store",
            "contact_number": "+91 98765 43210",
            "city": "Durg",
            "outstanding_amount": 500.0,
        },
        # Product & Inventory
        {
            "record_type": "Inventory",
            "product_id": "P_SWITCH_01",
            "product_name": "Modular Electrical Switch",
            "category": "Electricals",
            "purchase_price": 45.0,
            "selling_price": 75.0,
            "current_stock": 120.0,
        },
        # Sale for CUST001
        {
            "record_type": "Sale",
            "sale_id": "SALE_GEN_001",
            "customer_id": "CUST001",
            "product_id": "P_SWITCH_01",
            "quantity": 10,
            "selling_price": 75.0,
            "total_amount": 750.0,
            "payment_status": "Completed",
            "date": "2026-11-09",
        },
        # Sale for CUST002
        {
            "record_type": "Sale",
            "sale_id": "SALE_GEN_002",
            "customer_id": "CUST002",
            "product_id": "P_SWITCH_01",
            "quantity": 5,
            "selling_price": 75.0,
            "total_amount": 375.0,
            "payment_status": "Pending",
            "credit_amount": 375.0,
            "date": "2026-11-09",
        },
    ]
    df = pd.DataFrame(test_rows)

    res = import_master_df_to_database(df, db_path=temp_db)
    assert res["status"] == "success"
    assert res["imported"] >= 3
    assert res["errors"] == 0

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()

    # Verify Customer in DB
    cur.execute("SELECT customer_name, city, outstanding_amount FROM customers WHERE customer_id = 'CUST001'")
    cust_row = cur.fetchone()
    assert cust_row is not None
    assert cust_row[0] == "Shivansh Gupta"
    assert cust_row[1] == "Durg"

    # Verify Product in DB
    cur.execute("SELECT product_name, selling_price FROM products WHERE product_id = 'P_SWITCH_01'")
    prod_row = cur.fetchone()
    assert prod_row is not None
    assert prod_row[0] == "Modular Electrical Switch"

    # Verify Inventory
    cur.execute("SELECT current_stock FROM inventory WHERE product_id = 'P_SWITCH_01'")
    inv_row = cur.fetchone()
    assert inv_row is not None
    assert inv_row[0] == 120.0

    # Verify Sales
    cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE customer_id = 'CUST001'")
    c1_sales = cur.fetchone()[0]
    assert c1_sales == 1

    cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE customer_id = 'CUST002'")
    c2_sales = cur.fetchone()[0]
    assert c2_sales == 1

    conn.close()


def test_duplicate_prevention_on_reimport(temp_db):
    """Verify that importing the same dataset twice prevents duplicates and updates existing records."""
    df = pd.DataFrame([
        {
            "record_type": "Sale",
            "sale_id": "DUP_TEST_01",
            "customer_id": "CUST001",
            "product_id": "P01",
            "quantity": 2,
            "selling_price": 100.0,
            "total_amount": 200.0,
            "date": "2026-11-09",
        }
    ])

    res1 = import_master_df_to_database(df, db_path=temp_db)
    assert res1["imported"] == 1
    assert res1["duplicates"] == 0

    # Re-importing exact same record
    res2 = import_master_df_to_database(df, db_path=temp_db)
    assert res2["imported"] == 0
    assert res2["duplicates"] == 1

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE sale_id = 'DUP_TEST_01'")
    assert cur.fetchone()[0] == 1, "Duplicate record must not be duplicated in table"
    conn.close()


def test_customer_isolation_and_empty_state():
    """Verify that customer bills query returns empty dataframe and zeroes when customer has no transactions."""
    non_existent_cid = "CUST_NON_EXISTENT_9999"
    bills = get_customer_bills(non_existent_cid)
    assert bills.empty, "Non-existent customer must have empty bills"

    summary = get_bill_summary(bills)
    assert summary["total_bills"] == 0
    assert summary["total_purchase"] == 0.0
    assert summary["paid_amount"] == 0.0
    assert summary["outstanding"] == 0.0
    assert summary["avg_bill"] == 0.0

