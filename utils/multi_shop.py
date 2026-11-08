"""
BizMetrics Multi-Shop & Multi-Branch Management Module
Handles multiple business branches, branch-specific analytics, consolidated
owner-level aggregation, and branch role permissions.
"""
from __future__ import annotations

from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME


def get_all_registered_branches() -> list[dict[str, str]]:
    """Retrieve all active shops/branches from the shops table."""
    with get_db_cursor(commit=False) as cur:
        rows = cur.execute("SELECT shop_id, shop_name, owner_name, phone, address FROM shops ORDER BY shop_id").fetchall()
        if rows:
            return [dict(r) for r in rows]
        return [{"shop_id": DEFAULT_SHOP_ID, "shop_name": DEFAULT_SHOP_NAME, "owner_name": "Shivansh G", "phone": "+91 98765 43210", "address": "Raipur, Chhattisgarh"}]


def get_branch_selector_options() -> dict[str, str]:
    """
    Returns options dictionary for branch dropdown:
    {'all': '🌐 All Branches (Consolidated)', 'shop_id_1': 'Store 1', ...}
    """
    branches = get_all_registered_branches()
    options = {"all": "🌐 All Branches (Consolidated)"}
    for b in branches:
        options[b["shop_id"]] = f"🏢 {b['shop_name']}"
    return options


def get_consolidated_branch_metrics() -> pd.DataFrame:
    """
    Computes side-by-side revenue, orders, inventory stock, and customer dues
    across all branches in the network.
    """
    with get_db_cursor(commit=False) as cur:
        query = """
        SELECT 
            s.shop_id,
            s.shop_name,
            s.address,
            COALESCE(SUM(st.total_amount), 0.0) as total_revenue,
            COUNT(DISTINCT st.sale_id) as total_orders,
            COUNT(DISTINCT c.customer_id) as customer_count,
            COALESCE(SUM(c.outstanding_amount), 0.0) as total_outstanding
        FROM shops s
        LEFT JOIN sales_transactions st ON (s.shop_id = st.shop_id OR (s.shop_id = 'shivansh_electronics_hardware' AND st.shop_id IS NULL))
        LEFT JOIN customers c ON (s.shop_id = c.shop_id OR (s.shop_id = 'shivansh_electronics_hardware' AND c.shop_id IS NULL))
        GROUP BY s.shop_id;
        """
        rows = cur.execute(query).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])


def add_new_branch(
    shop_id: str,
    shop_name: str,
    owner_name: str = "Shivansh G",
    phone: str = "",
    address: str = "",
) -> tuple[bool, str]:
    """Registers a new branch in the shops table."""
    sid = str(shop_id).strip().lower().replace(" ", "_")
    if not sid or not shop_name:
        return False, "Shop ID and Shop Name cannot be empty."

    with get_db_cursor(commit=True) as cur:
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
            (sid, shop_name.strip(), owner_name.strip(), phone.strip(), address.strip()),
        )
    return True, f"Branch '{shop_name}' ({sid}) registered successfully."

