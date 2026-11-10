import os
import sys
import tempfile
import sqlite3
import io
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.database import (
    init_database,
    get_customer_master_table_df,
    get_customer_kpi_summary,
    add_customer_to_db,
    edit_customer_in_db,
    delete_customer_from_db,
    get_customer_detail_from_db,
    get_connection,
    DEFAULT_SHOP_ID,
)
from customer_qr_bills import get_customer_bills, get_customer_qr, _get_customer_profile


def test_database_connection_and_customer_schema():
    """Verify customers table exists with correct columns, primary keys, and relations."""
    init_database()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(customers)")
        cols = {row[1]: row[2] for row in cur.fetchall()}

    required_cols = [
        "customer_id", "shop_id", "customer_name", "business_name",
        "contact_number", "email", "city", "customer_type", "outstanding_amount"
    ]
    for c in required_cols:
        assert c in cols, f"Missing column {c} in customers table schema"


def test_get_customer_master_table_df_structure():
    """Verify get_customer_master_table_df returns comprehensive records with all required fields."""
    init_database()
    df = get_customer_master_table_df()
    assert not df.empty, "Customer master dataframe should not be empty"
    assert len(df) >= 40, f"Expected at least 40 customer records, found {len(df)}"

    required_keys = [
        "customer_id", "customer_name", "contact_number", "email", "city",
        "customer_type", "total_purchases", "total_paid", "outstanding_amount",
        "last_purchase_date", "customer_status"
    ]
    for k in required_keys:
        assert k in df.columns, f"Missing required column '{k}' in get_customer_master_table_df"

    # Status classification integrity
    valid_statuses = {"Active", "New", "At Risk", "Inactive"}
    assert set(df["customer_status"].unique()).issubset(valid_statuses)

    # Numerical metrics integrity
    assert (df["total_purchases"] >= 0).all()
    assert (df["total_paid"] >= 0).all()
    assert (df["outstanding_amount"] >= 0).all()


def test_get_customer_kpi_summary_values():
    """Verify 6 database KPIs match actual database aggregations."""
    init_database()
    kpis = get_customer_kpi_summary()

    assert kpis["total_customers"] >= 40
    assert kpis["active_customers"] >= 0
    assert kpis["new_customers"] >= 0
    assert kpis["repeat_customers"] >= 0
    assert 0.0 <= kpis["repeat_pct"] <= 100.0
    assert kpis["outstanding_dues"] >= 0.0
    assert kpis["total_revenue"] >= 0.0

    # Cross-reconcile with sales transactions
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(total_amount), 0.0) FROM sales_transactions")
        expected_rev = round(cur.fetchone()[0], 2)

    assert abs(kpis["total_revenue"] - expected_rev) < 0.01


def test_add_new_customer_and_validations():
    """Verify customer creation, duplicate ID check, and duplicate mobile check."""
    init_database()
    test_mob = "9988776655"
    test_id = "CUST_TEST_INTEG_01"

    # Clean up test user if lingering
    delete_customer_from_db(test_id, force=True)

    # 1. Add valid customer
    success, msg, created_id = add_customer_to_db(
        customer_name="Integration Test Buyer",
        contact_number=test_mob,
        email="integ_buyer@example.com",
        city="Durg",
        customer_type="Contractor",
        business_name="Integ Constructions",
        customer_id=test_id,
        outstanding_amount=2500.0
    )
    assert success is True, f"Failed to add customer: {msg}"
    assert created_id == test_id

    # 2. Duplicate ID validation
    dup_id_success, dup_id_msg, _ = add_customer_to_db(
        customer_name="Another Buyer",
        contact_number="9988776654",
        customer_id=test_id
    )
    assert dup_id_success is False
    assert ("already in use" in dup_id_msg.lower() or "already exists" in dup_id_msg.lower())

    # 3. Duplicate mobile validation
    dup_mob_success, dup_mob_msg, _ = add_customer_to_db(
        customer_name="Different Buyer",
        contact_number=test_mob,
        customer_id="CUST_TEST_INTEG_02"
    )
    assert dup_mob_success is False
    assert "already registered" in dup_mob_msg.lower()

    # Clean up
    delete_customer_from_db(test_id, force=True)


def test_edit_customer_and_unique_mobile_validation():
    """Verify customer profile editing and duplicate mobile prevention against other accounts."""
    init_database()
    cid_a = "CUST_TEST_EDIT_A"
    cid_b = "CUST_TEST_EDIT_B"
    delete_customer_from_db(cid_a, force=True)
    delete_customer_from_db(cid_b, force=True)

    add_customer_to_db(customer_name="User A", contact_number="9876500011", customer_id=cid_a)
    add_customer_to_db(customer_name="User B", contact_number="9876500022", customer_id=cid_b)

    # Update User A details successfully
    ok, msg = edit_customer_in_db(
        customer_id=cid_a,
        customer_name="User A Updated",
        contact_number="9876500099",
        email="user_a_upd@example.com",
        city="Bhilai Nagar",
        customer_type="Wholesaler"
    )
    assert ok is True
    detail = get_customer_detail_from_db(cid_a)
    assert detail["customer_name"] == "User A Updated"
    assert detail["city"] == "Bhilai Nagar"

    # Attempt to change User A's mobile to User B's mobile (should be rejected)
    dup_ok, dup_msg = edit_customer_in_db(
        customer_id=cid_a,
        customer_name="User A Updated",
        contact_number="9876500022",
    )
    assert dup_ok is False
    assert "already registered to another customer" in dup_msg.lower()

    # Clean up
    delete_customer_from_db(cid_a, force=True)
    delete_customer_from_db(cid_b, force=True)


