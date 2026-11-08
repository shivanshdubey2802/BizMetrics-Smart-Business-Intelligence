import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from components.charts import create_donut_chart, get_base_layout
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

st.set_page_config(page_title="BizMetrics - Customer Intelligence", layout="wide")
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
render_header(t("Customer Segmentation & Churn", lang), t("RFM value clustering, predictive churn scoring, and personalized retention playbooks.", lang))

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
cust_data = result.get("customers", {})
customers_list = cust_data.get("customers", [])

if not customers_list:
    st.info("No customer transaction records available for RFM modeling.")
    st.stop()

df_cust = pd.DataFrame(customers_list)

# -------------------------------------------------------------
# 1. RFM SCORING & CHURN PROBABILITY MODEL
# -------------------------------------------------------------
today = pd.Timestamp.today().normalize()
if 'Last_Purchase_Date' in df_cust.columns:
    df_cust['Last_Date'] = pd.to_datetime(df_cust['Last_Purchase_Date'], errors='coerce')
    df_cust['Days_Inactive'] = (today - df_cust['Last_Date']).dt.days.fillna(90).clip(lower=0)
else:
    df_cust['Days_Inactive'] = 45.0

# Quantile scores 1-5
q_count = min(5, len(df_cust))
df_cust['R_Score'] = pd.qcut(df_cust['Days_Inactive'].rank(method='first', ascending=False), q=q_count, labels=False) + 1
df_cust['F_Score'] = pd.qcut(df_cust['Total_Orders'].rank(method='first'), q=q_count, labels=False) + 1
df_cust['M_Score'] = pd.qcut(df_cust['Total_Spent'].rank(method='first'), q=q_count, labels=False) + 1

def categorize_rfm(row):
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

df_cust['Segment'] = df_cust.apply(categorize_rfm, axis=1)

# Churn Probability Score (0% - 100%)
# Based on inactivity days and order history
df_cust['Churn_Prob_Pct'] = np.clip(
    (df_cust['Days_Inactive'] / 120.0 * 60.0) +
    np.where(df_cust['Total_Orders'] == 1, 35.0, 5.0),
    5.0, 95.0
).round(1)

def churn_tier(prob):
    if prob >= 70: return "High Churn Risk", "#EF4444"
    elif prob >= 40: return "Moderate Risk", "#EA580C"
    return "Low Risk / Safe", "#059669"

df_cust['Churn_Tier'], df_cust['Churn_Color'] = zip(*df_cust['Churn_Prob_Pct'].apply(churn_tier))

# CLV = AOV * Orders * Gross Margin Ratio (0.25) * 12 months horizon
df_cust['CLV'] = (df_cust['AOV'] * np.maximum(1, df_cust['Total_Orders'] / 3.0) * 0.25 * 12.0).round(2)

# -------------------------------------------------------------
# 2. TOP KPI CARDS
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Champions (Top Tier)", f"{(df_cust['Segment']=='Champions').sum()}", "Highest spend and velocity")
with c2: kpi_card("Loyal Accounts", f"{(df_cust['Segment']=='Loyal Customers').sum()}", "Consistent repeat buyers")
with c3: kpi_card("At Risk Accounts", f"{(df_cust['Segment']=='At Risk').sum()}", "High past value, overdue")
with c4: kpi_card("High Churn Alerts", f"{(df_cust['Churn_Tier']=='High Churn Risk').sum()}", "Immediate outreach needed")

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 3. SEGMENT DISTRIBUTION & CHURN BREAKDOWN
# -------------------------------------------------------------
col_pie, col_scatter = st.columns([1.1, 1.3])

with col_pie:
    st.markdown(f"### 🎯 {t('Customer RFM Segment Distribution', lang)}")
    seg_summary = df_cust.groupby('Segment')['Total_Spent'].agg(['count', 'sum']).reset_index()
    fig_donut = create_donut_chart(seg_summary, 'Segment', 'sum', "")
    st.plotly_chart(fig_donut, use_container_width=True)

