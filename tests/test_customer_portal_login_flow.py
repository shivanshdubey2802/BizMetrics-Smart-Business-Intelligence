"""
Test suite verifying:
1. Authenticated customer portal renders ONLY the dashboard, never the login form.
2. Unauthenticated route renders ONLY the login screen, never account data.
3. Sidebar navigation items have plain text labels with no icons or emojis.
"""
from streamlit.testing.v1 import AppTest
import pytest
from components.sidebar import CUSTOMER_NAV_ITEMS


def test_authenticated_customer_renders_no_login_form():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["user_role"] = "customer"
    at.session_state["customer_authenticated"] = True
    at.session_state["customer_id"] = "CUST001"
    at.session_state["customer_name"] = "Shivansh"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run()
    assert not at.exception, f"AppTest exception: {[e.message for e in at.exception]}"

    # Verify no login widgets exist in the tree
    radio_keys = [r.key for r in at.radio]
    assert "landing_login_type" not in radio_keys, "Login type radio should NOT exist when authenticated"

    input_keys = [i.key for i in at.text_input]
    assert "landing_customer_name" not in input_keys, "Login customer name input should NOT exist when authenticated"
    assert "landing_customer_id" not in input_keys, "Login customer ID input should NOT exist when authenticated"

    button_keys = [b.key for b in at.button]
    assert "btn_landing_customer_login" not in button_keys, "Landing login button should NOT exist when authenticated"
    assert "btn_route2_customer_login" not in button_keys, "Route2 login button should NOT exist when authenticated"

    # Verify customer sidebar is present and has the radio navigation
    radio = at.sidebar.radio(key="customer_nav_selection")
    assert radio is not None, "Customer navigation radio must exist in sidebar"
    assert radio.value == "Dashboard"

    # Verify all 10 items are plain text (no emojis)
    emojis = ["🏠", "👤", "📦", "🧾", "⚠️", "📱", "🎁", "📊", "🔔", "💬"]
    for item in CUSTOMER_NAV_ITEMS:
        for emoji in emojis:
            assert emoji not in item, f"Emoji {emoji} found in nav item {item}"


def test_unauthenticated_renders_only_login_screen():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["user_role"] = None
    at.session_state["customer_authenticated"] = False
    at.session_state["owner_authenticated"] = False
    at.run()
    assert not at.exception, f"AppTest exception: {[e.message for e in at.exception]}"

    # Verify login form is present
    login_type = at.radio(key="landing_login_type")
    assert login_type is not None, "Login As radio must be present when unauthenticated"

    # Verify customer dashboard components are NOT present
    sidebar_radios = [r.key for r in at.sidebar.radio]
    assert "customer_nav_selection" not in sidebar_radios, "Customer nav radio must NOT exist when unauthenticated"
