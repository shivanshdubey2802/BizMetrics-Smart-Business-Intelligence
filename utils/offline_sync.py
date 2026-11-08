"""
BizMetrics Offline and Synchronization Support Module
Queues transactions during offline operation or mobile field sales,
enforces transaction idempotency, resolves conflicts gracefully,
and synchronizes queued batches safely back to primary tables.
"""
from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Optional
import pandas as pd
import streamlit as st
from utils.database import get_db_cursor, DEFAULT_SHOP_ID
from utils.audit_logger import log_audit_event


def queue_offline_operation(
    operation_type: str,
    payload: dict[str, Any],
    client_tx_id: Optional[str] = None,
    shop_id: str = DEFAULT_SHOP_ID,
) -> dict[str, Any]:
    """
    Enqueues an operation into offline_sync_queue.
    Uses client_tx_id to guarantee idempotency and prevent duplicate inserts.
    """
    tx_id = client_tx_id or f"TX-OFFLINE-{uuid.uuid4().hex[:8].upper()}"
    queue_id = f"Q-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    payload_str = json.dumps(payload)

    with get_db_cursor(commit=True) as cur:
        # Check if client_tx_id already exists (idempotency check)
        existing = cur.execute(
            "SELECT queue_id, status FROM offline_sync_queue WHERE client_tx_id = ?",
            (tx_id,),
        ).fetchone()

        if existing:
            return {
                "success": True,
                "queued": False,
                "already_present": True,
                "queue_id": existing["queue_id"],
                "status": existing["status"],
                "message": "Operation already queued (idempotency token matched).",
            }

        cur.execute(
            """
            INSERT INTO offline_sync_queue (queue_id, client_tx_id, shop_id, operation_type, payload_json, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
            """,
            (queue_id, tx_id, shop_id, operation_type.upper(), payload_str),
        )

    return {
        "success": True,
        "queued": True,
        "queue_id": queue_id,
        "client_tx_id": tx_id,
        "status": "Pending",
        "message": "Operation successfully added to offline sync queue.",
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_sync_queue_status(shop_id: str = DEFAULT_SHOP_ID) -> dict[str, Any]:
    """Retrieves current sync queue metrics."""
    with get_db_cursor(commit=False) as cur:
        pending_cnt = cur.execute("SELECT COUNT(*) FROM offline_sync_queue WHERE status = 'Pending'").fetchone()[0]
        synced_cnt = cur.execute("SELECT COUNT(*) FROM offline_sync_queue WHERE status = 'Synced'").fetchone()[0]
        conflict_cnt = cur.execute("SELECT COUNT(*) FROM offline_sync_queue WHERE status = 'Conflict'").fetchone()[0]
        
        recent_rows = cur.execute(
            "SELECT queue_id, client_tx_id, operation_type, status, created_at, synced_at FROM offline_sync_queue ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        recent_df = pd.DataFrame([dict(r) for r in recent_rows]) if recent_rows else pd.DataFrame(columns=[
            "queue_id", "client_tx_id", "operation_type", "status", "created_at", "synced_at"
        ])

    is_online_clean = pending_cnt == 0
    return {
        "pending_count": pending_cnt,
        "synced_count": synced_cnt,
        "conflict_count": conflict_cnt,
        "is_all_synced": is_online_clean,
        "recent_queue": recent_df,
    }


def process_sync_queue(username: str = "Shivansh G") -> dict[str, Any]:
    """
    Replays all 'Pending' operations in offline_sync_queue with conflict validation.
    Applies sales, stock adjustments, or customer records atomically.
    """
    with get_db_cursor(commit=False) as cur:
        pending_items = cur.execute(
            "SELECT queue_id, client_tx_id, shop_id, operation_type, payload_json FROM offline_sync_queue WHERE status = 'Pending' ORDER BY created_at ASC"
        ).fetchall()

    if not pending_items:
        return {"success": True, "processed": 0, "message": "No pending operations in sync queue."}

    processed_count = 0
    conflict_count = 0

    with get_db_cursor(commit=True) as cur:
        for item in pending_items:
            q_id = item["queue_id"]
            tx_id = item["client_tx_id"]
            op_type = item["operation_type"]
            shop_id = item["shop_id"]
            now_iso = datetime.datetime.now().isoformat()

            try:
                payload = json.loads(item["payload_json"])
            except Exception:
                cur.execute("UPDATE offline_sync_queue SET status = 'Conflict', synced_at = ? WHERE queue_id = ?", (now_iso, q_id))
                conflict_count += 1
                continue

            try:
                if op_type == "POS_SALE":
                    # Check idempotency in sales_transactions
                    sale_id = payload.get("sale_id", tx_id)
                    exists = cur.execute("SELECT sale_id FROM sales_transactions WHERE sale_id = ?", (sale_id,)).fetchone()
                    if not exists:
                        cur.execute(
                            """
                            INSERT INTO sales_transactions (
                                sale_id, shop_id, date, customer_id, product_id, quantity,
                                selling_price, total_amount, payment_mode, payment_status
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                sale_id,
                                shop_id,
                                payload.get("date", datetime.date.today().isoformat()),
                                payload.get("customer_id", "CUST001"),
                                payload.get("product_id", "PROD001"),
                                float(payload.get("quantity", 1.0)),
                                float(payload.get("selling_price", 0.0)),
                                float(payload.get("total_amount", 0.0)),
                                payload.get("payment_mode", "Cash"),
                                payload.get("payment_status", "Completed"),
                            ),
                        )
                        # Decrement inventory stock
                        cur.execute(
                            "UPDATE inventory SET current_stock = MAX(0.0, current_stock - ?) WHERE product_id = ?",
                            (float(payload.get("quantity", 1.0)), payload.get("product_id", "PROD001")),
                        )

                elif op_type == "STOCK_UPDATE":
                    pid = payload.get("product_id")
                    stock_delta = float(payload.get("stock_delta", 0.0))
                    cur.execute(
                        "UPDATE inventory SET current_stock = MAX(0.0, current_stock + ?), last_updated = CURRENT_TIMESTAMP WHERE product_id = ?",
                        (stock_delta, pid),
                    )

                cur.execute("UPDATE offline_sync_queue SET status = 'Synced', synced_at = ? WHERE queue_id = ?", (now_iso, q_id))
                processed_count += 1
            except Exception as e:
                cur.execute("UPDATE offline_sync_queue SET status = 'Conflict', synced_at = ? WHERE queue_id = ?", (now_iso, q_id))
                conflict_count += 1

    log_audit_event(
        username=username,
        action_type="SYNC",
        entity_type="OFFLINE_QUEUE",
        entity_id=f"SYNC-{datetime.date.today()}",
        details=f"Processed sync queue: {processed_count} synced, {conflict_count} conflicts.",
    )

    return {
        "success": True,
        "processed": processed_count,
        "conflicts": conflict_count,
        "message": f"Successfully synchronized {processed_count} operations ({conflict_count} conflicts).",
    }

