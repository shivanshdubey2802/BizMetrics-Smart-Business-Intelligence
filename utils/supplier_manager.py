"""
BizMetrics Supplier and Purchase Management Engine
Manages supplier profiles, Purchase Orders (PO), inward stock reception,
supplier payment tracking, and supplier reliability / performance scoring.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID
from utils.audit_logger import log_audit_event


def get_all_suppliers(shop_id: str = DEFAULT_SHOP_ID) -> pd.DataFrame:
    """Fetch all registered vendors and suppliers."""
    query = """
    SELECT 
        vendor_id, vendor_name, material_type, total_ordered_amount,
        total_paid_amount, outstanding_balance, next_payment_date,
        credit_days_allowed, created_at
    FROM vendors
    ORDER BY vendor_name;
    """
    with get_db_cursor(commit=False) as cur:
        rows = cur.execute(query).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame(columns=[
            "vendor_id", "vendor_name", "material_type", "total_ordered_amount",
            "total_paid_amount", "outstanding_balance", "next_payment_date", "credit_days_allowed", "created_at"
        ])


def add_or_update_supplier(
    vendor_id: str,
    vendor_name: str,
    material_type: str = "Hardware Supplies",
    credit_days_allowed: int = 30,
    next_payment_date: Optional[str] = None,
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
) -> tuple[bool, str]:
    """Adds a new vendor or updates existing vendor profile."""
    vid = vendor_id.strip().upper() if vendor_id else f"VEND-{uuid.uuid4().hex[:4].upper()}"
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO vendors (
                vendor_id, shop_id, vendor_name, material_type,
                credit_days_allowed, next_payment_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(vendor_id) DO UPDATE SET
                vendor_name = excluded.vendor_name,
                material_type = excluded.material_type,
                credit_days_allowed = excluded.credit_days_allowed,
                next_payment_date = excluded.next_payment_date
            """,
            (vid, shop_id, vendor_name.strip(), material_type.strip(), int(credit_days_allowed), next_payment_date or ""),
        )

    log_audit_event(
        username=username,
        action_type="SUPPLIER",
        entity_type="VENDOR_PROFILE",
        entity_id=vid,
        details=f"Saved vendor {vendor_name} ({vid})",
        shop_id=shop_id,
    )
    return True, f"Supplier '{vendor_name}' ({vid}) saved successfully."


def create_purchase_order(
    vendor_id: str,
    items: list[dict[str, Any]],
    expected_delivery_date: Optional[str] = None,
    notes: str = "",
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
) -> dict[str, Any]:
    """
    Creates a new Purchase Order (PO) with line items.
    Status starts as 'Sent'.
    """
    if not items:
        return {"success": False, "error": "PO must contain at least one product."}

    po_id = f"PO-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    order_date = datetime.date.today().isoformat()
    total_amount = sum(float(it.get("quantity", 1.0)) * float(it.get("unit_price", 0.0)) for it in items)

    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO purchase_orders (po_id, shop_id, vendor_id, order_date, expected_date, total_amount, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Sent', ?)
            """,
            (po_id, shop_id, vendor_id, order_date, expected_delivery_date or "", total_amount, notes),
        )

        for it in items:
            qty = float(it.get("quantity", 1.0))
            price = float(it.get("unit_price", 0.0))
            cur.execute(
                """
                INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_price, total_amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (po_id, it["product_id"], qty, price, qty * price),
            )

        # Update vendor's total ordered amount & outstanding balance
        cur.execute(
            """
            UPDATE vendors
            SET total_ordered_amount = COALESCE(total_ordered_amount, 0) + ?,
                outstanding_balance = COALESCE(outstanding_balance, 0) + ?
            WHERE vendor_id = ?
            """,
            (total_amount, total_amount, vendor_id),
        )

    log_audit_event(
        username=username,
        action_type="SUPPLIER",
        entity_type="PURCHASE_ORDER",
        entity_id=po_id,
        details=f"Created PO {po_id} for vendor {vendor_id}. Total: ₹{total_amount:,.2f}",
        shop_id=shop_id,
    )

    return {
        "success": True,
        "po_id": po_id,
        "order_date": order_date,
        "total_amount": total_amount,
        "status": "Sent",
    }


