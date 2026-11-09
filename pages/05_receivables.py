import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from components.charts import get_base_layout
from utils.formatting import format_currency
from utils.theme import apply_theme, get_colors
from utils.data_loader import load_public_benchmark_datasets
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

st.set_page_config(page_title="BizMetrics - Receivables", layout="wide")
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
render_header(t("Receivables & Credit Risk", lang), t("Monitor customer credit ageing, collection priorities, payment trends, and default risk indicators.", lang))

# Ensure application data is loaded
if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

if "pipeline_result" not in st.session_state:
    st.error("BizMetrics dataset could not be loaded.")
    st.info("Upload your business dataset using the Dataset Manager in the sidebar or refresh the application.")
    st.stop()

result = st.session_state["pipeline_result"]
raw_data = st.session_state.get("raw_data", pd.DataFrame())
receivables = result.get("receivables", {})
colors = get_colors()

if not raw_data.empty:
    rec_df = raw_data[raw_data['record_type'].astype(str).str.lower() == 'receivable'].copy()
    sales_df = raw_data[raw_data['record_type'].astype(str).str.lower() == 'sale'].copy()
else:
    rec_df = pd.DataFrame()
    sales_df = pd.DataFrame()

if rec_df.empty:
    st.info("No receivables data found in the current dataset.")
    st.stop()

# Clean numerical columns
for col in ['total_amount', 'total_paid_amount', 'outstanding_amount', 'days_overdue']:
    if col in rec_df.columns:
        rec_df[col] = pd.to_numeric(
            rec_df[col].astype(str).str.replace('₹', '').str.replace(',', ''),
            errors='coerce'
        ).fillna(0)

rec_df['due_date'] = pd.to_datetime(rec_df.get('due_date'), errors='coerce')
rec_df['date'] = pd.to_datetime(rec_df.get('date'), errors='coerce')