with col_scatter:
    st.markdown(f"### ⚖️ {t('Recency vs Frequency vs Spend', lang)}")
    fig_scat = go.Figure()
    for seg, group in df_cust.groupby('Segment'):
        fig_scat.add_trace(go.Scatter(
            x=group['Days_Inactive'],
            y=group['Total_Orders'],
            mode='markers',
            name=seg,
            marker=dict(size=np.clip(group['Total_Spent'] / 2000.0, 8, 30), opacity=0.8),
            text=group['business_name'] + " (₹" + group['Total_Spent'].astype(str) + ")",
            hoverinfo='text+x+y'
        ))
    base_l = get_base_layout()
    base_l.pop('title', None)
    base_l.update(dict(
        height=320,
        xaxis_title="Days Inactive (Recency Delay)",
        yaxis_title="Total Orders (Frequency)",
        margin=dict(l=20, r=20, t=20, b=20)
    ))
    fig_scat.update_layout(**base_l)
    st.plotly_chart(fig_scat, use_container_width=True)

render_html("<div style='height: 1rem;'></div>")

# -------------------------------------------------------------
# 4. ACTIONABLE RETENTION PLAYBOOKS BY SEGMENT
# -------------------------------------------------------------
st.markdown(f"### 📋 {t('Automated Retention Playbooks', lang)}")
p_c1, p_c2, p_c3 = st.columns(3)

with p_c1:
    render_html(
        """
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #059669; border-radius: 10px; padding: 1.1rem; height: 100%;">
            <strong style="color: #059669; font-size: 0.95rem;">🏆 Champions & Top Spenders</strong>
            <div style="font-size: 0.82rem; color: #475569; margin: 6px 0 10px 0; line-height: 1.5;">
                • Offer dedicated trade credit limits (30-day revolving credit).<br>
                • Provide first access to scarce seasonal hardware stock.<br>
                • Schedule quarterly commercial relationship review.
            </div>
            <span style="background: #ECFDF5; color: #065F46; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 8px;">Action: VIP Loyalty</span>
        </div>
        """
    )

with p_c2:
    render_html(
        """
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #EA580C; border-radius: 10px; padding: 1.1rem; height: 100%;">
            <strong style="color: #EA580C; font-size: 0.95rem;">🚨 At Risk & Lapsing Accounts</strong>
            <div style="font-size: 0.82rem; color: #475569; margin: 6px 0 10px 0; line-height: 1.5;">
                • Initiate store owner phone call to check satisfaction.<br>
                • Verify if competitor pricing is causing volume loss.<br>
                • Send personalized WhatsApp catalog with 5% reorder discount.
            </div>
            <span style="background: #FFF7ED; color: #C2410C; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 8px;">Action: Win-Back Protocol</span>
        </div>
        """
    )

with p_c3:
    render_html(
        """
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #64748B; border-radius: 10px; padding: 1.1rem; height: 100%;">
            <strong style="color: #475569; font-size: 0.95rem;">💤 Hibernating / Lost Accounts</strong>
            <div style="font-size: 0.82rem; color: #475569; margin: 6px 0 10px 0; line-height: 1.5;">
                • Clear outstanding balance before offering new orders.<br>
                • Offer one-time clearance bundle on slow-moving inventory.<br>
                • Audit if shop location or ownership has shifted.
            </div>
            <span style="background: #F1F5F9; color: #475569; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 8px;">Action: Reactivation / Clearance</span>
        </div>
        """
    )

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 5. DETAILED CUSTOMER AUDIT TABLE
# -------------------------------------------------------------
st.markdown(f"### 🗃️ {t('Customer Scoring Audit Ledger', lang)}")

display_df = df_cust[['customer_id', 'business_name', 'Segment', 'Total_Spent', 'Total_Orders', 'Days_Inactive', 'Churn_Prob_Pct', 'CLV']].copy()
display_df = display_df.sort_values(by='Total_Spent', ascending=False)
display_df['Total_Spent'] = display_df['Total_Spent'].apply(format_currency)
display_df['CLV'] = display_df['CLV'].apply(format_currency)
display_df['Churn_Prob_Pct'] = display_df['Churn_Prob_Pct'].apply(lambda p: f"{p}%")

st.dataframe(
    display_df,
    column_config={
        "customer_id": "ID",
        "business_name": "Account / Business Name",
        "Segment": "RFM Segment",
        "Total_Spent": "Total Purchases",
        "Total_Orders": "Orders",
        "Days_Inactive": "Days Inactive",
        "Churn_Prob_Pct": "Churn Probability",
        "CLV": "Projected CLV (12M)"
    },
    hide_index=True,
    use_container_width=True
)
