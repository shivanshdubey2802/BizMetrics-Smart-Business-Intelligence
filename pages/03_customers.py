import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from components.charts import create_bar_chart, create_donut_chart, get_base_layout
from utils.formatting import format_currency
from utils.theme import apply_theme, get_colors, render_html
from customer_qr_bills import render_customer_qr_and_bills
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

st.set_page_config(page_title="BizMetrics - Customers", layout="wide")
try:
    from utils.session_manager import ensure_authenticated_session
    if not ensure_authenticated_session(required_role="owner"):
        st.stop()
except Exception:
    if not st.session_state.get("owner_authenticated", False):
        st.switch_page("app.py")

apply_theme()
render_sidebar()
render_header("Customer Intelligence & RFM Segmentation", "Deep customer behavior analysis, RFM segmentation, Churn risk, and Lifetime Value.")
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
raw_data = st.session_state.get("raw_data", pd.DataFrame())
c = result.get("customers", {})
customers_list = c.get("customers", [])
colors = get_colors()

if not customers_list:
    st.info("No customer records found.")
    st.stop()

df_cust = pd.DataFrame(customers_list)

# -------------------------------------------------------------
# 1. ENRICH CUSTOMER RECORDS WITH RFM & CHURN SCORING
# -------------------------------------------------------------
today = pd.Timestamp.today().normalize()
if 'Last_Purchase_Date' in df_cust.columns:
    df_cust['Last_Date'] = pd.to_datetime(df_cust['Last_Purchase_Date'], errors='coerce')
    df_cust['Days_Since_Last_Order'] = (today - df_cust['Last_Date']).dt.days.fillna(90).clip(lower=0)
else:
    df_cust['Days_Since_Last_Order'] = 45

# Recency Score (1-5, higher is better/more recent)
df_cust['R_Score'] = pd.qcut(df_cust['Days_Since_Last_Order'].rank(method='first', ascending=False), q=min(5, len(df_cust)), labels=False) + 1
# Frequency Score (1-5)
df_cust['F_Score'] = pd.qcut(df_cust['Total_Orders'].rank(method='first'), q=min(5, len(df_cust)), labels=False) + 1
# Monetary Score (1-5)
df_cust['M_Score'] = pd.qcut(df_cust['Total_Spent'].rank(method='first'), q=min(5, len(df_cust)), labels=False) + 1

# RFM Segment Classification
def assign_rfm_segment(row):
    r, f, m = row['R_Score'], row['F_Score'], row['M_Score']
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif f >= 3 and m >= 3:
        return "Loyal Customers"
    elif r >= 4 and f <= 2:
        return "Potential Loyalists"
    elif r <= 2 and (f >= 3 or m >= 3):
        return "At Risk"
    return "Hibernating / Lost"

df_cust['RFM_Segment'] = df_cust.apply(assign_rfm_segment, axis=1)

# Churn Risk Calculation
def calculate_churn_risk(row):
    days = row['Days_Since_Last_Order']
    orders = row['Total_Orders']
    if days > 75 or (days > 45 and orders == 1):
        return "High Churn Risk", "#EF4444"
    elif days > 35:
        return "Medium Churn Risk", "#EA580C"
    return "Low Churn Risk", "#059669"

df_cust['Churn_Risk'], df_cust['Churn_Color'] = zip(*df_cust.apply(calculate_churn_risk, axis=1))

# Customer Lifetime Value (CLV) = AOV * Frequency * Margin (25%) * 24 Months
df_cust['Estimated_CLV'] = df_cust['AOV'] * np.maximum(1, df_cust['Total_Orders'] / 3.0) * 0.25 * 12.0

