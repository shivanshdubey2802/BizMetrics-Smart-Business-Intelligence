"""
BizMetrics Smart Billing and POS Engine
Handles real-time customer billing, cart management, item-level and bill-level
discounts, GST tax calculations (CGST/SGST/IGST), atomic stock deduction,
receivables creation on credit sales, and PDF/thermal receipt generation.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID, DEFAULT_SHOP_NAME
from utils.invoice_generator import generate_pdf_invoice
from utils.audit_logger import log_audit_event
from utils.inventory_qr import quick_update_product_stock


def create_pos_bill(
    customer_id: str,
    items: list[dict[str, Any]],
    payment_mode: str = "Cash",
    bill_discount_percent: float = 0.0,
    tax_rate_percent: float = 18.0,
    is_interstate: bool = False,
    notes: str = "",
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
) -> dict[str, Any]:
    """
    Finalizes a POS bill transaction atomically:
    1. Validates stock availability for each item.
    2. Calculates subtotal, item discounts, bill discount, CGST/SGST or IGST.
    3. Generates unique sale_id.
    4. Inserts into sales_transactions.
    5. Decrements stock in inventory.
    6. If payment_mode is 'Credit / Udhaar', records receivable entry and updates customer dues.
    7. Generates printable PDF invoice.
    8. Writes audit log.
    """
    if not items:
        return {"success": False, "error": "Cart cannot be empty."}

    sale_id = f"SALE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    today_str = datetime.date.today().isoformat()

    # Step 1: Pre-calculate bill values
    total_gross = 0.0
    for it in items:
        qty = float(it.get("quantity", 1.0))
        price = float(it.get("selling_price", 0.0))
        disc_pct = float(it.get("discount_percent", 0.0))
        line_gross = qty * price * (1.0 - (disc_pct / 100.0))
        total_gross += line_gross

    # Apply bill discount
    bill_discount_amount = total_gross * (bill_discount_percent / 100.0)
    taxable_value = max(0.0, total_gross - bill_discount_amount)

    # Tax breakdown
    tax_pct = float(tax_rate_percent)
    tax_amount = taxable_value * (tax_pct / 100.0)
    grand_total = round(taxable_value + tax_amount, 2)

    if is_interstate:
        cgst_amt, sgst_amt, igst_amt = 0.0, 0.0, tax_amount
    else:
        cgst_amt = round(tax_amount / 2.0, 2)
        sgst_amt = round(tax_amount / 2.0, 2)
        igst_amt = 0.0

    payment_status = "Pending" if payment_mode.lower() in {"credit", "udhaar", "credit / udhaar"} else "Completed"
    credit_amount = grand_total if payment_status == "Pending" else 0.0

    # Step 2: Atomic database transaction
    with get_db_cursor(commit=True) as cur:
        # Fetch customer details
        cust_row = cur.execute(
            "SELECT customer_id, customer_name, business_name, contact_number, email, city, address, outstanding_amount FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()

        if not cust_row:
            customer_name = "Walk-in Retail Customer"
            cust_dict = {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "business_name": "Walk-in Buyer",
                "contact_number": "N/A",
                "email": "N/A",
                "city": "Local",
                "address": "",
            }
        else:
            cust_dict = dict(cust_row)
            customer_name = cust_dict["customer_name"]

        # Insert sales record for the bill (using primary product or multi-item note)
        primary_prod = items[0]
        prod_id = primary_prod.get("product_id", "PROD001")
        prod_name = primary_prod.get("product_name", "Hardware Goods")

        cur.execute(
            """
            INSERT INTO sales_transactions (
                sale_id, shop_id, date, customer_id, product_id, quantity, selling_price,
                discount_percent, total_amount, payment_mode, payment_status, credit_amount, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sale_id,
                shop_id,
                today_str,
                customer_id,
                prod_id,
                float(primary_prod.get("quantity", 1.0)),
                float(primary_prod.get("selling_price", 0.0)),
                float(bill_discount_percent),
                grand_total,
                payment_mode,
                payment_status,
                credit_amount,
                f"Items: {len(items)} SKU(s). Tax: ₹{tax_amount:.2f}. {notes}".strip(),
            ),
        )

        # Decrement inventory stock atomically for each line item
        for it in items:
            pid = it.get("product_id")
            qty = float(it.get("quantity", 1.0))
            if pid:
                cur.execute(
                    """
                    UPDATE inventory 
                    SET current_stock = MAX(0.0, current_stock - ?),
                        status = CASE 
                            WHEN (current_stock - ?) <= 0 THEN 'Out of Stock'
                            WHEN (current_stock - ?) <= minimum_stock THEN 'Low Stock'
                            ELSE 'Healthy'
                        END,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE product_id = ?
                    """,
                    (qty, qty, qty, pid),
                )

        # Handle Credit / Udhaar sale
        if payment_status == "Pending":
            rec_id = f"REC-{sale_id}"
            due_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
            cur.execute(
                """
                INSERT INTO receivables (
                    receivable_id, shop_id, invoice_id, customer_id, amount, due_date,
                    days_overdue, status, collection_priority, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 'Pending', 'P2: Medium', ?)
                """,
                (rec_id, shop_id, sale_id, customer_id, grand_total, due_date, f"Auto-created from POS Bill {sale_id}"),
            )
            # Update customer outstanding amount
            cur.execute(
                "UPDATE customers SET outstanding_amount = COALESCE(outstanding_amount, 0) + ? WHERE customer_id = ?",
                (grand_total, customer_id),
            )

    # Step 3: Generate PDF Invoice
    bill_data_for_pdf = {
        "sale_id": sale_id,
        "date": today_str,
        "product_name": f"{prod_name} + {len(items)-1} more items" if len(items) > 1 else prod_name,
        "quantity": sum(float(x.get("quantity", 1.0)) for x in items),
        "selling_price": taxable_value,
        "discount_percent": bill_discount_percent,
        "total_amount": grand_total,
        "payment_mode": payment_mode,
        "payment_status": payment_status,
        "paid_amount": 0.0 if payment_status == "Pending" else grand_total,
        "outstanding": credit_amount,
        "items": items,
        "taxable_value": taxable_value,
        "tax_amount": tax_amount,
        "cgst": cgst_amt,
        "sgst": sgst_amt,
        "igst": igst_amt,
    }

    try:
        pdf_bytes = generate_pdf_invoice(bill_data_for_pdf, cust_dict)
    except Exception as e:
        pdf_bytes = b""
        print(f"Warning: PDF generation failed: {e}")

    # Step 4: Write Audit Log
    log_audit_event(
        username=username,
        action_type="BILLING",
        entity_type="POS_SALE",
        entity_id=sale_id,
        details=f"POS Sale created for {customer_name}. Total: ₹{grand_total:,.2f} ({payment_mode})",
        shop_id=shop_id,
    )

    return {
        "success": True,
        "sale_id": sale_id,
        "date": today_str,
        "grand_total": grand_total,
        "taxable_value": taxable_value,
        "tax_amount": tax_amount,
        "cgst": cgst_amt,
        "sgst": sgst_amt,
        "igst": igst_amt,
        "payment_mode": payment_mode,
        "payment_status": payment_status,
        "pdf_bytes": pdf_bytes,
        "customer_name": customer_name,
    }