def receive_purchase_order(
    po_id: str,
    username: str = "Shivansh G",
    shop_id: str = DEFAULT_SHOP_ID,
) -> tuple[bool, str]:
    """
    Marks a Purchase Order as 'Received' and automatically increases current_stock in inventory table!
    """
    with get_db_cursor(commit=True) as cur:
        po = cur.execute("SELECT status, vendor_id FROM purchase_orders WHERE po_id = ?", (po_id,)).fetchone()
        if not po:
            return False, f"Purchase order {po_id} not found."
        if po["status"] == "Received":
            return False, f"Purchase order {po_id} has already been received into stock."

        # Fetch items
        items = cur.execute("SELECT product_id, quantity FROM purchase_order_items WHERE po_id = ?", (po_id,)).fetchall()
        for it in items:
            pid = it["product_id"]
            qty = float(it["quantity"])
            cur.execute(
                """
                UPDATE inventory 
                SET current_stock = current_stock + ?,
                    status = CASE 
                        WHEN (current_stock + ?) <= 0 THEN 'Out of Stock'
                        WHEN (current_stock + ?) <= minimum_stock THEN 'Low Stock'
                        ELSE 'Healthy'
                    END,
                    last_updated = CURRENT_TIMESTAMP
                WHERE product_id = ?
                """,
                (qty, qty, qty, pid),
            )

        cur.execute("UPDATE purchase_orders SET status = 'Received' WHERE po_id = ?", (po_id,))

    log_audit_event(
        username=username,
        action_type="INVENTORY",
        entity_type="PO_STOCK_INWARD",
        entity_id=po_id,
        details=f"Inwarded stock from PO {po_id} ({len(items)} items)",
        shop_id=shop_id,
    )
    return True, f"PO {po_id} received. All product inventory balances increased automatically!"


def record_supplier_payment(
    vendor_id: str,
    amount: float,
    payment_mode: str = "Bank Transfer",
    reference_no: str = "",
    po_id: Optional[str] = None,
    notes: str = "",
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
) -> tuple[bool, str]:
    """Records a payment disbursed to a supplier and decrements vendor outstanding balance."""
    if amount <= 0:
        return False, "Payment amount must be greater than zero."

    payment_id = f"VPAY-{datetime.datetime.now().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:4].upper()}"
    today_str = datetime.date.today().isoformat()

    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO supplier_payments (payment_id, shop_id, vendor_id, po_id, payment_date, amount, payment_mode, reference_no, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payment_id, shop_id, vendor_id, po_id or "", today_str, float(amount), payment_mode, reference_no, notes),
        )

        cur.execute(
            """
            UPDATE vendors
            SET total_paid_amount = COALESCE(total_paid_amount, 0) + ?,
                outstanding_balance = MAX(0.0, COALESCE(outstanding_balance, 0) - ?)
            WHERE vendor_id = ?
            """,
            (float(amount), float(amount), vendor_id),
        )

    log_audit_event(
        username=username,
        action_type="FINANCE",
        entity_type="SUPPLIER_PAYMENT",
        entity_id=payment_id,
        details=f"Paid ₹{amount:,.2f} to vendor {vendor_id} via {payment_mode}",
        shop_id=shop_id,
    )
    return True, f"Recorded payment of ₹{amount:,.2f} to supplier {vendor_id}."


def get_supplier_performance_metrics() -> pd.DataFrame:
    """Computes vendor delivery fulfillment rate, outstanding ratio, and score."""
    with get_db_cursor(commit=False) as cur:
        query = """
        SELECT 
            v.vendor_id, v.vendor_name, v.material_type,
            v.total_ordered_amount, v.total_paid_amount, v.outstanding_balance,
            COUNT(po.po_id) as total_pos,
            SUM(CASE WHEN po.status = 'Received' THEN 1 ELSE 0 END) as received_pos
        FROM vendors v
        LEFT JOIN purchase_orders po ON v.vendor_id = po.vendor_id
        GROUP BY v.vendor_id;
        """
        rows = cur.execute(query).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["fulfillment_rate"] = df.apply(
            lambda r: round((r["received_pos"] / r["total_pos"] * 100.0) if r["total_pos"] > 0 else 100.0, 1),
            axis=1,
        )
        df["supplier_rating"] = df["fulfillment_rate"].apply(
            lambda f: "⭐⭐⭐⭐⭐ Exceptional" if f >= 90 else ("⭐⭐⭐⭐ Reliable" if f >= 75 else "⭐⭐⭐ Average")
        )
        return df

