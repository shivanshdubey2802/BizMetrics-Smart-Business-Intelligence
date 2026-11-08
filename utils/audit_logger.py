"""
BizMetrics Audit Logging Module
Records and retrieves user actions, security events, master data mutations,
POS billing events, backups, and administrative operations.
"""
from __future__ import annotations

import uuid
import datetime
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID


def log_audit_event(
    username: str,
    action_type: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
    shop_id: Optional[str] = None,
    ip_address: str = "127.0.0.1",
) -> str:
    """Record an immutable audit log entry."""
    audit_id = f"AUD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    effective_shop_id = shop_id or DEFAULT_SHOP_ID
    clean_username = username or "System"

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (audit_id, shop_id, username, action_type, entity_type, entity_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, effective_shop_id, clean_username, action_type, entity_type, entity_id or "", details or "", ip_address),
            )
    except Exception as e:
        # Graceful logging fallback - do not crash application if audit write fails
        print(f"Warning: Failed to write audit log: {e}")
    return audit_id


def fetch_audit_logs(
    shop_id: Optional[str] = None,
    action_type: Optional[str] = None,
    limit: int = 200,
    search_query: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch audit logs with optional filtering by shop, action type, or search term."""
    query = "SELECT audit_id, shop_id, username, action_type, entity_type, entity_id, details, ip_address, created_at FROM audit_logs WHERE 1=1"
    params = []

    if shop_id and shop_id != "all":
        query += " AND (shop_id = ? OR shop_id = 'all')"
        params.append(shop_id)

    if action_type and action_type.upper() != "ALL":
        query += " AND action_type = ?"
        params.append(action_type.upper())

    if search_query:
        query += " AND (username LIKE ? OR entity_type LIKE ? OR details LIKE ? OR entity_id LIKE ?)"
        s = f"%{search_query.strip()}%"
        params.extend([s, s, s, s])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))

    try:
        with get_db_cursor(commit=False) as cur:
            rows = cur.execute(query, tuple(params)).fetchall()
            if not rows:
                return pd.DataFrame(columns=[
                    "audit_id", "shop_id", "username", "action_type", "entity_type", "entity_id", "details", "ip_address", "created_at"
                ])
            return pd.DataFrame([dict(r) for r in rows])
    except Exception:
        return pd.DataFrame(columns=[
            "audit_id", "shop_id", "username", "action_type", "entity_type", "entity_id", "details", "ip_address", "created_at"
        ])

