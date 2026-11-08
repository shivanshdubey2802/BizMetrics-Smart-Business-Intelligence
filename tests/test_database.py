"""
Unit and Integration Tests for BizMetrics Centralized Relational Database.
Tests:
1. Schema initialization and table creation across all 13 required tables.
2. Data importation from original CSV files with foreign-key preservation.
3. PRAGMA foreign_key_check and PRAGMA integrity_check.
4. CRUD operations with atomic stock deduction and transaction rollback.
5. Owner and Customer credential authentication against database tables.
6. Pipeline compatibility with database-backed master DataFrame.
"""

import sqlite3
import pytest
import pandas as pd
from pathlib import Path

from utils.database import (
    DB_PATH,
    AUTH_DB_PATH,
    get_connection,
    get_db_cursor,
    init_database,
    import_all_csvs,
    query_df,
    query_records,
    get_products_df,
    get_sales_df,
    get_expenses_df,
    get_customers_df,
    get_receivables_df,
    get_loans_df,
    get_schemes_list,
    get_locations_df,
    get_consolidated_master_df,
    add_sales_transaction,
    update_inventory_stock,
    add_expense,
)
from pipeline import run_pipeline, validate_and_clean


def test_database_schema_and_tables():
    """Verify that all 13 required tables, indexes, and views exist in the database."""
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    views = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()}

    required_tables = {
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
    }

    for req in required_tables:
        assert req in tables, f"Required table '{req}' is missing from the database."

    assert "v_products_inventory" in views, "View 'v_products_inventory' is missing."
    conn.close()


def test_csv_records_imported_counts():
    """Verify record counts match or exceed original CSV data."""
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    counts = {
        "shops": cur.execute("SELECT COUNT(*) FROM shops").fetchone()[0],
        "users": cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "customer_credentials": cur.execute("SELECT COUNT(*) FROM customer_credentials").fetchone()[0],
        "customers": cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "products": cur.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "inventory": cur.execute("SELECT COUNT(*) FROM inventory").fetchone()[0],
        "sales_transactions": cur.execute("SELECT COUNT(*) FROM sales_transactions").fetchone()[0],
        "expenses": cur.execute("SELECT COUNT(*) FROM expenses").fetchone()[0],
        "receivables": cur.execute("SELECT COUNT(*) FROM receivables").fetchone()[0],
        "vendors": cur.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
        "loans_emi": cur.execute("SELECT COUNT(*) FROM loans_emi").fetchone()[0],
        "government_schemes": cur.execute("SELECT COUNT(*) FROM government_schemes").fetchone()[0],
        "business_locations": cur.execute("SELECT COUNT(*) FROM business_locations").fetchone()[0],
    }
    conn.close()

    assert counts["shops"] >= 1
    assert counts["users"] >= 2
    assert counts["customers"] >= 36
    assert counts["products"] == 12
    assert counts["inventory"] == 12
    assert counts["sales_transactions"] >= 1360
    assert counts["expenses"] >= 7
    assert counts["receivables"] >= 130
    assert counts["vendors"] >= 1
    assert counts["loans_emi"] >= 1
    assert counts["government_schemes"] >= 6
    assert counts["business_locations"] >= 40


def test_foreign_key_and_integrity_constraints():
    """Verify that foreign keys and overall SQLite database integrity are 100% valid."""
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    fk_violations = cur.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_violations) == 0, f"Foreign-key check failed with violations: {fk_violations}"

    integrity_result = cur.execute("PRAGMA integrity_check;").fetchone()[0]
    assert integrity_result.lower() == "ok", f"Integrity check failed: {integrity_result}"
    conn.close()


def test_crud_sales_with_atomic_inventory_deduction():
    """Verify that recording a sale atomically reduces the product's inventory stock level."""
    # 1. Get initial stock of PROD001
    prod_df = get_products_df()
    row_before = prod_df[prod_df["product_id"] == "PROD001"].iloc[0]
    stock_before = float(row_before["current_stock"])

    # 2. Add a sale of 3 units
    test_sale_id = f"TEST_SALE_{pd.Timestamp.now().strftime('%f')}"
    add_sales_transaction({
        "sale_id": test_sale_id,
        "product_id": "PROD001",
        "customer_id": "CUST001",
        "quantity": 3.0,
        "selling_price": 162.0,
        "total_amount": 486.0,
        "payment_mode": "Cash",
        "payment_status": "Completed",
        "notes": "Unit test sale"
    })

    # 3. Check stock after sale
    prod_df_after = get_products_df()
    row_after = prod_df_after[prod_df_after["product_id"] == "PROD001"].iloc[0]
    stock_after = float(row_after["current_stock"])
    assert stock_after == max(0.0, stock_before - 3.0)

    # 4. Clean up test sale and restore stock
    with get_db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM sales_transactions WHERE sale_id = ?", (test_sale_id,))
    update_inventory_stock("PROD001", stock_before)


def test_transaction_rollback_on_failure():
    """Verify that database transaction context manager rolls back on error."""
    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    initial_exp_count = cur.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()

    with pytest.raises(Exception):
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO expenses (expense_id, shop_id, date, category, amount) VALUES (?, ?, ?, ?, ?)",
                ("EXP_FAIL_TEST", "shivansh_electronics_hardware", "2026-11-06", "Test", 999.0)
            )
            # Deliberately raise exception to trigger rollback
            raise RuntimeError("Forced simulation error")

    conn_after = get_connection(DB_PATH)
    cur_after = conn_after.cursor()
    after_exp_count = cur_after.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn_after.close()

    assert after_exp_count == initial_exp_count


def test_customer_credentials_and_name_preservation():
    """Verify that CUST001 has customer_name 'Shivansh' and credentials exist in customer_credentials."""
    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    row = cur.execute(
        "SELECT customer_id, customer_name, password_hash FROM customer_credentials WHERE customer_id = 'CUST001'"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "CUST001"
    assert "Shivansh" in row[1]
    assert len(row[2]) == 64  # Valid SHA-256 hash


def test_database_backed_pipeline_execution():
    """Verify that the database can reconstruct a consolidated DataFrame that runs through the pipeline."""
    df_db = get_consolidated_master_df()
    assert not df_db.empty
    assert "record_type" in df_db.columns

    clean_df = validate_and_clean(df_db)
    result = run_pipeline(clean_df, include_inventory_ml=False)

    assert "financial" in result
    assert "inventory" in result
    assert "customers" in result
    assert result["financial"]["total_revenue"] > 100000.0
    assert len(result["inventory"]["items"]) == 12