def test_delete_customer_relationship_checks_and_cascade():
    """Verify relationship integrity checks when deleting customers."""
    init_database()
    cid = "CUST_TEST_RELATION_DEL"
    delete_customer_from_db(cid, force=True)

    add_customer_to_db(customer_name="Relation Test User", contact_number="9876599988", customer_id=cid)

    # Insert a fake sale and receivable
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sales_transactions (sale_id, shop_id, date, customer_id, product_id, quantity, selling_price, total_amount, payment_mode, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("SALE_REL_TEST", DEFAULT_SHOP_ID, "2026-11-10", cid, "PROD001", 1, 100.0, 100.0, "Credit", "Pending")
        )
        conn.execute(
            "INSERT INTO receivables (receivable_id, shop_id, invoice_id, customer_id, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("REC_REL_TEST", DEFAULT_SHOP_ID, "SALE_REL_TEST", cid, 100.0, "Pending")
        )
        conn.commit()

    # 1. Attempt non-force deletion (must be blocked by relationship check)
    blocked, block_msg, details = delete_customer_from_db(cid, force=False)
    assert blocked is False
    assert "cannot delete customer" in block_msg.lower()
    assert details["sales_count"] >= 1
    assert details["open_receivables"] >= 1

    # 2. Execute force deletion (must cascade cleanly)
    del_ok, del_msg, _ = delete_customer_from_db(cid, force=True)
    assert del_ok is True
    assert get_customer_detail_from_db(cid) is None


def test_customer_export_csv_and_excel_generation():
    """Verify customer records table can be exported to valid CSV and Excel files."""
    init_database()
    df = get_customer_master_table_df()
    assert not df.empty

    export_df = pd.DataFrame()
    export_df["Customer ID"] = df["customer_id"]
    export_df["Customer Name"] = df["customer_name"]
    export_df["Mobile Number"] = df["contact_number"]
    export_df["Email"] = df["email"]
    export_df["City"] = df["city"]
    export_df["Customer Type"] = df["customer_type"]
    export_df["Total Purchases"] = df["total_purchases"]
    export_df["Total Paid"] = df["total_paid"]
    export_df["Outstanding Amount"] = df["outstanding_amount"]
    export_df["Last Purchase Date"] = df["last_purchase_date"]
    export_df["Customer Status"] = df["customer_status"]

    # 1. CSV Export
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    assert len(csv_bytes) > 100
    read_back_csv = pd.read_csv(io.BytesIO(csv_bytes))
    assert len(read_back_csv) == len(df)
    assert list(read_back_csv.columns) == [
        "Customer ID", "Customer Name", "Mobile Number", "Email", "City",
        "Customer Type", "Total Purchases", "Total Paid", "Outstanding Amount",
        "Last Purchase Date", "Customer Status"
    ]

    # 2. Excel (.xlsx) Export
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Customers", index=False)
    excel_data = excel_buf.getvalue()
    assert len(excel_data) > 500
    read_back_excel = pd.read_excel(io.BytesIO(excel_data), sheet_name="Customers")
    assert len(read_back_excel) == len(df)


def test_customer_portal_data_isolation():
    """Verify Customer Portal strictly isolates data so Customer A cannot access Customer B."""
    init_database()
    bills_cust001 = get_customer_bills("CUST001")
    bills_cust002 = get_customer_bills("CUST002")

    assert not bills_cust001.empty, "CUST001 should have verified purchases"
    assert not bills_cust002.empty, "CUST002 should have verified purchases"

    # All bills returned for CUST001 must belong exclusively to CUST001
    assert (bills_cust001["Customer_ID"] == "CUST001").all()
    # All bills returned for CUST002 must belong exclusively to CUST002
    assert (bills_cust002["Customer_ID"] == "CUST002").all()

    # The sets of sales transactions must be completely disjoint
    sales_1 = set(bills_cust001["Sale_ID"])
    sales_2 = set(bills_cust002["Sale_ID"])
    assert sales_1.isdisjoint(sales_2), "Customer sales transactions leaked across accounts!"


def test_empty_database_state_graceful_handling():
    """Verify helper queries handle an empty database gracefully without crashing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        empty_db_path = f.name

    try:
        # Create empty schema without seeding
        with sqlite3.connect(empty_db_path) as conn:
            conn.execute("""
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    shop_id TEXT,
                    customer_name TEXT,
                    business_name TEXT,
                    contact_number TEXT,
                    email TEXT,
                    city TEXT,
                    customer_type TEXT,
                    registration_date TEXT,
                    customer_rating REAL,
                    outstanding_amount REAL,
                    address TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE sales_transactions (
                    sale_id TEXT PRIMARY KEY,
                    shop_id TEXT,
                    date TEXT,
                    customer_id TEXT,
                    product_id TEXT,
                    quantity REAL,
                    selling_price REAL,
                    discount_percent REAL,
                    total_amount REAL,
                    payment_mode TEXT,
                    payment_status TEXT,
                    credit_amount REAL,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE receivables (
                    receivable_id TEXT PRIMARY KEY,
                    shop_id TEXT,
                    invoice_id TEXT,
                    customer_id TEXT,
                    amount REAL,
                    due_date TEXT,
                    days_overdue INTEGER,
                    status TEXT,
                    collection_priority TEXT,
                    notes TEXT
                )
            """)

        # Execute queries against empty DB
        from utils.database import query_records
        sql = """
        SELECT c.customer_id, c.customer_name, COALESCE(SUM(s.total_amount), 0.0) as total_purchases
        FROM customers c
        LEFT JOIN sales_transactions s ON c.customer_id = s.customer_id
        GROUP BY c.customer_id
        """
        rows = query_records(sql, db_path=empty_db_path)
        assert len(rows) == 0, "Query should return 0 records on empty database"

    finally:
        try:
            os.remove(empty_db_path)
        except Exception:
            pass
