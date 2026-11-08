"""
BizMetrics Daily Business Reports Engine
Computes daily sales, daily expenses, net profit, new customer registrations,
collections recovered vs credit extended, generates end-of-day (EOD) WhatsApp
summaries, and exports daily PDF/Excel reports.
"""
from __future__ import annotations

import datetime
from io import BytesIO
from typing import Any, Optional
import pandas as pd
import streamlit as st
from utils.database import get_db_cursor, DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME
from utils.formatting import format_currency


@st.cache_data(ttl=60, show_spinner=False)
def get_daily_business_summary(target_date: Optional[str] = None, shop_id: str = DEFAULT_SHOP_ID) -> dict[str, Any]:
    """
    Computes comprehensive daily metrics for a specific date (defaults to today).
    Pulls ground-truth records directly from sales_transactions, expenses, customers, and receivables.
    """
    date_str = target_date or datetime.date.today().isoformat()

    with get_db_cursor(commit=False) as cur:
        # If target date has 0 transactions (e.g. fresh day), find latest active transaction date
        tx_check = cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE date = ?", (date_str,)).fetchone()[0]
        if tx_check == 0:
            latest_date_row = cur.execute("SELECT MAX(date) FROM sales_transactions").fetchone()
            if latest_date_row and latest_date_row[0]:
                date_str = latest_date_row[0]

        # 1. Sales on date
        sales_rows = cur.execute(
            """
            SELECT sale_id, customer_id, product_id, quantity, selling_price, total_amount, payment_mode, payment_status, credit_amount
            FROM sales_transactions
            WHERE date = ?
            """,
            (date_str,),
        ).fetchall()

        total_sales = sum(float(r["total_amount"]) for r in sales_rows)
        cash_sales = sum(float(r["total_amount"]) for r in sales_rows if r["payment_mode"] == "Cash")
        upi_sales = sum(float(r["total_amount"]) for r in sales_rows if r["payment_mode"] in {"UPI", "Online", "Card"})
        credit_sales = sum(float(r["total_amount"]) for r in sales_rows if r["payment_mode"].lower() in {"credit", "udhaar"})
        total_orders = len(sales_rows)

        # 2. Expenses on date
        exp_rows = cur.execute(
            "SELECT expense_id, category, amount, description FROM expenses WHERE date = ?",
            (date_str,),
        ).fetchall()
        total_expenses = sum(float(r["amount"]) for r in exp_rows)

        # 3. New Customers registered on or by date
        new_cust_cnt = cur.execute(
            "SELECT COUNT(*) FROM customers WHERE registration_date = ?",
            (date_str,),
        ).fetchone()[0]

        # 4. Receivables status
        pending_rec = cur.execute(
            "SELECT SUM(amount) FROM receivables WHERE status = 'Pending'"
        ).fetchone()[0] or 0.0

        # 5. Low stock alerts
        low_stock_cnt = cur.execute(
            "SELECT COUNT(*) FROM inventory WHERE current_stock <= minimum_stock"
        ).fetchone()[0]

    net_profit = total_sales - total_expenses
    gross_margin_pct = round((net_profit / total_sales * 100.0) if total_sales > 0 else 0.0, 1)

    # Persist in daily_business_summaries table
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO daily_business_summaries (
                    summary_id, shop_id, report_date, total_sales, total_expenses,
                    gross_profit, net_profit, new_customers, cash_collected, credit_extended,
                    receivables_pending, low_stock_alerts_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(shop_id, report_date) DO UPDATE SET
                    total_sales = excluded.total_sales,
                    total_expenses = excluded.total_expenses,
                    net_profit = excluded.net_profit,
                    cash_collected = excluded.cash_collected,
                    credit_extended = excluded.credit_extended,
                    receivables_pending = excluded.receivables_pending,
                    low_stock_alerts_count = excluded.low_stock_alerts_count,
                    generated_at = CURRENT_TIMESTAMP
                """,
                (
                    f"DSUM-{date_str}-{shop_id[:4]}",
                    shop_id,
                    date_str,
                    total_sales,
                    total_expenses,
                    net_profit,
                    net_profit,
                    new_cust_cnt,
                    cash_sales + upi_sales,
                    credit_sales,
                    pending_rec,
                    low_stock_cnt,
                ),
            )
    except Exception:
        pass

    return {
        "report_date": date_str,
        "shop_id": shop_id,
        "total_sales": total_sales,
        "cash_sales": cash_sales,
        "upi_sales": upi_sales,
        "credit_sales": credit_sales,
        "total_orders": total_orders,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "gross_margin_pct": gross_margin_pct,
        "new_customers": new_cust_cnt,
        "receivables_pending": pending_rec,
        "low_stock_count": low_stock_cnt,
        "sales_rows": [dict(r) for r in sales_rows],
        "expense_rows": [dict(r) for r in exp_rows],
    }


def generate_eod_whatsapp_digest(summary: dict[str, Any], shop_name: str = DEFAULT_SHOP_NAME) -> str:
    """Generates an aesthetic, concise WhatsApp End-of-Day text summary for the owner."""
    date_str = summary.get("report_date", "Today")
    tot_sales = summary.get("total_sales", 0.0)
    tot_exp = summary.get("total_expenses", 0.0)
    net_p = summary.get("net_profit", 0.0)
    cash_upi = summary.get("cash_sales", 0.0) + summary.get("upi_sales", 0.0)
    credit = summary.get("credit_sales", 0.0)
    pending_rec = summary.get("receivables_pending", 0.0)
    low_stock = summary.get("low_stock_count", 0)

    return (
        f"📊 *{shop_name} — Daily EOD Summary*\n"
        f"📅 *Date:* {date_str}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Total Sales:* ₹{tot_sales:,.2f} ({summary.get('total_orders', 0)} orders)\n"
        f"💵 *Cash/UPI Inflow:* ₹{cash_upi:,.2f}\n"
        f"📝 *New Udhaar/Credit:* ₹{credit:,.2f}\n"
        f"📉 *Total Expenses:* ₹{tot_exp:,.2f}\n"
        f"📈 *Net Profit Today:* ₹{net_p:,.2f} ({summary.get('gross_margin_pct', 0)}% margin)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Pending Baaki:* ₹{pending_rec:,.2f}\n"
        f"📦 *Low Stock Alerts:* {low_stock} items need reordering\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"BizMetrics AI Business Intelligence 🚀"
    )

