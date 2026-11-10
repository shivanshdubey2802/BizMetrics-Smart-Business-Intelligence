"""
BizMetrics - Customer Digital Portal (Complete Dashboard Upgrade)
Provides a modern, professional, self-service customer portal connected directly
to the BizMetrics relational database (bizmetrics.db / SQLite).
Includes:
  1. Default Customer Dashboard (Welcome greeting, Profile summary, 6 KPI cards, Quick Actions)
  2. Authentic Dashboard Visualizations (Monthly trend, Paid vs Outstanding donut, Category breakdown, Recent Orders)
  3. 10 Dedicated Navigation Sections:
     - 1. Dashboard (Default Landing)
     - 2. My Profile (Profile card + interactive editing in SQLite)
     - 3. Order History (Search, status/mode/date filters, sorting, CSV download, 4-stage fulfillment timeline)
     - 4. Digital Invoices (Itemized tax invoice preview, ReportLab PDF download, text memo, WhatsApp share)
     - 5. Payments & Outstanding (Dues status hero, Cash/UPI/Credit breakdowns, aging analysis, store settlement guidelines)
     - 6. EMI Details (Khata credit facilities, 30-day interest-free settlement, flexible EMI calculator)
     - 7. QR Code (High-res QR pass, PNG download, Digital VIP membership card, usage guide)
     - 8. Loyalty & Rewards (Spend-based points, Bronze/Silver/Gold/Platinum tiers, progress bar, vouchers)
     - 9. Offers & Notifications (Database-backed notifications with mark-as-read action)
     - 10. Support Center (Helpdesk ticket submission to SQLite, ticket history, verified store contacts)
"""

import html
import io
import re
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from customer_qr_bills import (
    _get_customer_profile,
    _normalize_mobile,
    _whatsapp_url,
    get_all_customers,
    get_bill_summary,
    get_customer_bills,
    get_customer_qr,
)
from utils.formatting import format_currency
from utils.invoice_generator import generate_pdf_invoice
from utils.theme import get_colors, render_html
from utils.database import (
    get_customer_detail_from_db,
    update_customer_profile,
    get_customer_support_tickets,
    create_customer_support_ticket,
    get_customer_notifications,
    mark_notification_as_read,
    query_records,
    DEFAULT_SHOP_ID,
)
try:
    from utils.translations import t, get_current_language, set_current_language, translate_df
except Exception:
    try:
        from utils import t, get_current_language, set_current_language, translate_df
    except Exception:
        def t(key, lang=None): return str(key) if key is not None else ""
        def get_current_language(): return "English"
        def set_current_language(lang): pass
        def translate_df(df, lang=None): return df


