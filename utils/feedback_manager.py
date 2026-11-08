"""
BizMetrics Feedback & Support Center Engine
Handles feedback submission, bug reporting, support ticket management,
and resolution tracking for both store owners and customers.
"""
from __future__ import annotations

import uuid
import datetime
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID


def submit_support_ticket(
    category: str,
    message: str,
    priority: str = "Medium",
    customer_id: str = "CUST001",
    shop_id: Optional[str] = None,
    resolution_notes: str = ""
) -> str:
    """Submit a feedback, bug report, or support ticket into the database with foreign key safety."""
    ticket_id = f"TCK-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db_cursor(commit=True) as cur:
        # Resolve foreign key customer_id
        valid_cid = customer_id
        c_check = cur.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if not c_check:
            first_c = cur.execute("SELECT customer_id FROM customers LIMIT 1").fetchone()
            valid_cid = first_c[0] if first_c else "CUST001"

        # Resolve foreign key shop_id
        valid_shop = shop_id or DEFAULT_SHOP_ID
        s_check = cur.execute("SELECT shop_id FROM shops WHERE shop_id = ?", (valid_shop,)).fetchone()
        if not s_check:
            first_s = cur.execute("SELECT shop_id FROM shops LIMIT 1").fetchone()
            valid_shop = first_s[0] if first_s else "shivansh_electronics_hardware"

        cur.execute("""
            INSERT INTO customer_support_tickets (
                ticket_id, shop_id, customer_id, category, priority, message, status, resolution_notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)
        """, (ticket_id, valid_shop, valid_cid, category, priority, message, resolution_notes, now_str, now_str))

    from utils.audit_logger import log_audit_event
    log_audit_event(
        username=customer_id or valid_cid,
        action_type="SUPPORT",
        entity_type="TICKET",
        entity_id=ticket_id,
        details=f"Created {category} ticket ({priority} priority): {message[:60]}...",
        shop_id=valid_shop
    )

    return ticket_id


def list_support_tickets(
    shop_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch support tickets with optional filtering."""
    query = """
        SELECT ticket_id, customer_id, category, priority, message, status, resolution_notes, created_at, updated_at
        FROM customer_support_tickets
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter.upper() != "ALL":
        query += " AND status = ?"
        params.append(status_filter)
    if category_filter and category_filter.upper() != "ALL":
        query += " AND category = ?"
        params.append(category_filter)

    query += " ORDER BY created_at DESC"

    with get_db_cursor(commit=False) as cur:
        rows = cur.execute(query, tuple(params)).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])


def update_ticket_status(ticket_id: str, new_status: str, resolution_notes: str = "", username: str = "Shivansh G") -> bool:
    """Update support ticket status and resolution notes."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE customer_support_tickets
            SET status = ?, resolution_notes = ?, updated_at = ?
            WHERE ticket_id = ?
        """, (new_status, resolution_notes, now_str, ticket_id))

    from utils.audit_logger import log_audit_event
    log_audit_event(
        username=username,
        action_type="SUPPORT",
        entity_type="TICKET",
        entity_id=ticket_id,
        details=f"Updated status to {new_status}. Notes: {resolution_notes[:60]}"
    )
    return True
