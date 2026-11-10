"""
Centralized Database Connection and Management Module for BizMetrics.
Manages SQLite schemas, transactions, CSV data imports, foreign key integrity,
and unified querying across all application modules.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator
import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / "bizmetrics.db"
AUTH_DB_PATH = APP_ROOT / "bizmetrics_auth.db"

_THREAD_LOCAL = threading.local()

def _get_cloud_secret(key: str, default: str = "") -> str:
    """Fetch secret from st.secrets first, falling back to os.environ and finally default."""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                return val
    except Exception:
        pass
    val = os.getenv(key)
    if val and str(val).strip():
        return str(val).strip()
    return default


_IS_PROD_ENV = _get_cloud_secret("BIZMETRICS_ENV", "development").lower() == "production"
DEFAULT_SHOP_ID = "shivansh_electronics_hardware"
DEFAULT_SHOP_NAME = "Shivansh Electronics and Hardware"
DEFAULT_OWNER_NAME = _get_cloud_secret("BIZMETRICS_OWNER_NAME", "Shivansh G")
DEFAULT_OWNER_PASSWORD = _get_cloud_secret("BIZMETRICS_OWNER_PASSWORD", "" if _IS_PROD_ENV else "Shivansh@1212")

CONSOLIDATED_MASTER_COLUMNS: list[str] = [
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


def _clean_numeric(val: Any) -> float:
    """Safely convert strings with currency symbols or commas into float."""
    if val is None or pd.isna(val):
        return 0.0
    s = str(val).replace("₹", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _clean_str(val: Any, default: str = "") -> str:
    """Safely clean strings."""
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    return default if s.lower() in {"nan", "none"} else s


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """
    Return a high-performance, thread-pooled SQLite connection.
    Enables WAL mode, foreign keys, and in-memory temporary cache.
    """
    target_path = str(Path(db_path) if db_path else DB_PATH)
    pool = getattr(_THREAD_LOCAL, "db_pool", None)
    if pool is None:
        pool = {}
        _THREAD_LOCAL.db_pool = pool

    conn = pool.get(target_path)
    if conn is not None:
        try:
            conn.execute("SELECT 1;")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            pool.pop(target_path, None)

    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    pool[target_path] = conn
    return conn


@contextmanager
def get_db_cursor(commit: bool = True, db_path: Path | str | None = None) -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for safe database transactions with automatic commit/rollback and connection reuse."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


_INITIALIZED_DBS: set[str] = set()

def _migrate_database_schema(cur: sqlite3.Cursor) -> None:
    """
    Safely and idempotently verifies table schemas, adding any missing columns
    to preserve existing data on databases without deleting or resetting anything.
    """
    try:
        # Check shops table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shops'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(shops)")
            cols = {row[1] if isinstance(row, tuple) else row["name"] for row in cur.fetchall()}
            if "owner_name" not in cols:
                cur.execute("ALTER TABLE shops ADD COLUMN owner_name TEXT DEFAULT 'Shivansh G'")
            if "phone" not in cols:
                cur.execute("ALTER TABLE shops ADD COLUMN phone TEXT DEFAULT '+91 98765 43210'")
            if "address" not in cols:
                cur.execute("ALTER TABLE shops ADD COLUMN address TEXT DEFAULT 'Raipur, Chhattisgarh'")

        # Check users table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(users)")
            cols = {row[1] if isinstance(row, tuple) else row["name"] for row in cur.fetchall()}
            if "role" not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'Owner'")
            if "shop_id" not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware'")

        # Check customers table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customers'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(customers)")
            cols = {row[1] if isinstance(row, tuple) else row["name"] for row in cur.fetchall()}
            if "shop_id" not in cols:
                cur.execute("ALTER TABLE customers ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware'")
            if "outstanding_amount" not in cols:
                cur.execute("ALTER TABLE customers ADD COLUMN outstanding_amount REAL DEFAULT 0.0")

        # Check customer_notifications table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_notifications'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(customer_notifications)")
            cols = {row[1] if isinstance(row, tuple) else row["name"] for row in cur.fetchall()}
            if "category" not in cols:
                cur.execute("ALTER TABLE customer_notifications ADD COLUMN category TEXT NOT NULL DEFAULT 'Announcement'")
            if "action_link" not in cols:
                cur.execute("ALTER TABLE customer_notifications ADD COLUMN action_link TEXT")

        # Check customer_support_tickets table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_support_tickets'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(customer_support_tickets)")
            cols = {row[1] if isinstance(row, tuple) else row["name"] for row in cur.fetchall()}
            if "priority" not in cols:
                cur.execute("ALTER TABLE customer_support_tickets ADD COLUMN priority TEXT DEFAULT 'Medium'")
    except Exception as exc:
        print(f"Notice: schema migration check: {exc}")

def init_database(db_path: Path | str | None = None) -> None:
    """
    Creates and verifies all required tables, indexes, and views for BizMetrics.
    Reuses existing schemas and guarantees data integrity.
    """
    target = str(db_path or DB_PATH)
    if target in _INITIALIZED_DBS:
        return
    with get_db_cursor(commit=True, db_path=db_path) as cur:
        # 0. Run idempotent schema migration checks first
        _migrate_database_schema(cur)

        # 1. SHOPS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS shops (
                shop_id TEXT PRIMARY KEY,
                shop_name TEXT NOT NULL,
                owner_name TEXT DEFAULT 'Shivansh G',
                phone TEXT DEFAULT '+91 98765 43210',
                address TEXT DEFAULT 'Raipur, Chhattisgarh',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 2. USERS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Owner',
                shop_id TEXT NOT NULL REFERENCES shops(shop_id),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 3. CUSTOMER CREDENTIALS (Reused from bizmetrics_auth.db)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shop_id, customer_id),
                FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
            )
            """
        )

        # 4. CUSTOMERS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                customer_name TEXT NOT NULL,
                business_name TEXT,
                contact_number TEXT,
                email TEXT,
                city TEXT,
                customer_type TEXT,
                registration_date TEXT,
                customer_rating REAL DEFAULT 0.0,
                outstanding_amount REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 5. VENDORS / SUPPLIERS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                vendor_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                vendor_name TEXT NOT NULL,
                material_type TEXT,
                total_ordered_amount REAL DEFAULT 0.0,
                total_paid_amount REAL DEFAULT 0.0,
                outstanding_balance REAL DEFAULT 0.0,
                next_payment_date TEXT,
                credit_days_allowed INTEGER DEFAULT 30,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 6. PRODUCTS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                product_name TEXT NOT NULL,
                category TEXT,
                sector TEXT,
                unit TEXT DEFAULT 'Piece',
                purchase_price REAL NOT NULL DEFAULT 0.0,
                selling_price REAL NOT NULL DEFAULT 0.0,
                description TEXT,
                supplier_id TEXT REFERENCES vendors(vendor_id),
                lead_time_days INTEGER DEFAULT 5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 7. INVENTORY
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                product_id TEXT NOT NULL UNIQUE REFERENCES products(product_id),
                current_stock REAL NOT NULL DEFAULT 0.0,
                minimum_stock REAL NOT NULL DEFAULT 0.0,
                maximum_stock REAL NOT NULL DEFAULT 0.0,
                reorder_level REAL NOT NULL DEFAULT 0.0,
                status TEXT DEFAULT 'Healthy',
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 8. SALES TRANSACTIONS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_transactions (
                sale_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                date TEXT NOT NULL,
                customer_id TEXT NOT NULL REFERENCES customers(customer_id),
                product_id TEXT NOT NULL REFERENCES products(product_id),
                quantity REAL NOT NULL DEFAULT 1.0,
                selling_price REAL NOT NULL DEFAULT 0.0,
                discount_percent REAL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                payment_mode TEXT DEFAULT 'Cash',
                payment_status TEXT DEFAULT 'Completed',
                credit_amount REAL DEFAULT 0.0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 9. EXPENSES
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL DEFAULT 0.0,
                payment_status TEXT DEFAULT 'Paid',
                is_fixed TEXT DEFAULT 'No',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 10. RECEIVABLES
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS receivables (
                receivable_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                invoice_id TEXT,
                customer_id TEXT NOT NULL REFERENCES customers(customer_id),
                amount REAL NOT NULL DEFAULT 0.0,
                due_date TEXT,
                days_overdue INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Pending',
                collection_priority TEXT DEFAULT 'P4: Low',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 11. LOANS & EMI
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS loans_emi (
                loan_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                loan_provider TEXT NOT NULL,
                principal_amount REAL NOT NULL DEFAULT 0.0,
                interest_rate REAL NOT NULL DEFAULT 0.0,
                tenure_months INTEGER NOT NULL DEFAULT 12,
                monthly_emi REAL NOT NULL DEFAULT 0.0,
                outstanding_principal REAL NOT NULL DEFAULT 0.0,
                start_date TEXT,
                next_due_date TEXT,
                loan_type TEXT,
                status TEXT DEFAULT 'Active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 12. GOVERNMENT SCHEMES
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS government_schemes (
                scheme_id TEXT PRIMARY KEY,
                scheme_name TEXT NOT NULL,
                ministry TEXT NOT NULL,
                category TEXT NOT NULL,
                tag TEXT,
                loan_amount TEXT,
                subsidy_rate TEXT,
                eligibility TEXT,
                application_portal TEXT,
                color TEXT,
                badge_icon TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 13. BUSINESS LOCATIONS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_locations (
                location_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                location_name TEXT NOT NULL,
                location_type TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                city TEXT,
                state TEXT DEFAULT 'Chhattisgarh',
                verified INTEGER DEFAULT 1,
                osm_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 14. CUSTOMER SUPPORT TICKETS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_support_tickets (
                ticket_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                customer_id TEXT NOT NULL REFERENCES customers(customer_id),
                category TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Normal',
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                resolution_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 15. CUSTOMER NOTIFICATIONS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_notifications (
                notification_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                customer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Announcement',
                is_read INTEGER DEFAULT 0,
                action_link TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 16. LOCAL BUSINESS DIRECTORY (DURG & BHILAI OSM DATASET)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS local_business_directory (
                business_id TEXT PRIMARY KEY,
                osm_id INTEGER,
                business_name TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                locality TEXT,
                city TEXT NOT NULL,
                ward TEXT,
                district TEXT DEFAULT 'Durg',
                address TEXT,
                source TEXT DEFAULT 'OpenStreetMap (ODbL 1.0)',
                reference_year INTEGER DEFAULT 2024,
                contact_info TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 17. LOCAL DEMOGRAPHICS (CENSUS 2011 / DISTRICT DURG)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS local_demographics (
                demographic_id TEXT PRIMARY KEY,
                area_name TEXT NOT NULL,
                admin_type TEXT NOT NULL,
                district TEXT DEFAULT 'Durg',
                total_population INTEGER,
                male_population INTEGER,
                female_population INTEGER,
                urban_population INTEGER,
                rural_population INTEGER,
                total_households INTEGER,
                literacy_rate REAL,
                workforce_total INTEGER,
                main_workers INTEGER,
                marginal_workers INTEGER,
                cultivators INTEGER,
                agricultural_labourers INTEGER,
                household_industry INTEGER,
                other_workers INTEGER,
                census_year INTEGER DEFAULT 2011,
                source TEXT DEFAULT 'Census of India 2011 / District Census Handbook Durg',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 18. LOCAL ECONOMIC INDICATORS (DURG DISTRICT & CHHATTISGARH)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS local_economic_indicators (
                indicator_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                indicator_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                indicator_value REAL NOT NULL,
                reference_period TEXT NOT NULL,
                source TEXT NOT NULL,
                locality_scope TEXT DEFAULT 'Durg District',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 19. LOCAL GEOGRAPHIC DATA (LOCALITIES, HUBS, CATCHMENTS)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS local_geographic_data (
                geo_id TEXT PRIMARY KEY,
                area_name TEXT NOT NULL,
                geo_type TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                radius_km REAL,
                parent_city TEXT,
                district TEXT DEFAULT 'Durg',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 20. DATASET SOURCES & PROVENANCE METADATA
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_sources (
                source_id TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                source_organization TEXT NOT NULL,
                source_url TEXT,
                license TEXT NOT NULL,
                reference_year TEXT,
                coverage_area TEXT,
                record_count INTEGER,
                last_verified TEXT,
                limitations TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 21. AUDIT LOGS (Audit Trail)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware',
                username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                ip_address TEXT DEFAULT '127.0.0.1',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 22. PURCHASE ORDERS (Supplier & Purchase Management)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_orders (
                po_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                vendor_id TEXT NOT NULL REFERENCES vendors(vendor_id),
                order_date TEXT NOT NULL,
                expected_date TEXT,
                total_amount REAL NOT NULL DEFAULT 0.0,
                tax_amount REAL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'Draft',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 23. PURCHASE ORDER ITEMS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id TEXT NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
                product_id TEXT NOT NULL REFERENCES products(product_id),
                quantity REAL NOT NULL DEFAULT 1.0,
                unit_price REAL NOT NULL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 24. SUPPLIER PAYMENTS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS supplier_payments (
                payment_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware' REFERENCES shops(shop_id),
                vendor_id TEXT NOT NULL REFERENCES vendors(vendor_id),
                po_id TEXT,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0.0,
                payment_mode TEXT DEFAULT 'Bank Transfer',
                reference_no TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 25. IMPORT LOGS (Smart Data Import Center)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS import_logs (
                import_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware',
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                target_table TEXT NOT NULL,
                total_rows INTEGER DEFAULT 0,
                imported_rows INTEGER DEFAULT 0,
                duplicate_rows INTEGER DEFAULT 0,
                error_rows INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Completed',
                error_details TEXT,
                imported_by TEXT DEFAULT 'Shivansh G',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 26. DATABASE BACKUPS (Backup & Restore)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS database_backups (
                backup_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                backup_type TEXT DEFAULT 'Manual',
                checksum TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 27. OFFLINE SYNC QUEUE (Offline & Synchronization Support)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_sync_queue (
                queue_id TEXT PRIMARY KEY,
                client_tx_id TEXT UNIQUE NOT NULL,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware',
                operation_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                retry_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                synced_at TEXT
            )
            """
        )

        # 28. DAILY BUSINESS SUMMARIES (Daily Reports)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_business_summaries (
                summary_id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL DEFAULT 'shivansh_electronics_hardware',
                report_date TEXT NOT NULL,
                total_sales REAL DEFAULT 0.0,
                total_expenses REAL DEFAULT 0.0,
                gross_profit REAL DEFAULT 0.0,
                net_profit REAL DEFAULT 0.0,
                new_customers INTEGER DEFAULT 0,
                cash_collected REAL DEFAULT 0.0,
                credit_extended REAL DEFAULT 0.0,
                receivables_pending REAL DEFAULT 0.0,
                low_stock_alerts_count INTEGER DEFAULT 0,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shop_id, report_date)
            )
            """
        )

        # 29. GST TAX CONFIGS (GST & Tax Analytics)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gst_tax_configs (
                config_id TEXT PRIMARY KEY,
                shop_id TEXT UNIQUE NOT NULL REFERENCES shops(shop_id),
                gstin TEXT NOT NULL DEFAULT '22AAAAA0000A1Z5',
                legal_name TEXT NOT NULL DEFAULT 'Shivansh Electronics and Hardware',
                state_code TEXT NOT NULL DEFAULT '22',
                default_cgst_pct REAL DEFAULT 9.0,
                default_sgst_pct REAL DEFAULT 9.0,
                default_igst_pct REAL DEFAULT 18.0,
                composition_scheme INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Ensure address column exists on customers table
        try:
            cur.execute("ALTER TABLE customers ADD COLUMN address TEXT DEFAULT '';")
        except Exception:
            pass

        # INDEXES FOR OPTIMAL QUERY PERFORMANCE
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_transactions(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_cust ON sales_transactions(customer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_prod ON sales_transactions(product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON sales_transactions(shop_id, date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_cust ON sales_transactions(shop_id, customer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_prod ON sales_transactions(shop_id, product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exp_shop_date ON expenses(shop_id, date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_prod ON inventory(product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_shop_prod ON inventory(shop_id, product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_due ON receivables(due_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_shop_status ON receivables(shop_id, status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cust_cred ON customer_credentials(shop_id, customer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lbd_city_cat ON local_business_directory(city, category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lbd_loc ON local_business_directory(locality);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lbd_coords ON local_business_directory(latitude, longitude);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ldemo_area ON local_demographics(area_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);")

        # VIEWS
        cur.execute(
            """
            CREATE VIEW IF NOT EXISTS v_products_inventory AS
            SELECT 
                p.product_id,
                p.shop_id,
                p.product_name,
                p.category,
                p.sector,
                p.unit,
                p.purchase_price,
                p.selling_price,
                p.description,
                p.supplier_id,
                p.lead_time_days,
                i.current_stock,
                i.minimum_stock,
                i.maximum_stock,
                i.reorder_level,
                i.status,
                i.last_updated
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id;
            """
        )

        # SEED DEFAULT SHOP & OWNER USER
        _migrate_database_schema(cur)
        try:
            cur.execute(
                """
                INSERT INTO shops (shop_id, shop_name, owner_name, phone, address)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(shop_id) DO UPDATE SET
                    shop_name = excluded.shop_name,
                    owner_name = excluded.owner_name
                """,
                (DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME, DEFAULT_OWNER_NAME, "+91 98765 43210", "Raipur, Chhattisgarh"),
            )
        except Exception as exc:
            print(f"Notice: shop seed: {exc}")

        # Seed Multi-Branch Network (Multi-Shop Management)
        branches = [
            ("shivansh_bhilai_branch", "Shivansh Electronics - Bhilai Branch", "Shivansh G", "+91 98765 43211", "Power House Market, Bhilai Nagar"),
            ("shivansh_durg_branch", "Shivansh Hardware - Durg Branch", "Shivansh G", "+91 98765 43212", "Station Road Commercial Hub, Durg")
        ]
        for b_id, b_name, b_owner, b_phone, b_addr in branches:
            try:
                cur.execute(
                    """
                    INSERT INTO shops (shop_id, shop_name, owner_name, phone, address)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(shop_id) DO UPDATE SET
                        shop_name = excluded.shop_name,
                        owner_name = excluded.owner_name
                    """,
                    (b_id, b_name, b_owner, b_phone, b_addr),
                )
            except Exception as exc:
                print(f"Notice: branch seed: {exc}")

        # Seed Default GST Config
        cur.execute(
            """
            INSERT INTO gst_tax_configs (config_id, shop_id, gstin, legal_name, state_code, default_cgst_pct, default_sgst_pct, default_igst_pct, composition_scheme)
            VALUES ('GST_CONF_001', ?, '22AAAAA0000A1Z5', ?, '22', 9.0, 9.0, 18.0, 0)
            ON CONFLICT(shop_id) DO NOTHING;
            """,
            (DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME),
        )

        if DEFAULT_OWNER_PASSWORD:
            owner_hash = hashlib.sha256(DEFAULT_OWNER_PASSWORD.encode()).hexdigest()
            cur.execute(
                """
                INSERT INTO users (username, full_name, password_hash, role, shop_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    full_name = excluded.full_name,
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    shop_id = excluded.shop_id
                """,
                (DEFAULT_OWNER_NAME, DEFAULT_OWNER_NAME, owner_hash, "Owner", DEFAULT_SHOP_ID),
            )
            cur.execute(
                """
                INSERT INTO users (username, full_name, password_hash, role, shop_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    full_name = excluded.full_name,
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    shop_id = excluded.shop_id
                """,
                (DEFAULT_OWNER_NAME.lower().replace(" ", ""), DEFAULT_OWNER_NAME, owner_hash, "Owner", DEFAULT_SHOP_ID),
            )

        # Seed core operational records (customers, credentials, sales, receivables) if default database is empty
        if target == DB_PATH:
            try:
                cur.execute("SELECT COUNT(*) FROM customers")
                c_cnt = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sales_transactions")
                s_cnt = cur.fetchone()[0]
                if c_cnt == 0 or s_cnt == 0:
                    _seed_core_business_data(cur)
            except Exception as e:
                print(f"Notice: core business data auto-seed: {e}")

        # Seed verified public Durg-Bhilai datasets if local_demographics table is empty
        try:
            cur.execute("SELECT COUNT(*) FROM local_demographics")
            if cur.fetchone()[0] == 0:
                _seed_public_durg_bhilai_data(cur)
        except Exception as e:
            print(f"Notice: public Durg-Bhilai auto-seed: {e}")

    _INITIALIZED_DBS.add(target)

    # Guarantee core operational business data if sales_transactions is empty in cloud mode for default DB
    if target == DB_PATH:
        try:
            orig_csv = APP_ROOT / "03_sales_transactions.csv"
            if not orig_csv.is_file():
                with get_connection(target) as chk_conn:
                    cnt = chk_conn.execute("SELECT COUNT(*) FROM sales_transactions").fetchone()[0]
                if cnt == 0:
                    with get_connection(target) as seed_conn:
                        _seed_core_business_data(seed_conn.cursor())
                        seed_conn.commit()
        except Exception as e:
            print(f"Notice: initial sales import: {e}")


def import_all_csvs(db_path: Path | str | None = None) -> dict[str, Any]:
    """
    Imports all original CSV files into their corresponding database tables.
    Validates data types, strips formatting symbols, maintains foreign-key integrity,
    and prevents duplicate entries.
    """
    init_database(db_path)
    summary: dict[str, Any] = {
        "status": "success",
        "imported": {},
        "preserved_existing": {},
        "errors": []
    }

    with get_db_cursor(commit=True, db_path=db_path) as cur:
        # 1. IMPORT VENDORS FIRST (To satisfy foreign keys in products)
        vendors_csv = APP_ROOT / "06_vendors_payables.csv"
        if vendors_csv.is_file():
            df_v = pd.read_csv(vendors_csv)
            v_count = 0
            for _, r in df_v.iterrows():
                vid = _clean_str(r.get("Vendor_ID"))
                if not vid:
                    continue
                cur.execute(
                    """
                    INSERT INTO vendors (vendor_id, shop_id, vendor_name, material_type, total_ordered_amount, total_paid_amount, outstanding_balance, next_payment_date, credit_days_allowed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(vendor_id) DO UPDATE SET
                        vendor_name = excluded.vendor_name,
                        total_ordered_amount = excluded.total_ordered_amount,
                        outstanding_balance = excluded.outstanding_balance
                    """,
                    (
                        vid,
                        DEFAULT_SHOP_ID,
                        _clean_str(r.get("Vendor_Name"), f"Vendor {vid}"),
                        _clean_str(r.get("Material_Type")),
                        _clean_numeric(r.get("Total_Ordered_Amount")),
                        _clean_numeric(r.get("Total_Paid_Amount")),
                        _clean_numeric(r.get("Outstanding_Balance")),
                        _clean_str(r.get("Next_Payment_Date")),
                        int(_clean_numeric(r.get("Credit_Days_Allowed")) or 30),
                    )
                )
                v_count += 1
            summary["imported"]["vendors"] = v_count

        # Ensure all suppliers referenced by products exist
        prod_csv = APP_ROOT / "02_products_inventory.csv"
        if prod_csv.is_file():
            df_p_temp = pd.read_csv(prod_csv)
            for supp_id in df_p_temp.get("Supplier_ID", pd.Series(dtype=str)).dropna().unique():
                sid = str(supp_id).strip()
                cur.execute(
                    """
                    INSERT OR IGNORE INTO vendors (vendor_id, shop_id, vendor_name, material_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sid, DEFAULT_SHOP_ID, f"Supplier {sid}", "Hardware & Electricals")
                )

        # 2. IMPORT CUSTOMERS (05_customers_receivables.csv)
        cust_csv = APP_ROOT / "05_customers_receivables.csv"
        if cust_csv.is_file():
            df_c = pd.read_csv(cust_csv)
            c_count = 0
            for _, r in df_c.iterrows():
                cid = _clean_str(r.get("Customer_ID"))
                if not cid:
                    continue
                cname = _clean_str(r.get("Customer_Name"), f"Customer {cid}")
                cur.execute(
                    """
                    INSERT INTO customers (customer_id, shop_id, customer_name, business_name, contact_number, email, city, customer_type, registration_date, customer_rating, outstanding_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(customer_id) DO UPDATE SET
                        customer_name = excluded.customer_name,
                        business_name = excluded.business_name,
                        outstanding_amount = excluded.outstanding_amount
                    """,
                    (
                        cid,
                        DEFAULT_SHOP_ID,
                        cname,
                        _clean_str(r.get("Business_Name")),
                        _clean_str(r.get("Contact_Number")),
                        _clean_str(r.get("Email")),
                        _clean_str(r.get("City")),
                        _clean_str(r.get("Customer_Type")),
                        _clean_str(r.get("Registration_Date")),
                        _clean_numeric(r.get("Customer_Rating")),
                        _clean_numeric(r.get("Outstanding_Amount")),
                    )
                )
                # Ensure customer credentials entry exists
                p_hash = hashlib.sha256(cid.encode("utf-8")).hexdigest()
                cur.execute(
                    """
                    INSERT INTO customer_credentials (shop_id, customer_id, customer_name, password_hash)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(shop_id, customer_id) DO UPDATE SET
                        customer_name = excluded.customer_name
                    """,
                    (DEFAULT_SHOP_ID, cid, cname, p_hash)
                )
                c_count += 1
            summary["imported"]["customers"] = c_count

        # Ensure any walk-in customer IDs appearing in sales (e.g. CUST037-CUST040) exist in customers
        sales_csv = APP_ROOT / "03_sales_transactions.csv"
        if sales_csv.is_file():
            df_s_temp = pd.read_csv(sales_csv)
            for cid in df_s_temp.get("Customer_ID", pd.Series(dtype=str)).dropna().unique():
                cid_str = str(cid).strip()
                cur.execute(
                    """
                    INSERT OR IGNORE INTO customers (customer_id, shop_id, customer_name, customer_type, city)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (cid_str, DEFAULT_SHOP_ID, f"Customer {cid_str}", "Retail Customer", "Raipur")
                )
                p_hash = hashlib.sha256(cid_str.encode("utf-8")).hexdigest()
                cur.execute(
                    """
                    INSERT OR IGNORE INTO customer_credentials (shop_id, customer_id, customer_name, password_hash)
                    VALUES (?, ?, ?, ?)
                    """,
                    (DEFAULT_SHOP_ID, cid_str, f"Customer {cid_str}", p_hash)
                )

        # 3. IMPORT PRODUCTS & INVENTORY (02_products_inventory.csv)
        if prod_csv.is_file():
            df_p = pd.read_csv(prod_csv)
            p_count = 0
            i_count = 0
            for _, r in df_p.iterrows():
                pid = _clean_str(r.get("Product_ID"))
                if not pid:
                    continue
                cur.execute(
                    """
                    INSERT INTO products (product_id, shop_id, product_name, category, sector, unit, purchase_price, selling_price, description, supplier_id, lead_time_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET
                        product_name = excluded.product_name,
                        purchase_price = excluded.purchase_price,
                        selling_price = excluded.selling_price
                    """,
                    (
                        pid,
                        DEFAULT_SHOP_ID,
                        _clean_str(r.get("Product_Name"), f"Product {pid}"),
                        _clean_str(r.get("Category")),
                        _clean_str(r.get("Sector")),
                        _clean_str(r.get("Unit"), "Piece"),
                        _clean_numeric(r.get("Purchase_Price")),
                        _clean_numeric(r.get("Selling_Price")),
                        _clean_str(r.get("Description")),
                        _clean_str(r.get("Supplier_ID")),
                        int(_clean_numeric(r.get("Lead_Time_Days")) or 5),
                    )
                )
                p_count += 1

                cur.execute(
                    """
                    INSERT INTO inventory (shop_id, product_id, current_stock, minimum_stock, maximum_stock, reorder_level, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET
                        current_stock = excluded.current_stock,
                        minimum_stock = excluded.minimum_stock,
                        maximum_stock = excluded.maximum_stock,
                        reorder_level = excluded.reorder_level,
                        status = excluded.status
                    """,
                    (
                        DEFAULT_SHOP_ID,
                        pid,
                        _clean_numeric(r.get("Current_Stock")),
                        _clean_numeric(r.get("Minimum_Stock")),
                        _clean_numeric(r.get("Maximum_Stock")),
                        _clean_numeric(r.get("Reorder_Level")),
                        _clean_str(r.get("Status"), "Healthy"),
                    )
                )
                i_count += 1

            summary["imported"]["products"] = p_count
            summary["imported"]["inventory"] = i_count

        # 4. IMPORT SALES TRANSACTIONS (03_sales_transactions.csv)
        if sales_csv.is_file():
            df_s = pd.read_csv(sales_csv)
            s_count = 0
            rec_count = 0
            now = pd.Timestamp.today().normalize()

            for _, r in df_s.iterrows():
                sid = _clean_str(r.get("Sale_ID"))
                if not sid:
                    continue
                cid = _clean_str(r.get("Customer_ID"))
                pid = _clean_str(r.get("Product_ID"))
                cur.execute(
                    """
                    INSERT INTO sales_transactions (sale_id, shop_id, date, customer_id, product_id, quantity, selling_price, discount_percent, total_amount, payment_mode, payment_status, credit_amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sale_id) DO UPDATE SET
                        total_amount = excluded.total_amount,
                        payment_status = excluded.payment_status
                    """,
                    (
                        sid,
                        DEFAULT_SHOP_ID,
                        _clean_str(r.get("Date")),
                        cid,
                        pid,
                        _clean_numeric(r.get("Quantity")),
                        _clean_numeric(r.get("Selling_Price")),
                        _clean_numeric(r.get("Discount_Percent")),
                        _clean_numeric(r.get("Total_Amount")),
                        _clean_str(r.get("Payment_Mode"), "Cash"),
                        _clean_str(r.get("Payment_Status"), "Completed"),
                        _clean_numeric(r.get("Credit_Amount")),
                        _clean_str(r.get("Notes")),
                    )
                )
                s_count += 1

                # If this is an unpaid credit sale, record in receivables
                pay_mode = _clean_str(r.get("Payment_Mode")).lower()
                pay_status = _clean_str(r.get("Payment_Status")).lower()
                c_amt = _clean_numeric(r.get("Credit_Amount"))
                if pay_status == "pending" or pay_mode == "credit" or c_amt > 0:
                    rec_id = f"REC-{sid}"
                    sale_date = _clean_str(r.get("Date"))
                    try:
                        due_date = (pd.to_datetime(sale_date) + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
                        days_over = max(0, (now - pd.to_datetime(due_date)).days)
                    except Exception:
                        due_date = sale_date
                        days_over = 0

                    if days_over > 90 or (days_over > 60 and c_amt >= 20000):
                        prio = "P1: URGENT"
                    elif days_over > 60 or (days_over > 30 and c_amt >= 10000):
                        prio = "P2: High"
                    elif days_over > 30:
                        prio = "P3: Medium"
                    else:
                        prio = "P4: Low"

                    cur.execute(
                        """
                        INSERT INTO receivables (receivable_id, shop_id, invoice_id, customer_id, amount, due_date, days_overdue, status, collection_priority, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(receivable_id) DO UPDATE SET
                            amount = excluded.amount,
                            days_overdue = excluded.days_overdue,
                            collection_priority = excluded.collection_priority
                        """,
                        (rec_id, DEFAULT_SHOP_ID, sid, cid, c_amt or _clean_numeric(r.get("Total_Amount")), due_date, days_over, "Pending", prio, f"Credit invoice from sale {sid}")
                    )
                    rec_count += 1

            summary["imported"]["sales_transactions"] = s_count
            summary["imported"]["receivables"] = rec_count

        # 5. IMPORT EXPENSES (04_expenses.csv)
        exp_csv = APP_ROOT / "04_expenses.csv"
        if exp_csv.is_file():
            df_e = pd.read_csv(exp_csv)
            e_count = 0
            for _, r in df_e.iterrows():
                eid = _clean_str(r.get("Expense_ID"))
                if not eid:
                    continue
                cur.execute(
                    """
                    INSERT INTO expenses (expense_id, shop_id, date, category, description, amount, payment_status, is_fixed, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(expense_id) DO UPDATE SET
                        amount = excluded.amount,
                        description = excluded.description
                    """,
                    (
                        eid,
                        DEFAULT_SHOP_ID,
                        _clean_str(r.get("Date")),
                        _clean_str(r.get("Category")),
                        _clean_str(r.get("Description")),
                        _clean_numeric(r.get("Amount")),
                        _clean_str(r.get("Payment_Status"), "Paid"),
                        _clean_str(r.get("Is_Fixed"), "No"),
                        _clean_str(r.get("Notes")),
                    )
                )
                e_count += 1
            summary["imported"]["expenses"] = e_count

        # 6. IMPORT LOANS & EMI (07_loans_emi.csv)
        loans_csv = APP_ROOT / "07_loans_emi.csv"
        if loans_csv.is_file():
            df_l = pd.read_csv(loans_csv)
            l_count = 0
            for _, r in df_l.iterrows():
                lid = _clean_str(r.get("Loan_ID"))
                if not lid:
                    continue
                cur.execute(
                    """
                    INSERT INTO loans_emi (loan_id, shop_id, loan_provider, principal_amount, interest_rate, tenure_months, monthly_emi, outstanding_principal, start_date, next_due_date, loan_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(loan_id) DO UPDATE SET
                        outstanding_principal = excluded.outstanding_principal,
                        next_due_date = excluded.next_due_date
                    """,
                    (
                        lid,
                        DEFAULT_SHOP_ID,
                        _clean_str(r.get("Loan_Provider"), "SBI Bank"),
                        _clean_numeric(r.get("Principal_Amount")),
                        _clean_numeric(r.get("Interest_Rate")),
                        int(_clean_numeric(r.get("Tenure_Months")) or 12),
                        _clean_numeric(r.get("Monthly_EMI")),
                        _clean_numeric(r.get("Outstanding_Principal")),
                        _clean_str(r.get("Start_Date")),
                        _clean_str(r.get("Next_Due_Date")),
                        _clean_str(r.get("Loan_Type")),
                        _clean_str(r.get("Status"), "Active"),
                    )
                )
                l_count += 1
            summary["imported"]["loans_emi"] = l_count

        # 7. IMPORT GOVERNMENT SCHEMES
        schemes_catalog = [
            ("SCHEME_01", "PM SVANidhi", "Ministry of Housing & Urban Affairs", "Credit & Finance", "Micro Credit", "Up to ₹50,000", "7% Interest Subsidy", "Street vendors with valid CoV / LOR", "https://pmsvanidhi.mohua.gov.in/", "#2563EB", "🛒"),
            ("SCHEME_02", "PMEGP (Prime Minister's Employment Generation Programme)", "Ministry of MSME", "Subsidies & Capital", "Capital Subsidy", "Up to ₹50 Lakh (Manufacturing) / ₹20 Lakh (Service)", "15% - 35% Margin Money Subsidy", "Any individual above 18 years, 8th pass for > ₹10L projects", "https://www.kviconline.gov.in/pmegpeportal/", "#EA580C", "🏭"),
            ("SCHEME_03", "Pradhan Mantri Mudra Yojana (PMMY)", "Ministry of Finance", "Credit & Finance", "Collateral-Free Loan", "Shishu (₹50k), Kishore (₹50k-₹5L), Tarun (₹5L-₹10L)", "Nil upfront processing fee", "Non-corporate, non-farm small/micro enterprises", "https://www.mudra.org.in/", "#2563EB", "💰"),
            ("SCHEME_04", "Stand-Up India Scheme", "Ministry of Finance", "Credit & Finance", "SC/ST & Women", "₹10 Lakh to ₹1 Crore", "Composite loan (term loan & working capital)", "SC/ST and/or woman entrepreneur, greenfield enterprise", "https://www.standupmitra.in/", "#2563EB", "🌟"),
            ("SCHEME_05", "CGTMSE (Credit Guarantee Fund Trust for MSEs)", "Ministry of MSME & SIDBI", "Credit & Finance", "Credit Guarantee", "Up to ₹500 Lakh", "75% - 85% guarantee coverage", "New and existing Micro and Small Enterprises", "https://www.cgtmse.in/", "#2563EB", "🛡️"),
            ("SCHEME_06", "PM Vishwakarma Scheme", "Ministry of MSME", "Training & Skilling", "Artisans & Craftsmen", "Collateral-free enterprise loan up to ₹3 Lakh (Tranche 1: ₹1L, Tranche 2: ₹2L)", "Concessional 5% interest rate, skill stipend ₹500/day, toolkit incentive ₹15,000", "Traditional artisans in 18 trades (Carpenter, Blacksmith, Sculptor, Cobbler, etc.)", "https://pmvishwakarma.gov.in/", "#9333EA", "⚒️"),
        ]
        sc_count = 0
        for sid, sname, min_name, cat, tag, amt, sub, elig, link, col, icon in schemes_catalog:
            cur.execute(
                """
                INSERT INTO government_schemes (scheme_id, scheme_name, ministry, category, tag, loan_amount, subsidy_rate, eligibility, application_portal, color, badge_icon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scheme_id) DO UPDATE SET
                    scheme_name = excluded.scheme_name,
                    ministry = excluded.ministry,
                    loan_amount = excluded.loan_amount,
                    application_portal = excluded.application_portal
                """,
                (sid, sname, min_name, cat, tag, amt, sub, elig, link, col, icon)
            )
            sc_count += 1
        summary["imported"]["government_schemes"] = sc_count

        # 8. IMPORT BUSINESS LOCATIONS (From verified OSM repository)
        osm_path = APP_ROOT / "data" / "sources" / "osm_verified_businesses.json"
        loc_count = 0
        # First add default shop location
        cur.execute(
            """
            INSERT INTO business_locations (location_id, shop_id, location_name, location_type, latitude, longitude, address, city, state, verified, osm_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(location_id) DO UPDATE SET
                location_name = excluded.location_name
            """,
            ("LOC_STORE_01", DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME, "Operating Store", 21.2514, 81.6296, "Station Road, Pandri", "Raipur", "Chhattisgarh", 1, "OSM_STORE_01")
        )
        loc_count += 1

        if osm_path.is_file():
            try:
                with open(osm_path, "r", encoding="utf-8") as f:
                    osm_data = json.load(f)
                cities_dict = osm_data.get("cities", {})
                for city_name, city_info in cities_dict.items():
                    for b in city_info.get("businesses", []):
                        oid = str(b.get("osm_id", f"LOC_{loc_count}"))
                        loc_id = f"LOC_{oid}"
                        b_type = "Direct Competitor" if b.get("type") == "competitor" else "Commercial Opportunity"
                        cur.execute(
                            """
                            INSERT INTO business_locations (location_id, shop_id, location_name, location_type, latitude, longitude, address, city, state, verified, osm_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(location_id) DO UPDATE SET
                                location_name = excluded.location_name,
                                location_type = excluded.location_type,
                                latitude = excluded.latitude,
                                longitude = excluded.longitude
                            """,
                            (
                                loc_id,
                                DEFAULT_SHOP_ID,
                                _clean_str(b.get("name")),
                                b_type,
                                float(b.get("lat", 0.0)),
                                float(b.get("lon", 0.0)),
                                _clean_str(b.get("street")),
                                _clean_str(city_name),
                                "Chhattisgarh",
                                1,
                                oid
                            )
                        )
                        loc_count += 1
            except Exception as exc:
                summary["errors"].append(f"OSM Location import warning: {exc}")

        summary["imported"]["business_locations"] = loc_count

    # Also synchronize the tables into bizmetrics_auth.db so both databases have identical records
    target_path = Path(db_path) if db_path else DB_PATH
    if target_path.resolve() != AUTH_DB_PATH.resolve():
        try:
            import shutil
            shutil.copy2(target_path, AUTH_DB_PATH)
        except Exception:
            pass

    return summary


def import_master_df_to_database(
    df: pd.DataFrame,
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
    file_name: str = "uploaded_dataset.csv",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Imports a consolidated business master DataFrame (such as the 59-column canonical schema
    or custom sales/customer CSV) into SQLite database tables atomically.
    Preserves existing records, prevents duplicates via primary keys and ON CONFLICT handling,
    and returns an accurate summary of imported, duplicate, and error records.
    """
    init_database(db_path)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "status": "error",
            "imported": 0,
            "duplicates": 0,
            "errors": 1,
            "breakdown": {},
            "message": "Provided dataset is empty.",
        }

    summary: dict[str, Any] = {
        "status": "success",
        "imported": 0,
        "duplicates": 0,
        "errors": 0,
        "breakdown": {
            "customers": 0,
            "products": 0,
            "inventory": 0,
            "sales_transactions": 0,
            "expenses": 0,
            "loans": 0,
            "vendors": 0,
            "shops": 0,
        },
        "message": "",
    }

    col_map = {str(c).strip().lower(): c for c in df.columns}

    def _row_val(row, *aliases, default=""):
        for a in aliases:
            k = a.strip().lower()
            if k in col_map:
                v = row.get(col_map[k])
                if v is not None and not pd.isna(v) and str(v).strip().lower() != "nan":
                    return str(v).strip()
        return default

    def _row_num(row, *aliases, default=0.0):
        v = _row_val(row, *aliases, default="")
        if not v:
            return default
        try:
            return float(str(v).replace("₹", "").replace(",", "").replace("%", "").strip())
        except (ValueError, TypeError):
            return default

    import_id = f"IMP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    with get_db_cursor(commit=True, db_path=db_path) as cur:
        has_record_type = "record_type" in col_map

        for _, r in df.iterrows():
            rec_type = _row_val(r, "record_type", default="").lower()

            try:
                # 1. BUSINESS PROFILE RECORD
                if rec_type in ("business", "shop"):
                    s_name = _row_val(r, "shop_name", "business_name", default=DEFAULT_SHOP_NAME)
                    o_name = _row_val(r, "owner_name", default=DEFAULT_OWNER_NAME)
                    ph = _row_val(r, "contact_number", "phone", "mobile_number", default="+91 98765 43210")
                    addr = _row_val(r, "address", "city", default="Raipur, Chhattisgarh")
                    cur.execute(
                        """
                        INSERT INTO shops (shop_id, shop_name, owner_name, phone, address)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(shop_id) DO UPDATE SET
                            shop_name = excluded.shop_name,
                            owner_name = excluded.owner_name,
                            phone = excluded.phone,
                            address = excluded.address
                        """,
                        (shop_id, s_name, o_name, ph, addr),
                    )
                    summary["breakdown"]["shops"] += 1
                    summary["imported"] += 1
                    continue

                # 2. CUSTOMER & RECEIVABLES RECORD
                cid = _row_val(r, "customer_id", "customerid")
                cname = _row_val(r, "customer_name", "customername")
                if rec_type in ("customer", "receivable") or (not has_record_type and cid and (cname or _row_val(r, "outstanding_amount"))):
                    if cid:
                        cname = cname or f"Customer {cid}"
                        bname = _row_val(r, "business_name")
                        contact = _row_val(r, "contact_number", "mobile_number", "phone")
                        email = _row_val(r, "email")
                        city = _row_val(r, "city", default="Raipur")
                        ctype = _row_val(r, "customer_type", default="Retail Customer")
                        reg_date = _row_val(r, "registration_date", "date", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
                        rating = _row_num(r, "customer_rating", default=4.5)
                        out_amt = _row_num(r, "outstanding_amount", "credit_amount", default=0.0)

                        ex = cur.execute("SELECT 1 FROM customers WHERE customer_id = ?", (cid,)).fetchone()
                        if ex:
                            summary["duplicates"] += 1
                        else:
                            summary["imported"] += 1

                        cur.execute(
                            """
                            INSERT INTO customers (customer_id, shop_id, customer_name, business_name, contact_number, email, city, customer_type, registration_date, customer_rating, outstanding_amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(customer_id) DO UPDATE SET
                                customer_name = excluded.customer_name,
                                business_name = excluded.business_name,
                                contact_number = excluded.contact_number,
                                email = excluded.email,
                                city = excluded.city,
                                customer_type = excluded.customer_type,
                                customer_rating = excluded.customer_rating,
                                outstanding_amount = excluded.outstanding_amount
                            """,
                            (cid, shop_id, cname, bname, contact, email, city, ctype, reg_date, rating, out_amt),
                        )
                        p_hash = hashlib.sha256(cid.encode("utf-8")).hexdigest()
                        cur.execute(
                            """
                            INSERT INTO customer_credentials (shop_id, customer_id, customer_name, password_hash)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(shop_id, customer_id) DO UPDATE SET customer_name = excluded.customer_name
                            """,
                            (shop_id, cid, cname, p_hash),
                        )
                        summary["breakdown"]["customers"] += 1
                        if rec_type in ("customer", "receivable"):
                            continue

                # 3. PRODUCT & INVENTORY RECORD
                pid = _row_val(r, "product_id", "productid", "sku")
                pname = _row_val(r, "product_name", "product")
                if rec_type in ("inventory", "product") or (not has_record_type and pid and (pname or _row_val(r, "purchase_price") or _row_val(r, "current_stock"))):
                    if pid:
                        pname = pname or f"Product {pid}"
                        cat = _row_val(r, "category", default="Hardware & Electricals")
                        sector = _row_val(r, "sector", default="Retail")
                        unit = _row_val(r, "unit", default="Piece")
                        pur_price = _row_num(r, "purchase_price", "cost_price", default=0.0)
                        sel_price = _row_num(r, "selling_price", "price", default=pur_price * 1.25)
                        desc = _row_val(r, "description", default=f"{pname} ({cat})")
                        supp_id = _row_val(r, "supplier_id", "vendor_id", default="SUP-001")
                        lead_days = int(_row_num(r, "lead_time_days", default=5))
                        curr_stock = _row_num(r, "current_stock", "quantity", default=50.0)
                        min_stock = _row_num(r, "minimum_stock", default=10.0)
                        max_stock = _row_num(r, "maximum_stock", default=200.0)
                        reorder_lvl = _row_num(r, "reorder_level", default=20.0)
                        status = _row_val(r, "status", default="Healthy")

                        # Ensure supplier exists
                        cur.execute(
                            """
                            INSERT OR IGNORE INTO vendors (vendor_id, shop_id, vendor_name, material_type)
                            VALUES (?, ?, ?, ?)
                            """,
                            (supp_id, shop_id, f"Supplier {supp_id}", cat),
                        )

                        ex = cur.execute("SELECT 1 FROM products WHERE product_id = ?", (pid,)).fetchone()
                        if ex:
                            summary["duplicates"] += 1
                        else:
                            summary["imported"] += 1

                        cur.execute(
                            """
                            INSERT INTO products (product_id, shop_id, product_name, category, sector, unit, purchase_price, selling_price, description, supplier_id, lead_time_days)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(product_id) DO UPDATE SET
                                product_name = excluded.product_name,
                                category = excluded.category,
                                purchase_price = excluded.purchase_price,
                                selling_price = excluded.selling_price
                            """,
                            (pid, shop_id, pname, cat, sector, unit, pur_price, sel_price, desc, supp_id, lead_days),
                        )
                        cur.execute(
                            """
                            INSERT INTO inventory (shop_id, product_id, current_stock, minimum_stock, maximum_stock, reorder_level, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(product_id) DO UPDATE SET
                                current_stock = excluded.current_stock,
                                status = excluded.status
                            """,
                            (shop_id, pid, curr_stock, min_stock, max_stock, reorder_lvl, status),
                        )
                        summary["breakdown"]["products"] += 1
                        summary["breakdown"]["inventory"] += 1
                        if rec_type in ("inventory", "product"):
                            continue

                # 4. SALES TRANSACTIONS RECORD
                sid = _row_val(r, "sale_id", "saleid", "order_id", "transaction_id")
                if rec_type in ("sale", "sales", "transaction") or (not has_record_type and (sid or (_row_val(r, "total_amount") and (cid or pid)))):
                    date_val = _row_val(r, "date", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
                    c_id_sale = cid or _row_val(r, "customer_id", default="CUST001")
                    p_id_sale = pid or _row_val(r, "product_id", default="PROD-GEN-01")
                    qty = _row_num(r, "quantity", "qty", default=1.0)
                    sp = _row_num(r, "selling_price", "price", default=0.0)
                    disc = _row_num(r, "discount_percent", default=0.0)
                    tot_amt = _row_num(r, "total_amount", "amount", default=max(0.0, qty * sp * (1.0 - disc / 100.0)))
                    if sp == 0.0 and tot_amt > 0.0 and qty > 0.0:
                        sp = tot_amt / qty
                    pay_mode = _row_val(r, "payment_mode", default="Cash")
                    pay_status = _row_val(r, "payment_status", default="Completed")
                    credit_amt = _row_num(r, "credit_amount", default=(tot_amt if pay_status.lower() in ("pending", "unpaid") else 0.0))
                    notes = _row_val(r, "notes", default="Imported Transaction")

                    if not sid:
                        hash_src = f"{c_id_sale}_{p_id_sale}_{date_val}_{qty}_{tot_amt}"
                        sid = f"SALE-{hashlib.md5(hash_src.encode('utf-8')).hexdigest()[:8].upper()}"

                    # Ensure customer exists
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO customers (customer_id, shop_id, customer_name, city)
                        VALUES (?, ?, ?, 'Raipur')
                        """,
                        (c_id_sale, shop_id, f"Customer {c_id_sale}"),
                    )
                    # Ensure product exists
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO products (product_id, shop_id, product_name, category, purchase_price, selling_price)
                        VALUES (?, ?, ?, 'General Hardware', ?, ?)
                        """,
                        (p_id_sale, shop_id, f"Product {p_id_sale}", sp * 0.8, sp),
                    )

                    ex = cur.execute("SELECT 1 FROM sales_transactions WHERE sale_id = ?", (sid,)).fetchone()
                    if ex:
                        summary["duplicates"] += 1
                    else:
                        summary["imported"] += 1

                    cur.execute(
                        """
                        INSERT INTO sales_transactions (sale_id, shop_id, date, customer_id, product_id, quantity, selling_price, discount_percent, total_amount, payment_mode, payment_status, credit_amount, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(sale_id) DO UPDATE SET
                            total_amount = excluded.total_amount,
                            payment_status = excluded.payment_status,
                            credit_amount = excluded.credit_amount
                        """,
                        (sid, shop_id, date_val, c_id_sale, p_id_sale, qty, sp, disc, tot_amt, pay_mode, pay_status, credit_amt, notes),
                    )
                    summary["breakdown"]["sales_transactions"] += 1
                    continue

                # 5. EXPENSE RECORD
                if rec_type in ("expense", "expenses"):
                    eid = _row_val(r, "expense_id", default=f"EXP-{uuid.uuid4().hex[:6].upper()}")
                    edate = _row_val(r, "date", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
                    ecat = _row_val(r, "category", default="Operational")
                    edesc = _row_val(r, "description", default="Business Expense")
                    eamt = _row_num(r, "amount", default=0.0)
                    emode = _row_val(r, "payment_mode", default="Cash")
                    efixed = _row_val(r, "is_fixed", default="No")

                    ex = cur.execute("SELECT 1 FROM expenses WHERE expense_id = ?", (eid,)).fetchone()
                    if ex:
                        summary["duplicates"] += 1
                    else:
                        summary["imported"] += 1

                    cur.execute(
                        """
                        INSERT INTO expenses (expense_id, shop_id, date, category, description, amount, payment_mode, is_fixed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(expense_id) DO UPDATE SET amount = excluded.amount
                        """,
                        (eid, shop_id, edate, ecat, edesc, eamt, emode, efixed),
                    )
                    summary["breakdown"]["expenses"] += 1
                    continue

                # 6. LOAN RECORD
                if rec_type in ("loan", "loans"):
                    lid = _row_val(r, "loan_id", default=f"LOAN-{uuid.uuid4().hex[:6].upper()}")
                    lprov = _row_val(r, "loan_provider", default="SBI")
                    lprin = _row_num(r, "principal_amount", default=500000.0)
                    lrate = _row_num(r, "interest_rate", default=10.5)
                    ltenure = int(_row_num(r, "tenure_months", default=24))
                    lemi = _row_num(r, "monthly_emi", default=lprin / max(1, ltenure))
                    lout = _row_num(r, "outstanding_principal", default=lprin)
                    lstart = _row_val(r, "start_date", default="2024-01-01")
                    lnext = _row_val(r, "next_due_date", default="2026-12-01")
                    ltype = _row_val(r, "loan_type", default="Term Loan")

                    ex = cur.execute("SELECT 1 FROM loans_emi WHERE loan_id = ?", (lid,)).fetchone()
                    if ex:
                        summary["duplicates"] += 1
                    else:
                        summary["imported"] += 1

                    cur.execute(
                        """
                        INSERT INTO loans_emi (loan_id, shop_id, loan_provider, principal_amount, interest_rate, tenure_months, monthly_emi, outstanding_principal, start_date, next_due_date, loan_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(loan_id) DO UPDATE SET outstanding_principal = excluded.outstanding_principal
                        """,
                        (lid, shop_id, lprov, lprin, lrate, ltenure, lemi, lout, lstart, lnext, ltype),
                    )
                    summary["breakdown"]["loans"] += 1
                    continue

                # 7. VENDOR / PAYABLE RECORD
                if rec_type in ("vendor", "vendors", "payable", "payables"):
                    vid = _row_val(r, "vendor_id", default=f"VEND-{uuid.uuid4().hex[:6].upper()}")
                    vname = _row_val(r, "vendor_name", default=f"Vendor {vid}")
                    vmat = _row_val(r, "material_type", default="Hardware")
                    vtord = _row_num(r, "total_ordered_amount", default=0.0)
                    vtpaid = _row_num(r, "total_paid_amount", default=0.0)
                    vout = _row_num(r, "outstanding_balance", default=max(0.0, vtord - vtpaid))
                    vnext = _row_val(r, "next_payment_date", default="2026-12-01")
                    vdays = int(_row_num(r, "credit_days_allowed", default=30))

                    ex = cur.execute("SELECT 1 FROM vendors WHERE vendor_id = ?", (vid,)).fetchone()
                    if ex:
                        summary["duplicates"] += 1
                    else:
                        summary["imported"] += 1

                    cur.execute(
                        """
                        INSERT INTO vendors (vendor_id, shop_id, vendor_name, material_type, total_ordered_amount, total_paid_amount, outstanding_balance, next_payment_date, credit_days_allowed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(vendor_id) DO UPDATE SET
                            vendor_name = excluded.vendor_name,
                            total_ordered_amount = excluded.total_ordered_amount,
                            outstanding_balance = excluded.outstanding_balance
                        """,
                        (vid, shop_id, vname, vmat, vtord, vtpaid, vout, vnext, vdays),
                    )
                    summary["breakdown"]["vendors"] += 1
                    continue

            except Exception as exc:
                summary["errors"] += 1

        # Atomically record import log
        try:
            cur.execute(
                """
                INSERT INTO import_logs (
                    import_id, shop_id, file_name, file_type, target_table, total_rows,
                    imported_rows, duplicate_rows, error_rows, status, error_details, imported_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    shop_id,
                    file_name,
                    "CSV",
                    "master_consolidated",
                    len(df),
                    summary["imported"],
                    summary["duplicates"],
                    summary["errors"],
                    "Completed" if summary["errors"] == 0 else "Completed with warnings",
                    f"Imported {summary['imported']} rows, {summary['duplicates']} duplicates updated, {summary['errors']} errors",
                    username,
                ),
            )
        except Exception:
            pass

    summary["message"] = (
        f"Imported {summary['imported']} records, updated/preserved {summary['duplicates']} existing records "
        f"({summary['errors']} errors/skipped)."
    )

    try:
        from utils.audit_logger import log_audit_event
        log_audit_event(
            username=username,
            action_type="IMPORT",
            entity_type="DATASET_CSV",
            entity_id=import_id,
            details=f"Master CSV import from {file_name}: {summary['message']}",
            shop_id=shop_id,
        )
    except Exception:
        pass

    return summary


# -----------------------------------------------------------------------------
# HIGH-LEVEL DATA ACCESS AND QUERY APIS
# -----------------------------------------------------------------------------

def query_df(sql: str, params: tuple | list | dict | None = None, db_path: Path | str | None = None) -> pd.DataFrame:
    """Execute a SELECT query and return results as a Pandas DataFrame."""
    init_database(db_path)
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def query_records(sql: str, params: tuple | list | dict | None = None, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Execute a query and return rows as a list of dictionaries."""
    with get_db_cursor(commit=False, db_path=db_path) as cur:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def execute_statement(sql: str, params: tuple | list | dict | None = None, db_path: Path | str | None = None) -> int:
    """Execute an INSERT, UPDATE, or DELETE statement and return affected row count."""
    with get_db_cursor(commit=True, db_path=db_path) as cur:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur.rowcount


def clear_db_caches():
    """Clear all cached query dataframes after mutations."""
    try:
        get_products_df.clear()
        get_sales_df.clear()
        get_expenses_df.clear()
        get_customers_df.clear()
        get_receivables_df.clear()
        get_loans_df.clear()
        get_schemes_list.clear()
        get_locations_df.clear()
        get_consolidated_master_df.clear()
    except Exception:
        pass
    try:
        from utils.data_loader import get_cached_database_pipeline_result
        get_cached_database_pipeline_result.clear()
    except Exception:
        pass
    try:
        from utils.daily_reports import get_daily_business_summary
        get_daily_business_summary.clear()
    except Exception:
        pass
    try:
        from customer_qr_bills import get_customer_bills
        get_customer_bills.clear()
    except Exception:
        pass


@st.cache_data(show_spinner=False)
def get_products_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return all products with joined inventory levels."""
    return query_df("SELECT * FROM v_products_inventory WHERE shop_id = ?", (shop_id,))


@st.cache_data(show_spinner=False)
def get_sales_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return all sales transactions."""
    return query_df(
        """
        SELECT 
            s.*,
            p.product_name,
            p.category,
            p.purchase_price as cogs_unit_price,
            c.customer_name,
            c.city
        FROM sales_transactions s
        LEFT JOIN products p ON s.product_id = p.product_id
        LEFT JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.shop_id = ?
        ORDER BY s.date DESC
        """,
        (shop_id,)
    )


@st.cache_data(show_spinner=False)
def get_expenses_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return all operating expenses."""
    return query_df("SELECT * FROM expenses WHERE shop_id = ? ORDER BY date DESC", (shop_id,))


@st.cache_data(show_spinner=False)
def get_customers_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return all registered customers."""
    return query_df("SELECT * FROM customers WHERE shop_id = ? ORDER BY customer_id ASC", (shop_id,))


@st.cache_data(show_spinner=False)
def get_receivables_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return all outstanding receivables with customer contact details."""
    return query_df(
        """
        SELECT 
            r.*,
            c.customer_name,
            c.business_name,
            c.contact_number,
            c.city
        FROM receivables r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.shop_id = ?
        ORDER BY r.days_overdue DESC, r.amount DESC
        """,
        (shop_id,)
    )


@st.cache_data(show_spinner=False)
def get_loans_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Return active loans and repayment parameters."""
    return query_df("SELECT * FROM loans_emi WHERE shop_id = ?", (shop_id,))


@st.cache_data(show_spinner=False)
def get_schemes_list() -> list[dict[str, Any]]:
    """Return all verified government schemes."""
    return query_records("SELECT * FROM government_schemes ORDER BY scheme_id ASC")


@st.cache_data(show_spinner=False)
def get_locations_df(shop_id: str = DEFAULT_SHOP_ID, city: str | None = None) -> pd.DataFrame:
    """Return verified commercial locations and POIs."""
    if city:
        return query_df("SELECT * FROM business_locations WHERE shop_id = ? AND city = ?", (shop_id, city))
    return query_df("SELECT * FROM business_locations WHERE shop_id = ?", (shop_id,))


# -----------------------------------------------------------------------------
# CRUD OPERATION APIS
# -----------------------------------------------------------------------------

def add_sales_transaction(sale_data: dict[str, Any]) -> str:
    """
    Record a new sales transaction and atomically deduct sold stock from inventory.
    """
    with get_db_cursor(commit=True) as cur:
        sale_id = sale_data.get("sale_id")
        if not sale_id:
            count = cur.execute("SELECT COUNT(*) FROM sales_transactions").fetchone()[0]
            sale_id = f"SALE{count + 1:04d}"

        shop_id = sale_data.get("shop_id", DEFAULT_SHOP_ID)
        pid = sale_data["product_id"]
        qty = float(sale_data.get("quantity", 1.0))
        selling_price = float(sale_data.get("selling_price", 0.0))
        total_amount = float(sale_data.get("total_amount", qty * selling_price))
        pay_mode = sale_data.get("payment_mode", "Cash")
        pay_status = sale_data.get("payment_status", "Completed")
        credit_amt = float(sale_data.get("credit_amount", 0.0 if pay_status == "Completed" else total_amount))

        cur.execute(
            """
            INSERT INTO sales_transactions (sale_id, shop_id, date, customer_id, product_id, quantity, selling_price, discount_percent, total_amount, payment_mode, payment_status, credit_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sale_id,
                shop_id,
                sale_data.get("date", pd.Timestamp.today().strftime("%Y-%m-%d")),
                sale_data["customer_id"],
                pid,
                qty,
                selling_price,
                float(sale_data.get("discount_percent", 0.0)),
                total_amount,
                pay_mode,
                pay_status,
                credit_amt,
                sale_data.get("notes", "New Sale Recorded via DB"),
            )
        )

        # Atomically deduct stock from inventory
        cur.execute(
            """
            UPDATE inventory 
            SET current_stock = MAX(0.0, current_stock - ?),
                last_updated = CURRENT_TIMESTAMP
            WHERE product_id = ? AND shop_id = ?
            """,
            (qty, pid, shop_id)
        )

        # If credit, add to receivables
        if pay_status.lower() == "pending" or credit_amt > 0:
            rec_id = f"REC-{sale_id}"
            cur.execute(
                """
                INSERT INTO receivables (receivable_id, shop_id, invoice_id, customer_id, amount, due_date, days_overdue, status, collection_priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(receivable_id) DO UPDATE SET amount = excluded.amount
                """,
                (
                    rec_id,
                    shop_id,
                    sale_id,
                    sale_data["customer_id"],
                    credit_amt,
                    (pd.Timestamp.today() + pd.Timedelta(days=30)).strftime("%Y-%m-%d"),
                    0,
                    "Pending",
                    "P4: Low",
                    f"Credit invoice from sale {sale_id}"
                )
            )

        clear_db_caches()
        return sale_id


def update_inventory_stock(product_id: str, new_stock: float, shop_id: str = DEFAULT_SHOP_ID) -> None:
    """Update current stock level for a product."""
    execute_statement(
        """
        UPDATE inventory 
        SET current_stock = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE product_id = ? AND shop_id = ?
        """,
        (max(0.0, float(new_stock)), product_id, shop_id)
    )
    clear_db_caches()


def add_expense(expense_data: dict[str, Any]) -> str:
    """Record an operational expense."""
    with get_db_cursor(commit=True) as cur:
        eid = expense_data.get("expense_id")
        if not eid:
            count = cur.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            eid = f"EXP{count + 1:03d}"

        cur.execute(
            """
            INSERT INTO expenses (expense_id, shop_id, date, category, description, amount, payment_status, is_fixed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                expense_data.get("shop_id", DEFAULT_SHOP_ID),
                expense_data.get("date", pd.Timestamp.today().strftime("%Y-%m-%d")),
                expense_data["category"],
                expense_data.get("description", ""),
                float(expense_data.get("amount", 0.0)),
                expense_data.get("payment_status", "Paid"),
                expense_data.get("is_fixed", "No"),
                expense_data.get("notes", ""),
            )
        )
        clear_db_caches()
        return eid


@st.cache_data(show_spinner=False)
def get_consolidated_master_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """
    Construct a consolidated DataFrame directly from the relational database tables,
    matching the schema expected by pipeline.py.
    Optimized with fast dictionary records extraction for minimal latency.
    """
    records = []

    # 1. Products / Inventory
    inv_rows = get_products_df(shop_id).to_dict(orient="records")
    for r in inv_rows:
        records.append({
            "record_type": "Inventory",
            "product_id": r.get("product_id"),
            "product_name": r.get("product_name"),
            "category": r.get("category"),
            "sector": r.get("sector"),
            "unit": r.get("unit"),
            "purchase_price": r.get("purchase_price"),
            "selling_price": r.get("selling_price"),
            "current_stock": r.get("current_stock"),
            "minimum_stock": r.get("minimum_stock"),
            "maximum_stock": r.get("maximum_stock"),
            "reorder_level": r.get("reorder_level"),
            "status": r.get("status"),
            "description": r.get("description"),
            "supplier_id": r.get("supplier_id"),
            "lead_time_days": r.get("lead_time_days"),
        })

    # 2. Sales
    sales_rows = get_sales_df(shop_id).to_dict(orient="records")
    for r in sales_rows:
        records.append({
            "record_type": "Sale",
            "sale_id": r.get("sale_id"),
            "business_id": "BUS001",
            "date": r.get("date"),
            "customer_id": r.get("customer_id"),
            "product_id": r.get("product_id"),
            "quantity": r.get("quantity"),
            "selling_price": r.get("selling_price"),
            "discount_percent": r.get("discount_percent"),
            "total_amount": r.get("total_amount"),
            "payment_mode": r.get("payment_mode"),
            "payment_status": r.get("payment_status"),
            "credit_amount": r.get("credit_amount"),
            "notes": r.get("notes"),
        })

    # 3. Expenses
    exp_rows = get_expenses_df(shop_id).to_dict(orient="records")
    for r in exp_rows:
        records.append({
            "record_type": "Expense",
            "expense_id": r.get("expense_id"),
            "business_id": "BUS001",
            "date": r.get("date"),
            "category": r.get("category"),
            "description": r.get("description"),
            "amount": r.get("amount"),
            "payment_status": r.get("payment_status"),
            "is_fixed": r.get("is_fixed"),
            "notes": r.get("notes"),
        })

    # 4. Customers / Receivables
    cust_rows = get_customers_df(shop_id).to_dict(orient="records")
    for r in cust_rows:
        records.append({
            "record_type": "Receivable",
            "customer_id": r.get("customer_id"),
            "customer_name": r.get("customer_name"),
            "business_name": r.get("business_name"),
            "contact_number": r.get("contact_number"),
            "email": r.get("email"),
            "city": r.get("city"),
            "customer_type": r.get("customer_type"),
            "registration_date": r.get("registration_date"),
            "customer_rating": r.get("customer_rating"),
            "outstanding_amount": r.get("outstanding_amount"),
            "mobile_number": r.get("contact_number"),
            "due_date": None,
        })

    # 5. Loans
    loan_rows = get_loans_df(shop_id).to_dict(orient="records")
    for r in loan_rows:
        records.append({
            "record_type": "Loan",
            "loan_id": r.get("loan_id"),
            "business_id": "BUS001",
            "loan_provider": r.get("loan_provider"),
            "principal_amount": r.get("principal_amount"),
            "interest_rate": r.get("interest_rate"),
            "tenure_months": r.get("tenure_months"),
            "monthly_emi": r.get("monthly_emi"),
            "outstanding_principal": r.get("outstanding_principal"),
            "start_date": r.get("start_date"),
            "next_due_date": r.get("next_due_date"),
            "loan_type": r.get("loan_type"),
            "status": r.get("status"),
        })

    if not records:
        return pd.DataFrame(columns=CONSOLIDATED_MASTER_COLUMNS)

    df_out = pd.DataFrame(records)
    df_out.columns = df_out.columns.str.strip().str.lower()
    return df_out


# ==============================================================================
# CUSTOMER PORTAL SPECIFIC DATABASE OPERATIONS
# ==============================================================================

def get_customer_detail_from_db(customer_id: str, shop_id: str = DEFAULT_SHOP_ID) -> Optional[dict]:
    """Fetch complete customer record directly from the database with variant tolerance."""
    init_database()
    cid = str(customer_id).strip()
    variants = [cid]
    digits = "".join(filter(str.isdigit, cid))
    if digits:
        val = int(digits)
        for cand in [f"CUST{val:03d}", f"CUST_DEMO_{val:02d}", f"CUST_{val:03d}"]:
            if cand not in variants:
                variants.append(cand)
    if cid.upper() in {"CUST001", "CUST01", "SHIVANSH", "CUST_DEMO_01"}:
        for cand in ["CUST001", "CUST_DEMO_01", "CUST01"]:
            if cand not in variants:
                variants.append(cand)

    for var in variants:
        rows = query_records(
            "SELECT * FROM customers WHERE customer_id = ? AND shop_id = ?",
            (var, shop_id),
        )
        if rows:
            res = dict(rows[0])
            res["customer_id"] = cid
            return res
        rows_fallback = query_records("SELECT * FROM customers WHERE customer_id = ?", (var,))
        if rows_fallback:
            res = dict(rows_fallback[0])
            res["customer_id"] = cid
            return res
    return None


def update_customer_profile(customer_id: str, updates: dict, shop_id: str = DEFAULT_SHOP_ID) -> bool:
    """
    Update permitted customer profile fields (contact_number, email, address, city).
    Protects sensitive fields like customer_id, outstanding_amount, and customer_rating.
    """
    allowed_fields = {"contact_number", "email", "address", "city", "business_name"}
    clean_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not clean_updates:
        return False

    init_database()
    cid = str(customer_id).strip()

    set_clauses = [f"{col} = ?" for col in clean_updates.keys()]
    values = list(clean_updates.values())
    values.append(cid)

    sql = f"UPDATE customers SET {', '.join(set_clauses)} WHERE customer_id = ?"
    
    with get_db_cursor(commit=True) as cur:
        cur.execute(sql, tuple(values))

    # Also synchronize customer_credentials if name changed
    if "customer_name" in updates:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE customer_credentials SET customer_name = ? WHERE customer_id = ?",
                (str(updates["customer_name"]).strip(), cid),
            )

    clear_db_caches()
    try:
        from customer_qr_bills import clear_customer_profile_cache
        clear_customer_profile_cache(cid)
    except Exception:
        pass
    return True


def get_customer_master_table_df(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """
    Fetch comprehensive, live aggregated customer records joined with sales and receivables.
    Returns DataFrame containing:
    - customer_id (Customer ID)
    - customer_name (Customer Name)
    - contact_number (Mobile Number)
    - email (Email)
    - city (City)
    - customer_type (Customer Type)
    - total_purchases (Total Purchases, float)
    - total_paid (Total Paid, float)
    - outstanding_amount (Outstanding Amount, float)
    - last_purchase_date (Last Purchase Date, YYYY-MM-DD)
    - customer_status ('Active', 'At Risk', 'New', 'Inactive')
    - total_orders (Total verified order count)
    - business_name (Business Name)
    - address (Physical address)
    - customer_rating (Rating score)
    - days_since_last_order (int)
    """
    init_database()
    sql = """
    WITH sales_agg AS (
        SELECT 
            customer_id,
            COUNT(sale_id) as total_orders,
            COALESCE(SUM(total_amount), 0.0) as total_purchases,
            COALESCE(SUM(CASE 
                WHEN LOWER(payment_status) = 'completed' THEN total_amount 
                ELSE total_amount - credit_amount 
            END), 0.0) as total_paid,
            MAX(date) as last_purchase_date
        FROM sales_transactions
        GROUP BY customer_id
    ),
    rec_agg AS (
        SELECT 
            customer_id,
            COALESCE(SUM(amount), 0.0) as total_receivable_due
        FROM receivables
        WHERE LOWER(status) NOT IN ('settled', 'paid')
        GROUP BY customer_id
    )
    SELECT 
        c.customer_id,
        c.customer_name,
        c.business_name,
        COALESCE(c.contact_number, '') as contact_number,
        COALESCE(c.email, '') as email,
        COALESCE(c.city, 'Unknown') as city,
        COALESCE(c.customer_type, 'Retail Customer') as customer_type,
        COALESCE(c.registration_date, '') as registration_date,
        COALESCE(s.total_orders, 0) as total_orders,
        ROUND(COALESCE(s.total_purchases, 0.0), 2) as total_purchases,
        ROUND(COALESCE(s.total_paid, 0.0), 2) as total_paid,
        ROUND(CASE 
            WHEN COALESCE(r.total_receivable_due, 0.0) > 0 THEN r.total_receivable_due
            ELSE COALESCE(c.outstanding_amount, 0.0)
        END, 2) as outstanding_amount,
        COALESCE(s.last_purchase_date, c.registration_date, '') as last_purchase_date,
        COALESCE(c.address, '') as address,
        COALESCE(c.customer_rating, 4.5) as customer_rating
    FROM customers c
    LEFT JOIN sales_agg s ON c.customer_id = s.customer_id
    LEFT JOIN rec_agg r ON c.customer_id = r.customer_id
    WHERE c.shop_id = ? OR ? = ''
    ORDER BY c.customer_id ASC
    """
    df = query_df(sql, (shop_id, shop_id))
    if df.empty:
        df = query_df(sql.replace("WHERE c.shop_id = ? OR ? = ''", ""))
        if df.empty:
            return pd.DataFrame(columns=[
                "customer_id", "customer_name", "business_name", "contact_number",
                "email", "city", "customer_type", "registration_date", "total_orders",
                "total_purchases", "total_paid", "outstanding_amount", "last_purchase_date",
                "address", "customer_rating", "days_since_last_order", "customer_status"
            ])

    today = pd.Timestamp.today().normalize()
    last_dates = pd.to_datetime(df['last_purchase_date'], errors='coerce')
    days_since = (today - last_dates).dt.days.fillna(999).clip(lower=0)
    df['days_since_last_order'] = days_since.astype(int)

    reg_dates = pd.to_datetime(df['registration_date'], errors='coerce')
    days_since_reg = (today - reg_dates).dt.days.fillna(999).clip(lower=0)
    df['days_since_registration'] = days_since_reg.astype(int)

    def _determine_status(row):
        orders = row['total_orders']
        days = row['days_since_last_order']
        reg_days = row['days_since_registration']
        dues = row['outstanding_amount']
        if orders == 0 or (reg_days <= 240 and orders <= 2):
            return "New"
        elif days <= 90:
            return "Active"
        elif days <= 180:
            return "At Risk" if dues > 0 else "Active"
        elif days <= 365:
            return "At Risk"
        else:
            return "Inactive"

    df['customer_status'] = df.apply(_determine_status, axis=1)
    return df


def get_customer_kpi_summary(shop_id: str = DEFAULT_SHOP_ID) -> dict[str, Any]:
    """
    Compute live database-driven customer metrics:
    - Total Customers
    - Active Customers
    - New Customers
    - Repeat Customers
    - Outstanding Customer Dues
    - Total Customer Revenue
    """
    df = get_customer_master_table_df(shop_id=shop_id)
    if df.empty:
        return {
            "total_customers": 0,
            "active_customers": 0,
            "new_customers": 0,
            "repeat_customers": 0,
            "repeat_pct": 0.0,
            "outstanding_dues": 0.0,
            "total_revenue": 0.0,
            "avg_aov": 0.0,
        }

    total_customers = len(df)
    active_customers = int((df["days_since_last_order"] <= 90).sum())
    new_customers = int((df["days_since_registration"] <= 240).sum())
    repeat_customers = int((df["total_orders"] > 1).sum())
    repeat_pct = round((repeat_customers / max(1, total_customers)) * 100, 1)
    outstanding_dues = round(float(df["outstanding_amount"].sum()), 2)
    total_revenue = round(float(df["total_purchases"].sum()), 2)
    total_orders_sum = int(df["total_orders"].sum())
    avg_aov = round(total_revenue / max(1, total_orders_sum), 2)

    return {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "new_customers": new_customers,
        "repeat_customers": repeat_customers,
        "repeat_pct": repeat_pct,
        "outstanding_dues": outstanding_dues,
        "total_revenue": total_revenue,
        "avg_aov": avg_aov,
    }


def add_customer_to_db(
    customer_name: str,
    customer_id: str | None = None,
    business_name: str = "",
    contact_number: str = "",
    email: str = "",
    city: str = "Raipur",
    customer_type: str = "Retail Customer",
    address: str = "",
    outstanding_amount: float = 0.0,
    shop_id: str = DEFAULT_SHOP_ID,
) -> tuple[bool, str, str]:
    """
    Add a new customer to the database with validation against duplicate ID and phone number.
    Returns: (success: bool, message: str, customer_id: str)
    """
    init_database()
    c_name = str(customer_name).strip()
    if not c_name:
        return False, "Customer Name is required.", ""

    cid = str(customer_id).strip().upper() if customer_id else ""
    with get_db_cursor(commit=False) as cur:
        # Auto-generate customer ID if not supplied
        if not cid:
            rows = cur.execute("SELECT customer_id FROM customers").fetchall()
            cids = [r[0] for r in rows if r[0]]
            nums = [int("".join(filter(str.isdigit, x))) for x in cids if any(c.isdigit() for c in x)]
            next_num = max(nums) + 1 if nums else 1
            cid = f"CUST{next_num:03d}"

        # 1. Validate duplicate Customer ID
        cur.execute("SELECT customer_id, customer_name FROM customers WHERE customer_id = ?", (cid,))
        dup_id = cur.fetchone()
        if dup_id:
            return False, f"Customer ID '{cid}' is already in use by {dup_id[1]}.", cid

        # 2. Validate duplicate Mobile Number
        c_mob = str(contact_number).strip()
        if c_mob:
            clean_digits = "".join(filter(str.isdigit, c_mob))
            if len(clean_digits) >= 10:
                lookup_mob = clean_digits[-10:]
                cur.execute(
                    "SELECT customer_id, customer_name FROM customers WHERE contact_number LIKE ?",
                    (f"%{lookup_mob}",)
                )
                dup_mob = cur.fetchone()
                if dup_mob:
                    return False, f"Mobile number '{c_mob}' is already registered to customer {dup_mob[0]} ({dup_mob[1]}).", cid

    from datetime import date
    reg_date = date.today().strftime("%Y-%m-%d")

    # Insert customer record
    sql = """
    INSERT INTO customers (
        customer_id, shop_id, customer_name, business_name, contact_number,
        email, city, customer_type, registration_date, customer_rating,
        outstanding_amount, address
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 5.0, ?, ?)
    """
    with get_db_cursor(commit=True) as cur:
        cur.execute(sql, (
            cid, shop_id, c_name, business_name.strip() or f"{c_name}'s Store",
            c_mob, email.strip(), city.strip() or "Raipur", customer_type.strip() or "Retail Customer",
            reg_date, float(outstanding_amount or 0.0), address.strip()
        ))

        # Auto-create customer credentials so new customer can login to Digital Portal immediately
        import hashlib
        def _hash_id(id_str):
            return hashlib.sha256(f"BIZMETRICS_SALT_{str(id_str).strip().upper()}".encode()).hexdigest()
        pwd_hash = _hash_id(cid)
        cur.execute(
            """
            INSERT INTO customer_credentials (shop_id, customer_id, customer_name, password_hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(shop_id, customer_id) DO UPDATE SET
                customer_name = excluded.customer_name,
                password_hash = excluded.password_hash
            """,
            (shop_id, cid, c_name, pwd_hash)
        )

    clear_db_caches()
    try:
        from utils.audit_logger import log_audit_event
        log_audit_event("Owner", "CUSTOMER", "CREATE", cid, f"Added new customer {c_name} ({cid})", shop_id=shop_id)
    except Exception:
        pass

    return True, f"Successfully created customer account {cid} for '{c_name}'.", cid


def edit_customer_in_db(
    customer_id: str,
    customer_name: str,
    business_name: str = "",
    contact_number: str = "",
    email: str = "",
    city: str = "",
    customer_type: str = "",
    address: str = "",
    outstanding_amount: float = 0.0,
    shop_id: str = DEFAULT_SHOP_ID,
) -> tuple[bool, str]:
    """
    Update customer details with duplicate mobile validation across other customers.
    Returns: (success: bool, message: str)
    """
    init_database()
    cid = str(customer_id).strip()
    c_name = str(customer_name).strip()
    if not c_name:
        return False, "Customer Name is required."

    c_mob = str(contact_number).strip()
    with get_db_cursor(commit=False) as cur:
        cur.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (cid,))
        if not cur.fetchone():
            return False, f"Customer {cid} does not exist in database."

        if c_mob:
            clean_digits = "".join(filter(str.isdigit, c_mob))
            if len(clean_digits) >= 10:
                lookup_mob = clean_digits[-10:]
                cur.execute(
                    "SELECT customer_id, customer_name FROM customers WHERE contact_number LIKE ? AND customer_id != ?",
                    (f"%{lookup_mob}", cid)
                )
                dup_mob = cur.fetchone()
                if dup_mob:
                    return False, f"Mobile number '{c_mob}' is already registered to another customer: {dup_mob[0]} ({dup_mob[1]})."

    sql = """
    UPDATE customers SET
        customer_name = ?,
        business_name = ?,
        contact_number = ?,
        email = ?,
        city = ?,
        customer_type = ?,
        address = ?,
        outstanding_amount = ?
    WHERE customer_id = ?
    """
    with get_db_cursor(commit=True) as cur:
        cur.execute(sql, (
            c_name, business_name.strip(), c_mob, email.strip(),
            city.strip(), customer_type.strip(), address.strip(),
            float(outstanding_amount or 0.0), cid
        ))
        cur.execute(
            "UPDATE customer_credentials SET customer_name = ? WHERE customer_id = ?",
            (c_name, cid)
        )

    clear_db_caches()
    try:
        from customer_qr_bills import clear_customer_profile_cache
        clear_customer_profile_cache(cid)
    except Exception:
        pass
    try:
        from utils.audit_logger import log_audit_event
        log_audit_event("Owner", "CUSTOMER", "UPDATE", cid, f"Updated customer {c_name} ({cid}) details", shop_id=shop_id)
    except Exception:
        pass

    return True, f"Customer {cid} ('{c_name}') updated successfully."


def delete_customer_from_db(
    customer_id: str,
    force: bool = False,
    shop_id: str = DEFAULT_SHOP_ID,
) -> tuple[bool, str, dict]:
    """
    Delete customer with relationship checks.
    If force=False and sales_transactions or open receivables exist, deletion is rejected with audit details.
    If force=True, gracefully cascades and removes related customer records.
    Returns: (success: bool, message: str, details: dict)
    """
    init_database()
    cid = str(customer_id).strip()

    with get_db_cursor(commit=False) as cur:
        cur.execute("SELECT customer_name FROM customers WHERE customer_id = ?", (cid,))
        row = cur.fetchone()
        if not row:
            return False, f"Customer {cid} not found in database.", {}
        c_name = row[0]

        cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE customer_id = ?", (cid,))
        sales_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM receivables WHERE customer_id = ? AND LOWER(status) NOT IN ('settled', 'paid')", (cid,))
        open_rec_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM customer_support_tickets WHERE customer_id = ?", (cid,))
        ticket_count = cur.fetchone()[0]

    details = {
        "customer_id": cid,
        "customer_name": c_name,
        "sales_count": sales_count,
        "open_receivables": open_rec_count,
        "support_tickets": ticket_count,
    }

    if (sales_count > 0 or open_rec_count > 0) and not force:
        msg = (
            f"Cannot delete customer {cid} ({c_name}): Account has {sales_count} sales transactions "
            f"and {open_rec_count} unpaid ledger receivables. Please confirm force-delete to proceed."
        )
        return False, msg, details

    # Execute cascade deletion within a single atomic transaction
    with get_db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM customer_credentials WHERE customer_id = ?", (cid,))
        cur.execute("DELETE FROM customer_notifications WHERE customer_id = ?", (cid,))
        cur.execute("DELETE FROM customer_support_tickets WHERE customer_id = ?", (cid,))
        cur.execute("DELETE FROM receivables WHERE customer_id = ?", (cid,))
        cur.execute("DELETE FROM sales_transactions WHERE customer_id = ?", (cid,))
        cur.execute("DELETE FROM customers WHERE customer_id = ?", (cid,))

    clear_db_caches()
    try:
        from customer_qr_bills import clear_customer_profile_cache
        clear_customer_profile_cache(cid)
    except Exception:
        pass
    try:
        from utils.audit_logger import log_audit_event
        log_audit_event("Owner", "CUSTOMER", "DELETE", cid, f"Deleted customer {c_name} ({cid}) with {sales_count} historical sales", shop_id=shop_id)
    except Exception:
        pass

    return True, f"Customer {cid} ({c_name}) and associated historical records deleted successfully.", details


def get_customer_support_tickets(customer_id: str, shop_id: str = DEFAULT_SHOP_ID) -> list[dict]:
    """Retrieve all support requests filed by this customer."""
    init_database()
    cid = str(customer_id).strip()
    return query_records(
        """
        SELECT ticket_id, shop_id, customer_id, category, priority, message, status, resolution_notes, created_at
        FROM customer_support_tickets
        WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (cid,),
    )


def create_customer_support_ticket(
    customer_id: str,
    category: str,
    priority: str,
    message: str,
    shop_id: str = DEFAULT_SHOP_ID,
) -> str:
    """Create a new customer support ticket in SQLite."""
    import time
    init_database()
    cid = str(customer_id).strip()
    ticket_id = f"TCK-{int(time.time())}-{cid[-3:] if len(cid) >= 3 else cid}"

    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO customer_support_tickets (ticket_id, shop_id, customer_id, category, priority, message, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Open')
            """,
            (ticket_id, shop_id, cid, category, priority, message),
        )
    return ticket_id


def get_customer_notifications(customer_id: str, shop_id: str = DEFAULT_SHOP_ID) -> list[dict]:
    """Retrieve all notifications for this customer, seeding default authentic notifications if empty."""
    try:
        init_database()
    except Exception as exc:
        print(f"Notice: init_database in get_customer_notifications: {exc}")

    cid = str(customer_id).strip()
    notifs = []
    try:
        notifs = query_records(
            """
            SELECT notification_id, shop_id, customer_id, title, message, category, is_read, action_link, created_at
            FROM customer_notifications
            WHERE customer_id = ? OR customer_id = 'ALL'
            ORDER BY created_at DESC
            """,
            (cid,),
        )
    except Exception as exc:
        print(f"Notice: query_records in get_customer_notifications: {exc}")
        notifs = []

    if not notifs:
        try:
            # Seed default authentic notifications for the customer
            default_items = [
                (
                    f"NOTIF-{cid}-001",
                    shop_id,
                    cid,
                    "Welcome to Shivansh Electronics & Hardware Portal",
                    "Your customer account and digital ledger have been securely verified. Enjoy paperless billing and express checkout.",
                    "System",
                    0,
                    None,
                ),
                (
                    f"NOTIF-{cid}-002",
                    shop_id,
                    cid,
                    "Festive Wholesale Supply & Bulk Cable Offers",
                    "Special 5% trade discount on premium copper cabling and industrial circuit breakers this month.",
                    "Offer",
                    0,
                    None,
                ),
                (
                    f"NOTIF-{cid}-003",
                    shop_id,
                    cid,
                    "Khata Ledger & GST Invoicing Synchronized",
                    "Your registered contact and billing records are synced with GST-compliant tax invoicing.",
                    "Announcement",
                    0,
                    None,
                ),
            ]
            with get_db_cursor(commit=True) as cur:
                for item in default_items:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO customer_notifications
                        (notification_id, shop_id, customer_id, title, message, category, is_read, action_link)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        item,
                    )
            notifs = query_records(
                """
                SELECT notification_id, shop_id, customer_id, title, message, category, is_read, action_link, created_at
                FROM customer_notifications
                WHERE customer_id = ? OR customer_id = 'ALL'
                ORDER BY created_at DESC
                """,
                (cid,),
            )
        except Exception as exc:
            print(f"Notice: seeding notifications in get_customer_notifications: {exc}")

    return notifs if notifs is not None else []


def mark_notification_as_read(notification_id: str) -> bool:
    """Mark a notification as read."""
    init_database()
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE customer_notifications SET is_read = 1 WHERE notification_id = ?",
            (notification_id,),
        )
    return True


# ==============================================================================
# DURG-BHILAI LOCAL DATASET QUERIES & INGESTION
# ==============================================================================

@st.cache_data(show_spinner=False)
def get_local_businesses_df(city: Optional[str] = None, category: Optional[str] = None) -> pd.DataFrame:
    """Retrieve verified OpenStreetMap local businesses in Durg and Bhilai."""
    init_database()
    conditions = []
    params = []

    if city and city.lower() != "all":
        conditions.append("LOWER(city) = LOWER(?)")
        params.append(city)

    if category and category.lower() != "all":
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT business_id, osm_id, business_name, category, sub_category,
           latitude, longitude, locality, city, ward, district, address,
           source, reference_year, contact_info
    FROM local_business_directory
    {where_clause}
    ORDER BY city, locality, business_name
    """
    return query_df(sql, tuple(params))


@st.cache_data(show_spinner=False)
def get_local_demographics_df(area_name: Optional[str] = None) -> pd.DataFrame:
    """Retrieve Census 2011 demographics for Durg district and its urban local bodies."""
    init_database()
    if area_name and area_name.lower() != "all":
        sql = "SELECT * FROM local_demographics WHERE LOWER(area_name) = LOWER(?) ORDER BY total_population DESC"
        return query_df(sql, (area_name,))
    sql = "SELECT * FROM local_demographics ORDER BY total_population DESC"
    return query_df(sql)


@st.cache_data(show_spinner=False)
def get_local_economic_indicators_df() -> pd.DataFrame:
    """Retrieve economic indicators for Durg district (SAIL, Mandi, MSME, Banking)."""
    init_database()
    sql = "SELECT * FROM local_economic_indicators ORDER BY category, indicator_name"
    return query_df(sql)


@st.cache_data(show_spinner=False)
def get_local_geographic_nodes_df() -> pd.DataFrame:
    """Retrieve standardized geographic locality nodes across Durg and Bhilai."""
    init_database()
    sql = "SELECT * FROM local_geographic_data ORDER BY parent_city, area_name"
    return query_df(sql)


@st.cache_data(show_spinner=False)
def get_dataset_sources_df() -> pd.DataFrame:
    """Retrieve source provenance metadata for public datasets."""
    init_database()
    sql = "SELECT * FROM dataset_sources ORDER BY dataset_name"
    return query_df(sql)


def _seed_core_business_data(cur: sqlite3.Cursor) -> dict:
    """Internal helper to seed authentic business data (vendors, products, customers, credentials, sales, receivables) from data/seed JSON files or CSVs."""
    seed_dir = Path(__file__).resolve().parent.parent / "data" / "seed"
    stats = {"vendors": 0, "customers": 0, "sales": 0, "receivables": 0, "products": 0, "credentials": 0}

    # 0. Vendors (required for products supplier_id foreign key)
    vend_file = seed_dir / "vendors.json"
    if vend_file.exists():
        try:
            with open(vend_file, "r", encoding="utf-8") as f:
                vends = json.load(f)
            for v in vends:
                cur.execute("""
                    INSERT OR IGNORE INTO vendors (
                        vendor_id, shop_id, vendor_name, material_type,
                        total_ordered_amount, total_paid_amount, outstanding_balance, credit_days_allowed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    v.get("vendor_id"), v.get("shop_id", DEFAULT_SHOP_ID), v.get("vendor_name"),
                    v.get("material_type", "Hardware"), float(v.get("total_ordered_amount") or 0.0),
                    float(v.get("total_paid_amount") or 0.0), float(v.get("outstanding_balance") or 0.0),
                    int(v.get("credit_days_allowed") or 30)
                ))
                stats["vendors"] += 1
        except Exception as e:
            print(f"Notice: vendors seed: {e}")

    # 1. Products
    prod_file = seed_dir / "products.json"
    if prod_file.exists():
        try:
            with open(prod_file, "r", encoding="utf-8") as f:
                prods = json.load(f)
            for p in prods:
                cur.execute("""
                    INSERT OR IGNORE INTO products (
                        product_id, shop_id, product_name, category, sector, unit,
                        purchase_price, selling_price, description, supplier_id, lead_time_days
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.get("product_id"), p.get("shop_id", DEFAULT_SHOP_ID), p.get("product_name"),
                    p.get("category"), p.get("sector", "Hardware & Electricals"), p.get("unit", "Piece"),
                    float(p.get("purchase_price") or 0.0), float(p.get("selling_price") or 0.0),
                    p.get("description", ""), p.get("supplier_id", "SUP001"), int(p.get("lead_time_days") or 5)
                ))
                stats["products"] += 1
        except Exception as e:
            print(f"Notice: products seed: {e}")

    # 2. Customers
    cust_file = seed_dir / "customers.json"
    if cust_file.exists():
        try:
            with open(cust_file, "r", encoding="utf-8") as f:
                custs = json.load(f)
            for c in custs:
                cur.execute("""
                    INSERT OR IGNORE INTO customers (
                        customer_id, shop_id, customer_name, business_name, contact_number,
                        email, city, customer_type, registration_date, customer_rating, outstanding_amount, address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.get("customer_id"), c.get("shop_id", DEFAULT_SHOP_ID), c.get("customer_name"), c.get("business_name"),
                    c.get("contact_number"), c.get("email"), c.get("city"), c.get("customer_type"),
                    c.get("registration_date"), c.get("customer_rating"), c.get("outstanding_amount"), c.get("address")
                ))
                stats["customers"] += 1
        except Exception as e:
            print(f"Notice: customers seed: {e}")

    # 3. Customer Credentials
    cred_file = seed_dir / "customer_credentials.json"
    if cred_file.exists():
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                creds = json.load(f)
            for cr in creds:
                cur.execute("""
                    INSERT OR IGNORE INTO customer_credentials (shop_id, customer_id, customer_name, password_hash)
                    VALUES (?, ?, ?, ?)
                """, (
                    cr.get("shop_id", DEFAULT_SHOP_ID), cr.get("customer_id"), cr.get("customer_name"), cr.get("password_hash")
                ))
                stats["credentials"] += 1
        except Exception as e:
            print(f"Notice: customer credentials seed: {e}")

    # 4. Sales Transactions
    sales_file = seed_dir / "sales_transactions.json"
    if sales_file.exists():
        try:
            with open(sales_file, "r", encoding="utf-8") as f:
                sales = json.load(f)
            for s in sales:
                cur.execute("""
                    INSERT OR IGNORE INTO sales_transactions (
                        sale_id, shop_id, date, customer_id, product_id, quantity,
                        selling_price, discount_percent, total_amount, payment_mode, payment_status, credit_amount, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.get("sale_id"), s.get("shop_id", DEFAULT_SHOP_ID), s.get("date"), s.get("customer_id"),
                    s.get("product_id"), s.get("quantity"), s.get("selling_price"), s.get("discount_percent"),
                    s.get("total_amount"), s.get("payment_mode"), s.get("payment_status"), s.get("credit_amount"), s.get("notes")
                ))
                stats["sales"] += 1
        except Exception as e:
            print(f"Notice: sales seed: {e}")

    # 5. Receivables
    rec_file = seed_dir / "receivables.json"
    if rec_file.exists():
        try:
            with open(rec_file, "r", encoding="utf-8") as f:
                recs = json.load(f)
            for r in recs:
                cur.execute("""
                    INSERT OR IGNORE INTO receivables (
                        receivable_id, shop_id, invoice_id, customer_id, amount, due_date,
                        days_overdue, status, collection_priority, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("receivable_id"), r.get("shop_id", DEFAULT_SHOP_ID), r.get("invoice_id"), r.get("customer_id"),
                    r.get("amount"), r.get("due_date"), r.get("days_overdue"), r.get("status"), r.get("collection_priority"), r.get("notes")
                ))
                stats["receivables"] += 1
        except Exception as e:
            print(f"Notice: receivables seed: {e}")

    return stats


def _seed_public_durg_bhilai_data(cur: sqlite3.Cursor) -> dict:
    """Internal helper to seed compiled Census, OSM, and economic datasets using an active cursor."""
    base_dir = Path(__file__).resolve().parent.parent / "data" / "durg_bhilai"
    stats = {"demographics": 0, "localities": 0, "businesses": 0, "economic": 0, "sources": 0}

    # 1. Demographics
    demo_file = base_dir / "demographics" / "durg_bhilai_census_demographics.csv"
    if demo_file.exists():
        df_demo = pd.read_csv(demo_file)
        for _, r in df_demo.iterrows():
            cur.execute(
                """
                INSERT INTO local_demographics (
                    demographic_id, area_name, admin_type, district, total_population,
                    male_population, female_population, urban_population, rural_population,
                    total_households, literacy_rate, workforce_total, main_workers,
                    marginal_workers, cultivators, agricultural_labourers, household_industry,
                    other_workers, census_year, source, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(demographic_id) DO UPDATE SET
                    total_population = excluded.total_population,
                    literacy_rate = excluded.literacy_rate,
                    workforce_total = excluded.workforce_total
                """,
                (
                    r["demographic_id"], r["area_name"], r["admin_type"], r.get("district", "Durg"),
                    int(r["total_population"]), int(r["male_population"]), int(r["female_population"]),
                    int(r["urban_population"]), int(r["rural_population"]), int(r["total_households"]),
                    float(r["literacy_rate"]), int(r["workforce_total"]), int(r["main_workers"]),
                    int(r["marginal_workers"]), int(r.get("cultivators", 0)), int(r.get("agricultural_labourers", 0)),
                    int(r.get("household_industry", 0)), int(r.get("other_workers", 0)),
                    int(r.get("census_year", 2011)), r.get("source", ""), r.get("notes", "")
                )
            )
            stats["demographics"] += 1

    # 2. Localities Geographic
    geo_file = base_dir / "geographic" / "durg_bhilai_localities.csv"
    if geo_file.exists():
        df_geo = pd.read_csv(geo_file)
        for _, r in df_geo.iterrows():
            cur.execute(
                """
                INSERT INTO local_geographic_data (
                    geo_id, area_name, geo_type, latitude, longitude, radius_km, parent_city, district, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(geo_id) DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    radius_km = excluded.radius_km
                """,
                (
                    r["geo_id"], r["area_name"], r["geo_type"], float(r["latitude"]),
                    float(r["longitude"]), float(r["radius_km"]), r.get("parent_city", ""),
                    r.get("district", "Durg"), r.get("description", "")
                )
            )
            stats["localities"] += 1

    # 3. OSM Business Directory
    biz_file = base_dir / "business_directory" / "durg_bhilai_business_directory.csv"
    if biz_file.exists():
        df_biz = pd.read_csv(biz_file)
        for _, r in df_biz.iterrows():
            cur.execute(
                """
                INSERT INTO local_business_directory (
                    business_id, osm_id, business_name, category, sub_category,
                    latitude, longitude, locality, city, ward, district, address,
                    source, reference_year, contact_info
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(business_id) DO UPDATE SET
                    business_name = excluded.business_name,
                    category = excluded.category,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    locality = excluded.locality
                """,
                (
                    r["business_id"], int(r["osm_id"]) if pd.notnull(r.get("osm_id")) else None,
                    r["business_name"], r["category"], r.get("sub_category", ""),
                    float(r["latitude"]), float(r["longitude"]), r.get("locality", ""),
                    r["city"], r.get("ward", ""), r.get("district", "Durg"),
                    r.get("address", ""), r.get("source", "OpenStreetMap (ODbL 1.0)"),
                    int(r.get("reference_year", 2024)), str(r.get("contact_info", "")) if pd.notnull(r.get("contact_info")) else ""
                )
            )
            stats["businesses"] += 1

    # 4. Economic Indicators
    econ_file = base_dir / "economic_indicators" / "durg_district_economy.csv"
    if econ_file.exists():
        df_econ = pd.read_csv(econ_file)
        for _, r in df_econ.iterrows():
            cur.execute(
                """
                INSERT INTO local_economic_indicators (
                    indicator_id, category, indicator_name, unit, indicator_value,
                    reference_period, source, locality_scope, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(indicator_id) DO UPDATE SET
                    indicator_value = excluded.indicator_value,
                    reference_period = excluded.reference_period
                """,
                (
                    r["indicator_id"], r["category"], r["indicator_name"], r["unit"],
                    float(r["indicator_value"]), r["reference_period"], r["source"],
                    r.get("locality_scope", "Durg District"), r.get("notes", "")
                )
            )
            stats["economic"] += 1

    # 5. Dataset Sources
    src_file = base_dir / "metadata" / "dataset_sources.json"
    if src_file.exists():
        with open(src_file, "r", encoding="utf-8") as f:
            sources_data = json.load(f)
        for s in sources_data:
            cur.execute(
                """
                INSERT INTO dataset_sources (
                    source_id, dataset_name, source_organization, source_url,
                    license, reference_year, coverage_area, record_count,
                    last_verified, limitations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    record_count = excluded.record_count,
                    last_verified = excluded.last_verified
                """,
                (
                    s["source_id"], s["dataset_name"], s["source_organization"],
                    s.get("source_url", ""), s["license"], s.get("reference_year", ""),
                    s.get("coverage_area", ""), int(s.get("record_count", 0)),
                    s.get("last_verified", ""), s.get("limitations", "")
                )
            )
            stats["sources"] += 1

    return stats


def import_durg_bhilai_datasets(db_path: Path = DB_PATH) -> dict:
    """
    Batch imports the compiled Census, OSM, and economic datasets into SQLite.
    Prevents duplicate imports using PRIMARY KEY ON CONFLICT DO UPDATE.
    """
    target = str(db_path or DB_PATH)
    if target not in _INITIALIZED_DBS:
        init_database(db_path)
    with get_db_cursor(commit=True, db_path=db_path) as cur:
        stats = _seed_public_durg_bhilai_data(cur)
    clear_db_caches()
    return stats


