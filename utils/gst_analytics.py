"""
BizMetrics GST and Tax Analytics Engine
Calculates taxable sales, Output CGST, SGST, IGST liabilities, Input Tax Credit (ITC),
GSTR-1 invoice summaries, GSTR-3B computation sheets, and tax audit reports.
"""
from __future__ import annotations

import datetime
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID


def get_gst_configuration(shop_id: str = DEFAULT_SHOP_ID) -> dict[str, Any]:
    """Retrieve GST setup for shop."""
    with get_db_cursor(commit=False) as cur:
        row = cur.execute(
            "SELECT * FROM gst_tax_configs WHERE shop_id = ?",
            (shop_id,),
        ).fetchone()
        if row:
            return dict(row)
        return {
            "shop_id": shop_id,
            "gstin": "22AAAAA0000A1Z5",
            "legal_name": "Shivansh Electronics and Hardware",
            "state_code": "22",
            "default_cgst_pct": 9.0,
            "default_sgst_pct": 9.0,
            "default_igst_pct": 18.0,
            "composition_scheme": 0,
        }


def update_gst_configuration(
    shop_id: str,
    gstin: str,
    legal_name: str,
    default_cgst_pct: float = 9.0,
    default_sgst_pct: float = 9.0,
    default_igst_pct: float = 18.0,
    composition_scheme: int = 0,
) -> tuple[bool, str]:
    """Updates shop GSTIN and default tax rates."""
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO gst_tax_configs (
                config_id, shop_id, gstin, legal_name, state_code,
                default_cgst_pct, default_sgst_pct, default_igst_pct, composition_scheme
            )
            VALUES (?, ?, ?, ?, '22', ?, ?, ?, ?)
            ON CONFLICT(shop_id) DO UPDATE SET
                gstin = excluded.gstin,
                legal_name = excluded.legal_name,
                default_cgst_pct = excluded.default_cgst_pct,
                default_sgst_pct = excluded.default_sgst_pct,
                default_igst_pct = excluded.default_igst_pct,
                composition_scheme = excluded.composition_scheme
            """,
            (
                f"GST-{shop_id[:6]}",
                shop_id,
                gstin.strip().upper(),
                legal_name.strip(),
                float(default_cgst_pct),
                float(default_sgst_pct),
                float(default_igst_pct),
                int(composition_scheme),
            ),
        )
    return True, "GST configuration updated successfully."


def compute_gst_tax_analytics(
    shop_id: str = DEFAULT_SHOP_ID,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Computes complete GST Output Tax liability and Input Tax Credit (ITC) for the specified period.
    """
    gst_conf = get_gst_configuration(shop_id)
    cgst_rate = float(gst_conf.get("default_cgst_pct", 9.0))
    sgst_rate = float(gst_conf.get("default_sgst_pct", 9.0))
    total_tax_rate = cgst_rate + sgst_rate  # usually 18%

    with get_db_cursor(commit=False) as cur:
        # 1. Fetch sales transactions in period
        sales_query = "SELECT sale_id, date, customer_id, product_id, total_amount, payment_mode, notes FROM sales_transactions WHERE 1=1"
        params = []
        if shop_id and shop_id != "all":
            sales_query += " AND (shop_id = ? OR shop_id = 'shivansh_electronics_hardware')"
            params.append(shop_id)
        if start_date:
            sales_query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sales_query += " AND date <= ?"
            params.append(end_date)

        sales_rows = cur.execute(sales_query, tuple(params)).fetchall()

        # 2. Fetch expenses in period for Input Tax Credit (ITC) calculation
        exp_query = "SELECT expense_id, date, category, amount, is_fixed FROM expenses WHERE 1=1"
        exp_params = []
        if start_date:
            exp_query += " AND date >= ?"
            exp_params.append(start_date)
        if end_date:
            exp_query += " AND date <= ?"
            exp_params.append(end_date)

        exp_rows = cur.execute(exp_query, tuple(exp_params)).fetchall()

    total_gross_sales = sum(float(r["total_amount"]) for r in sales_rows)
    # Total sales in retail typically include tax. Taxable value = Gross / (1 + TaxRate)
    tax_divisor = 1.0 + (total_tax_rate / 100.0)
    taxable_turnover = round(total_gross_sales / tax_divisor, 2)
    output_tax_total = round(total_gross_sales - taxable_turnover, 2)
    output_cgst = round(output_tax_total / 2.0, 2)
    output_sgst = round(output_tax_total / 2.0, 2)
    output_igst = 0.0

    # Expenses & ITC calculation (eligible business purchases like packaging, logistics, tools, freight)
    total_expenses = sum(float(r["amount"]) for r in exp_rows)
    eligible_itc_expenses = sum(
        float(r["amount"]) for r in exp_rows 
        if r["category"] in {"Inventory Purchase", "Packaging & Dispatch", "Freight & Logistics", "Store Operations", "Utilities"}
    )
    # Estimated 18% ITC on eligible purchases
    estimated_itc_total = round((eligible_itc_expenses / tax_divisor) * (total_tax_rate / 100.0), 2)
    itc_cgst = round(estimated_itc_total / 2.0, 2)
    itc_sgst = round(estimated_itc_total / 2.0, 2)

    # Net tax payable
    net_payable_cgst = max(0.0, output_cgst - itc_cgst)
    net_payable_sgst = max(0.0, output_sgst - itc_sgst)
    net_tax_payable_total = round(net_payable_cgst + net_payable_sgst, 2)

    # GSTR-1 Preview Summary
    gstr1_summary = [
        {"Section": "4A - B2B Invoices (Registered)", "Count": 0, "Taxable_Value": 0.0, "CGST": 0.0, "SGST": 0.0, "Total_Tax": 0.0},
        {"Section": "7 - B2C Others (Retail Sales)", "Count": len(sales_rows), "Taxable_Value": taxable_turnover, "CGST": output_cgst, "SGST": output_sgst, "Total_Tax": output_tax_total},
    ]

    # GSTR-3B Computation Table
    gstr3b_computation = [
        {"Description": "3.1 (a) Outward Taxable Supplies", "Taxable_Value": taxable_turnover, "IGST": 0.0, "CGST": output_cgst, "SGST": output_sgst},
        {"Description": "4 (A) Eligible ITC Available", "Taxable_Value": round(eligible_itc_expenses / tax_divisor, 2), "IGST": 0.0, "CGST": itc_cgst, "SGST": itc_sgst},
        {"Description": "6.1 Net Tax Payable in Cash", "Taxable_Value": 0.0, "IGST": 0.0, "CGST": net_payable_cgst, "SGST": net_payable_sgst},
    ]

    return {
        "gst_config": gst_conf,
        "total_gross_sales": total_gross_sales,
        "taxable_turnover": taxable_turnover,
        "output_tax_total": output_tax_total,
        "output_cgst": output_cgst,
        "output_sgst": output_sgst,
        "output_igst": output_igst,
        "eligible_itc_total": estimated_itc_total,
        "itc_cgst": itc_cgst,
        "itc_sgst": itc_sgst,
        "net_tax_payable_total": net_tax_payable_total,
        "net_payable_cgst": net_payable_cgst,
        "net_payable_sgst": net_payable_sgst,
        "gstr1_summary": pd.DataFrame(gstr1_summary),
        "gstr3b_computation": pd.DataFrame(gstr3b_computation),
        "total_invoices": len(sales_rows),
    }