def _compute_loyalty_tier(total_spend: float) -> tuple[str, str, int, float, float]:
    """
    Compute customer loyalty tier, color, earned points, current spend, and next tier requirement.
    Points: 1 point per Rs. 100 of genuine purchase.
    """
    pts = int(total_spend // 100)
    if total_spend >= 150000:
        return "Platinum Wholesale VIP", "#7C3AED", pts, total_spend, 150000.0
    elif total_spend >= 50000:
        return "Gold Wholesale Tier", "#D97706", pts, total_spend, 150000.0
    elif total_spend >= 10000:
        return "Silver Business Tier", "#2563EB", pts, total_spend, 50000.0
    else:
        return "Bronze Member", "#64748B", pts, total_spend, 10000.0


def get_customer_dashboard_data(shop_id: str, customer_id: str):
    """Returns aggregated customer profile and transaction summary for session management."""
    profile = _get_customer_profile(customer_id)
    bills = get_customer_bills(customer_id)
    summary = get_bill_summary(bills)
    return {
        "profile": profile,
        "orders": summary.get("total_bills", 0),
        "spent": summary.get("total_purchase", 0.0),
        "average_order_value": summary.get("avg_bill", 0.0),
        "last_purchase": summary.get("last_purchase", "N/A"),
        "outstanding": summary.get("outstanding", 0.0),
        "paid": summary.get("paid_amount", 0.0),
        "bills": bills,
    }


@st.cache_data(ttl=600, show_spinner=False)
def _get_product_category_map() -> dict:
    try:
        from utils.database import query_records
        prod_rows = query_records("SELECT product_id, category FROM products")
        if prod_rows:
            return {str(r["product_id"]).strip(): r["category"] for r in prod_rows if r.get("category")}
    except Exception:
        pass
    return {}


def render_customer_portal():
    """
    Renders the complete, fully-featured BizMetrics Customer Dashboard & Self-Service Portal.
    """
    colors = get_colors()
    curr_lang = get_current_language()

    def tr(en: str, hi: str = "", hinglish: str = "") -> str:
        if curr_lang == "हिंदी":
            return hi if hi else t(en, "हिंदी")
        elif curr_lang == "Hinglish":
            return hinglish if hinglish else t(en, "Hinglish")
        return t(en, "English")

    # Ensure database migrations and data loading are initialized before querying
    try:
        from utils.database import init_database
        init_database()
    except Exception:
        pass
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

    # Render Customer Sidebar Navigation
    from components.sidebar import render_customer_sidebar, CUSTOMER_NAV_ITEMS
    render_customer_sidebar()

    # --------------------------------------------------------------------------
    # 1. TOP BRANDING & VERIFICATION HEADER CARD
    # --------------------------------------------------------------------------
    portal_header = (
        '<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.3rem 1.6rem; margin-bottom: 1.1rem; box-shadow: 0 2px 8px rgba(30,41,59,0.04); display: flex; justify-content: space-between; align-items: center; gap: 16px;">'
        '<div>'
        f'<div style="font-size: 0.76rem; font-weight: 700; color: #0D9488; letter-spacing: 0.06em; text-transform: uppercase;">SHIVANSH ELECTRONICS & HARDWARE • {tr("CUSTOMER DASHBOARD", "ग्राहक डैशबोर्ड")}</div>'
        f'<h2 style="margin: 3px 0 4px 0; color: #1E293B !important; font-size: 1.7rem; font-family: \'Playfair Display\', serif; font-weight: 700;">{tr("Customer Digital Portal", "ग्राहक डिजिटल पोर्टल")}</h2>'
        f'<p style="margin: 0; font-size: 0.88rem; color: #64748B;">{tr("Comprehensive self-service dashboard: verified orders, digital GST invoices, payment records, and express QR check-in.", "आपकी खरीदारी, डिजिटल जीएसटी बिल, भुगतान स्थिति और स्टोर चेक-इन क्यूआर कोड का संपूर्ण डैशबोर्ड।")}</p>'
        '</div>'
        '<div style="text-align: right; background: #FAF5EE; border: 1px solid #E2DBD0; border-radius: 10px; padding: 0.6rem 1rem; min-width: 150px;">'
        '<div style="font-size: 1.5rem; line-height: 1;">🏪📱</div>'
        f'<div style="font-size: 0.72rem; font-weight: 700; color: #1E293B; margin-top: 3px;">{tr("Verified Client", "सत्यापित ग्राहक")}</div>'
        f'<div style="font-size: 0.68rem; color: #059669; font-weight: 600;">● {tr("Connected Live", "लाइव कनेक्टेड")}</div>'
        '</div>'
        '</div>'
    )
    render_html(portal_header)

    # All available customers for selection
    all_customers = get_all_customers()
    all_cust_ids = [c["id"] for c in all_customers]

    # Customer Security & Identification
    # If authenticated as a customer, strictly lock to their own authenticated account (Customer A cannot access Customer B)
    is_cust_role = (st.session_state.get("user_role") == "customer") and not st.session_state.get("owner_authenticated", False)
    auth_cust_id = st.session_state.get("customer_id")

    if is_cust_role:
        current_id = auth_cust_id or "CUST001"
        st.session_state["current_customer_id"] = current_id
    elif "current_customer_id" not in st.session_state:
        st.session_state["current_customer_id"] = auth_cust_id if (auth_cust_id in all_cust_ids) else (all_cust_ids[0] if all_cust_ids else "CUST001")
        current_id = st.session_state["current_customer_id"]
    elif st.session_state["current_customer_id"] not in all_cust_ids and all_cust_ids:
        st.session_state["current_customer_id"] = all_cust_ids[0]
        current_id = st.session_state["current_customer_id"]
    else:
        current_id = st.session_state["current_customer_id"]

    # Customer Account Switcher / Direct Lookup Bar
    if is_cust_role:
        # Show locked account badge for customer security
        st.markdown(
            f'<div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.5rem 1rem; margin-bottom: 0.8rem; font-size: 0.85rem; color: #475569; display: flex; justify-content: space-between; align-items: center;">'
            f'<div>🔒 <strong>{tr("Secure Session Active", "सुरक्षित सत्र सक्रिय")}:</strong> {tr("Authenticated as", "प्रमाणित खाता")} <strong style="color: #0D9488;">{current_id}</strong></div>'
            f'<span style="background: #DCFCE7; color: #166534; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 6px;">✓ {tr("Encrypted Store Connection", "सुरक्षित कनेक्शन")}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        # Owner / Staff testing mode: allow testing different customer accounts
        with st.container():
            cust_switch_c1, cust_switch_c2 = st.columns([2.5, 1.5])
            with cust_switch_c1:
                display_options = [c["display"] for c in all_customers]
                current_index = 0
                for idx, c in enumerate(all_customers):
                    if c["id"] == current_id:
                        current_index = idx
                        break

                selected_display = st.selectbox(
                    f"👤 {tr('Identified Customer Account', 'पहचाना गया ग्राहक खाता')} ({len(all_customers)} {tr('registered accounts', 'पंजीकृत खाते')})",
                    display_options,
                    index=current_index,
                    key="cust_portal_selector"
                )
                for c in all_customers:
                    if c["display"] == selected_display:
                        if c["id"] != current_id:
                            st.session_state["current_customer_id"] = c["id"]
                            st.rerun()

            with cust_switch_c2:
                search_direct = st.text_input(
                    f"🔍 {tr('Direct Customer ID Lookup', 'ग्राहक आईडी खोजें')}",
                    value="",
                    placeholder="e.g. CUST001, CUST015...",
                    key="cust_portal_direct_search"
                ).strip().upper()
                if search_direct:
                    if search_direct in all_cust_ids and search_direct != current_id:
                        st.session_state["current_customer_id"] = search_direct
                        st.rerun()
                    elif search_direct not in all_cust_ids:
                        st.caption(f"⚠️ {tr(f'Customer ID {search_direct} not found in registered accounts.', f'ग्राहक आईडी {search_direct} पंजीकृत खातों में नहीं मिली।')}")

    # Load customer profile from database / fallback
    profile = _get_customer_profile(current_id)
    cust_name = profile.get("customer_name") or profile.get("Customer_Name", "Valued Customer")
    biz_name = profile.get("business_name") or profile.get("Business_Name", "")
    mob_num = profile.get("mobile_number") or profile.get("Mobile_Number", "")
    email_val = profile.get("email") or profile.get("Email", "Not on file")
    addr_val = profile.get("address") or profile.get("Address", "Station Road Commercial Area")
    city_val = profile.get("city") or profile.get("City", "Raipur")
    cust_type = profile.get("customer_type") or profile.get("Customer_Type", "Retail Buyer")
    reg_date = profile.get("registration_date") or profile.get("Registration_Date", "2024-01-15")
    rating_val = float(profile.get("customer_rating") or profile.get("Customer_Rating", 4.5))

    # Load authentic customer bills from database / sales transactions
    bills = get_customer_bills(current_id)
    if bills.empty:
        try:
            from utils.database import init_database
            init_database()
            bills = get_customer_bills(current_id)
        except Exception:
            pass

    # Enrich bills with Product Categories from database if available (fast cached lookup)
    if not bills.empty and "Category" not in bills.columns:
        cat_map = _get_product_category_map()
        if cat_map:
            bills["Category"] = bills["Product_ID"].astype(str).str.strip().map(cat_map).fillna("General Hardware")
        else:
            bills["Category"] = "General Hardware"

    summary = get_bill_summary(bills)
    tot_orders = summary["total_bills"]
    tot_purchase = summary["total_purchase"]
    avg_order = summary["avg_bill"]
    ledger_due = float(profile.get("outstanding_amount") or profile.get("Outstanding_Amount", 0.0))
    outstanding_amt = max(summary["outstanding"], ledger_due)
    paid_amt = max(0.0, tot_purchase - outstanding_amt) if tot_purchase > 0 else summary["paid_amount"]
    last_purchase = summary["last_purchase"]

    # Compute Loyalty Points and Tier
    tier_name, tier_color, loyalty_pts, cur_spend, next_req = _compute_loyalty_tier(tot_purchase)

    # Fetch notifications from database safely
    try:
        cust_notifs = get_customer_notifications(current_id)
    except Exception:
        cust_notifs = []
    unread_notifs = [n for n in (cust_notifs or []) if not n.get("is_read", 0)]

    # --------------------------------------------------------------------------
    # 2. ACTIVE NAVIGATION & SECTION MANAGEMENT
    # --------------------------------------------------------------------------
    NAV_ALIASES = {
        "Dashboard": "Dashboard",
        "Profile & Account": "Profile & Account",
        "Profile": "Profile & Account",
        "My Profile": "Profile & Account",
        "Customer Profile & Account": "Profile & Account",
        "Order History": "Order History",
        "History": "Order History",
        "Purchase History": "Order History",
        "Orders": "Order History",
        "Digital Invoices": "Digital Invoices",
        "Invoices": "Digital Invoices",
        "Outstanding Dues": "Outstanding Dues",
        "Outstanding": "Outstanding Dues",
        "Payments & Outstanding": "Outstanding Dues",
        "Dues": "Outstanding Dues",
        "EMI Details": "EMI Details",
        "EMI": "EMI Details",
        "Khata EMI": "EMI Details",
        "Overview": "Dashboard",
        "My Orders": "Order History",
        "Payments & Invoices": "Digital Invoices",
        "Digital QR / Check-in": "QR Code Pass",
        "QR Code Pass": "QR Code Pass",
        "QR Code": "QR Code Pass",
        "Customer QR Code": "QR Code Pass",
        "QR Pass": "QR Code Pass",
        "Loyalty & Rewards": "Loyalty & Rewards",
        "Loyalty": "Loyalty & Rewards",
        "Rewards": "Loyalty & Rewards",
        "Customer Insights": "Customer Insights",
        "Insights": "Customer Insights",
        "Offers & Notifications": "Offers & Notifications",
        "Offers": "Offers & Notifications",
        "Notifications": "Offers & Notifications",
        "Support Center": "Support Center",
        "Support": "Support Center",
        "Customer Support": "Support Center",
    }

    st.session_state.setdefault("customer_active_section", "Dashboard")
    raw_section = st.session_state.get("customer_active_section", "Dashboard")
    active_section = NAV_ALIASES.get(raw_section, raw_section)
    if active_section not in CUSTOMER_NAV_ITEMS:
        active_section = "Dashboard"
    st.session_state["customer_active_section"] = active_section

    def set_customer_section(section: str):
        target = NAV_ALIASES.get(section, section)
        st.session_state["customer_active_section"] = target

    # If currently inside a specific section, provide clear way to return to Dashboard
    if active_section != "Dashboard":
        b_c1, b_c2 = st.columns([1.6, 4.4])
        with b_c1:
            st.button(
                f"🏠 ← {tr('Return to Dashboard', 'डैशबोर्ड पर वापस जाएं', 'Dashboard par Wapas')}",
                key=f"btn_ret_dash_top_{active_section.replace(' ', '_')}",
                type="secondary",
                use_container_width=True,
                on_click=set_customer_section,
                args=("Dashboard",)
            )
        with b_c2:
            st.markdown(
                f"<div style='font-size: 0.92rem; font-weight: 600; color: #64748B; margin-top: 6px;'>"
                f"{biz_name} &nbsp;›&nbsp; <strong style='color: #0D9488;'>{t(active_section, curr_lang)}</strong> &nbsp;•&nbsp; "
                f"<span style='color: #475569;'>{html.escape(cust_name)} ({current_id})</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        render_html("<div style='height: 0.65rem;'></div>")

    # ==========================================================================
    # SECTION 1: DEFAULT CUSTOMER DASHBOARD
    # ==========================================================================
    if active_section == "Dashboard":
        # Time-based personalized greeting
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting_text = tr("Good Morning", "शुभ प्रभात", "Good Morning")
        elif 12 <= hour < 17:
            greeting_text = tr("Good Afternoon", "शुभ दोपहर", "Good Afternoon")
        else:
            greeting_text = tr("Good Evening", "शुभ संध्या", "Good Evening")

        # 1. ACTIVE CUSTOMER WELCOME STRIP & MEMBERSHIP BADGE
        notif_badge_html = (
            f'<span style="background: #EF4444; color: #FFFFFF; font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 10px; margin-left: 6px;">{len(unread_notifs)} {tr("New", "नए")}</span>'
            if unread_notifs else
            f'<span style="background: #DCFCE7; color: #166534; font-size: 0.7rem; font-weight: 600; padding: 2px 7px; border-radius: 10px; margin-left: 6px;">{tr("All Read", "सभी पढ़े गए")}</span>'
        )

        banner_html = (
            f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid {tier_color}; border-radius: 12px; padding: 1.1rem 1.4rem; margin: 0.5rem 0 1.15rem 0; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
            f'<div style="display: flex; align-items: center; gap: 14px;">'
            f'<div style="width: 52px; height: 52px; border-radius: 50%; background: #EFF6FF; color: {tier_color}; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 800; border: 2px solid {tier_color}33;">{cust_name[0] if cust_name else "C"}</div>'
            f'<div>'
            f'<div style="display: flex; align-items: center; gap: 8px;">'
            f'<span style="font-size: 1.22rem; font-weight: 700; color: #1E293B;">{greeting_text}, {html.escape(cust_name)}!</span>'
            f'<span style="font-size: 0.85rem; font-weight: 500; color: #64748B;">({html.escape(biz_name)})</span>'
            f'<span style="background: {tier_color}18; color: {tier_color}; font-size: 0.74rem; font-weight: 700; padding: 3px 9px; border-radius: 8px; border: 1px solid {tier_color}44;">★ {tier_name}</span>'
            f'</div>'
            f'<div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">'
            f'<strong>ID:</strong> <code style="color: #0F766E; font-weight: 700;">{current_id}</code> &nbsp;•&nbsp; <strong>{tr("Mobile", "मोबाइल")}:</strong> {_normalize_mobile(mob_num)} &nbsp;•&nbsp; <strong>{tr("City", "शहर")}:</strong> {html.escape(city_val)} &nbsp;•&nbsp; <strong>{tr("Type", "प्रकार")}:</strong> {html.escape(cust_type)} &nbsp;•&nbsp; <strong>Rating:</strong> ★ {rating_val:.1f}'
            f'</div>'
            f'</div>'
            f'</div>'
            f'<div style="text-align: right; display: flex; align-items: center; gap: 16px;">'
            f'<div>'
            f'<div style="font-size: 0.7rem; font-weight: 700; color: #64748B; text-transform: uppercase;">{tr("NOTIFICATIONS", "सूचनाएं")}</div>'
            f'<div style="font-size: 0.88rem; font-weight: 600; color: #1E293B; margin-top: 2px;">🔔 {len(cust_notifs)} {notif_badge_html}</div>'
            f'</div>'
            f'<div style="border-left: 1px solid #E2E8F0; padding-left: 14px;">'
            f'<div style="font-size: 0.7rem; font-weight: 700; color: #64748B; text-transform: uppercase;">{tr("CURRENT DUES", "बकाया राशि")}</div>'
            f'<div style="font-size: 1.45rem; font-weight: 800; color: {"#059669" if outstanding_amt == 0 else "#EA580C"}; line-height: 1.1;">{format_currency(outstanding_amt)}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        render_html(banner_html)

        # 2. CUSTOMER KPI CARDS (6 RESPONSIVE BUSINESS METRICS)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid #6366F1; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">📦 {tr("TOTAL ORDERS", "कुल ऑर्डर", "TOTAL ORDERS")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:#1E293B; margin-top:2px;">{tot_orders}</div>'
                f'<div style="font-size:0.68rem; color:#6366F1; margin-top:2px;">{tr("Verified sales", "सत्यापित लेन-देन", "Verified Orders")}</div>'
                f'</div>'
            )
        with k2:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid #2563EB; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">💰 {tr("TOTAL PURCHASE", "कुल खरीदारी", "TOTAL KHARIDARI")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:#2563EB; margin-top:2px;">{format_currency(tot_purchase)}</div>'
                f'<div style="font-size:0.68rem; color:#64748B; margin-top:2px;">{tr("Gross business value", "सकल व्यापार", "Total Kharidari")}</div>'
                f'</div>'
            )
        with k3:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid #059669; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">✓ {tr("TOTAL PAID", "कुल भुगतान", "TOTAL PAYMENT DIYA")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:#059669; margin-top:2px;">{format_currency(paid_amt)}</div>'
                f'<div style="font-size:0.68rem; color:#059669; margin-top:2px;">✓ {tr("Settled funds", "निपटाया गया", "Chukta Payment")}</div>'
                f'</div>'
            )
        with k4:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid {"#059669" if outstanding_amt == 0 else "#EA580C"}; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">⚠️ {tr("OUTSTANDING DUES", "बकाया राशि", "BAAKI PAYMENT")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:{"#059669" if outstanding_amt == 0 else "#EA580C"}; margin-top:2px;">{format_currency(outstanding_amt)}</div>'
                f'<div style="font-size:0.68rem; color:{"#059669" if outstanding_amt == 0 else "#EA580C"}; margin-top:2px;">{tr("✓ No pending dues", "✓ कोई बकाया नहीं", "✓ Koi Baaki Nahi") if outstanding_amt == 0 else tr("Pending khata", "लंबित खाता", "Pending Baaki Khata")}</div>'
                f'</div>'
            )
        with k5:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid #0D9488; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">📊 {tr("AVG ORDER (AOV)", "औसत ऑर्डर", "AVERAGE ORDER")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:#1E293B; margin-top:2px;">{format_currency(avg_order)}</div>'
                f'<div style="font-size:0.68rem; color:#0D9488; margin-top:2px;">{tr("Per invoice mean", "प्रति बिल औसत", "Prati Bill Average")}</div>'
                f'</div>'
            )
        with k6:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top: 3px solid {tier_color}; border-radius:10px; padding:0.9rem; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.02);">'
                f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">🎁 {tr("LOYALTY POINTS", "रिवॉर्ड पॉइंट्स", "REWARD POINTS")}</div>'
                f'<div style="font-size:1.55rem; font-weight:800; color:{tier_color}; margin-top:2px;">{loyalty_pts:,} pts</div>'
                f'<div style="font-size:0.68rem; color:{tier_color}; margin-top:2px;">★ {tier_name.split()[0]}</div>'
                f'</div>'
            )

        render_html("<div style='height: 0.95rem;'></div>")

        # 2. Visualizations (Row 1): Monthly Purchase Trend & Paid vs Outstanding
        st.markdown(f"#### 📊 {tr('Account Financial Visualizations', 'खाता वित्तीय विश्लेषण')}")
        v_col1, v_col2 = st.columns([1.8, 1.2])

        with v_col1:
            if bills.empty:
                st.info(tr("No purchase history available yet.", "अभी कोई खरीदारी इतिहास उपलब्ध नहीं है।"))
            else:
                b_copy = bills.copy()
                b_copy["Month_Year"] = b_copy["Date"].dt.to_period("M").dt.to_timestamp()
                monthly_spend = b_copy.groupby("Month_Year")["Bill_Amount"].sum().reset_index()

                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=monthly_spend["Month_Year"].dt.strftime("%b %Y"),
                    y=monthly_spend["Bill_Amount"],
                    mode="lines+markers",
                    fill="tozeroy",
                    fillcolor="rgba(13, 148, 136, 0.12)",
                    line=dict(color="#0D9488", width=3, shape="spline"),
                    marker=dict(size=7, color="#0F766E", symbol="circle"),
                    hovertemplate="%{x}<br><b>Spend:</b> ₹%{y:,.2f}<extra></extra>",
                    name=tr("Monthly Spend", "मासिक खर्च")
                ))
                fig_trend.update_layout(
                    title=dict(text=f"📈 {tr('Monthly Purchase Trend', 'मासिक खरीदारी रुझान')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=15, r=15, t=40, b=15),
                    height=290,
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    xaxis=dict(showgrid=False, linecolor="#E2E8F0"),
                    yaxis=dict(gridcolor="#F1F5F9", linecolor="#E2E8F0"),
                )
                st.plotly_chart(fig_trend, use_container_width=True)

        with v_col2:
            # Paid vs Outstanding Donut Chart
            fig_donut = go.Figure(go.Pie(
                labels=[tr("Paid Amount", "भुगतान किया गया"), tr("Outstanding Dues", "बकाया राशि")],
                values=[max(0.0, paid_amt), max(0.0, outstanding_amt)],
                hole=0.60,
                marker=dict(colors=["#0D9488", "#EA580C" if outstanding_amt > 0 else "#A7F3D0"]),
                textinfo="percent+label",
                textposition="outside",
                hoverinfo="label+value+percent",
                hovertemplate="<b>%{label}</b><br>Amount: ₹%{value:,.2f}<br>%{percent}<extra></extra>"
            ))
            settle_pct = (paid_amt / tot_purchase * 100) if tot_purchase > 0 else 100.0
            fig_donut.update_layout(
                title=dict(text=f"🍩 {tr('Paid vs Outstanding Amount', 'भुगतान बनाम बकाया राशि')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                font=dict(family="Inter, sans-serif", size=11),
                margin=dict(l=10, r=10, t=40, b=10),
                height=290,
                showlegend=False,
                annotations=[dict(text=f"<b>{settle_pct:.0f}%</b><br><span style='font-size:10px; color:#64748B;'>Settled</span>", x=0.5, y=0.5, font_size=16, showarrow=False)]
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        # 3. Visualizations (Row 2): Purchase Category Breakdown (if data supports it)
        if not bills.empty and "Category" in bills.columns and bills["Category"].nunique() > 1:
            render_html("<div style='height: 0.5rem;'></div>")
            cat_summary = bills.groupby("Category")["Bill_Amount"].sum().reset_index().sort_values(by="Bill_Amount", ascending=True)
            
            c_bar_col1, c_bar_col2 = st.columns([1.5, 1.5])
            with c_bar_col1:
                fig_cat = go.Figure(go.Bar(
                    x=cat_summary["Bill_Amount"],
                    y=cat_summary["Category"],
                    orientation="h",
                    marker=dict(color="#2563EB", opacity=0.85),
                    text=cat_summary["Bill_Amount"].apply(lambda v: format_currency(v)),
                    textposition="auto"
                ))
                fig_cat.update_layout(
                    title=dict(text=f"🏷️ {tr('Purchase Category Breakdown', 'खरीदारी श्रेणी विवरण')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=15, r=15, t=40, b=15),
                    height=260,
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    xaxis=dict(showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_cat, use_container_width=True)

            with c_bar_col2:
                # Top Purchased SKUs
                top_skus = bills.groupby("Product_Name")["Bill_Amount"].sum().reset_index().sort_values(by="Bill_Amount", ascending=True).tail(5)
                fig_top_skus = go.Figure(go.Bar(
                    x=top_skus["Bill_Amount"],
                    y=top_skus["Product_Name"],
                    orientation="h",
                    marker=dict(color="#0D9488", opacity=0.85),
                    text=top_skus["Bill_Amount"].apply(lambda v: format_currency(v)),
                    textposition="auto"
                ))
                fig_top_skus.update_layout(
                    title=dict(text=f"📦 {tr('Top Purchased Products', 'सर्वाधिक खरीदे गए उत्पाद')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=15, r=15, t=40, b=15),
                    height=260,
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    xaxis=dict(showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_top_skus, use_container_width=True)

        render_html("<div style='height: 0.8rem;'></div>")

        # 4. Recent Orders Table & Recent Payment Activity
        st.markdown(f"#### 📋 {tr('Recent Activity & Outstanding Invoices', 'हाल की गतिविधि व बकाया बिल')}")
        rec_c1, rec_c2 = st.columns([1.6, 1.4])

        with rec_c1:
            st.markdown(f"**{tr('Recent Orders', 'हाल के ऑर्डर')} (Top 5)**")
            if bills.empty:
                st.info(tr("No purchase history available yet.", "अभी कोई खरीदारी इतिहास उपलब्ध नहीं है।"))
            else:
                recent_bills = bills.head(5).copy()
                r_disp = pd.DataFrame()
                r_disp["Date"] = recent_bills["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
                r_disp["Order ID"] = recent_bills["Sale_ID"].astype(str)
                r_disp["Product"] = recent_bills["Product_Name"].astype(str)
                r_disp["Qty"] = recent_bills.get("Quantity", 1).astype(str)
                r_disp["Amount"] = recent_bills["Bill_Amount"].apply(lambda x: format_currency(x))
                r_disp["Status"] = recent_bills.get("Payment_Status", "Completed").astype(str)
                st.dataframe(translate_df(r_disp, curr_lang), width="stretch", hide_index=True)
                st.button(
                    f"→ {tr('View All Orders', 'सभी ऑर्डर देखें')}",
                    key="btn_dash_view_all_orders",
                    on_click=set_customer_section,
                    args=("History",)
                )

        with rec_c2:
            st.markdown(f"**{tr('Outstanding Invoices', 'बकाया इनवॉइस')} / {tr('Recent Payment Transactions', 'हाल के भुगतान')}**")
            pending_invoices = bills[bills["Outstanding"] > 0].head(5) if not bills.empty else pd.DataFrame()
            if not pending_invoices.empty:
                p_disp = pd.DataFrame()
                p_disp["Invoice ID"] = pending_invoices["Sale_ID"].astype(str)
                p_disp["Date"] = pending_invoices["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
                p_disp["Due Amount"] = pending_invoices["Outstanding"].apply(lambda x: format_currency(x))
                p_disp["Status"] = pending_invoices.get("Payment_Status", "Pending").astype(str)
                st.dataframe(translate_df(p_disp, curr_lang), width="stretch", hide_index=True)
            else:
                st.success(f"✓ {tr('All invoices settled. No outstanding dues found.', 'सभी बिल चुकता हैं। कोई बकाया शेष नहीं है।')}")
                if not bills.empty:
                    settled_txs = bills[bills["Outstanding"] == 0].head(5)
                    s_disp = pd.DataFrame()
                    s_disp["Receipt ID"] = settled_txs["Sale_ID"].astype(str)
                    s_disp["Date"] = settled_txs["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
                    s_disp["Amount"] = settled_txs["Bill_Amount"].apply(lambda x: format_currency(x))
                    s_disp["Mode"] = settled_txs.get("Payment_Mode", "Cash").astype(str)
                    st.dataframe(translate_df(s_disp, curr_lang), width="stretch", hide_index=True)

            st.button(
                f"→ {tr('View Payments & Outstanding Details', 'भुगतान और बकाया विवरण देखें')}",
                key="btn_dash_view_all_payments",
                on_click=set_customer_section,
                args=("Outstanding Dues",)
            )

        # 5. Important Notifications & Alerts
        render_html("<div style='height: 0.95rem;'></div>")
        st.markdown(f"#### 🔔 {tr('Important Notifications & Alerts', 'महत्वपूर्ण सूचनाएं और अलर्ट')}")
        if not cust_notifs:
            st.info(f"✓ {tr('No active notifications on record. You are all caught up!', 'रिकॉर्ड पर कोई सक्रिय सूचना नहीं है। सभी अलर्ट अद्यतित हैं!')}")
        else:
            for notif in cust_notifs[:4]:
                is_unread = not notif.get("is_read", 0)
                n_id = notif.get("notification_id", "")
                n_title = notif.get("title", "Store Notice")
                n_msg = notif.get("message", "")
                n_date = notif.get("created_at", "")[:10] if notif.get("created_at") else ""
                notif_bg = "#FEF3C7" if is_unread else "#FFFFFF"
                notif_border = "#F59E0B" if is_unread else "#E2E8F0"
                badge_text = tr("UNREAD", "नया") if is_unread else tr("READ", "पढ़ा गया")
                badge_bg = "#F59E0B" if is_unread else "#94A3B8"

                nc1, nc2 = st.columns([5.2, 0.8])
                with nc1:
                    render_html(
                        f'<div style="background:{notif_bg}; border:1px solid {notif_border}; border-left:4px solid {notif_border}; border-radius:8px; padding:0.75rem 1rem; margin-bottom:0.5rem;">'
                        f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                        f'<strong style="color:#1E293B; font-size:0.9rem;">{html.escape(n_title)}</strong>'
                        f'<span style="background:{badge_bg}; color:#FFFFFF; font-size:0.68rem; font-weight:700; padding:1px 6px; border-radius:4px;">{badge_text}</span>'
                        f'</div>'
                        f'<p style="color:#475569; font-size:0.83rem; margin:4px 0 0 0;">{html.escape(n_msg)}</p>'
                        f'<div style="font-size:0.7rem; color:#94A3B8; margin-top:3px;">{n_date}</div>'
                        f'</div>'
                    )
                with nc2:
                    if is_unread:
                        if st.button(tr("Read", "पढ़ा"), key=f"btn_mark_read_dash_{n_id}", use_container_width=True):
                            mark_notification_as_read(n_id)
                            st.rerun()

            st.button(
                f"→ {tr('View All in Offers & Notifications', 'सभी ऑफ़र और सूचनाएं देखें')}",
                key="btn_dash_view_all_notifs",
                on_click=set_customer_section,
                args=("Offers & Notifications",)
            )

    # ==========================================================================
    # SECTION 2: PROFILE & ACCOUNT (PRESERVED + UPGRADED EDITING)
    # ==========================================================================
    elif active_section in ("Profile & Account", "My Profile", "Customer Profile & Account", "Profile"):
        st.markdown(f"### 👤 {tr('Profile & Account', 'प्रोफ़ाइल और खाता', 'Profile aur Khata')} — {html.escape(cust_name)}")
        st.caption(tr("Verified store client credentials, registration information, and contact address registered with Shivansh Electronics & Hardware.", "सत्यापित ग्राहक विवरण और स्टोर में पंजीकृत पता।"))

        col_prof_left, col_prof_right = st.columns([1.6, 1.4])
        with col_prof_left:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.4rem 1.6rem; height: 100%; box-shadow: 0 2px 8px rgba(30,41,59,0.04);">'
                f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">'
                f'<div>'
                f'<span style="background: #EFF6FF; color: #2563EB; font-size: 0.72rem; font-weight: 700; padding: 3px 10px; border-radius: 12px; border: 1px solid #BFDBFE;">{tr("STORE CLIENT PROFILE", "ग्राहक प्रोफ़ाइल")}</span>'
                f'<h3 style="margin: 0.4rem 0 2px 0; color: #1E293B !important; font-size: 1.35rem; font-family: \'Playfair Display\', serif;">{html.escape(cust_name)}</h3>'
                f'<div style="font-size: 0.88rem; color: #0D9488; font-weight: 600;">{html.escape(biz_name)}</div>'
                f'</div>'
                f'<div style="background: #FAF5EE; border: 1px solid #E2DBD0; border-radius: 8px; padding: 4px 10px; text-align: center;">'
                f'<div style="font-size: 0.68rem; color: #64748B; font-weight: 700;">RATING</div>'
                f'<div style="font-size: 1rem; color: #D97706; font-weight: 800;">★ {rating_val:.1f}</div>'
                f'</div>'
                f'</div>'
                f'<hr style="border: none; border-top: 1px solid #F1F5F9; margin: 0.75rem 0 1rem 0;">'
                f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.86rem;">'
                f'<div><span style="color: #64748B;">{tr("Customer ID", "ग्राहक आईडी")}:</span> <strong style="color: #1E293B;">{current_id}</strong></div>'
                f'<div><span style="color: #64748B;">{tr("Customer Type", "ग्राहक प्रकार")}:</span> <strong style="color: #1E293B;">{html.escape(cust_type)}</strong></div>'
                f'<div><span style="color: #64748B;">{tr("Mobile", "मोबाइल")}:</span> <strong style="color: #1E293B;">{_normalize_mobile(mob_num)}</strong></div>'
                f'<div><span style="color: #64748B;">{tr("City / Location", "शहर / स्थान")}:</span> <strong style="color: #1E293B;">{html.escape(city_val)}</strong></div>'
                f'<div><span style="color: #64748B;">{tr("Email", "ईमेल")}:</span> <strong style="color: #1E293B;">{html.escape(email_val)}</strong></div>'
                f'<div><span style="color: #64748B;">{tr("Registered On", "पंजीकरण तिथि")}:</span> <strong style="color: #1E293B;">{html.escape(str(reg_date))}</strong></div>'
                f'</div>'
                f'<hr style="border: none; border-top: 1px solid #F1F5F9; margin: 1rem 0 0.8rem 0;">'
                f'<div style="font-size: 0.82rem; color: #475569; line-height: 1.45;">'
                f'<strong>{tr("Store Linkage", "स्टोर संबंध")}:</strong> Primary client of <em>Shivansh Electronics & Hardware</em>. Eligible for trade discounts, GST tax credit invoices, and seasonal wholesale offers.'
                f'</div>'
                f'</div>'
            )

        with col_prof_right:
            # QR Code Preview Card
            qr_bytes = get_customer_qr(current_id)
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.4rem 1.6rem; height: 100%; box-shadow: 0 2px 8px rgba(30,41,59,0.04); display: flex; flex-direction: column; justify-content: space-between;">'
                f'<div>'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; font-family: \'Playfair Display\', serif;">🔳 {tr("Digital Store ID & QR", "डिजिटल स्टोर आईडी व क्यूआर")}</div>'
                f'<span style="background: #FAF5EE; color: #7C3AED; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; border: 1px solid #E2E8F0;">ACTIVE</span>'
                f'</div>'
                f'<p style="font-size: 0.82rem; color: #64748B; margin: 4px 0 1rem 0;">{tr("Scan this unique barcode/QR at checkout counter for express billing and credit deduction.", "त्वरित बिलिंग के लिए काउंटर पर यह क्यूआर कोड स्कैन करें।")}</p>'
                f'</div>'
                f'<div style="display: flex; align-items: center; justify-content: center; padding: 0.5rem 0;">'
            )
            if qr_bytes:
                try:
                    img = Image.open(BytesIO(qr_bytes))
                    st.image(img, width=170, caption=f"{current_id} — {cust_name}")
                except Exception:
                    st.info(f"QR ID: {current_id}")

            render_html(
                f'<div style="text-align: center; font-size: 0.78rem; color: #64748B; margin-top: 0.5rem;">'
                f'<strong>{tr("Last Active Purchase", "अंतिम खरीदारी")}:</strong> {last_purchase}'
                f'</div>'
                f'</div>'
            )

        # Interactive Profile Management & Permitted Field Updates
        render_html("<div style='height: 1rem;'></div>")
        with st.expander(f"✏️ {tr('Update Contact & Address Information', 'संपर्क और पता जानकारी अपडेट करें')}", expanded=False):
            st.caption(tr("Update permitted customer profile details. Changes are securely validated and saved directly into the database.", "केवल अनुमत फ़ील्ड्स को अपडेट करें। परिवर्तन सुरक्षित रूप से डेटाबेस में सहेजे जाते हैं।"))
            with st.form(key=f"edit_profile_form_{current_id}"):
                ep_c1, ep_c2 = st.columns(2)
                with ep_c1:
                    new_mobile = st.text_input(
                        tr("Mobile Number", "मोबाइल नंबर"),
                        value=mob_num if mob_num and mob_num != "Not Available" else "",
                        max_chars=12,
                        help="10-digit Indian mobile number"
                    ).strip()
                    new_email = st.text_input(
                        tr("Email Address", "ईमेल पता"),
                        value=email_val if email_val and email_val != "Not on file" else "",
                        placeholder="e.g. client@example.com"
                    ).strip()
                with ep_c2:
                    new_city = st.text_input(
                        tr("City / District", "शहर / जिला"),
                        value=city_val
                    ).strip()
                    new_address = st.text_input(
                        tr("Street Address / Shop Location", "दुकान का पता / स्थान"),
                        value=addr_val
                    ).strip()

                st.info(f"🔒 {tr('Protected Fields', 'सुरक्षित फ़ील्ड्स')}: Customer ID ({current_id}), Trade Rating (★ {rating_val:.1f}), and Ledger Dues cannot be modified directly.")
                
                if st.form_submit_button(tr("Save Profile Changes", "प्रोफ़ाइल परिवर्तन सहेजें"), type="primary"):
                    clean_digits = "".join(c for c in new_mobile if c.isdigit())
                    if clean_digits.startswith("91") and len(clean_digits) == 12:
                        clean_digits = clean_digits[2:]
                    
                    email_valid = bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", new_email)) if new_email else True
                    
                    if clean_digits and not (len(clean_digits) == 10 and clean_digits[0] in "6789"):
                        st.error("⚠️ Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")
                    elif not email_valid:
                        st.error("⚠️ Please enter a valid email address format (e.g. name@domain.com).")
                    else:
                        updates = {
                            "contact_number": clean_digits or mob_num,
                            "email": new_email or email_val,
                            "city": new_city or city_val,
                            "address": new_address or addr_val,
                        }
                        success = update_customer_profile(current_id, updates)
                        if success:
                            try:
                                from customer_qr_bills import clear_customer_profile_cache
                                clear_customer_profile_cache(current_id)
                            except Exception:
                                pass
                            st.success(f"✓ {tr('Profile successfully updated in database!', 'प्रोफ़ाइल डेटाबेस में सफलतापूर्वक अपडेट हो गई!')}")
                            st.rerun()
                        else:
                            st.error("Failed to update profile. Please try again.")

    # ==========================================================================
    # SECTION 3: HISTORY (SEARCH, FILTERS, TIMELINE)
    # ==========================================================================
    elif active_section in ("Order History", "History", "Purchase History", "Orders"):
        st.markdown(f"### 📦 {tr('History & Purchase Ledger', 'ऑर्डर इतिहास व खरीद बहीखाता', 'Order History')}")
        st.caption(tr("Search, inspect, and track all verified orders, invoices, and fulfillment timelines for this account.", "इस खाते के सभी ऑर्डर, इनवॉइस और डिलीवरी स्थिति ट्रैक करें।"))

        if bills.empty:
            st.info(tr("No purchase history available yet.", "अभी कोई खरीदारी इतिहास उपलब्ध नहीं है।"))
        else:
            status_filter_type = st.radio(
                "Filter Orders",
                [tr("All Orders", "सभी ऑर्डर"), tr("Completed Orders", "पूर्ण ऑर्डर"), tr("Pending / Khata Orders", "लंबित / खाता ऑर्डर")],
                horizontal=True,
                label_visibility="collapsed",
                key="orders_status_tab"
            )

            f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.2, 1.2, 1.2])
            with f_col1:
                hist_search = st.text_input(
                    tr("Search by Order ID or Product", "ऑर्डर आईडी या उत्पाद खोजें"),
                    placeholder="e.g. SALE0001, Wire, Switch...",
                    key="hist_search_kw"
                ).strip().lower()

            with f_col2:
                modes = ["All Modes"] + sorted([m for m in bills["Payment_Mode"].dropna().unique() if m])
                sel_mode = st.selectbox(tr("Payment Mode", "भुगतान माध्यम"), modes, key="hist_mode_filter")

            with f_col3:
                date_filter = st.selectbox(
                    tr("Date Range", "समय सीमा"),
                    ["All Time", "Last 30 Days", "Last 3 Months", "Last 6 Months", "This Year"],
                    key="hist_date_range"
                )

            with f_col4:
                sort_choice = st.selectbox(
                    tr("Sort Order", "क्रम"),
                    [tr("Latest First", "नवीनतम पहले"), tr("Oldest First", "पुरातन पहले"), tr("Highest Amount", "उच्चतम राशि"), tr("Lowest Amount", "न्यूनतम राशि")],
                    key="hist_sort_order"
                )

            # Apply filters
            fbills = bills.copy()

            if status_filter_type in ["Completed Orders", "पूर्ण ऑर्डर"]:
                fbills = fbills[fbills["Payment_Status"].astype(str).str.lower() == "completed"]
            elif status_filter_type in ["Pending / Khata Orders", "लंबित / खाता ऑर्डर"]:
                fbills = fbills[fbills["Outstanding"] > 0]

            if hist_search:
                match_mask = (
                    fbills["Product_Name"].astype(str).str.lower().str.contains(hist_search) |
                    fbills["Sale_ID"].astype(str).str.lower().str.contains(hist_search) |
                    fbills["Payment_Mode"].astype(str).str.lower().str.contains(hist_search)
                )
                fbills = fbills[match_mask]

            if sel_mode != "All Modes":
                fbills = fbills[fbills["Payment_Mode"] == sel_mode]

            if not fbills.empty and "Date" in fbills.columns:
                max_dt = fbills["Date"].max()
                if pd.notnull(max_dt):
                    if date_filter == "Last 30 Days":
                        fbills = fbills[fbills["Date"] >= (max_dt - timedelta(days=30))]
                    elif date_filter == "Last 3 Months":
                        fbills = fbills[fbills["Date"] >= (max_dt - timedelta(days=90))]
                    elif date_filter == "Last 6 Months":
                        fbills = fbills[fbills["Date"] >= (max_dt - timedelta(days=180))]
                    elif date_filter == "This Year":
                        fbills = fbills[fbills["Date"].dt.year == max_dt.year]

            if sort_choice in ["Latest First", "नवीनतम पहले"]:
                fbills = fbills.sort_values(by="Date", ascending=False)
            elif sort_choice in ["Oldest First", "पुरातन पहले"]:
                fbills = fbills.sort_values(by="Date", ascending=True)
            elif sort_choice in ["Highest Amount", "उच्चतम राशि"]:
                fbills = fbills.sort_values(by="Bill_Amount", ascending=False)
            elif sort_choice in ["Lowest Amount", "न्यूनतम राशि"]:
                fbills = fbills.sort_values(by="Bill_Amount", ascending=True)

            st.write(f"**{tr('Displaying', 'दिखाए जा रहे हैं')}:** {len(fbills)} {tr('of', 'में से')} {len(bills)} {tr('orders', 'ऑर्डर')}")

            disp_df = pd.DataFrame()
            disp_df["Order / Sale ID"] = fbills["Sale_ID"].astype(str)
            disp_df["Order Date"] = fbills["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
            disp_df["Product Details"] = fbills["Product_Name"].astype(str)
            disp_df["Qty"] = fbills.get("Quantity", 1).astype(str)
            disp_df["Unit Rate"] = fbills.get("Selling_Price", 0).apply(lambda x: format_currency(x))
            disp_df["Discount"] = fbills.get("Discount_Percent", 0).astype(str) + "%"
            disp_df["Total Amount"] = fbills["Bill_Amount"].apply(lambda x: format_currency(x))
            disp_df["Payment Mode"] = fbills.get("Payment_Mode", "Cash")
            disp_df["Payment Status"] = fbills.get("Payment_Status", "Completed")
            disp_df["Outstanding Due"] = fbills["Outstanding"].apply(lambda x: format_currency(x))

            st.dataframe(translate_df(disp_df, curr_lang), width="stretch", hide_index=True)

            csv_data = disp_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📥 {tr('Download Orders (CSV)', 'ऑर्डर इतिहास डाउनलोड करें (CSV)')}",
                data=csv_data,
                file_name=f"BizMetrics_Orders_{current_id}.csv",
                mime="text/csv",
                key="download_purchases_csv"
            )

            # Interactive 4-Stage Timeline Inspector
            render_html("<div style='height: 1rem;'></div>")
            st.markdown(f"#### 🔍 {tr('Inspect Order Details & Fulfillment Timeline', 'ऑर्डर का विवरण व स्थिति देखें')}")
            
            order_choices = fbills["Sale_ID"].dropna().unique().tolist()
            if order_choices:
                sel_order_inspect = st.selectbox(
                    tr("Select Order ID to Inspect", "विवरण देखने के लिए ऑर्डर चुनें"),
                    order_choices,
                    key="order_timeline_selector"
                )
                if sel_order_inspect:
                    ord_row = fbills[fbills["Sale_ID"] == sel_order_inspect].iloc[0]
                    o_date = ord_row["Date"].strftime("%Y-%m-%d") if pd.notnull(ord_row["Date"]) else "2026-06-01"
                    o_prod = ord_row.get("Product_Name", "Certified Hardware")
                    o_qty = ord_row.get("Quantity", 1)
                    o_amt = float(ord_row.get("Bill_Amount", 0))
                    o_status = str(ord_row.get("Payment_Status", "Completed"))
                    o_mode = str(ord_row.get("Payment_Mode", "Cash"))
                    o_out = float(ord_row.get("Outstanding", 0))

                    is_completed = (o_status.lower() == "completed")
                    timeline_html = (
                        f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.4rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">'
                        f'<div>'
                        f'<span style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase;">ORDER FULFILLMENT TIMELINE</span>'
                        f'<h4 style="margin: 2px 0 0 0; color: #1E293B; font-size: 1.15rem;">#{sel_order_inspect} • {o_prod}</h4>'
                        f'</div>'
                        f'<span style="background: {"#DCFCE7" if is_completed else "#FFEDD5"}; color: {"#166534" if is_completed else "#9A3412"}; font-size: 0.78rem; font-weight: 700; padding: 4px 10px; border-radius: 8px;">{o_status}</span>'
                        f'</div>'
                        f'<div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; text-align: center; margin-top: 1rem;">'
                        f'<div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 0.6rem 0.4rem;">'
                        f'<div style="font-size: 1.2rem;">📝</div>'
                        f'<div style="font-size: 0.75rem; font-weight: 700; color: #065F46;">1. Order Placed</div>'
                        f'<div style="font-size: 0.68rem; color: #047857;">{o_date}</div>'
                        f'</div>'
                        f'<div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 0.6rem 0.4rem;">'
                        f'<div style="font-size: 1.2rem;">📦</div>'
                        f'<div style="font-size: 0.75rem; font-weight: 700; color: #065F46;">2. Stock Allocated</div>'
                        f'<div style="font-size: 0.68rem; color: #047857;">Verified in Store</div>'
                        f'</div>'
                        f'<div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 0.6rem 0.4rem;">'
                        f'<div style="font-size: 1.2rem;">🧾</div>'
                        f'<div style="font-size: 0.75rem; font-weight: 700; color: #065F46;">3. Invoice Billed</div>'
                        f'<div style="font-size: 0.68rem; color: #047857;">Tax Memo Generated</div>'
                        f'</div>'
                        f'<div style="background: {"#ECFDF5" if is_completed else "#FFF7ED"}; border: 1px solid {"#A7F3D0" if is_completed else "#FED7AA"}; border-radius: 8px; padding: 0.6rem 0.4rem;">'
                        f'<div style="font-size: 1.2rem;">{"🚚" if is_completed else "⏳"}</div>'
                        f'<div style="font-size: 0.75rem; font-weight: 700; color: {"#065F46" if is_completed else "#9A3412"};">4. {"Dispatched" if is_completed else "Khata Pending"}</div>'
                        f'<div style="font-size: 0.68rem; color: {"#047857" if is_completed else "#C2410C"};">{"Counter Handover" if is_completed else f"Due: {format_currency(o_out)}"}</div>'
                        f'</div>'
                        f'</div>'
                        f'</div>'
                    )
                    render_html(timeline_html)

    # ==========================================================================
    # SECTION 4: DIGITAL INVOICES & CASH MEMO (REPORTLAB PDF)
    # ==========================================================================
    elif active_section in ("Digital Invoices", "Invoices"):
        st.markdown(f"### 🧾 {tr('Digital Tax Invoice & Cash Memo Center', 'डिजिटल बिल व इनवॉइस केंद्र')}")
        st.caption(tr("Select any transaction to preview, generate, and download an official GST-compliant PDF invoice.", "विस्तृत इनवॉइस देखने और आधिकारिक जीएसटी पीडीएफ डाउनलोड करने के लिए लेन-देन चुनें।"))

        if bills.empty:
            st.info(tr("No purchase history available yet.", "अभी कोई खरीदारी इतिहास उपलब्ध नहीं है।"))
        else:
            bill_list = bills["Sale_ID"].dropna().unique().tolist()
            selected_bill_id = st.selectbox(
                tr("Select Bill / Sale ID to Inspect", "जांच के लिए बिल / सेल आईडी चुनें"),
                bill_list,
                key="bill_inspector_selector"
            )

            if selected_bill_id:
                bill_row = bills[bills["Sale_ID"] == selected_bill_id].iloc[0]
                b_date = bill_row["Date"].strftime("%Y-%m-%d") if pd.notnull(bill_row["Date"]) else "2026-06-01"
                b_prod = bill_row.get("Product_Name", "Hardware Supplies")
                b_qty = bill_row.get("Quantity", 1)
                b_sp = float(bill_row.get("Selling_Price", 0))
                b_disc = float(bill_row.get("Discount_Percent", 0))
                b_amt = float(bill_row.get("Bill_Amount", 0))
                b_mode = bill_row.get("Payment_Mode", "Cash")
                b_status = bill_row.get("Payment_Status", "Completed")
                b_out = float(bill_row.get("Outstanding", 0))
                b_paid = float(bill_row.get("Paid_Amount", b_amt - b_out))

                gross_val = b_qty * b_sp
                disc_val = gross_val * (b_disc / 100.0)

                invoice_html = (
                    f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 2rem; max-width: 800px; margin: 0.5rem auto 1.5rem auto; box-shadow: 0 4px 14px rgba(30,41,59,0.06);">'
                    f'<div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1E293B; padding-bottom: 1rem; margin-bottom: 1.25rem;">'
                    f'<div>'
                    f'<div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; font-family: \'Playfair Display\', serif;">SHIVANSH ELECTRONICS & HARDWARE</div>'
                    f'<div style="font-size: 0.82rem; color: #64748B; margin-top: 3px;">Station Road & Telibandha Hub, Raipur, Chhattisgarh • +91 9876540001</div>'
                    f'<div style="font-size: 0.78rem; color: #0D9488; font-weight: 600;">GSTIN: 22AAAAA0000A1Z5 &nbsp;|&nbsp; MSME: UDYAM-CG-02-0012345</div>'
                    f'</div>'
                    f'<div style="text-align: right;">'
                    f'<div style="background: #2563EB; color: #FFFFFF; font-size: 0.75rem; font-weight: 800; padding: 4px 12px; border-radius: 6px; letter-spacing: 0.05em; display: inline-block;">TAX INVOICE / CASH MEMO</div>'
                    f'<div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; margin-top: 6px;">#{selected_bill_id}</div>'
                    f'<div style="font-size: 0.8rem; color: #64748B;">Date: {b_date}</div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 1.4rem; font-size: 0.86rem;">'
                    f'<div>'
                    f'<div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">BILLED TO:</div>'
                    f'<div style="font-size: 1rem; font-weight: 700; color: #1E293B; margin: 2px 0;">{html.escape(cust_name)}</div>'
                    f'<div style="color: #475569;">{html.escape(biz_name)}</div>'
                    f'<div style="color: #64748B;">Customer ID: <strong>{current_id}</strong> | Ph: {_normalize_mobile(mob_num)}</div>'
                    f'<div style="color: #64748B;">Location: {html.escape(city_val)}</div>'
                    f'</div>'
                    f'<div style="text-align: right;">'
                    f'<div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">TRANSACTION SUMMARY:</div>'
                    f'<div style="color: #475569; margin-top: 2px;">Payment Mode: <strong style="color: #1E293B;">{html.escape(b_mode)}</strong></div>'
                    f'<div style="color: #475569;">Status: <span style="background: {"#DCFCE7" if b_status == "Completed" else "#FFEDD5"}; color: {"#166534" if b_status == "Completed" else "#9A3412"}; font-weight: 700; font-size: 0.75rem; padding: 2px 8px; border-radius: 8px;">{html.escape(b_status)}</span></div>'
                    f'<div style="color: #475569; margin-top: 2px;">Payment Recorded: <strong style="color: #059669;">{format_currency(b_paid)}</strong></div>'
                    f'</div>'
                    f'</div>'
                    f'<table style="width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; font-size: 0.88rem;">'
                    f'<thead>'
                    f'<tr style="background: #FAF5EE; border-top: 1px solid #E2E8F0; border-bottom: 2px solid #E2E8F0; color: #1E293B; text-align: left;">'
                    f'<th style="padding: 9px 12px;">#</th>'
                    f'<th style="padding: 9px 12px;">Item Description</th>'
                    f'<th style="padding: 9px 12px; text-align: right;">Rate</th>'
                    f'<th style="padding: 9px 12px; text-align: center;">Qty</th>'
                    f'<th style="padding: 9px 12px; text-align: right;">Gross</th>'
                    f'<th style="padding: 9px 12px; text-align: right;">Discount</th>'
                    f'<th style="padding: 9px 12px; text-align: right;">Net Total</th>'
                    f'</tr>'
                    f'</thead>'
                    f'<tbody>'
                    f'<tr style="border-bottom: 1px solid #F1F5F9; color: #1E293B;">'
                    f'<td style="padding: 10px 12px;">1</td>'
                    f'<td style="padding: 10px 12px; font-weight: 600;">{html.escape(b_prod)}</td>'
                    f'<td style="padding: 10px 12px; text-align: right;">{format_currency(b_sp)}</td>'
                    f'<td style="padding: 10px 12px; text-align: center;">{b_qty}</td>'
                    f'<td style="padding: 10px 12px; text-align: right;">{format_currency(gross_val)}</td>'
                    f'<td style="padding: 10px 12px; text-align: right; color: #EA580C;">{f"-{format_currency(disc_val)}" if disc_val > 0 else "0%"}</td>'
                    f'<td style="padding: 10px 12px; text-align: right; font-weight: 700; color: #1E293B;">{format_currency(b_amt)}</td>'
                    f'</tr>'
                    f'</tbody>'
                    f'</table>'
                    f'<div style="display: flex; justify-content: flex-end; margin-bottom: 1.5rem;">'
                    f'<div style="width: 280px; font-size: 0.88rem;">'
                    f'<div style="display: flex; justify-content: space-between; padding: 4px 0; color: #64748B;"><span>Subtotal:</span> <strong>{format_currency(gross_val)}</strong></div>'
                    f'<div style="display: flex; justify-content: space-between; padding: 4px 0; color: #64748B;"><span>Total Discount:</span> <strong style="color: #EA580C;">-{format_currency(disc_val)}</strong></div>'
                    f'<div style="display: flex; justify-content: space-between; padding: 8px 0; border-top: 2px solid #1E293B; border-bottom: 2px solid #1E293B; font-size: 1.15rem; color: #1E293B; font-weight: 800; margin-top: 4px;"><span>Invoice Total:</span> <span style="color: #2563EB;">{format_currency(b_amt)}</span></div>'
                    f'<div style="display: flex; justify-content: space-between; padding: 5px 0; color: #059669; font-weight: 600; font-size: 0.85rem;"><span>Amount Received:</span> <strong>{format_currency(b_paid)}</strong></div>'
                    f'<div style="display: flex; justify-content: space-between; padding: 5px 0; color: {"#059669" if b_out == 0 else "#EA580C"}; font-weight: 700; font-size: 0.88rem;"><span>Balance Due:</span> <strong>{format_currency(b_out)}</strong></div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="border-top: 1px dashed #CBD5E1; padding-top: 1rem; text-align: center; font-size: 0.78rem; color: #94A3B8;">'
                    f'This is a computer-generated digital tax receipt from Shivansh Electronics & Hardware. Registered for SIH BizMetrics Rural Digital Enablement.'
                    f'</div>'
                    f'</div>'
                )
                render_html(invoice_html)

                # Generate Real ReportLab PDF Invoice
                pdf_bytes = generate_pdf_invoice(bill_row.to_dict(), profile)

                btn_c1, btn_c2, btn_c3 = st.columns([1.2, 1, 1])
                with btn_c1:
                    st.download_button(
                        label=f"📄 {tr('Download Official PDF Invoice', 'आधिकारिक पीडीएफ इनवॉइस डाउनलोड करें')}",
                        data=pdf_bytes,
                        file_name=f"Invoice_{selected_bill_id}_{current_id}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                        key="dl_bill_pdf_btn"
                    )
                with btn_c2:
                    inv_text = f"SHIVANSH ELECTRONICS & HARDWARE\nTax Invoice: {selected_bill_id}\nDate: {b_date}\nCustomer: {cust_name} ({current_id})\nProduct: {b_prod} x {b_qty}\nTotal Amount: Rs. {b_amt}\nPaid: Rs. {b_paid}\nOutstanding: Rs. {b_out}\nThank you for your business!"
                    st.download_button(
                        label=f"📥 {tr('Download Text Memo', 'टेक्स्ट मेमो डाउनलोड करें')}",
                        data=inv_text.encode("utf-8"),
                        file_name=f"Invoice_{selected_bill_id}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="dl_bill_txt"
                    )
                with btn_c3:
                    wa_url = _whatsapp_url(cust_name, mob_num)
                    if wa_url:
                        st.link_button(f"💬 {tr('Share on WhatsApp', 'व्हाट्सएप पर भेजें')}", wa_url, use_container_width=True)

    # ==========================================================================
    # SECTION 5: OUTSTANDING (PENDING DUES, DUE DATES, PAYMENT HISTORY, EMI INFO)
    # ==========================================================================
    elif active_section in ("Outstanding Dues", "Outstanding", "Payments & Outstanding", "Dues", "EMI Details"):
        st.markdown(f"### 💳 {tr('Outstanding Dues, Payments & Khata EMI Details', 'बकाया राशि, भुगतान व खाता ईएमआई विवरण', 'Outstanding Dues aur EMI')}")
        st.caption(tr("Track unsettled dues, due dates, payment history, and revolving khata EMI credit facilities.", "लंबित बकाया, देय तिथियां, भुगतान इतिहास और खाता ईएमआई सुविधा की जानकारी।"))

        tab_dues, tab_emi = st.tabs([
            f"📋 {tr('Pending Dues & Payment Records', 'लंबित बकाया व भुगतान लेजर', 'Pending Dues aur Payment')}",
            f"💳 {tr('Khata Credit & EMI Facilities', 'खाता क्रेडिट व ईएमआई सुविधा', 'Khata Credit aur EMI')}"
        ])

        with tab_dues:
            if outstanding_amt == 0:
                render_html(
                    f'<div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 12px; padding: 1.4rem 1.6rem; margin-bottom: 1.25rem; display: flex; align-items: center; gap: 16px;">'
                    f'<div style="font-size: 2.2rem; line-height: 1;">🎉</div>'
                    f'<div>'
                    f'<div style="font-size: 1.15rem; font-weight: 800; color: #065F46;">{tr("All Dues Cleared!", "सभी बकाया राशि चुकाई जा चुकी है!")}</div>'
                    f'<div style="font-size: 0.85rem; color: #047857; margin-top: 2px;">{tr("You have no pending balance with Shivansh Electronics & Hardware. Your credit rating is in excellent standing.", "आपका कोई भी बकाया शेष नहीं है। आपकी क्रेडिट रेटिंग उत्कृष्ट स्थिति में है।")}</div>'
                    f'</div>'
                    f'</div>'
                )
            else:
                render_html(
                    f'<div style="background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 12px; padding: 1.4rem 1.6rem; margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: center; gap: 16px;">'
                    f'<div style="display: flex; align-items: center; gap: 16px;">'
                    f'<div style="font-size: 2.2rem; line-height: 1;">⚠️</div>'
                    f'<div>'
                    f'<div style="font-size: 1.15rem; font-weight: 800; color: #9A3412;">{tr("Outstanding Credit Balance Pending", "लंबित क्रेडिट बकाया राशि")}</div>'
                    f'<div style="font-size: 0.85rem; color: #C2410C; margin-top: 2px;">{tr(f"Current unpaid balance: {format_currency(outstanding_amt)}. Please clear dues to maintain priority wholesale terms.", f"वर्तमान बकाया राशि: {format_currency(outstanding_amt)}। कृपया थोक शर्तों को बनाए रखने के लिए बकाया चुकाएं।")}</div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="background: #FFFFFF; border: 1px solid #FDBA74; border-radius: 8px; padding: 6px 14px; text-align: center;">'
                    f'<div style="font-size: 0.72rem; color: #9A3412; font-weight: 700;">TOTAL DUE</div>'
                    f'<div style="font-size: 1.35rem; font-weight: 800; color: #EA580C;">{format_currency(outstanding_amt)}</div>'
                    f'</div>'
                    f'</div>'
                )

            if not bills.empty:
                cash_txs = bills[bills["Payment_Mode"].astype(str).str.lower() == "cash"]
                upi_txs = bills[bills["Payment_Mode"].astype(str).str.lower() == "upi"]
                credit_txs = bills[bills["Payment_Mode"].astype(str).str.lower() == "credit"]

                p_col1, p_col2, p_col3 = st.columns(3)
                with p_col1:
                    render_html(
                        f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #059669; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                        f'<div style="font-size: 0.72rem; font-weight: 700; color: #059669; text-transform: uppercase;">💵 CASH PAYMENTS</div>'
                        f'<div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 2px;">{format_currency(cash_txs["Bill_Amount"].sum())}</div>'
                        f'<div style="font-size: 0.78rem; color: #64748B; margin-top: 2px;">{len(cash_txs)} {tr("settled counter payments", "लेन-देन")}</div>'
                        f'</div>'
                    )
                with p_col2:
                    render_html(
                        f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #2563EB; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                        f'<div style="font-size: 0.72rem; font-weight: 700; color: #2563EB; text-transform: uppercase;">📱 UPI & DIGITAL TRANSFERS</div>'
                        f'<div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 2px;">{format_currency(upi_txs["Bill_Amount"].sum())}</div>'
                        f'<div style="font-size: 0.78rem; color: #64748B; margin-top: 2px;">{len(upi_txs)} {tr("digital settlements", "डिजिटल लेन-देन")}</div>'
                        f'</div>'
                    )
                with p_col3:
                    render_html(
                        f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #EA580C; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                        f'<div style="font-size: 0.72rem; font-weight: 700; color: #EA580C; text-transform: uppercase;">📖 CREDIT (KHATA) PURCHASES</div>'
                        f'<div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 2px;">{format_currency(credit_txs["Bill_Amount"].sum())}</div>'
                        f'<div style="font-size: 0.78rem; color: #EA580C; margin-top: 2px;">{len(credit_txs)} {tr("credit invoices", "क्रेडिट लेन-देन")}</div>'
                        f'</div>'
                    )

                render_html("<div style='height: 1.2rem;'></div>")

                # Aging Analysis for Outstanding Dues
                pending_bills = bills[bills["Outstanding"] > 0]
                if not pending_bills.empty:
                    st.markdown(f"#### ⚠️ {tr('Pending Credit Invoices Requiring Settlement', 'लंबित क्रेडिट बिल जिनका भुगतान शेष है')}")
                    p_disp = pd.DataFrame()
                    p_disp["Invoice / Sale ID"] = pending_bills["Sale_ID"].astype(str)
                    p_disp["Bill Date"] = pending_bills["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
                    p_disp["Product"] = pending_bills["Product_Name"].astype(str)
                    p_disp["Total Bill"] = pending_bills["Bill_Amount"].apply(lambda x: format_currency(x))
                    p_disp["Amount Paid"] = pending_bills["Paid_Amount"].apply(lambda x: format_currency(x))
                    p_disp["Outstanding Due"] = pending_bills["Outstanding"].apply(lambda x: format_currency(x))
                    p_disp["Status"] = pending_bills["Payment_Status"].astype(str)
                    st.dataframe(translate_df(p_disp, curr_lang), width="stretch", hide_index=True)
                else:
                    st.success(f"✓ {tr('All invoices have been settled in full. No pending bills found.', 'सभी बिलों का पूर्ण भुगतान हो चुका है। कोई लंबित बिल नहीं है।')}")

                # Store Settlement Guidelines
                render_html("<div style='height: 1rem;'></div>")
                render_html(
                    f'<div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; font-size: 0.85rem; color: #475569;">'
                    f'<strong style="color: #1E293B; font-size: 0.95rem;">🏛️ {tr("Store Settlement & Payment Clearance Instructions", "स्टोर भुगतान व बकाया निपटान निर्देश")}:</strong><br/>'
                    f'1. Payments must be deposited directly at the store counter via <strong>Cash</strong>, <strong>Official Store UPI QR</strong>, or <strong>NEFT/IMPS Bank Transfer</strong>.<br/>'
                    f'2. Mention your registered Customer ID (<code>{current_id}</code>) during bank or UPI transfers for instant khata ledger reconciliation.<br/>'
                    f'3. For credit ledger inquiries or receipts, contact Shivansh Electronics & Hardware cashier at <strong>+91 98765 40001</strong>.'
                    f'</div>'
                )

        with tab_emi:
            emi_c1, emi_c2 = st.columns([1.5, 1.5])
            with emi_c1:
                render_html(
                    f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.3rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                    f'<div style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase;">ACTIVE STORE CREDIT POLICY</div>'
                    f'<h4 style="margin: 4px 0 10px 0; color: #1E293B;">30-Day Interest-Free Settlement</h4>'
                    f'<div style="font-size: 0.84rem; color: #475569; line-height: 1.5;">'
                    f'• <strong>Khata Facility:</strong> Active revolving trade credit approved for account <code>{current_id}</code>.<br/>'
                    f'• <strong>Current Dues:</strong> <span style="color: {"#059669" if outstanding_amt == 0 else "#EA580C"}; font-weight: 700;">{format_currency(outstanding_amt)}</span><br/>'
                    f'• <strong>Terms:</strong> Dues must be settled within 30 days of invoice date to maintain interest-free benefits.<br/>'
                    f'• <strong>Commercial Loans:</strong> High-ticket purchases above ₹25,000 are eligible for merchant-assisted NBFC / bank installment conversion.'
                    f'</div>'
                    f'</div>'
                )

            with emi_c2:
                render_html(
                    f'<div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.3rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                    f'<div style="font-size: 0.75rem; font-weight: 700; color: #2563EB; text-transform: uppercase;">CREDIT HEALTH & TRUST SCORE</div>'
                    f'<div style="display: flex; align-items: baseline; gap: 8px; margin: 4px 0;">'
                    f'<span style="font-size: 2rem; font-weight: 800; color: #1E293B;">★ {rating_val:.1f}</span>'
                    f'<span style="font-size: 0.85rem; color: #059669; font-weight: 700;">/ 5.0 (High Reliability)</span>'
                    f'</div>'
                    f'<div style="font-size: 0.82rem; color: #64748B; line-height: 1.45;">'
                    f'Your prompt settlement record qualifies your business for priority delivery, seasonal stocking credit, and flexible trade payment terms.'
                    f'</div>'
                    f'</div>'
                )

            render_html("<div style='height: 1rem;'></div>")

            # Flexible EMI Calculator
            st.markdown(f"#### 🧮 {tr('Flexible Purchase EMI Calculator', 'लचीला खरीद ईएमआई कैलकुलेटर')}")
            st.caption(tr("Estimate monthly installment amounts for upcoming equipment, solar installations, or bulk hardware orders.", "आगामी उपकरणों, सौर प्रणाली या थोक हार्डवेयर खरीद के लिए मासिक किस्तों का अनुमान लगाएं।"))

            calc_c1, calc_c2, calc_c3 = st.columns(3)
            with calc_c1:
                calc_p = st.number_input(
                    tr("Planned Purchase Amount (₹)", "नियोजित खरीद राशि (₹)"),
                    min_value=5000,
                    max_value=1000000,
                    value=50000,
                    step=5000,
                    key="emi_calc_principal"
                )
            with calc_c2:
                calc_tenure = st.selectbox(
                    tr("Installment Tenure", "किस्त अवधि"),
                    [3, 6, 9, 12, 18, 24],
                    index=1,
                    format_func=lambda m: f"{m} {tr('Months', 'महीने')}",
                    key="emi_calc_tenure"
                )
            with calc_c3:
                calc_rate = st.slider(
                    tr("Annual Interest Rate (%)", "वार्षिक ब्याज दर (%)"),
                    min_value=8.0,
                    max_value=18.0,
                    value=12.0,
                    step=0.5,
                    key="emi_calc_rate"
                )

            # Standard banking EMI calculation: E = P * r * (1+r)^n / ((1+r)^n - 1)
            r = (calc_rate / 100.0) / 12.0
            n = calc_tenure
            if r > 0 and n > 0:
                emi_val = (calc_p * r * ((1 + r) ** n)) / (((1 + r) ** n) - 1)
            else:
                emi_val = calc_p / max(1, n)
            
            tot_payment = emi_val * n
            tot_interest = tot_payment - calc_p

            em_res1, em_res2, em_res3 = st.columns(3)
            with em_res1:
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #0D9488; border-radius:10px; padding:1rem; text-align:center;">'
                    f'<div style="font-size:0.75rem; font-weight:700; color:#64748B;">{tr("Estimated Monthly EMI", "अनुमानित मासिक ईएमआई")}</div>'
                    f'<div style="font-size:1.6rem; font-weight:800; color:#0D9488; margin-top:2px;">{format_currency(emi_val)}</div>'
                    f'<div style="font-size:0.7rem; color:#64748B;">per month for {n} months</div>'
                    f'</div>'
                )
            with em_res2:
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #2563EB; border-radius:10px; padding:1rem; text-align:center;">'
                    f'<div style="font-size:0.75rem; font-weight:700; color:#64748B;">{tr("Total Interest", "कुल ब्याज")}</div>'
                    f'<div style="font-size:1.6rem; font-weight:800; color:#2563EB; margin-top:2px;">{format_currency(tot_interest)}</div>'
                    f'<div style="font-size:0.7rem; color:#64748B;">over entire duration</div>'
                    f'</div>'
                )
            with em_res3:
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #1E293B; border-radius:10px; padding:1rem; text-align:center;">'
                    f'<div style="font-size:0.75rem; font-weight:700; color:#64748B;">{tr("Total Payable", "कुल देय राशि")}</div>'
                    f'<div style="font-size:1.6rem; font-weight:800; color:#1E293B; margin-top:2px;">{format_currency(tot_payment)}</div>'
                    f'<div style="font-size:0.7rem; color:#64748B;">Principal + Interest</div>'
                    f'</div>'
                )

    # ==========================================================================
    # SECTION 5: QR CODE & DIGITAL STORE PASS
    # ==========================================================================
    elif active_section in ("QR Code Pass", "QR Code", "Customer QR Code", "QR Pass"):
        st.markdown(f"### ▣ {tr('Customer Identity QR & Rapid Checkout Pass', 'ग्राहक पहचान क्यूआर कोड')}")
        st.caption(tr("Use this personalized barcode/QR pass for express checkout, digital invoices, and khata record tracking.", "एक्सप्रेस बिलिंग और डिजिटल खाता प्रबंधन के लिए इस व्यक्तिगत क्यूआर पास का उपयोग करें।"))

        qr_col1, qr_col2 = st.columns([1.3, 2.0])
        with qr_col1:
            qr_bytes = get_customer_qr(current_id)
            if qr_bytes:
                try:
                    qr_img = Image.open(BytesIO(qr_bytes))
                    st.image(qr_img, width=280, caption=f"BIZMETRICS STORE PASS — {current_id}")
                except Exception as e:
                    st.warning(f"QR rendering error: {e}")

                q_act1, q_act2 = st.columns(2)
                with q_act1:
                    st.download_button(
                        f"⬇ {tr('Download QR', 'क्यूआर डाउनलोड')}",
                        data=qr_bytes,
                        file_name=f"{current_id}_BizMetrics_QR.png",
                        mime="image/png",
                        use_container_width=True,
                        key="qr_tab_dl_btn"
                    )
                with q_act2:
                    w_url = _whatsapp_url(cust_name, mob_num)
                    if w_url:
                        st.link_button(f"💬 {tr('WhatsApp Share', 'व्हाट्सएप पर भेजें')}", w_url, use_container_width=True)
            else:
                st.warning("QR code generator unavailable.")

        with qr_col2:
            render_html(
                f'<div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 2px solid {tier_color}; border-radius: 14px; padding: 1.5rem; color: #FFFFFF; box-shadow: 0 4px 15px rgba(15,23,42,0.25); margin-bottom: 1.2rem;">'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<div style="font-size: 0.72rem; letter-spacing: 0.1em; color: #94A3B8; font-weight: 700; text-transform: uppercase;">SHIVANSH ELECTRONICS DIGITAL PASS</div>'
                f'<span style="background: {tier_color}33; color: {tier_color}; font-size: 0.7rem; font-weight: 800; padding: 3px 8px; border-radius: 6px; border: 1px solid {tier_color};">★ {tier_name.upper()}</span>'
                f'</div>'
                f'<div style="margin: 1.2rem 0; font-size: 1.5rem; letter-spacing: 0.08em; font-family: \'Playfair Display\', serif;">{html.escape(cust_name)}</div>'
                f'<div style="display: flex; justify-content: space-between; align-items: flex-end; font-size: 0.82rem; color: #CBD5E1;">'
                f'<div>'
                f'<div style="font-size: 0.65rem; color: #94A3B8; text-transform: uppercase;">CLIENT ID</div>'
                f'<div style="font-size: 1rem; font-weight: 700; color: #38BDF8; font-family: monospace;">{current_id}</div>'
                f'</div>'
                f'<div>'
                f'<div style="font-size: 0.65rem; color: #94A3B8; text-transform: uppercase;">MEMBER SINCE</div>'
                f'<div>{reg_date}</div>'
                f'</div>'
                f'<div style="text-align: right;">'
                f'<div style="font-size: 0.65rem; color: #94A3B8; text-transform: uppercase;">STATUS</div>'
                f'<div style="color: #4ADE80; font-weight: 700;">● VERIFIED LIVE</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.2rem; box-shadow: 0 2px 8px rgba(30,41,59,0.04);">'
                f'<h4 style="margin: 0 0 10px 0; color: #1E293B; font-family: \'Playfair Display\', serif;">{tr("How Your Customer QR Works", "आपका ग्राहक क्यूआर कैसे काम करता है")}</h4>'
                f'<div style="font-size: 0.84rem; color: #475569; line-height: 1.5;">'
                f'1. <strong>{tr("Show at Checkout", "चेकआउट पर दिखाएं")}:</strong> Present this QR on your smartphone when purchasing at Shivansh Electronics.<br/>'
                f'2. <strong>{tr("Instant Profile Match", "त्वरित प्रोफ़ाइल मिलान")}:</strong> The counter cashier scans it to retrieve your trade discounts.<br/>'
                f'3. <strong>{tr("Automated Digital Bill", "स्वचालित डिजिटल बिल")}:</strong> The itemized receipt immediately syncs to your portal.'
                f'</div>'
                f'</div>'
            )

    # ==========================================================================
    # SECTION 6: LOYALTY & REWARDS
    # ==========================================================================
    elif active_section in ("Loyalty & Rewards", "Rewards", "Loyalty"):
        st.markdown(f"### 🎁 {tr('Loyalty Points & VIP Rewards Program', 'लॉयल्टी पॉइंट्स व वीआईपी रिवॉर्ड्स')}")
        st.caption(tr("Earn points on every genuine store purchase. Redeem points for trade discounts and priority credit terms.", "प्रत्येक वास्तविक खरीदारी पर अंक अर्जित करें। विशेष छूट व प्राथमिक क्रेडिट के लिए पॉइंट्स रिडीम करें।"))

        rew_c1, rew_c2 = st.columns([1.5, 1.5])
        with rew_c1:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid {tier_color}; border-radius: 12px; padding: 1.4rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                f'<div style="font-size: 0.75rem; font-weight: 700; color: {tier_color}; text-transform: uppercase;">CURRENT MEMBERSHIP TIER</div>'
                f'<h3 style="margin: 4px 0; color: #1E293B;">★ {tier_name}</h3>'
                f'<div style="font-size: 0.88rem; color: #64748B;">Total Lifetime Purchase: <strong>{format_currency(tot_purchase)}</strong></div>'
                f'<div style="margin: 1rem 0 0.4rem 0; font-size: 0.8rem; color: #475569; font-weight: 600;">Tier Progress to Next Level:</div>'
            )
            progress_pct = min(1.0, tot_purchase / next_req) if next_req > 0 else 1.0
            st.progress(progress_pct)
            render_html(
                f'<div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #64748B;">'
                f'<span>Current: {format_currency(tot_purchase)}</span>'
                f'<span>Goal: {format_currency(next_req)}</span>'
                f'</div>'
                f'</div>'
            )

        with rew_c2:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.4rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                f'<div style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase;">AVAILABLE REWARD POINTS</div>'
                f'<div style="font-size: 2.2rem; font-weight: 800; color: #0D9488; margin: 4px 0;">{loyalty_pts:,} <span style="font-size: 1rem; color: #64748B; font-weight: 500;">Points</span></div>'
                f'<div style="font-size: 0.82rem; color: #475569; line-height: 1.45;">'
                f'• Earning rate: <strong>1 Point per ₹100 spent</strong>.<br/>'
                f'• Equivalent redeemable store credit value: <strong>{format_currency(loyalty_pts * 0.50)}</strong>.<br/>'
                f'• Eligible for express checkout and seasonal hardware promotions.'
                f'</div>'
                f'</div>'
            )

        render_html("<div style='height: 1rem;'></div>")
        st.markdown(f"#### 🏷️ {tr('Available Rewards & Exclusive Trade Offers', 'उपलब्ध रिवॉर्ड्स व विशेष ऑफ़र्स')}")
        
        o1, o2, o3 = st.columns(3)
        with o1:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                f'<div style="font-size: 0.72rem; font-weight: 700; color: #2563EB;">VOUCHER #BIZ250</div>'
                f'<div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; margin: 4px 0;">₹250 Instant Discount</div>'
                f'<div style="font-size: 0.8rem; color: #64748B;">Valid on wiring & electrical supplies orders exceeding ₹2,500.</div>'
                f'<div style="margin-top: 8px; font-size: 0.75rem; color: #059669; font-weight: 700;">✓ Active • Show at Checkout</div>'
                f'</div>'
            )
        with o2:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                f'<div style="font-size: 0.72rem; font-weight: 700; color: #7C3AED;">PRIORITY SERVICE</div>'
                f'<div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; margin: 4px 0;">48-Hour Khata Approval</div>'
                f'<div style="font-size: 0.8rem; color: #64748B;">Instant verification for seasonal agricultural wholesale supplies.</div>'
                f'<div style="margin-top: 8px; font-size: 0.75rem; color: #059669; font-weight: 700;">✓ Tier Perk • Automatic</div>'
                f'</div>'
            )
        with o3:
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
                f'<div style="font-size: 0.72rem; font-weight: 700; color: #0D9488;">BULK FREIGHT</div>'
                f'<div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; margin: 4px 0;">Free Store Delivery</div>'
                f'<div style="font-size: 0.8rem; color: #64748B;">Complimentary transport on orders of 5+ industrial cable bundles.</div>'
                f'<div style="margin-top: 8px; font-size: 0.75rem; color: #059669; font-weight: 700;">✓ Local Raipur/Durg Hubs</div>'
                f'</div>'
            )

    # ==========================================================================
    # SECTION 7: INSIGHTS (MONTHLY PURCHASE ANALYTICS, SPENDING TRENDS, CATEGORY CHARTS)
    # ==========================================================================
    elif active_section in ("Customer Insights", "Insights"):
        st.markdown(f"### 📊 {tr('Customer Insights & Spending Analytics', 'ग्राहक खरीदारी व खर्च विश्लेषण', 'Customer Insights')}")
        st.caption(tr("Interactive monthly purchase analytics, spending trends, category breakdown, and customer-specific metrics.", "मासिक खरीदारी रुझान, श्रेणीवार खर्च और ग्राहक-विशिष्ट चार्ट का विस्तृत विश्लेषण।"))

        if bills.empty:
            st.info(tr("No transaction records available yet to generate analytics charts for this customer.", "इस ग्राहक के लिए विश्लेषण चार्ट उत्पन्न करने हेतु अभी कोई लेन-देन रिकॉर्ड नहीं मिला।"))
        else:
            b_insights = bills.copy()
            b_insights["Month_Year"] = b_insights["Date"].dt.to_period("M").dt.to_timestamp()
            monthly_agg = b_insights.groupby("Month_Year").agg(
                Total_Spend=("Bill_Amount", "sum"),
                Total_Paid=("Paid_Amount", "sum"),
                Total_Due=("Outstanding", "sum"),
                Order_Count=("Sale_ID", "count")
            ).reset_index().sort_values("Month_Year")

            # 1. Summary Analytics KPI Row
            ins_k1, ins_k2, ins_k3, ins_k4 = st.columns(4)
            with ins_k1:
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #0D9488; border-radius:10px; padding:0.9rem; text-align:center;">'
                    f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">{tr("TOTAL SPENT", "कुल खर्च")}</div>'
                    f'<div style="font-size:1.45rem; font-weight:800; color:#0D9488; margin-top:2px;">{format_currency(tot_purchase)}</div>'
                    f'<div style="font-size:0.68rem; color:#64748B;">{len(bills)} {tr("total transactions", "लेन-देन")}</div>'
                    f'</div>'
                )
            with ins_k2:
                avg_m_spend = tot_purchase / max(1, len(monthly_agg))
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #2563EB; border-radius:10px; padding:0.9rem; text-align:center;">'
                    f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">{tr("MONTHLY AVERAGE", "मासिक औसत")}</div>'
                    f'<div style="font-size:1.45rem; font-weight:800; color:#2563EB; margin-top:2px;">{format_currency(avg_m_spend)}</div>'
                    f'<div style="font-size:0.68rem; color:#64748B;">{tr("Across active periods", "सक्रिय महीनों में")}</div>'
                    f'</div>'
                )
            with ins_k3:
                peak_row = monthly_agg.sort_values("Total_Spend", ascending=False).iloc[0] if not monthly_agg.empty else None
                peak_m_str = peak_row["Month_Year"].strftime("%b %Y") if peak_row is not None else "N/A"
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #7C3AED; border-radius:10px; padding:0.9rem; text-align:center;">'
                    f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">{tr("PEAK MONTH", "उच्चतम खरीद महीना")}</div>'
                    f'<div style="font-size:1.45rem; font-weight:800; color:#7C3AED; margin-top:2px;">{peak_m_str}</div>'
                    f'<div style="font-size:0.68rem; color:#64748B;">{format_currency(peak_row["Total_Spend"]) if peak_row is not None else "₹0"}</div>'
                    f'</div>'
                )
            with ins_k4:
                settle_pct = (paid_amt / tot_purchase * 100) if tot_purchase > 0 else 100.0
                render_html(
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid {"#059669" if settle_pct >= 90 else "#EA580C"}; border-radius:10px; padding:0.9rem; text-align:center;">'
                    f'<div style="font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase;">{tr("SETTLEMENT RATIO", "निपटान अनुपात")}</div>'
                    f'<div style="font-size:1.45rem; font-weight:800; color:{"#059669" if settle_pct >= 90 else "#EA580C"}; margin-top:2px;">{settle_pct:.1f}%</div>'
                    f'<div style="font-size:0.68rem; color:#64748B;">{tr("Payment clearance", "भुगतान चुकता")}</div>'
                    f'</div>'
                )

            render_html("<div style='height: 1rem;'></div>")

            # 2. Charts Row 1: Monthly Purchase & Spending Trend + Paid vs Outstanding Donut
            st.markdown(f"#### 📈 {tr('Purchase & Spending Trends', 'खरीदारी और खर्च रुझान')}")
            ic_col1, ic_col2 = st.columns([1.8, 1.2])
            with ic_col1:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=monthly_agg["Month_Year"].dt.strftime("%b %Y"),
                    y=monthly_agg["Total_Spend"],
                    mode="lines+markers",
                    fill="tozeroy",
                    fillcolor="rgba(13, 148, 136, 0.15)",
                    line=dict(color="#0D9488", width=3, shape="spline"),
                    marker=dict(size=8, color="#0F766E", symbol="circle"),
                    hovertemplate="%{x}<br><b>Total Spend:</b> ₹%{y:,.2f}<extra></extra>",
                    name=tr("Total Spend", "कुल खर्च")
                ))
                fig_trend.add_trace(go.Scatter(
                    x=monthly_agg["Month_Year"].dt.strftime("%b %Y"),
                    y=monthly_agg["Total_Paid"],
                    mode="lines+markers",
                    line=dict(color="#059669", width=2, dash="dot"),
                    marker=dict(size=6, color="#059669"),
                    hovertemplate="%{x}<br><b>Settled:</b> ₹%{y:,.2f}<extra></extra>",
                    name=tr("Settled Paid", "चुकता भुगतान")
                ))
                fig_trend.update_layout(
                    title=dict(text=f"📈 {tr('Monthly Purchase Analytics', 'मासिक खरीदारी विश्लेषण')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=15, r=15, t=40, b=15),
                    height=300,
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    xaxis=dict(showgrid=False, linecolor="#E2E8F0"),
                    yaxis=dict(gridcolor="#F1F5F9", linecolor="#E2E8F0"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_trend, use_container_width=True)

            with ic_col2:
                fig_donut = go.Figure(go.Pie(
                    labels=[tr("Paid Settled", "चुकता भुगतान"), tr("Pending Dues", "लंबित बकाया")],
                    values=[max(0.0, paid_amt), max(0.0, outstanding_amt)],
                    hole=0.60,
                    marker=dict(colors=["#0D9488", "#EA580C" if outstanding_amt > 0 else "#A7F3D0"]),
                    textinfo="percent+label",
                    textposition="outside",
                    hovertemplate="<b>%{label}</b><br>Amount: ₹%{value:,.2f}<br>%{percent}<extra></extra>"
                ))
                fig_donut.update_layout(
                    title=dict(text=f"🍩 {tr('Paid vs Outstanding Breakdown', 'भुगतान बनाम बकाया')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=10, r=10, t=40, b=10),
                    height=300,
                    showlegend=False,
                    annotations=[dict(text=f"<b>{settle_pct:.0f}%</b><br><span style='font-size:10px; color:#64748B;'>Settled</span>", x=0.5, y=0.5, font_size=16, showarrow=False)]
                )
                st.plotly_chart(fig_donut, use_container_width=True)

            # 3. Charts Row 2: Purchase Category Breakdown & Top Products
            render_html("<div style='height: 0.8rem;'></div>")
            st.markdown(f"#### 🏷️ {tr('Purchase Category & Product Breakdown', 'श्रेणीवार व उत्पाद विश्लेषण')}")
            cat_c1, cat_c2 = st.columns([1.5, 1.5])
            with cat_c1:
                if "Category" in bills.columns and bills["Category"].dropna().nunique() > 0:
                    cat_agg = bills.groupby("Category")["Bill_Amount"].sum().reset_index().sort_values("Bill_Amount", ascending=True)
                    fig_cat = go.Figure(go.Bar(
                        x=cat_agg["Bill_Amount"],
                        y=cat_agg["Category"],
                        orientation="h",
                        marker=dict(color="#2563EB", opacity=0.85),
                        text=cat_agg["Bill_Amount"].apply(lambda v: format_currency(v)),
                        textposition="auto"
                    ))
                    fig_cat.update_layout(
                        title=dict(text=f"🏷️ {tr('Purchase Category Breakdown', 'खरीदारी श्रेणी विवरण')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                        font=dict(family="Inter, sans-serif", size=11),
                        margin=dict(l=15, r=15, t=40, b=15),
                        height=270,
                        plot_bgcolor="#FFFFFF",
                        paper_bgcolor="#FFFFFF",
                        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                        yaxis=dict(showgrid=False),
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.info(tr("Category breakdown data unavailable.", "श्रेणीवार डेटा उपलब्ध नहीं है।"))

            with cat_c2:
                top_skus = bills.groupby("Product_Name")["Bill_Amount"].sum().reset_index().sort_values("Bill_Amount", ascending=True).tail(5)
                fig_top = go.Figure(go.Bar(
                    x=top_skus["Bill_Amount"],
                    y=top_skus["Product_Name"],
                    orientation="h",
                    marker=dict(color="#0D9488", opacity=0.85),
                    text=top_skus["Bill_Amount"].apply(lambda v: format_currency(v)),
                    textposition="auto"
                ))
                fig_top.update_layout(
                    title=dict(text=f"📦 {tr('Top 5 Purchased Products', 'शीर्ष 5 उत्पाद')}", font=dict(family="Playfair Display, serif", size=15, color="#1E293B")),
                    font=dict(family="Inter, sans-serif", size=11),
                    margin=dict(l=15, r=15, t=40, b=15),
                    height=270,
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    xaxis=dict(showgrid=True, gridcolor="#F1F5F9", showticklabels=False),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_top, use_container_width=True)

            # 4. Data Table: Monthly Spending Performance Table
            render_html("<div style='height: 0.8rem;'></div>")
            st.markdown(f"#### 📅 {tr('Monthly Spending History & Order Breakdown', 'मासिक खर्च इतिहास व ऑर्डर विवरण')}")
            tbl_disp = pd.DataFrame()
            tbl_disp["Month"] = monthly_agg["Month_Year"].dt.strftime("%B %Y")
            tbl_disp["Orders"] = monthly_agg["Order_Count"].astype(str)
            tbl_disp["Total Spend"] = monthly_agg["Total_Spend"].apply(lambda x: format_currency(x))
            tbl_disp["Amount Settled"] = monthly_agg["Total_Paid"].apply(lambda x: format_currency(x))
            tbl_disp["Pending Due"] = monthly_agg["Total_Due"].apply(lambda x: format_currency(x))
            st.dataframe(translate_df(tbl_disp, curr_lang), width="stretch", hide_index=True)

    # ==========================================================================
    # SECTION 8: OFFERS & NOTIFICATIONS
    # ==========================================================================
    elif active_section in ("Offers & Notifications", "Offers", "Notifications"):
        st.markdown(f"### 🔔 {tr('Personalized Offers & Store Announcements', 'ऑफ़र्स व स्टोर घोषणाएं')}")
        st.caption(tr("Official updates, payment reminders, and exclusive trade offers from Shivansh Electronics & Hardware.", "आधिकारिक अपडेट, भुगतान रिमाइंडर और विशेष व्यापार ऑफ़र।"))

        if not cust_notifs:
            st.info(tr("No notifications at this time.", "इस समय कोई सूचना नहीं है।"))
        else:
            for notif in cust_notifs:
                n_id = notif.get("notification_id", "")
                n_title = notif.get("title", "Store Update")
                n_msg = notif.get("message", "")
                n_cat = notif.get("category", "Announcement")
                n_read = bool(notif.get("is_read", 0))
                n_date = str(notif.get("created_at", "2026-11-06"))[:10]

                cat_color = "#2563EB" if n_cat == "Offer" else ("#EA580C" if n_cat == "Payment Reminder" else "#0D9488")
                unread_badge = '<span style="background: #FEE2E2; color: #DC2626; font-size: 0.68rem; font-weight: 700; padding: 2px 7px; border-radius: 6px;">UNREAD</span>' if not n_read else '<span style="color: #94A3B8; font-size: 0.72rem;">Read</span>'

                render_html(
                    f'<div style="background: {"#FFFFFF" if n_read else "#F0FDF4"}; border: 1px solid {"#E2E8F0" if n_read else "#BBF7D0"}; border-left: 4px solid {cat_color}; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.85rem; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">'
                    f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
                    f'<div>'
                    f'<div style="display: flex; align-items: center; gap: 8px;">'
                    f'<span style="background: {cat_color}18; color: {cat_color}; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 6px;">{n_cat.upper()}</span>'
                    f'<span style="font-size: 0.98rem; font-weight: 700; color: #1E293B;">{html.escape(n_title)}</span>'
                    f'{unread_badge}'
                    f'</div>'
                    f'<div style="font-size: 0.85rem; color: #475569; margin-top: 6px; line-height: 1.45;">{html.escape(n_msg)}</div>'
                    f'</div>'
                    f'<div style="font-size: 0.75rem; color: #94A3B8; white-space: nowrap;">{n_date}</div>'
                    f'</div>'
                    f'</div>'
                )
                if not n_read:
                    if st.button(f"✓ {tr('Mark as Read', 'पढ़ा हुआ चिह्नित करें')}", key=f"mark_read_{n_id}"):
                        mark_notification_as_read(n_id)
                        st.rerun()

    # ==========================================================================
    # SECTION 9: SUPPORT (CUSTOMER SUPPORT & STORE HELPDESK)
    # ==========================================================================
    elif active_section in ("Support Center", "Support", "Customer Support"):
        st.markdown(f"### 💬 {tr('Customer Support & Store Helpdesk', 'ग्राहक सहायता व हेल्पडेस्क')}")
        st.caption(tr("Submit inquiries, billing clarifications, or warranty support requests directly to store management.", "स्टोर प्रबंधन को सीधे पूछताछ, बिल स्पष्टीकरण या वारंटी सहायता अनुरोध भेजें।"))

        sup_col1, sup_col2 = st.columns([1.6, 1.4])

        with sup_col1:
            st.markdown(f"#### 📝 {tr('Submit a Support Request', 'सहायता अनुरोध सबमिट करें')}")
            with st.form(key="support_ticket_form"):
                ticket_cat = st.selectbox(
                    tr("Issue Category", "समस्या श्रेणी"),
                    [
                        "Billing & Invoices",
                        "Delivery & Stock Availability",
                        "Khata & Payment Reconciliation",
                        "Product Warranty & Defect",
                        "General Trade Inquiry"
                    ]
                )
                ticket_pri = st.selectbox(
                    tr("Priority Level", "प्राथमिकता"),
                    ["Normal", "High", "Urgent"]
                )
                ticket_msg = st.text_area(
                    tr("Message / Description", "संदेश / विवरण"),
                    placeholder=tr("Describe your inquiry, affected invoice number, or request in detail...", "अपनी पूछताछ या अनुरोध का विस्तृत विवरण दर्ज करें..."),
                    height=110
                )
                if st.form_submit_button(tr("Submit Request", "अनुरोध भेजें"), type="primary"):
                    if not ticket_msg.strip():
                        st.warning("⚠️ Please provide a message description before submitting.")
                    else:
                        tck_id = create_customer_support_ticket(
                            current_id,
                            category=ticket_cat,
                            priority=ticket_pri,
                            message=ticket_msg.strip()
                        )
                        st.success(f"✓ {tr(f'Support ticket created successfully! Reference ID: {tck_id}', f'सहायता टिकट सफलतापूर्वक बनाया गया! संदर्भ आईडी: {tck_id}')}")
                        st.rerun()

        with sup_col2:
            st.markdown(f"#### 📞 {tr('Store Contact & Working Hours', 'स्टोर संपर्क व कार्य समय')}")
            render_html(
                f'<div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.3rem; box-shadow: 0 2px 6px rgba(0,0,0,0.02); font-size: 0.85rem; color: #475569;">'
                f'<div style="font-size: 1.1rem; font-weight: 700; color: #1E293B; margin-bottom: 6px;">Shivansh Electronics & Hardware</div>'
                f'<p style="margin: 0 0 10px 0; color: #64748B;">Central Hardware, Electrical & Power Hub, Raipur</p>'
                f'<div style="margin-bottom: 8px;">📍 <strong>{tr("Address", "पता")}:</strong> Station Road & Telibandha Hub, Raipur, Chhattisgarh 492001</div>'
                f'<div style="margin-bottom: 8px;">📞 <strong>{tr("Helpdesk Phone", "फोन")}:</strong> +91 98765 40001 / +91 98765 43210</div>'
                f'<div style="margin-bottom: 8px;">✉️ <strong>{tr("Email Support", "ईमेल")}:</strong> support@shivanshelectronics.com</div>'
                f'<div style="margin-bottom: 8px;">⏰ <strong>{tr("Operating Hours", "समय")}:</strong> Monday – Saturday: 9:00 AM – 8:30 PM (Sunday: 10:00 AM – 2:00 PM)</div>'
                f'<div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 8px 12px; margin-top: 12px; font-size: 0.8rem; color: #1E40AF;">'
                f'💡 <em>{tr("Store visits welcome for immediate counter khata reconciliation and bulk trade pricing.", "तत्काल खाता मिलान और थोक मूल्य निर्धारण के लिए स्टोर पर पधारें।")}</em>'
                f'</div>'
                f'</div>'
            )

        render_html("<div style='height: 1.2rem;'></div>")
        st.markdown(f"#### 📋 {tr('Your Previous Support Requests', 'आपके पूर्व सहायता अनुरोध')}")
        cust_tickets = get_customer_support_tickets(current_id)
        if not cust_tickets:
            st.info(tr("No previous support tickets recorded for this account.", "इस खाते के लिए कोई पूर्व सहायता टिकट दर्ज नहीं है।"))
        else:
            t_df = pd.DataFrame()
            t_df["Ticket ID"] = [t["ticket_id"] for t in cust_tickets]
            t_df["Date Filed"] = [str(t.get("created_at", ""))[:16] for t in cust_tickets]
            t_df["Category"] = [t.get("category", "") for t in cust_tickets]
            t_df["Priority"] = [t.get("priority", "Normal") for t in cust_tickets]
            t_df["Message Summary"] = [t.get("message", "")[:60] + ("..." if len(t.get("message", "")) > 60 else "") for t in cust_tickets]
            t_df["Status"] = [t.get("status", "Open") for t in cust_tickets]
            st.dataframe(translate_df(t_df, curr_lang), width="stretch", hide_index=True)

    if active_section != "Dashboard":
        render_html("<div style='height: 1.5rem;'></div>")
        st.button(
            f"🏠 ← {tr('Return to Customer Dashboard', 'ग्राहक डैशबोर्ड पर वापस जाएं', 'Dashboard par Wapas')}",
            key=f"btn_footer_back_dash_{active_section.replace(' ', '_')}",
            type="secondary",
            on_click=set_customer_section,
            args=("Dashboard",),
        )