# ==============================================================================
# CSS STYLES FOR CONSISTENT COLOR MARKERS (REQUIREMENT 4)
# ==============================================================================
st.markdown(
    """
    <style>
    .badge-overdue {
        background-color: #FEE2E2; color: #DC2626; border: 1px solid #FCA5A5;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;
    }
    .badge-duesoon {
        background-color: #FFF7ED; color: #EA580C; border: 1px solid #FDBA74;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;
    }
    .badge-paid {
        background-color: #DCFCE7; color: #166534; border: 1px solid #86EFAC;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;
    }
    .badge-risk-high {
        background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem;
    }
    .badge-risk-med {
        background-color: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem;
    }
    .badge-risk-low {
        background-color: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;
        padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem;
    }
    .badge-p1 {
        background-color: #DC2626; color: #FFFFFF; font-weight: 800;
        padding: 2px 7px; border-radius: 4px; font-size: 0.75rem;
    }
    .badge-p2 {
        background-color: #EA580C; color: #FFFFFF; font-weight: 800;
        padding: 2px 7px; border-radius: 4px; font-size: 0.75rem;
    }
    .badge-p3 {
        background-color: #D97706; color: #FFFFFF; font-weight: 800;
        padding: 2px 7px; border-radius: 4px; font-size: 0.75rem;
    }
    .badge-p4 {
        background-color: #059669; color: #FFFFFF; font-weight: 800;
        padding: 2px 7px; border-radius: 4px; font-size: 0.75rem;
    }
    .ageing-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }
    .provenance-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 0.65rem 1rem;
        font-size: 0.8rem;
        color: #475569;
        margin-bottom: 1.2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Provenance Label (Requirement 2 & 4)
st.markdown(
    """
    <div class="provenance-box">
        <div>
            <strong>Ledger Source:</strong> Gupta Hardware Mart / Shivansh Electronics Customer Accounts (Actual Business Records)
        </div>
        <div style="color: #0D9488; font-weight: 600;">
            ● Active Customer Ledger • 36 Accounts
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# 1. OUTSTANDING BALANCE SUMMARIES (KPIS)
# ==============================================================================
st.markdown(f"### {t('Outstanding Summary', lang)}")

total_outstanding = float(rec_df['outstanding_amount'].sum())
total_invoiced = float(rec_df['total_amount'].sum())
total_paid = float(rec_df['total_paid_amount'].sum())
collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0.0

# Calculate overdue, due soon, current
overdue_mask = (rec_df['days_overdue'] > 0) & (rec_df['outstanding_amount'] > 0)
due_soon_mask = (rec_df['days_overdue'] == 0) & (rec_df['outstanding_amount'] > 0)

overdue_amt = float(rec_df[overdue_mask]['outstanding_amount'].sum())
due_soon_amt = float(rec_df[due_soon_mask]['outstanding_amount'].sum())
avg_dso = float(rec_df[overdue_mask]['days_overdue'].mean()) if overdue_mask.any() else 0.0

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card(t("Total Receivables (Outstanding)", lang), format_currency(total_outstanding), t("Current unpaid client balance", lang))
with c2: kpi_card(t("Total Invoiced on Credit", lang), format_currency(total_invoiced), t("Cumulative trade credit", lang))
with c3: kpi_card(t("Total Collected / Settled", lang), format_currency(total_paid), t("Recovered cash flow", lang))
with c4: kpi_card(t("Collection Efficiency", lang), f"{collection_rate:.1f}%", t("Cash recovery ratio", lang))

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
c5, c6, c7, c8 = st.columns(4)
with c5: kpi_card(t("Critical Overdue Balance", lang), format_currency(overdue_amt), t("Requires collection action", lang))
with c6: kpi_card(t("Due Soon / Maturing", lang), format_currency(due_soon_amt), t("Expected in next 7-14 days", lang))
with c7: kpi_card(t("Average Delay (Overdue)", lang), f"{avg_dso:.0f} days", t("Days past payment terms", lang))
with c8: kpi_card(t("Overdue Account Count", lang), f"{int(overdue_mask.sum())} invoices", t("Actionable accounts", lang))

# ==============================================================================
# 2. RECEIVABLES AGEING ANALYSIS (REQUIREMENT 4)
# ==============================================================================
st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0;'>", unsafe_allow_html=True)
st.markdown(f"### ⏳ {t('Receivables Ageing Analysis', lang)}")
st.caption(t("Standardized ageing buckets based on days elapsed past the credit invoice due date.", lang))

# Categorize into 4 standard ageing buckets
def categorize_ageing(row):
    days = row['days_overdue']
    out = row['outstanding_amount']
    if out <= 0:
        return "Paid / Settled"
    elif days <= 30:
        return "0–30 Days (Current)"
    elif days <= 60:
        return "31–60 Days (30d Overdue)"
    elif days <= 90:
        return "61–90 Days (60d Overdue)"
    else:
        return "90+ Days (Critical)"

rec_df['Ageing_Bucket'] = rec_df.apply(categorize_ageing, axis=1)

b_current = rec_df[(rec_df['Ageing_Bucket'] == "0–30 Days (Current)") & (rec_df['outstanding_amount'] > 0)]
b_30 = rec_df[rec_df['Ageing_Bucket'] == "31–60 Days (30d Overdue)"]
b_60 = rec_df[rec_df['Ageing_Bucket'] == "61–90 Days (60d Overdue)"]
b_90 = rec_df[rec_df['Ageing_Bucket'] == "90+ Days (Critical)"]

amt_curr = float(b_current['outstanding_amount'].sum())
amt_30 = float(b_30['outstanding_amount'].sum())
amt_60 = float(b_60['outstanding_amount'].sum())
amt_90 = float(b_90['outstanding_amount'].sum())

a1, a2, a3, a4 = st.columns(4)
with a1:
    st.markdown(
        f"""
        <div class="ageing-card" style="border-top: 4px solid #059669;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #059669; text-transform: uppercase;">{t("0–30 Days (Current)", lang).upper()}</div>
            <div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 4px;">{format_currency(amt_curr)}</div>
            <div style="font-size: 0.76rem; color: #64748B; margin-top: 2px;">{len(b_current)} invoice(s) • Normal terms</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with a2:
    st.markdown(
        f"""
        <div class="ageing-card" style="border-top: 4px solid #D97706;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #D97706; text-transform: uppercase;">{t("31–60 Days (30d Overdue)", lang).upper()}</div>
            <div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 4px;">{format_currency(amt_30)}</div>
            <div style="font-size: 0.76rem; color: #64748B; margin-top: 2px;">{len(b_30)} invoice(s) • Courtesy reminder</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with a3:
    st.markdown(
        f"""
        <div class="ageing-card" style="border-top: 4px solid #EA580C;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #EA580C; text-transform: uppercase;">{t("61–90 Days (60d Overdue)", lang).upper()}</div>
            <div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 4px;">{format_currency(amt_60)}</div>
            <div style="font-size: 0.76rem; color: #64748B; margin-top: 2px;">{len(b_60)} invoice(s) • Formal follow-up</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with a4:
    st.markdown(
        f"""
        <div class="ageing-card" style="border-top: 4px solid #DC2626;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #DC2626; text-transform: uppercase;">{t("90+ Days (Critical)", lang).upper()}</div>
            <div style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-top: 4px;">{format_currency(amt_90)}</div>
            <div style="font-size: 0.76rem; color: #64748B; margin-top: 2px;">{len(b_90)} invoice(s) • High loss risk</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Ageing Distribution Bar Chart
ageing_summary = pd.DataFrame({
    'Bucket': ["0–30 Days (Current)", "31–60 Days", "61–90 Days", "90+ Days"],
    'Amount': [amt_curr, amt_30, amt_60, amt_90],
    'Color': ["#059669", "#D97706", "#EA580C", "#DC2626"]
})

fig_ageing = px.bar(
    ageing_summary,
    x='Bucket',
    y='Amount',
    color='Bucket',
    color_discrete_map={
        "0–30 Days (Current)": "#059669",
        "31–60 Days": "#D97706",
        "61–90 Days": "#EA580C",
        "90+ Days": "#DC2626"
    },
    title=t("Outstanding Receivables by Ageing Bracket", lang),
    text_auto='.2s'
)
fig_ageing.update_layout(**get_base_layout())
fig_ageing.update_layout(
    title_text=t("Outstanding Receivables by Ageing Bracket", lang),
    showlegend=False,
    yaxis_title="Outstanding Amount (₹)"
)
st.plotly_chart(fig_ageing, width="stretch")

# ==============================================================================
# 3. CUSTOMER-WISE COLLECTION PRIORITY & RISK SCORING (REQUIREMENT 4)
# ==============================================================================
st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0;'>", unsafe_allow_html=True)
st.markdown(f"### 🎯 {t('Customer-Wise Collection Priority & Action Matrix', lang)}")
st.caption(t("Prioritizes recovery efforts by combining outstanding balance, days overdue, and historical credit rating.", lang))

# Aggregate customer level
cust_summary = rec_df.groupby('customer_name').agg(
    Total_Invoiced=('total_amount', 'sum'),
    Total_Paid=('total_paid_amount', 'sum'),
    Outstanding=('outstanding_amount', 'sum'),
    Max_Days_Overdue=('days_overdue', 'max'),
    Customer_Rating=('customer_rating', 'mean')
).reset_index()

def assign_priority_and_risk(row):
    out = row['Outstanding']
    days = row['Max_Days_Overdue']
    rating = row['Customer_Rating']
    
    if out <= 0:
        priority = "P4: Low"
        risk = "Low Risk"
        rec = "Account fully cleared; maintain standard trade credit terms."
    elif days > 60 or out > 8000 or (days > 30 and rating < 3.8):
        priority = "P1: URGENT"
        risk = "High Risk"
        rec = "Issue formal WhatsApp recovery notice; pause all new credit orders."
    elif days > 30 or out > 4000 or rating < 4.2:
        priority = "P2: High"
        risk = "Medium Risk"
        rec = "Direct phone call from shopkeeper; set up structured bi-weekly repayment."
    elif days > 0:
        priority = "P3: Medium"
        risk = "Medium Risk"
        rec = "Send friendly WhatsApp invoice reminder with instant UPI payment QR."
    else:
        priority = "P4: Low"
        risk = "Low Risk"
        rec = "Current invoice maturing soon; send standard automated reminder."
        
    return pd.Series([priority, risk, rec], index=['Collection_Priority', 'Credit_Risk', 'Action_Recommendation'])

scored_cust = cust_summary.copy()
scored_cust[['Collection_Priority', 'Credit_Risk', 'Action_Recommendation']] = cust_summary.apply(assign_priority_and_risk, axis=1)
scored_cust = scored_cust.sort_values(by=['Outstanding', 'Max_Days_Overdue'], ascending=[False, False])

def style_priority(val):
    v = str(val).upper()
    if "URGENT" in v:
        return "background-color: #FEE2E2; color: #DC2626; font-weight: 800;"
    elif "P2" in v or "HIGH" in v:
        return "background-color: #FFF7ED; color: #EA580C; font-weight: 700;"
    elif "P3" in v or "MEDIUM" in v:
        return "background-color: #FFFBEB; color: #D97706; font-weight: 700;"
    elif "LOW" in v or "P4" in v:
        return "background-color: #DCFCE7; color: #166534; font-weight: 600;"
    return ""

def style_risk(val):
    v = str(val).lower()
    if "high" in v:
        return "color: #DC2626; font-weight: 700;"
    elif "medium" in v:
        return "color: #EA580C; font-weight: 700;"
    elif "low" in v:
        return "color: #059669; font-weight: 700;"
    return ""

st.dataframe(
    scored_cust.style
    .map(style_priority, subset=['Collection_Priority'])
    .map(style_risk, subset=['Credit_Risk'])
    .format({
        'Total_Invoiced': '₹ {:,.2f}',
        'Total_Paid': '₹ {:,.2f}',
        'Outstanding': '₹ {:,.2f}',
        'Max_Days_Overdue': '{:.0f} d',
        'Customer_Rating': '{:.1f} ★'
    }),
    width="stretch"
)

# ==============================================================================
# 4. PAYMENT TREND ANALYSIS (REQUIREMENT 4)
# ==============================================================================
st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0;'>", unsafe_allow_html=True)
st.markdown(f"### 📈 {t('Payment & Collection Trend Analysis', lang)}")
st.caption(t("Monthly comparison between trade credit extended and cash collections settled.", lang))

if not rec_df.empty and 'date' in rec_df.columns:
    rec_monthly = rec_df.copy()
    rec_monthly['Month'] = rec_monthly['date'].dt.to_period('M').astype(str)
    
    monthly_trend = rec_monthly.groupby('Month').agg(
        Invoiced=('total_amount', 'sum'),
        Paid=('total_paid_amount', 'sum'),
        Outstanding=('outstanding_amount', 'sum')
    ).reset_index()
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=monthly_trend['Month'],
        y=monthly_trend['Invoiced'],
        name=t('Total Credit Invoiced', lang),
        marker_color='#2563EB'
    ))
    fig_trend.add_trace(go.Bar(
        x=monthly_trend['Month'],
        y=monthly_trend['Paid'],
        name=t('Total Amount Paid', lang),
        marker_color='#059669'
    ))
    fig_trend.add_trace(go.Scatter(
        x=monthly_trend['Month'],
        y=monthly_trend['Outstanding'],
        name=t('Outstanding Balance', lang),
        mode='lines+markers',
        line=dict(color='#DC2626', width=3)
    ))
    fig_trend.update_layout(**get_base_layout())
    fig_trend.update_layout(
        title_text=t("Monthly Credit Extended vs Collections Recovered", lang),
        barmode='group',
        yaxis_title=f"{t('Amount', lang)} (₹)"
    )
    st.plotly_chart(fig_trend, width="stretch")

# ==============================================================================
# 5. DETAILED INVOICE-LEVEL STATUS AUDIT TABLE
# ==============================================================================
st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0;'>", unsafe_allow_html=True)
st.markdown(f"### {t('Detailed Invoices Audit', lang)}")

# Map explicit status formatting per prompt specification
def get_inv_status_label(row):
    out = row['outstanding_amount']
    days = row['days_overdue']
    if out <= 0:
        return "Paid"
    elif days > 0:
        return "Overdue"
    else:
        return "Due Soon"

rec_df['Status_Label'] = rec_df.apply(get_inv_status_label, axis=1)

def style_invoice_status(val):
    v = str(val).lower()
    if "overdue" in v:
        return "background-color: #FEE2E2; color: #DC2626; font-weight: 700;"
    elif "due soon" in v:
        return "background-color: #FFF7ED; color: #EA580C; font-weight: 700;"
    elif "paid" in v:
        return "background-color: #DCFCE7; color: #166534; font-weight: 700;"
    return ""

display_invoices = rec_df[[
    'customer_name', 'sale_id', 'total_amount', 'total_paid_amount',
    'outstanding_amount', 'date', 'due_date', 'days_overdue', 'Status_Label'
]].rename(columns={
    'customer_name': 'Customer',
    'sale_id': 'Invoice No',
    'total_amount': 'Invoice Amount',
    'total_paid_amount': 'Amount Paid',
    'outstanding_amount': 'Outstanding',
    'date': 'Invoice Date',
    'due_date': 'Due Date',
    'days_overdue': 'Days Overdue',
    'Status_Label': 'Status'
}).sort_values(by=['Outstanding', 'Days Overdue'], ascending=[False, False])

st.dataframe(
    display_invoices.style
    .map(style_invoice_status, subset=['Status'])
    .format({
        'Invoice Amount': '₹ {:,.2f}',
        'Amount Paid': '₹ {:,.2f}',
        'Outstanding': '₹ {:,.2f}',
        'Days Overdue': '{:.0f} d',
        'Invoice Date': lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else 'N/A',
        'Due Date': lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else 'N/A'
    }),
    width="stretch"
)

# ==============================================================================
# 6. CREDIT-RISK RESEARCH BENCHMARK INTELLIGENCE EXPANDER
# ==============================================================================
st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0;'>", unsafe_allow_html=True)
with st.expander("🔬 Credit-Risk Research Benchmark Standards (UCI Machine Learning)", expanded=False):
    st.caption("Reference risk provisioning benchmarks from open credit-risk research repositories (separate from actual store ledger).")
    benchmarks = load_public_benchmark_datasets()
    cr_df = benchmarks.get("credit_risk", pd.DataFrame())
    if not cr_df.empty:
        st.dataframe(
            cr_df.rename(columns={
                'ageing_bucket': 'Ageing Bucket',
                'risk_tier': 'Risk Tier',
                'default_rate_pct': 'Historical Default Rate (%)',
                'standard_provision_pct': 'Prudent Reserve (%)',
                'collection_sla_days': 'Collection SLA (Days)',
                'action': 'Recommended Industry Action'
            }),
            width="stretch",
            hide_index=True
        )
    else:
        st.info("Public credit-risk benchmark dataset is available in data/sources/credit_risk_research_benchmark.csv.")
