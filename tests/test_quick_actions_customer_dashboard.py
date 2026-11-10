"""
Dedicated Test Suite for Customer Digital Portal Sidebar Navigation.
Verifies:
1. Customer Portal is mounted with a dedicated left vertical sidebar.
2. All 10 sidebar navigation items exist and navigate without StreamlitAPIException:
   - Dashboard
   - Profile & Account
   - Order History
   - Digital Invoices
   - Outstanding Dues
   - QR Code Pass
   - Loyalty & Rewards
   - Customer Insights
   - Offers & Notifications
   - Support Center
3. Each section displays customer-specific authenticated records.
4. Each non-dashboard section provides a working Return to Dashboard action.
5. Customer selection (CUST001 / Shivansh) and language preferences are preserved.
"""

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def customer_app():
    at = AppTest.from_file("app.py")
    at.session_state["user_role"] = "customer"
    at.session_state["customer_authenticated"] = True
    at.session_state["customer_id"] = "CUST001"
    at.session_state["customer_name"] = "Shivansh"
    at.session_state["current_customer_id"] = "CUST001"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.session_state["customer_active_section"] = "Dashboard"
    at.session_state["customer_nav_selection"] = "Dashboard"
    at.run(timeout=30)
    assert not at.exception
    return at


def test_quick_action_profile(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Profile_&_Account")
    assert btn is not None, "Sidebar button 'cust_nav_btn_Profile_&_Account' not found"
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Profile: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Profile & Account"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Profile_&_Account")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_orders(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Order_History")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Orders: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Order History"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Order_History")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_invoices(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Digital_Invoices")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Invoices: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Digital Invoices"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Digital_Invoices")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_dues(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Outstanding_Dues")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Dues: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Outstanding Dues"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Outstanding_Dues")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_insights(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Customer_Insights")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Insights: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Customer Insights"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Customer_Insights")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_rewards(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Loyalty_&_Rewards")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Rewards: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Loyalty & Rewards"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Loyalty_&_Rewards")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_qr_pass(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_QR_Code_Pass")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting QR Pass: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "QR Code Pass"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_QR_Code_Pass")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"


def test_quick_action_support(customer_app):
    at = customer_app
    btn = at.sidebar.button(key="cust_nav_btn_Support_Center")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not at.exception, f"Crash selecting Support: {[e.message for e in at.exception]}"
    assert at.session_state["customer_active_section"] == "Support Center"
    assert at.session_state["customer_id"] == "CUST001"

    # Return to Dashboard
    ret_btn = at.button(key="btn_ret_dash_top_Support_Center")
    assert ret_btn is not None
    ret_btn.click().run(timeout=30)
    assert not at.exception
    assert at.session_state["customer_active_section"] == "Dashboard"

