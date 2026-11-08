import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from utils.formatting import format_currency
from utils.theme import apply_theme, get_colors, render_html
try:
    from utils.translations import t, get_current_language, translate_df
except (ImportError, AttributeError):
    import sys, importlib
    if "utils.translations" in sys.modules:
        importlib.reload(sys.modules["utils.translations"])
    try:
        from utils.translations import t, get_current_language, translate_df
    except Exception:
        from utils.translations import t, get_current_language
        def translate_df(df, lang=None):
            return df

st.set_page_config(page_title="BizMetrics - Smart Alerts", layout="wide")
try:
    from utils.session_manager import ensure_authenticated_session
    if not ensure_authenticated_session(required_role="owner"):
        st.stop()
except Exception:
    if not st.session_state.get("owner_authenticated", False):
        st.switch_page("app.py")
apply_theme()
render_sidebar()
render_header("Smart Alerts & Notification Center", "Centralized real-time operational alerts, threshold violations, and automated risk notifications.")
lang = get_current_language()

if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

if "pipeline_result" not in st.session_state:
    st.error("BizMetrics dataset could not be found.")
    st.stop()

result = st.session_state["pipeline_result"]
f = result.get("financial", {})
r = result.get("receivables", {})
inv = result.get("inventory", {})
cust_data = result.get("customers", {})
customers_list = cust_data.get("customers", [])

# -------------------------------------------------------------
# 1. COMPILE LIVE OPERATIONAL ALERTS
# -------------------------------------------------------------
alerts = []

# 1. Critical Inventory Stockouts & Low Stock
reorder_items = inv.get("reorder_items", [])
if reorder_items:
    alerts.append({
        "id": "ALT-INV-01",
        "category": "Inventory",
        "severity": "CRITICAL",
        "title": f"Low Stock Warning: {len(reorder_items)} SKUs Below Reorder Point",
        "detail": f"{len(reorder_items)} products have breached safety thresholds. Expected lead-time depletion could trigger customer stockouts.",
        "action_page": "pages/04_inventory_and_forecasting.py",
        "action_label": "Review Inventory & Reorder",
        "timestamp": "Today, Live"
    })

# 2. Overdue Receivables Alerts
out_val = r.get("total_outstanding", 0.0)
overdue_list = r.get("overdue_list", [])
if out_val > 0:
    alerts.append({
        "id": "ALT-REC-01",
        "category": "Receivables",
        "severity": "CRITICAL" if out_val > 50000 else "WARNING",
        "title": f"Receivables Delinquency Alert: {format_currency(out_val)} Outstanding",
        "detail": f"{len(overdue_list)} customer invoices are currently past due date. Delayed cash collection restricts operating working capital.",
        "action_page": "pages/05_receivables.py",
        "action_label": "Manage Overdue Invoices",
        "timestamp": "Today, Live"
    })

# 3. Customer Churn Risk Alert
if customers_list:
    df_c = pd.DataFrame(customers_list)
    inactive_count = sum(1 for c in customers_list if c.get('Total_Orders', 0) == 1)
    if inactive_count > 0:
        alerts.append({
            "id": "ALT-CUST-01",
            "category": "Customer",
            "severity": "WARNING",
            "title": f"Customer Churn Warning: {inactive_count} Single-Order Accounts",
            "detail": f"{inactive_count} accounts made only one purchase and have not repurchased. High churn probability without re-engagement.",
            "action_page": "pages/03_customers.py",
            "action_label": "Inspect Churn Radar",
            "timestamp": "1 Day Ago"
        })

# 4. Operating Margin / Cash Flow Alert
net_margin = f.get("profit_margin", 0.0)
if net_margin < 15.0:
    alerts.append({
        "id": "ALT-FIN-01",
        "category": "Financial",
        "severity": "WARNING",
        "title": f"Operating Margin Compression: {net_margin:.1f}%",
        "detail": "Operating profit margin is below the recommended 15% threshold for rural hardware retail enterprises.",
        "action_page": "pages/02_financial.py",
        "action_label": "Inspect Financial P&L",
        "timestamp": "Today, Live"
    })
else:
    alerts.append({
        "id": "ALT-FIN-02",
        "category": "Financial",
        "severity": "INFO",
        "title": f"Financial Performance Stable: {net_margin:.1f}% Net Margin",
        "detail": "Operating expenses are disciplined and business gross margin comfortably covers all fixed overheads.",
        "action_page": "pages/02_financial.py",
        "action_label": "View Financial Statement",
        "timestamp": "Today, Live"
    })

# -------------------------------------------------------------
# 2. TOP KPI CARDS
# -------------------------------------------------------------
crit_count = sum(1 for a in alerts if a['severity'] == 'CRITICAL')
warn_count = sum(1 for a in alerts if a['severity'] == 'WARNING')
info_count = sum(1 for a in alerts if a['severity'] == 'INFO')

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total Active Alerts", f"{len(alerts)}", "System notification count")
with c2: kpi_card("Critical Warnings", f"{crit_count}", "Immediate operational focus")
with c3: kpi_card("Monitoring Warnings", f"{warn_count}", "Elevated trend changes")
with c4: kpi_card("Informational Notes", f"{info_count}", "Performance confirmations")

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 3. FILTERS & ALERT FEED
# -------------------------------------------------------------
f_col1, f_col2, _ = st.columns([1.5, 1.5, 2])
with f_col1:
    filter_sev = st.selectbox(
        t("Filter by Severity", lang),
        ["All Severities", "CRITICAL", "WARNING", "INFO"],
        format_func=lambda x: t(x, lang),
        key="alert_sev_filter"
    )
with f_col2:
    filter_cat = st.selectbox(
        t("Filter by Category", lang),
        ["All Categories", "Inventory", "Receivables", "Customer", "Financial"],
        format_func=lambda x: t(x, lang),
        key="alert_cat_filter"
    )

filtered_alerts = alerts
if filter_sev != "All Severities":
    filtered_alerts = [a for a in filtered_alerts if a['severity'] == filter_sev]
if filter_cat != "All Categories":
    filtered_alerts = [a for a in filtered_alerts if a['category'] == filter_cat]

st.markdown(f"### 🔔 {t('Active Notification Feed', lang)}")

if not filtered_alerts:
    st.success("🟢 " + t("No alerts match your current filter criteria.", lang))
else:
    for a in filtered_alerts:
        sev = a['severity']
        sev_color = "#DC2626" if sev == "CRITICAL" else ("#EA580C" if sev == "WARNING" else "#059669")
        
        render_html(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid {sev_color}; border-radius: 12px; padding: 1.15rem 1.4rem; margin-bottom: 0.95rem; box-shadow: 0 1px 4px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="background: {sev_color}14; color: {sev_color}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; border: 1px solid {sev_color}30;">{sev}</span>
                        <strong style="color: #1E293B; font-size: 1.05rem;">{a['title']}</strong>
                    </div>
                    <span style="font-size: 0.75rem; color: #94A3B8;">{a['timestamp']} • {a['id']}</span>
                </div>
                <p style="font-size: 0.86rem; color: #475569; margin: 0 0 10px 0; line-height: 1.5;">
                    {a['detail']}
                </p>
                <div style="font-size: 0.8rem; color: #64748B;">
                    <strong>Domain Category:</strong> {a['category']}
                </div>
            </div>
            """
        )
        if st.button(f"👉 Navigate to {a['action_label']}", key=f"btn_nav_{a['id']}"):
            st.switch_page(a['action_page'])

