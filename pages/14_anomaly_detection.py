import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from components.charts import get_base_layout
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

st.set_page_config(page_title="BizMetrics - Anomaly Detection", layout="wide")
try:
    from utils.session_manager import ensure_authenticated_session
    if not ensure_authenticated_session(required_role="owner"):
        st.stop()
except Exception:
    if not st.session_state.get("owner_authenticated", False):
        st.switch_page("app.py")
apply_theme()
render_sidebar()
lang = get_current_language()
render_header(
    t("Anomaly Detection & Recommendations", lang),
    t("Unsupervised statistical anomaly detection across sales, expenses, and inventory ledgers.", lang)
)

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
raw_data = st.session_state["raw_data"]
f = result.get("financial", {})
r = result.get("receivables", {})
inv = result.get("inventory", {})
colors = get_colors()

# -------------------------------------------------------------
# 1. DETECT ANOMALIES IN TRANSACTION RECORDS
# -------------------------------------------------------------
sales_df = raw_data[raw_data['record_type'].astype(str).str.lower() == 'sale'].copy()
exp_df = raw_data[raw_data['record_type'].astype(str).str.lower() == 'expense'].copy()

# Sales anomalies using IQR
sales_anomalies = []
if not sales_df.empty:
    amt_c = 'total_amount' if 'total_amount' in sales_df.columns and sales_df['total_amount'].notna().any() else 'amount'
    sales_df['amt'] = pd.to_numeric(sales_df[amt_c], errors='coerce').fillna(0)
    q25, q75 = sales_df['amt'].quantile(0.25), sales_df['amt'].quantile(0.75)
    iqr = q75 - q25
    upper_threshold = q75 + 2.5 * iqr
    
    outlier_sales = sales_df[sales_df['amt'] > upper_threshold].copy()
    for _, row in outlier_sales.iterrows():
        sales_anomalies.append({
            "Domain": "Sales Outlier",
            "Entity / Product": str(row.get('product_name', row.get('product_id', 'Transaction'))),
            "Observed Value": format_currency(row['amt']),
            "Baseline Threshold": format_currency(upper_threshold),
            "Severity": "High",
            "Detection Method": "IQR Outlier (2.5x Upper Band)",
            "Date": str(row.get('date', 'N/A'))[:10]
        })

# Expense anomalies
expense_anomalies = []
if not exp_df.empty and 'category' in exp_df.columns:
    e_amt_c = 'total_amount' if 'total_amount' in exp_df.columns and exp_df['total_amount'].notna().any() else 'amount'
    exp_df['amt'] = pd.to_numeric(exp_df[e_amt_c], errors='coerce').fillna(0)
    cat_means = exp_df.groupby('category')['amt'].mean()
    cat_stds = exp_df.groupby('category')['amt'].std().fillna(100.0)
    
    for _, row in exp_df.iterrows():
        cat = row['category']
        mean = cat_means.get(cat, 0)
        std = cat_stds.get(cat, 100.0)
        z_score = (row['amt'] - mean) / max(1.0, std)
        if z_score > 2.2:
            expense_anomalies.append({
                "Domain": "Expense Spike",
                "Entity / Product": str(cat),
                "Observed Value": format_currency(row['amt']),
                "Baseline Threshold": format_currency(mean + 2.0 * std),
                "Severity": "Warning",
                "Detection Method": f"Z-Score (Z = {z_score:.2f})",
                "Date": str(row.get('date', 'N/A'))[:10]
            })

all_anomalies = sales_anomalies + expense_anomalies

# -------------------------------------------------------------
# 2. TOP KPI CARDS
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total Anomalies Detected", f"{len(all_anomalies)}", "Statistical outliers flagged")
with c2: kpi_card("Sales Value Outliers", f"{len(sales_anomalies)}", "Orders exceeding 2.5x IQR")
with c3: kpi_card("Expense Spikes", f"{len(expense_anomalies)}", "Transactions exceeding Z > 2.2")
with c4: kpi_card("Anomaly Detection Method", "IQR + Z-Score", "Unsupervised statistical test")

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 3. ANOMALY DETECTION LEDGER
# -------------------------------------------------------------
st.markdown(f"### 🚨 {t('Detected Anomalies & Irregularities', lang)}")
if not all_anomalies:
    st.success("🟢 No severe statistical anomalies detected across sales or operating expenses.")
else:
    st.dataframe(
        pd.DataFrame(all_anomalies),
        column_config={
            "Domain": "Anomaly Domain",
            "Entity / Product": "Entity / Category",
            "Observed Value": "Observed Value",
            "Baseline Threshold": "Normal Baseline Threshold",
            "Severity": "Severity",
            "Detection Method": "Algorithm",
            "Date": "Date"
        },
        hide_index=True,
        use_container_width=True
    )

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 4. PRIORITIZED AI BUSINESS RECOMMENDATIONS
# -------------------------------------------------------------
st.markdown(f"### 💡 {t('Prioritized AI Business Recommendations', lang)}")
st.caption("Contextual, explainable recommendations supported by quantitative ledger evidence.")

recs = [
    {
        "priority": "P1: URGENT",
        "title": "Replenish Critical Inventory to Prevent Lost Sales",
        "evidence": f"{len(inv.get('reorder_items', []))} SKUs have breached their calculated Reorder Point (ROP).",
        "action": "Place supplier purchase orders for priority SKUs before safety stock depletes.",
        "color": "#DC2626"
    },
    {
        "priority": "P2: HIGH",
        "title": "Enforce Collection SLAs on Overdue Receivables",
        "evidence": f"Total outstanding receivables stand at {format_currency(r.get('total_outstanding', 0))}.",
        "action": "Dispatch formal WhatsApp reminders to P1 and P2 delinquent debtor accounts.",
        "color": "#EA580C"
    },
    {
        "priority": "P3: MEDIUM",
        "title": "Liquidate or Bundle Dead-Stock Inventory",
        "evidence": f"Estimated dead stock represents {format_currency(inv.get('dead_stock_value', 0))} in tied-up capital.",
        "action": "Bundle slow-moving hardware items with fast-moving goods at a 10% promotional discount.",
        "color": "#2563EB"
    },
    {
        "priority": "P4: OPPORTUNITY",
        "title": "Scale Margin-Leading Product Lines",
        "evidence": f"Net operating profit margin is currently {f.get('profit_margin', 0):.1f}%.",
        "action": "Increase inventory depth on top 3 gross margin contributors identified in the financial dashboard.",
        "color": "#059669"
    }
]

for rec in recs:
    c_pri = rec["color"]
    render_html(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {c_pri}; border-radius: 10px; padding: 1.1rem 1.3rem; margin-bottom: 0.85rem; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <strong style="color: #1E293B; font-size: 1.02rem;">{rec['title']}</strong>
                <span style="background: {c_pri}14; color: {c_pri}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; border: 1px solid {c_pri}30;">{rec['priority']}</span>
            </div>
            <div style="font-size: 0.85rem; color: #475569; margin: 4px 0;"><strong>Supporting Evidence:</strong> {rec['evidence']}</div>
            <div style="font-size: 0.85rem; color: #0D9488;"><strong>Recommended Action:</strong> {rec['action']}</div>
        </div>
        """
    )

