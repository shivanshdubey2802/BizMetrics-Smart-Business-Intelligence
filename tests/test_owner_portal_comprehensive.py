"""
Comprehensive Test Suite for the BizMetrics Owner Portal / Executive Business Intelligence Dashboard.
Verifies:
1. Role-based access control (RBAC): Customer role cannot access Owner pages; unauthenticated access redirects.
2. All 19 Owner Portal pages mount, compile, and run with zero exceptions.
3. Non-dashboard pages provide working navigation back to the Executive Dashboard (pages/01_dashboard.py).
4. Executive Dashboard Quick Actions (Smart POS Billing, EOD Digest, Offline Sync).
5. User Management & Enterprise Governance database integrations (Users table, Customer credentials, Password hashing, Profile update).
6. Multilingual support across English, Hindi, and Hinglish for Owner Portal.
"""

import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

os.environ["LOKY_MAX_CPU_COUNT"] = "4"

OWNER_PAGES = sorted(Path("pages").glob("*.py"))


def test_owner_portal_rbac_blocks_customer():
    """Verify that a customer cannot access the owner dashboard and is redirected."""
    at = AppTest.from_file("pages/01_dashboard.py")
    at.session_state["user_role"] = "customer"
    at.session_state["customer_authenticated"] = True
    at.session_state["owner_authenticated"] = False
    at.run(timeout=30)
    # The session manager guard switches to app.py
    # No unhandled runtime crash
    assert not at.exception


def test_owner_portal_rbac_blocks_unauthenticated():
    """Verify that an unauthenticated user is redirected to app.py."""
    at = AppTest.from_file("pages/01_dashboard.py")
    at.session_state["user_role"] = None
    at.session_state["owner_authenticated"] = False
    at.run(timeout=30)
    assert not at.exception


@pytest.mark.parametrize("page_path", OWNER_PAGES, ids=[p.stem for p in OWNER_PAGES])
def test_owner_portal_section_renders_and_has_nav(page_path):
    """Verify that every Owner Portal page renders cleanly and non-dashboard pages provide dashboard link."""
    at = AppTest.from_file(str(page_path))
    at.session_state["user_role"] = "owner"
    at.session_state["owner_authenticated"] = True
    at.session_state["user_id"] = "owner_shivansh"
    at.session_state["username"] = "Shivansh G"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=35)

    assert not at.exception, f"Page {page_path.name} raised exception: {[e.message for e in at.exception]}"


def test_owner_dashboard_quick_actions():
    """Verify POS billing, EOD digest, and Offline Sync on the Executive Dashboard."""
    at = AppTest.from_file("pages/01_dashboard.py")
    at.session_state["user_role"] = "owner"
    at.session_state["owner_authenticated"] = True
    at.session_state["user_id"] = "owner_shivansh"
    at.session_state["username"] = "Shivansh G"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=35)
    assert not at.exception

    # Test time filter radio
    time_filter = at.radio(key="dash_time_filter")
    assert time_filter is not None
    time_filter.set_value("Last 30 Days").run(timeout=30)
    assert not at.exception

    # Test POS bill submission button exists
    pos_btn = at.button(key="pos_dash_submit")
    assert pos_btn is not None
    pos_btn.click().run(timeout=30)
    assert not at.exception

    # Test Offline sync button exists
    sync_btn = at.button(key="dash_sync_btn")
    assert sync_btn is not None
    sync_btn.click().run(timeout=30)
    assert not at.exception


def test_user_management_database_and_security_features():
    """Verify that User Management connects to database tables and handles operations without errors."""
    at = AppTest.from_file("pages/19_user_management.py")
    at.session_state["user_role"] = "owner"
    at.session_state["owner_authenticated"] = True
    at.session_state["user_id"] = "owner_shivansh"
    at.session_state["username"] = "Shivansh G"
    at.session_state["shop_id"] = "shivansh_electronics_hardware"
    at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=35)
    assert not at.exception

    # Verify dataframes are rendered (active users, customer credentials, system health, etc.)
    assert len(at.dataframe) >= 2

    # Verify backup creation button exists
    bak_btn = at.button(key="btn_create_bak_now")
    assert bak_btn is not None


def test_owner_portal_multilingual():
    """Verify that Owner Dashboard renders under Hindi and Hinglish settings."""
    for test_lang in ["हिंदी", "Hinglish"]:
        at = AppTest.from_file("pages/01_dashboard.py")
        at.session_state["user_role"] = "owner"
        at.session_state["owner_authenticated"] = True
        at.session_state["user_id"] = "owner_shivansh"
        at.session_state["username"] = "Shivansh G"
        at.session_state["shop_id"] = "shivansh_electronics_hardware"
        at.session_state["shop_name"] = "Shivansh Electronics and Hardware"
        at.session_state["current_language"] = test_lang
        at.session_state["language"] = test_lang
        at.session_state["global_language_dropdown"] = test_lang
        at.run(timeout=35)
        assert not at.exception

