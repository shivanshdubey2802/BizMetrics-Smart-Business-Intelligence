"""
Database Optimization & Indexing Script for BizMetrics.
Adds compound indexes for high-frequency query patterns and runs SQLite ANALYZE.
Preserves all existing data, tables, and relationships.
"""

import sqlite3
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

DB_PATHS = [
    APP_ROOT / "bizmetrics.db",
    APP_ROOT / "bizmetrics_auth.db",
]

INDEXES_TO_ENSURE = [
    # Table: sales_transactions
    ("sales_transactions", "idx_sales_cust_date", "CREATE INDEX IF NOT EXISTS idx_sales_cust_date ON sales_transactions (customer_id, date DESC);"),
    ("sales_transactions", "idx_sales_shop_date_amt", "CREATE INDEX IF NOT EXISTS idx_sales_shop_date_amt ON sales_transactions (shop_id, date, total_amount);"),
    
    # Table: receivables
    ("receivables", "idx_rec_shop_cust_due", "CREATE INDEX IF NOT EXISTS idx_rec_shop_cust_due ON receivables (shop_id, customer_id, due_date);"),
    
    # Table: customer_support_tickets
    ("customer_support_tickets", "idx_cst_shop_cust_created", "CREATE INDEX IF NOT EXISTS idx_cst_shop_cust_created ON customer_support_tickets (shop_id, customer_id, created_at DESC);"),
    
    # Table: customer_notifications
    ("customer_notifications", "idx_cnotif_shop_cust_created", "CREATE INDEX IF NOT EXISTS idx_cnotif_shop_cust_created ON customer_notifications (shop_id, customer_id, is_read, created_at DESC);"),
    
    # Table: audit_logs
    ("audit_logs", "idx_audit_shop_created", "CREATE INDEX IF NOT EXISTS idx_audit_shop_created ON audit_logs (shop_id, created_at DESC);"),
    
    # Table: offline_sync_queue
    ("offline_sync_queue", "idx_sync_shop_status", "CREATE INDEX IF NOT EXISTS idx_sync_shop_status ON offline_sync_queue (shop_id, status);"),
    
    # Table: daily_business_summaries
    ("daily_business_summaries", "idx_daily_shop_date", "CREATE INDEX IF NOT EXISTS idx_daily_shop_date ON daily_business_summaries (shop_id, report_date);"),
    
    # Table: user_sessions
    ("user_sessions", "idx_sessions_token_active", "CREATE INDEX IF NOT EXISTS idx_sessions_token_active ON user_sessions (session_token, is_active);"),
    
    # Table: customer_credentials
    ("customer_credentials", "idx_cust_cred_lookup", "CREATE INDEX IF NOT EXISTS idx_cust_cred_lookup ON customer_credentials (shop_id, customer_id, customer_name);"),
]

def optimize_databases():
    for db_path in DB_PATHS:
        if not db_path.exists():
            continue
        print(f"Optimizing {db_path.name}...")
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Check existing tables
        existing_tables = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
        
        # Apply indexes
        created = 0
        for tbl, idx_name, sql in INDEXES_TO_ENSURE:
            if tbl in existing_tables:
                cur.execute(sql)
                created += 1
                
        # Optimize storage & statistics
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA optimize;")
        conn.execute("ANALYZE;")
        conn.commit()
        conn.close()
        print(f"  Applied {created} indexes and ANALYZE on {db_path.name}.")

if __name__ == "__main__":
    optimize_databases()