# -------------------------------------------------------------
# 2. TOP KPI CARDS
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total Customers", f"{c.get('total_customers', len(df_cust))}", "Active ledger accounts")
with c2: kpi_card("Total Customer Revenue", format_currency(c.get('total_revenue', df_cust['Total_Spent'].sum())), "Cumulative purchases")
with c3: kpi_card("Average Order Value (AOV)", format_currency(c.get('aov', df_cust['AOV'].mean())), "Average ticket size")
with c4:
    repeat_count = int((df_cust['Total_Orders'] > 1).sum())
    repeat_pct = (repeat_count / max(1, len(df_cust))) * 100
    kpi_card("Repeat Customer Rate", f"{repeat_pct:.1f}%", f"{repeat_count} repeat buyers")

c5, c6, c7, c8 = st.columns(4)
with c5:
    champ_count = int((df_cust['RFM_Segment'] == 'Champions').sum())
    kpi_card("Champions (Top Tier)", f"{champ_count}", "Highest frequency & spend")
with c6:
    at_risk_count = int((df_cust['RFM_Segment'] == 'At Risk').sum())
    kpi_card("At Risk Customers", f"{at_risk_count}", "High past value, overdue")
with c7:
    high_churn_count = int((df_cust['Churn_Risk'] == 'High Churn Risk').sum())
    kpi_card("High Churn Alert", f"{high_churn_count}", "Immediate outreach needed")
with c8:
    avg_clv = df_cust['Estimated_CLV'].mean()
    kpi_card("Average Projected CLV", format_currency(avg_clv), "12-month expected value")

render_html("<div style='height: 1rem;'></div>")

# -------------------------------------------------------------
# 3. TABS: SEGMENTATION, CHURN, CRM & DIGITAL BILLS
# -------------------------------------------------------------
tab_rfm, tab_churn, tab_crm = st.tabs([
    t("🎯 RFM Segmentation & Value", lang),
    t("⚠️ Churn Risk & Retention Playbook", lang),
    t("📇 CRM Directory & QR Bills", lang)
])

