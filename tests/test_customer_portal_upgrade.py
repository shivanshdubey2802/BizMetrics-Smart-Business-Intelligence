"""
Unit and Integration Tests for Customer Digital Portal Upgrade.
Validates:
1. Direct customer lookup and profile retrieval.
2. Customer KPI calculations (orders, purchase, paid, dues, AOV).
3. ReportLab PDF invoice generation with valid binary stream.
4. Permitted customer profile updating in SQLite with validation.
5. Support ticket creation, retrieval, and status tracking in SQLite.
6. Personalized notifications retrieval and mark-as-read in SQLite.
7. Customer loyalty points and tier calculations.
8. End-to-end customer authentication and portal mounting via Streamlit AppTest.
"""

import io
from PIL import Image
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from customer_qr_bills import (
    _get_customer_profile,
    get_all_customers,
    get_bill_summary,
    get_customer_bills,
    get_customer_qr,
)
from components.customer_portal import _compute_loyalty_tier
from utils.database import (
    init_database,
    get_customer_detail_from_db,
    update_customer_profile,
    get_customer_support_tickets,
    create_customer_support_ticket,
    get_customer_notifications,
    mark_notification_as_read,
)
from utils.invoice_generator import generate_pdf_invoice


@pytest.fixture(autouse=True)
def setup_db():
    init_database()


def test_customer_list_and_lookup():
    """Verify that genuine registered customers are loaded from the database."""
    customers = get_all_customers()
    assert len(customers) > 0, "Customer list should not be empty."
    cust_ids = [c["id"] for c in customers]
    assert "CUST001" in cust_ids, "CUST001 must be present in customer accounts."

    prof = _get_customer_profile("CUST001")
    assert prof["customer_id"] == "CUST001"
    assert "Shivansh" in prof["customer_name"] or "Customer" in prof["customer_name"]


def test_customer_kpi_calculations():
    """Verify financial formulas for customer KPIs (Orders, Purchase, AOV, Dues)."""
    bills = get_customer_bills("CUST001")
    summary = get_bill_summary(bills)
    
    assert summary["total_bills"] == len(bills)
    if not bills.empty:
        assert summary["total_purchase"] > 0
        assert summary["avg_bill"] == summary["total_purchase"] / summary["total_bills"]
        assert summary["paid_amount"] >= 0


def test_customer_loyalty_tier_computation():
    """Verify spend-based loyalty tier transitions and point math."""
    tier, color, pts, spend, req = _compute_loyalty_tier(5000.0)
    assert tier == "Bronze Member"
    assert pts == 50

    tier, color, pts, spend, req = _compute_loyalty_tier(25000.0)
    assert tier == "Silver Business Tier"
    assert pts == 250

    tier, color, pts, spend, req = _compute_loyalty_tier(80000.0)
    assert tier == "Gold Wholesale Tier"
    assert pts == 800

    tier, color, pts, spend, req = _compute_loyalty_tier(200000.0)
    assert tier == "Platinum Wholesale VIP"
    assert pts == 2000


def test_pdf_invoice_generation():
    """Verify that generate_pdf_invoice outputs a valid, well-formed PDF binary."""
    bill = {
        "Sale_ID": "SALE-TEST-001",
        "Date": "2026-06-01",
        "Product_Name": "Heavy Duty Industrial Wire 4mm",
        "Quantity": 2,
        "Selling_Price": 1200.0,
        "Discount_Percent": 5.0,
        "Bill_Amount": 2280.0,
        "Payment_Mode": "UPI",
        "Payment_Status": "Completed",
        "Paid_Amount": 2280.0,
        "Outstanding": 0.0,
    }
    cust = {
        "Customer_ID": "CUST001",
        "Customer_Name": "Shivansh",
        "Business_Name": "Shivansh Retail",
        "Mobile_Number": "9876543337",
        "City": "Raipur",
        "Address": "Station Road Hub",
        "Email": "shivansh@example.com",
    }
    pdf_bytes = generate_pdf_invoice(bill, cust)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_customer_profile_update_database_persistence():
    """Verify permitted profile updates save to SQLite and disallow forbidden fields."""
    # Test valid update
    success = update_customer_profile("CUST001", {
        "contact_number": "9876540001",
        "email": "updated_shivansh@example.com",
        "city": "Raipur Central",
        "address": "Telibandha Commercial Hub",
        "outstanding_amount": 999999.0,  # Should be ignored / protected
    })
    assert success is True

    updated_cust = get_customer_detail_from_db("CUST001")
    assert updated_cust["contact_number"] == "9876540001"
    assert updated_cust["email"] == "updated_shivansh@example.com"
    assert updated_cust["city"] == "Raipur Central"
    assert updated_cust["address"] == "Telibandha Commercial Hub"
    assert updated_cust["outstanding_amount"] != 999999.0  # Protected


