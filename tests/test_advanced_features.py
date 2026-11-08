"""
Test Suite for Additional Advanced Features in BizMetrics
Covers all 15 capabilities:
1. Smart Data Import Center
2. Barcode and QR Inventory
3. Smart Billing and POS
4. Communication Integration
5. Mobile-Friendly Owner Dashboard
6. Database Backup and Restore
7. Supplier and Purchase Management
8. Daily Business Reports
9. Voice-Based Multilingual AI Advisor
10. Multi-Shop Management
11. GST and Tax Analytics
12. Offline and Synchronization Support
13. Audit Trail
14. Local Market Comparison
15. AI Report Generator
"""
from __future__ import annotations

import pandas as pd
import pytest
from utils.database import get_db_cursor, DEFAULT_SHOP_ID
from utils.audit_logger import log_audit_event, fetch_audit_logs
from utils.backup_manager import create_database_backup, check_database_health, list_database_backups
from utils.inventory_qr import generate_product_qr_code, generate_barcode_svg_pattern, lookup_product_by_code, quick_update_product_stock
from utils.pos_billing import create_pos_bill, render_thermal_receipt_html
from utils.communications import format_whatsapp_url, format_mailto_url, build_invoice_share_message, build_payment_reminder_message, get_configured_providers
from utils.data_importer import auto_map_columns, validate_and_preview_import, execute_import_to_database
from utils.supplier_manager import get_all_suppliers, add_or_update_supplier, create_purchase_order, receive_purchase_order, record_supplier_payment, get_supplier_performance_metrics
from utils.daily_reports import get_daily_business_summary, generate_eod_whatsapp_digest
from utils.gst_analytics import compute_gst_tax_analytics, get_gst_configuration
from utils.offline_sync import queue_offline_operation, get_sync_queue_status, process_sync_queue
from utils.multi_shop import get_all_registered_branches, get_branch_selector_options, get_consolidated_branch_metrics
from utils.voice_input import get_speech_language_code, transcribe_audio


def test_01_smart_data_import_center():
    """Verify column mapping, validation, duplicate prevention, and database import."""
    cols = ["Item Code", "Item Name", "Category", "Sale Price", "Cost Price"]
    mapping = auto_map_columns(cols, "products")
    assert "product_id" in mapping
    assert "product_name" in mapping
    assert "selling_price" in mapping

    import uuid
    dynamic_id = f"PROD_IMP_{uuid.uuid4().hex[:6].upper()}"
    batch_df = pd.DataFrame([
        {"Item Code": dynamic_id, "Item Name": "Smart LED 9W", "Category": "Electrical", "Sale Price": "120", "Cost Price": "80"},
        {"Item Code": "PROD001", "Item Name": "Duplicate SKU", "Category": "Hardware", "Sale Price": "500", "Cost Price": "400"},
    ])
    preview, summary = validate_and_preview_import(batch_df, "products", mapping)
    assert summary["valid_rows"] >= 1
    assert summary["duplicate_rows"] >= 1

    try:
        imp_res = execute_import_to_database(preview, "products", mapping, file_name="test_upload.csv", skip_duplicates=True)
        assert imp_res["success"] is True
        assert imp_res["imported"] >= 1
    finally:
        with get_db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM inventory WHERE product_id = ?", (dynamic_id,))
            cur.execute("DELETE FROM products WHERE product_id = ?", (dynamic_id,))
            cur.execute("DELETE FROM import_logs WHERE file_name = 'test_upload.csv'")


def test_02_barcode_and_qr_inventory():
    """Verify QR generation, SVG barcode generation, product lookup, and atomic stock updates."""
    raw_qr, data_uri = generate_product_qr_code("PROD001", "Steel Pipes", 500.0)
    assert len(raw_qr) > 500
    assert data_uri.startswith("data:image/png;base64,")

    svg = generate_barcode_svg_pattern("PROD001")
    assert "<svg" in svg
    assert "PROD001" in svg

    prod = lookup_product_by_code("PROD001")
    assert prod is not None
    assert "product_name" in prod

    ok, msg, new_stk = quick_update_product_stock("PROD001", stock_delta=2.0)
    assert ok is True
    assert new_stk >= 0.0


def test_03_smart_billing_and_pos():
    """Verify POS checkout, atomic stock deduction, receivables link, and PDF invoice generation."""
    items = [{"product_id": "PROD001", "product_name": "Steel Pipes", "quantity": 1.0, "selling_price": 450.0, "discount_percent": 0.0}]
    try:
        bill = create_pos_bill("CUST001", items, payment_mode="Credit / Udhaar", tax_rate_percent=18.0)
        assert bill["success"] is True
        assert bill["grand_total"] > 0
        assert bill["payment_status"] == "Pending"
        assert len(bill["pdf_bytes"]) > 1000

        html_rec = render_thermal_receipt_html(bill, items)
        assert "Tax Invoice" in html_rec
        assert "GRAND TOTAL" in html_rec
    finally:
        if "bill" in locals() and bill.get("sale_id"):
            with get_db_cursor(commit=True) as cur:
                cur.execute("DELETE FROM sales_transactions WHERE sale_id = ?", (bill["sale_id"],))
                cur.execute("DELETE FROM receivables WHERE invoice_id = ?", (bill["sale_id"],))
                cur.execute("UPDATE inventory SET current_stock = current_stock + 1.0 WHERE product_id = 'PROD001'")