with tab_rfm:
    col_rfm1, col_rfm2 = st.columns([1.2, 1.0])
    with col_rfm1:
        st.markdown(f"### 📊 {t('Customer Distribution by RFM Segment', lang)}")
        rfm_summary = df_cust.groupby('RFM_Segment').agg(
            Customer_Count=('customer_id', 'count'),
            Total_Revenue=('Total_Spent', 'sum'),
            Average_AOV=('AOV', 'mean')
        ).reset_index()
        
        fig_rfm = go.Figure(go.Bar(
            x=[t(str(x), lang) for x in rfm_summary['RFM_Segment']],
            y=rfm_summary['Total_Revenue'],
            text=rfm_summary['Customer_Count'].apply(lambda n: f"{n} {t('Customers', lang)}"),
            textposition='auto',
            marker_color=['#059669', '#2563EB', '#0D9488', '#EA580C', '#94A3B8']
        ))
        base_layout = get_base_layout()
        base_layout.pop('title', None)
        base_layout.update(dict(height=320, yaxis_title=f"{t('Total Revenue', lang)} (₹)", margin=dict(l=20, r=20, t=20, b=20)))
        fig_rfm.update_layout(**base_layout)
        st.plotly_chart(fig_rfm, use_container_width=True)
        
    with col_rfm2:
        st.markdown(f"### 💡 {t('Recommended Retention Actions', lang)}")
        render_html(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                <div style="margin-bottom: 8px;">
                    <strong style="color: #059669;">🏆 {t('Champions', lang)}:</strong> {t('Offer exclusive bulk trade discounts and priority credit terms.', lang)}
                </div>
                <div style="margin-bottom: 8px;">
                    <strong style="color: #2563EB;">🤝 {t('Loyal Customers', lang)}:</strong> {t('Upsell seasonal high-margin hardware bundles and festive supplies.', lang)}
                </div>
                <div style="margin-bottom: 8px;">
                    <strong style="color: #0D9488;">🌱 {t('Potential Loyalists', lang)}:</strong> {t('Send personalized WhatsApp product catalog to encourage repeat purchase.', lang)}
                </div>
                <div style="margin-bottom: 8px;">
                    <strong style="color: #EA580C;">🚨 {t('At Risk', lang)}:</strong> {t('Send proactive owner check-in call and resolve any delayed shipments or invoice issues.', lang)}
                </div>
                <div>
                    <strong style="color: #64748B;">💤 {t('Hibernating', lang)}:</strong> {t('Clear past dues with attractive settlement discount on new orders.', lang)}
                </div>
            </div>
            """
        )

with tab_churn:
    st.markdown(f"### 🚨 {t('Churn Risk Radar', lang)}")
    st.caption(t("Identifies customers showing declining purchase velocity or prolonged inactivity.", lang))
    
    churn_cols = ['customer_id', 'business_name', 'Days_Since_Last_Order', 'Total_Orders', 'Total_Spent', 'Churn_Risk']
    df_churn_view = df_cust[churn_cols].sort_values(by='Days_Since_Last_Order', ascending=False).copy()
    df_churn_view['Total_Spent'] = df_churn_view['Total_Spent'].apply(format_currency)
    
    st.dataframe(
        translate_df(df_churn_view, lang),
        column_config={
            "customer_id": t("Customer ID", lang),
            "business_name": t("Account / Business Name", lang),
            "Days_Since_Last_Order": t("Days Since Last Order", lang),
            "Total_Orders": "Orders",
            "Total_Spent": "Total Spend",
            "Churn_Risk": "Churn Classification"
        },
        hide_index=True,
        use_container_width=True
    )

with tab_crm:
    st.markdown(f"### 📇 {t('Customer CRM Directory & Digital Ledger', lang)}")
    
    # Filter controls
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        search_term = st.text_input(t("Search Customer/Business Name", lang), "", key="cust_search_term")
    with f_col2:
        status_opts = ["All"] + sorted(df_cust['status'].dropna().unique().tolist())
        status_filter = st.selectbox(
            t("Status", lang),
            status_opts,
            format_func=lambda x: t(x, lang),
            key="cust_status_filter"
        )
    with f_col3:
        seg_opts = ["All"] + sorted(df_cust['RFM_Segment'].unique().tolist())
        seg_filter = st.selectbox(
            t("RFM Segment", lang),
            seg_opts,
            format_func=lambda x: t(x, lang),
            key="cust_seg_filter"
        )

    filtered_df = df_cust.copy()
    if search_term:
        filtered_df = filtered_df[
            filtered_df['customer_name'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['business_name'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['customer_id'].astype(str).str.contains(search_term, case=False, na=False)
        ]
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df['status'] == status_filter]
    if seg_filter != "All":
        filtered_df = filtered_df[filtered_df['RFM_Segment'] == seg_filter]

    display_cols = ['business_name', 'customer_id', 'RFM_Segment', 'Total_Spent', 'Total_Orders', 'AOV', 'Estimated_CLV', 'Churn_Risk']
    formatted_df = filtered_df[display_cols].copy()
    formatted_df.columns = ['Customer', 'ID', 'Segment', 'Total Spent', 'Orders', 'AOV', 'Projected CLV', 'Churn Risk']
    formatted_df['Total Spent'] = formatted_df['Total Spent'].apply(format_currency)
    formatted_df['AOV'] = formatted_df['AOV'].apply(format_currency)
    formatted_df['Projected CLV'] = formatted_df['Projected CLV'].apply(format_currency)

    st.dataframe(translate_df(formatted_df, lang), use_container_width=True, hide_index=True)

    render_html("<div style='height: 1.25rem;'></div>")
    st.markdown(f"### 📱 {t('Customer Profile Details & QR Bill Generator', lang)}")
    if not filtered_df.empty:
        selected_customer_id = st.selectbox(
            t("Select Customer to Inspect:", lang),
            filtered_df['customer_id'].tolist(),
            key="select_cust_inspect"
        )
        if selected_customer_id:
            render_customer_qr_and_bills(str(selected_customer_id))