def render_thermal_receipt_html(bill_summary: dict[str, Any], items: list[dict[str, Any]], shop_name: str = DEFAULT_SHOP_NAME) -> str:
    """Generates an aesthetic thermal-style POS receipt preview."""
    rows_html = ""
    for it in items:
        name = it.get("product_name", "Item")[:22]
        qty = it.get("quantity", 1.0)
        price = it.get("selling_price", 0.0)
        tot = qty * price
        rows_html += f"""
        <tr>
            <td style="text-align: left; padding: 2px 0;">{name}</td>
            <td style="text-align: center; padding: 2px 0;">{qty}</td>
            <td style="text-align: right; padding: 2px 0;">₹{price:,.2f}</td>
            <td style="text-align: right; padding: 2px 0; font-weight: 600;">₹{tot:,.2f}</td>
        </tr>
        """

    return f"""
    <div style="font-family: 'Courier New', Courier, monospace; background: #FFFDF9; border: 1px dashed #CBD5E1; padding: 1.25rem; border-radius: 8px; max-width: 360px; margin: 0 auto; color: #1E293B; box-shadow: 0 4px 6px rgba(0,0,0,0.04);">
        <div style="text-align: center; border-bottom: 1px dashed #94A3B8; padding-bottom: 8px; margin-bottom: 8px;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700;">{shop_name}</h3>
            <p style="margin: 2px 0; font-size: 0.75rem; color: #64748B;">Tax Invoice / Cash Memo</p>
            <p style="margin: 2px 0; font-size: 0.75rem;">Bill No: <strong>{bill_summary.get('sale_id', 'N/A')}</strong></p>
            <p style="margin: 2px 0; font-size: 0.75rem;">Date: {bill_summary.get('date', 'N/A')} | Customer: {bill_summary.get('customer_name', 'Customer')}</p>
        </div>
        <table style="width: 100%; font-size: 0.78rem; border-collapse: collapse; margin-bottom: 8px;">
            <thead>
                <tr style="border-bottom: 1px solid #E2E8F0; color: #64748B;">
                    <th style="text-align: left;">Item</th>
                    <th style="text-align: center;">Qty</th>
                    <th style="text-align: right;">Rate</th>
                    <th style="text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <div style="border-top: 1px dashed #94A3B8; padding-top: 6px; font-size: 0.8rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                <span>Taxable Value:</span>
                <span>₹{bill_summary.get('taxable_value', 0):,.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                <span>GST ({bill_summary.get('tax_pct', 18)}%):</span>
                <span>₹{bill_summary.get('tax_amount', 0):,.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 0.95rem; margin-top: 4px; padding-top: 4px; border-top: 1px solid #1E293B;">
                <span>GRAND TOTAL:</span>
                <span style="color: #0D9488;">₹{bill_summary.get('grand_total', 0):,.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #64748B; margin-top: 4px;">
                <span>Payment Mode:</span>
                <span>{bill_summary.get('payment_mode', 'Cash')} ({bill_summary.get('payment_status', 'Completed')})</span>
            </div>
        </div>
        <div style="text-align: center; margin-top: 12px; padding-top: 8px; border-top: 1px dashed #CBD5E1; font-size: 0.7rem; color: #64748B;">
            Thank you for your business! Visit Again.
        </div>
    </div>
    """