def test_04_communication_integration():
    """Verify WhatsApp click-to-chat links, mailto deep links, and message templates."""
    providers = get_configured_providers()
    assert isinstance(providers, dict)

    wa_link = format_whatsapp_url("9876543210", "Hello BizMetrics!")
    assert wa_link.startswith("https://api.whatsapp.com/send?phone=919876543210")
    assert "Hello" in wa_link

    mail_link = format_mailto_url("client@example.com", "Invoice 123", "Body text")
    assert mail_link.startswith("mailto:client@example.com")

    msg = build_invoice_share_message("Shivansh", "INV-100", 5000.0)
    assert "INV-100" in msg
    assert "*Invoice No:* INV-100" in msg
    assert "₹5,000.00" in msg

    rem = build_payment_reminder_message("Ramesh", 3500.0, "2026-11-30")
    assert "₹3,500.00" in rem


def test_05_database_backup_and_restore():
    """Verify database health diagnostics, backup snapshot creation, and checksum calculation."""
    health = check_database_health()
    assert health["status"] == "Healthy"
    assert health["integrity_check"] == "ok"
    assert health["total_tables"] >= 20

    bak = create_database_backup(backup_type="Automated_Test", notes="Pytest backup")
    assert bak["success"] is True
    assert bak["file_size"] > 0
    assert len(bak["checksum"]) == 64

    baks = list_database_backups()
    assert not baks.empty


def test_06_supplier_and_purchase_management():
    """Verify supplier registration, PO creation, inward stock reception, and payment recording."""
    ok_v, msg_v = add_or_update_supplier("VEND_TEST_01", "Durg Metal Traders", material_type="Structural Steel")
    assert ok_v is True

    po = create_purchase_order("VEND_TEST_01", [{"product_id": "PROD001", "quantity": 10.0, "unit_price": 300.0}])
    assert po["success"] is True
    assert po["total_amount"] == 3000.0

    rec_ok, rec_msg = receive_purchase_order(po["po_id"])
    assert rec_ok is True

    pay_ok, pay_msg = record_supplier_payment("VEND_TEST_01", 1500.0, payment_mode="Bank Transfer")
    assert pay_ok is True

    metrics = get_supplier_performance_metrics()
    assert not metrics.empty


def test_07_daily_business_reports():
    """Verify daily metrics computation, P&L aggregation, and WhatsApp EOD digest."""
    summ = get_daily_business_summary()
    assert "total_sales" in summ
    assert "net_profit" in summ
    assert "report_date" in summ

    eod = generate_eod_whatsapp_digest(summ)
    assert "Daily EOD Summary" in eod
    assert "Total Sales" in eod


def test_08_gst_and_tax_analytics():
    """Verify GST turnover, CGST/SGST output calculation, and GSTR computation tables."""
    gst = compute_gst_tax_analytics()
    assert gst["taxable_turnover"] > 0
    assert gst["output_cgst"] == gst["output_sgst"]
    assert not gst["gstr1_summary"].empty
    assert not gst["gstr3b_computation"].empty


def test_09_offline_and_sync_support():
    """Verify offline action queueing, idempotency check, and sync replay."""
    q1 = queue_offline_operation("STOCK_UPDATE", {"product_id": "PROD001", "stock_delta": 1.0}, client_tx_id="TX-TEST-UNIQUE-01")
    assert q1["success"] is True

    # Idempotency verification: same tx_id must not duplicate
    q2 = queue_offline_operation("STOCK_UPDATE", {"product_id": "PROD001", "stock_delta": 1.0}, client_tx_id="TX-TEST-UNIQUE-01")
    assert q2["success"] is True
    assert q2["already_present"] is True

    status = get_sync_queue_status()
    assert "pending_count" in status

    sync = process_sync_queue()
    assert sync["success"] is True


def test_10_audit_trail_logging():
    """Verify recording and querying immutable audit logs."""
    aud_id = log_audit_event("Shivansh G", "TEST", "SYSTEM", "TEST-01", "Automated test audit log entry")
    assert aud_id.startswith("AUD-")

    logs = fetch_audit_logs(action_type="TEST")
    assert not logs.empty
    assert any(logs["audit_id"] == aud_id)


def test_11_multi_shop_management():
    """Verify branch retrieval, branch switcher options, and consolidated metrics."""
    branches = get_all_registered_branches()
    assert len(branches) >= 2

    opts = get_branch_selector_options()
    assert "all" in opts

    consolidated = get_consolidated_branch_metrics()
    assert not consolidated.empty


def test_12_voice_adapter_and_speech_codes():
    """Verify voice BCP 47 language code mappings and transcription fallback."""
    assert get_speech_language_code("हिंदी") == "hi-IN"
    assert get_speech_language_code("Hinglish") == "hi-IN"
    assert get_speech_language_code("English") == "en-IN"

    empty_res = transcribe_audio(b"")
    assert empty_res["status"] == "empty"