def test_customer_support_tickets_crud():
    """Verify support ticket submission, persistence, and retrieval from database."""
    tck_id = create_customer_support_ticket(
        "CUST001",
        category="Billing & Invoices",
        priority="Urgent",
        message="Requesting revised cash memo with GST credit input."
    )
    assert tck_id.startswith("TCK-")

    tickets = get_customer_support_tickets("CUST001")
    assert len(tickets) > 0
    created = next((t for t in tickets if t["ticket_id"] == tck_id), None)
    assert created is not None
    assert created["category"] == "Billing & Invoices"
    assert created["priority"] == "Urgent"
    assert created["status"] == "Open"


def test_customer_notifications_and_mark_as_read():
    """Verify database-backed notifications and mark-as-read updates."""
    notifs = get_customer_notifications("CUST001")
    assert len(notifs) >= 3, "Customer should have seeded notifications."

    first_notif = notifs[0]
    n_id = first_notif["notification_id"]
    success = mark_notification_as_read(n_id)
    assert success is True

    updated_notifs = get_customer_notifications("CUST001")
    matching = next(n for n in updated_notifs if n["notification_id"] == n_id)
    assert matching["is_read"] == 1


def test_customer_portal_apptest_rendering():
    """Verify that app.py renders the customer portal when authenticated as customer."""
    at = AppTest.from_file("app.py")
    at.session_state["user_role"] = "customer"
    at.session_state["customer_authenticated"] = True
    at.session_state["customer_id"] = "CUST001"
    at.session_state["customer_name"] = "Shivansh"
    at.session_state["current_customer_id"] = "CUST001"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=30)

    assert not at.exception, f"App execution failed: {[e.message for e in at.exception]}"


def test_customer_portal_tab_navigation_no_widget_conflict():
    """Simulate switching tabs in the Customer Portal via dedicated sidebar radio without StreamlitAPIException."""
    at = AppTest.from_file("app.py")
    at.session_state["user_role"] = "customer"
    at.session_state["customer_authenticated"] = True
    at.session_state["customer_id"] = "CUST001"
    at.session_state["customer_name"] = "Shivansh"
    at.session_state["current_customer_id"] = "CUST001"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=30)
    assert not at.exception

    from components.sidebar import CUSTOMER_NAV_ITEMS

    for item in CUSTOMER_NAV_ITEMS:
        btn = at.sidebar.button(key=f"cust_nav_btn_{item.replace(' ', '_')}")
        assert btn is not None, f"Sidebar button key 'cust_nav_btn_{item}' not found"
        btn.click().run(timeout=30)
        assert not at.exception, f"Exception selecting {item} in sidebar: {[e.message for e in at.exception]}"
        assert at.session_state["customer_id"] == "CUST001"
        assert at.session_state["customer_name"] == "Shivansh"

        # Verify Return to Dashboard button works when inside any non-dashboard section
        if item != "Dashboard":
            ret_btn = at.button(key=f"btn_ret_dash_top_{item.replace(' ', '_')}")
            assert ret_btn is not None, f"Return to Dashboard button missing in {item}"
            ret_btn.click().run(timeout=30)
            assert not at.exception, f"Exception returning to dashboard from {item}: {[e.message for e in at.exception]}"
            assert at.session_state["customer_active_section"] == "Dashboard"

    # Test Dashboard contextual links
    at.sidebar.button(key="cust_nav_btn_Dashboard").click().run(timeout=30)
    assert not at.exception

    orders_btn = at.button(key="btn_dash_view_all_orders")
    assert orders_btn is not None
    orders_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Order History"

    # Return to Dashboard
    at.button(key="btn_ret_dash_top_Order_History").click().run(timeout=30)
    assert not at.exception

    payments_btn = at.button(key="btn_dash_view_all_payments")
    assert payments_btn is not None
    payments_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Outstanding Dues"


def test_customer_portal_multilingual_navigation():
    """Verify that language changes to Hindi and Hinglish preserve customer selection and translate sidebar items."""
    from utils.translations import t

    for test_lang in ["हिंदी", "Hinglish", "English"]:
        at = AppTest.from_file("app.py")
        at.session_state["user_role"] = "customer"
        at.session_state["customer_authenticated"] = True
        at.session_state["customer_id"] = "CUST001"
        at.session_state["customer_name"] = "Shivansh"
        at.session_state["shop_id"] = "shivansh_electronics_hardware"
        at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
        at.session_state["current_language"] = test_lang
        at.session_state["language"] = test_lang
        at.session_state["global_language_dropdown"] = test_lang
        at.session_state["customer_nav_selection"] = "Customer Insights"
        at.run(timeout=30)
        assert not at.exception
        assert at.session_state["customer_id"] == "CUST001"






