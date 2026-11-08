"""
BizMetrics - PDF Invoice Generator
Generates clean, professional, publication-quality Tax Invoices / Cash Memos using ReportLab.
"""

from io import BytesIO
from typing import Dict, Any, Optional
import html
import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)

from utils.formatting import format_currency


def generate_pdf_invoice(
    bill_data: Dict[str, Any],
    customer_data: Dict[str, Any],
    shop_data: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate an authentic, professionally designed PDF Tax Invoice in memory.
    
    Args:
        bill_data: Dictionary containing transaction details (sale_id, date, product_name,
                   quantity, selling_price, discount_percent, total_amount, payment_mode,
                   payment_status, paid_amount, outstanding).
        customer_data: Dictionary containing customer details (customer_id, customer_name,
                       business_name, contact_number, email, city, address).
        shop_data: Optional shop information override.
    
    Returns:
        bytes: Binary PDF document.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    shop = shop_data or {
        "shop_name": "Shivansh Electronics and Hardware",
        "tagline": "Smart Business Intelligence & Hardware Distribution Hub",
        "address": "Station Road & Telibandha Commercial Hub, Raipur, Chhattisgarh 492001",
        "phone": "+91 98765 40001",
        "email": "billing@shivanshelectronics.com",
        "gstin": "22AAAAA0000A1Z5",
        "msme": "UDYAM-CG-02-0012345",
    }

    styles = getSampleStyleSheet()

    # Custom styles
    brand_title = ParagraphStyle(
        "BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E293B"),
    )
    brand_sub = ParagraphStyle(
        "BrandSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    )
    brand_badge = ParagraphStyle(
        "BrandBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0D9488"),
    )
    inv_title_style = ParagraphStyle(
        "InvTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        alignment=2,  # Right align
        textColor=colors.HexColor("#2563EB"),
    )
    inv_meta_style = ParagraphStyle(
        "InvMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=2,
        textColor=colors.HexColor("#334155"),
    )
    section_head = ParagraphStyle(
        "SectionHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F766E"),
    )
    body_text = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    th_style = ParagraphStyle(
        "THStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )
    th_right = ParagraphStyle(
        "THRight",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        alignment=2,
        textColor=colors.white,
    )
    td_style = ParagraphStyle(
        "TDStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
    )
    td_right = ParagraphStyle(
        "TDRight",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=2,
        textColor=colors.HexColor("#1E293B"),
    )
    footer_text = ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#94A3B8"),
    )

    story = []

    # 1. Header Row (Store Brand on Left, Invoice Details on Right)
    store_info_p = [
        Paragraph(shop["shop_name"], brand_title),
        Paragraph(shop["tagline"], brand_sub),
        Paragraph(shop["address"], brand_sub),
        Paragraph(f"Phone: {shop['phone']} | Email: {shop['email']}", brand_sub),
        Paragraph(f"GSTIN: {shop['gstin']} | UDYAM MSME: {shop['msme']}", brand_badge),
    ]

    sale_id = str(bill_data.get("Sale_ID", bill_data.get("sale_id", "SALE-0000")))
    raw_date = bill_data.get("Date", bill_data.get("date", "2026-06-01"))
    inv_date = str(raw_date)[:10] if pd.notnull(raw_date) else "2026-06-01"
    pay_mode = str(bill_data.get("Payment_Mode", bill_data.get("payment_mode", "Cash")))
    pay_status = str(bill_data.get("Payment_Status", bill_data.get("payment_status", "Completed")))

    inv_meta_p = [
        Paragraph("TAX INVOICE / CASH MEMO", inv_title_style),
        Paragraph(f"<b>Invoice No:</b> #{sale_id}", inv_meta_style),
        Paragraph(f"<b>Invoice Date:</b> {inv_date}", inv_meta_style),
        Paragraph(f"<b>Payment Mode:</b> {pay_mode}", inv_meta_style),
        Paragraph(f"<b>Status:</b> {pay_status}", inv_meta_style),
    ]

    header_table = Table(
        [[store_info_p, inv_meta_p]],
        colWidths=[340, 200],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0D9488"), spaceAfter=10))

    # 2. Billed To & Store Relationship Strip
    c_name = customer_data.get("customer_name", customer_data.get("Customer_Name", "Valued Customer"))
    c_biz = customer_data.get("business_name", customer_data.get("Business_Name", ""))
    c_id = customer_data.get("customer_id", customer_data.get("Customer_ID", "CUST001"))
    c_mob = customer_data.get("contact_number", customer_data.get("mobile_number", customer_data.get("Mobile_Number", "")))
    c_city = customer_data.get("city", customer_data.get("City", "Chhattisgarh"))
    c_addr = customer_data.get("address", "") or f"{c_city}, India"
    c_email = customer_data.get("email", customer_data.get("Email", ""))

    billed_to_cells = [
        Paragraph("BILLED TO / CUSTOMER DETAILS", section_head),
        Paragraph(f"<b>{c_name}</b>" + (f" ({c_biz})" if c_biz else ""), body_bold),
        Paragraph(f"<b>Customer ID:</b> {c_id}", body_text),
        Paragraph(f"<b>Contact:</b> {c_mob}" + (f" | <b>Email:</b> {c_email}" if c_email else ""), body_text),
        Paragraph(f"<b>Address:</b> {c_addr}", body_text),
    ]

    dispatch_cells = [
        Paragraph("SUPPLY & DISPATCH DETAILS", section_head),
        Paragraph("<b>Place of Supply:</b> Chhattisgarh (State Code: 22)", body_text),
        Paragraph("<b>Delivery Terms:</b> Store Counter / Verified Express", body_text),
        Paragraph("<b>Transaction Type:</b> Local B2B / B2C Rural Supply", body_text),
        Paragraph(f"<b>Verification:</b> Secured Client Profile ({c_id})", body_text),
    ]

    address_table = Table(
        [[billed_to_cells, dispatch_cells]],
        colWidths=[270, 270],
    )
    address_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FAF8F5")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#E2DBD0")),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(address_table)
    story.append(Spacer(1, 14))

    # 3. Itemized Products Table
    p_name = str(bill_data.get("Product_Name", bill_data.get("product_name", "Hardware Equipment & Supplies")))
    qty = float(bill_data.get("Quantity", bill_data.get("quantity", 1)))
    unit_price = float(bill_data.get("Selling_Price", bill_data.get("selling_price", 0)))
    disc_pct = float(bill_data.get("Discount_Percent", bill_data.get("discount_percent", 0)))
    
    gross_val = qty * unit_price
    disc_val = gross_val * (disc_pct / 100.0)
    net_val = float(bill_data.get("Bill_Amount", bill_data.get("total_amount", gross_val - disc_val)))
    
    out_amt = float(bill_data.get("Outstanding", bill_data.get("outstanding", 0.0)))
    paid_amt = float(bill_data.get("Paid_Amount", bill_data.get("paid_amount", net_val - out_amt)))

    items_data = [
        [
            Paragraph("#", th_style),
            Paragraph("Item Description", th_style),
            Paragraph("Qty", th_right),
            Paragraph("Unit Rate (INR)", th_right),
            Paragraph("Gross Total", th_right),
            Paragraph("Disc (%)", th_right),
            Paragraph("Net Amount", th_right),
        ],
        [
            Paragraph("1", td_style),
            Paragraph(f"<b>{html.escape(p_name)}</b><br/><font color='#64748B' size='7'>Standard Certified Trade Supply</font>", td_style),
            Paragraph(f"{qty:.0f}" if qty.is_integer() else f"{qty:.2f}", td_right),
            Paragraph(format_currency(unit_price), td_right),
            Paragraph(format_currency(gross_val), td_right),
            Paragraph(f"{disc_pct:.1f}%" if disc_pct > 0 else "0%", td_right),
            Paragraph(f"<b>{format_currency(net_val)}</b>", td_right),
        ],
    ]

    items_table = Table(
        items_data,
        colWidths=[25, 205, 45, 75, 65, 55, 70],
    )
    items_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D9488")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ])
    )
    story.append(items_table)
    story.append(Spacer(1, 12))

    # 4. Summary & Settlement Calculations Box
    summary_data = [
        ["Subtotal Gross:", format_currency(gross_val)],
        ["Trade Discount Applied:", f"-{format_currency(disc_val)}" if disc_val > 0 else "Rs. 0.00"],
        ["GST Included in Pricing (CGST+SGST):", "Included"],
        ["Total Net Invoice Amount:", format_currency(net_val)],
        ["Amount Paid / Settled:", format_currency(paid_amt)],
        ["Balance Due / Outstanding:", format_currency(out_amt)],
    ]

    sum_table_data = []
    for row in summary_data:
        is_total = "Total Net Invoice" in row[0]
        is_due = "Balance Due" in row[0]
        
        lbl_style = ParagraphStyle(
            f"SumLbl_{row[0][:4]}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold" if (is_total or is_due) else "Helvetica",
            fontSize=9.5 if is_total else 8.5,
            textColor=colors.HexColor("#1E293B"),
        )
        val_style = ParagraphStyle(
            f"SumVal_{row[0][:4]}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold" if (is_total or is_due) else "Helvetica",
            fontSize=10.5 if is_total else 8.5,
            alignment=2,
            textColor=colors.HexColor("#2563EB") if is_total else (colors.HexColor("#EA580C") if (is_due and out_amt > 0) else colors.HexColor("#059669")),
        )
        sum_table_data.append([Paragraph(row[0], lbl_style), Paragraph(row[1], val_style)])

    sum_table = Table(sum_table_data, colWidths=[150, 100])
    sum_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 2), (1, 2), 1, colors.HexColor("#1E293B")),
            ("LINEBELOW", (0, 3), (1, 3), 1, colors.HexColor("#1E293B")),
            ("BACKGROUND", (0, 3), (1, 3), colors.HexColor("#EFF6FF")),
        ])
    )

    terms_p = [
        Paragraph("<b>Terms & Payment Information:</b>", section_head),
        Paragraph("1. All hardware products are covered by manufacturer warranty against defects.", body_text),
        Paragraph("2. Outstanding credit ledger dues must be cleared as per trade agreement terms.", body_text),
        Paragraph("3. For electronic fund transfers, quote Customer ID & Invoice # as payment reference.", body_text),
        Paragraph("4. Computer generated digital invoice registered under BizMetrics Rural BI.", body_text),
    ]

    split_summary = Table(
        [[terms_p, sum_table]],
        colWidths=[290, 250],
    )
    split_summary.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(split_summary)
    story.append(Spacer(1, 20))

    # 5. Authorization & Verification Footer
    auth_data = [
        [
            Paragraph("<b>Customer Acknowledgment</b><br/><br/><br/>____________________________<br/>Received in Good Condition", body_text),
            Paragraph("<b>For Shivansh Electronics and Hardware</b><br/><br/><br/>____________________________<br/>Authorized Signatory", ParagraphStyle("AuthSign", parent=body_text, alignment=2)),
        ]
    ]
    auth_table = Table(auth_data, colWidths=[270, 270])
    auth_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(auth_table)
    story.append(Spacer(1, 14))

    # 6. Computer Generated Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=8))
    story.append(Paragraph("This is a computer-generated tax invoice generated from the BizMetrics – Smart Business Intelligence portal. No physical signature is required.", footer_text))

    doc.build(story)
    return buffer.getvalue()

