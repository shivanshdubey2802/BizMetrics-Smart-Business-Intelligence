import math
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from utils.formatting import format_currency
from utils.theme import apply_theme
from utils.sih_finance import build_quarterly_schedule, calculate_emi, financing_capacity, select_scheme
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

st.set_page_config(page_title="BizMetrics - Loans and EMI", layout="wide")
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
render_header(t("Loans and EMI", lang), t("Automated SIH Scheme selection and repayment calculator based on Project Cost rules.", lang))

# -------------------------------------------------------------
# 0. ENSURE APPLICATION DATA IS LOADED
# -------------------------------------------------------------
if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

result = st.session_state.get("pipeline_result", {})
loans_data = result.get("loans", {})
financials = result.get("financial", result.get("financials", {}))

# Extract business financials for affordability analysis
total_revenue = financials.get("total_revenue", 0.0)
net_profit = financials.get("net_profit", 0.0)
total_expenses = financials.get("total_expenses", 0.0)

monthly_business_income = total_revenue / 12.0 if total_revenue else 0.0
monthly_operating_expenses = total_expenses / 12.0 if total_expenses else 0.0
monthly_net_profit = net_profit / 12.0 if net_profit else 0.0

existing_principal = float(loans_data.get("outstanding_principal", 0.0) or 0.0)
existing_emi = float(loans_data.get("monthly_emi", 0.0) or 0.0)

# -------------------------------------------------------------
# 1. STATE INITIALIZATION & RULE CONSTANTS
# -------------------------------------------------------------
MICRO_LIMIT = 140_000.0   # ₹1.40 Lakh
MAX_COST_LIMIT = 5_000_000.0  # ₹50.00 Lakh

if "loan_project_cost" not in st.session_state:
    st.session_state["loan_project_cost"] = 140_000.0

# Quick-select button handler
def set_project_cost(val: float):
    st.session_state["loan_project_cost"] = float(val)

# -------------------------------------------------------------
# 2. LOGIC RULE SUMMARY BANNER
# -------------------------------------------------------------
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #FFFFFF, #F8FAFC); border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.5rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
            <div>
                <span style="font-size: 0.82rem; font-weight: 700; color: #0D9488; text-transform: uppercase; letter-spacing: 0.06em;">SIH Scheme Allocation Logic</span>
                <h4 style="margin: 0.25rem 0 0 0; color: #1E293B; font-size: 1.15rem;">Automated Policy Selection Rules</h4>
            </div>
            <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 0.5rem 0.9rem;">
                    <strong style="color: #166534; font-size: 0.88rem;">Logic A: Project Cost ≤ ₹1.40 Lakh</strong><br>
                    <span style="color: #15803D; font-size: 0.8rem;">Micro Finance Scheme • 6.5% Interest • 3-Yr Tenure • 3-Mo Moratorium</span>
                </div>
                <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 0.5rem 0.9rem;">
                    <strong style="color: #1E40AF; font-size: 0.88rem;">Logic B: ₹1.40 Lakh &lt; Cost ≤ ₹50.00 Lakh</strong><br>
                    <span style="color: #2563EB; font-size: 0.8rem;">Term Loan Scheme • 8.0% Interest • 7-Yr Tenure • 6-Mo Moratorium</span>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------
# 3. PROJECT COST & MARGIN INPUT
# -------------------------------------------------------------
st.markdown(f"### ⚙️ {t('Project Cost & Capital Configuration', lang)}")

col_setup1, col_setup2 = st.columns([3, 2])

with col_setup1:
    cost_input = st.number_input(
        "Total Project Cost (₹)",
        min_value=1_000.0,
        max_value=10_000_000.0,
        value=float(st.session_state["loan_project_cost"]),
        step=10_000.0,
        format="%.0f",
        help="Enter your total estimated business project cost to automatically determine scheme eligibility and EMI."
    )
    st.session_state["loan_project_cost"] = cost_input

    # Quick preset chips
    st.caption(t("Quick Select Presets:", lang))
    q_cols = st.columns(6)
    presets = [
        ("₹50,000", 50_000.0),
        ("₹1.00 Lakh", 100_000.0),
        ("₹1.40 Lakh", 140_000.0),
        ("₹5.00 Lakh", 500_000.0),
        ("₹15.00 Lakh", 1_500_000.0),
        ("₹50.00 Lakh", 5_000_000.0),
    ]
    for idx, (label, val) in enumerate(presets):
        if q_cols[idx].button(label, use_container_width=True, key=f"btn_preset_{idx}"):
            set_project_cost(val)
            st.rerun()

current_cost = st.session_state["loan_project_cost"]
required_margin = current_cost * 0.10
max_loan_cap = current_cost * 0.90

with col_setup2:
    st.markdown(
        f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.04);">
            <div style="font-size: 0.85rem; font-weight: 700; color: #475569; margin-bottom: 0.5rem; text-transform: uppercase;">
                SIH 10 / 90 Capital Structure
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
                <span style="color: #64748B;">Promoter Margin Contribution (10%):</span>
                <strong style="color: #1E293B;">{format_currency(required_margin)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
                <span style="color: #64748B;">Maximum Eligible Loan (90%):</span>
                <strong style="color: #0D9488;">{format_currency(max_loan_cap)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #64748B;">Total Project Cost:</span>
                <strong style="color: #1E293B;">{format_currency(current_cost)}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------------------
# 4. AUTOMATED SCHEME DETERMINATION ENGINE (LOGIC A & B)
# -------------------------------------------------------------
scheme_info = select_scheme(current_cost)
is_supported = scheme_info.get("supported", False)
scheme_name = scheme_info.get("name", "Unsupported")

if not is_supported or current_cost > MAX_COST_LIMIT:
    st.error(
        f"⚠️ **Project Cost Exceeds Scheme Ceiling**: {format_currency(current_cost)} exceeds the maximum "
        f"supported limit of ₹50.00 Lakh under SIH Micro Finance and Term Loan schemes."
    )
    st.info("Please enter a project cost between ₹1,000 and ₹50,00,000 to simulate loan repayment.")
    st.stop()

# Identify rule logic
if current_cost <= MICRO_LIMIT:
    matched_rule = "Logic A"
    scheme_title = "Micro Finance Scheme"
    badge_color = "#166534"
    badge_bg = "#DCFCE7"
    border_color = "#86EFAC"
    default_rate = 6.5
    default_tenure_years = 3
    default_moratorium = 3
    rule_desc = f"Project Cost ({format_currency(current_cost)}) is ≤ ₹1.40 Lakh. Automatically assigned to Micro Finance Scheme."
else:
    matched_rule = "Logic B"
    scheme_title = "Term Loan Scheme"
    badge_color = "#1E40AF"
    badge_bg = "#DBEAFE"
    border_color = "#93C5FD"
    default_rate = 8.0
    default_tenure_years = 7
    default_moratorium = 6
    rule_desc = f"Project Cost ({format_currency(current_cost)}) is &gt; ₹1.40 Lakh and ≤ ₹50.00 Lakh. Automatically assigned to Term Loan Scheme."

# Display Active Scheme Banner
st.markdown(
    f"""
    <div style="background-color: {badge_bg}; border: 1.5px solid {border_color}; border-radius: 10px; padding: 1rem 1.25rem; margin-top: 1rem; margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="background-color: {badge_color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">
                    {matched_rule} Triggered
                </span>
                <h3 style="color: {badge_color}; margin: 0.4rem 0 0.2rem 0; font-size: 1.4rem;">{scheme_title}</h3>
                <p style="margin: 0; color: #1E293B; font-size: 0.9rem;">{rule_desc}</p>
            </div>
            <div style="text-align: right; margin-top: 0.5rem;">
                <div style="font-size: 0.85rem; color: #475569;">Policy Terms Applied:</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: {badge_color};">
                    {default_rate}% p.a. • {default_tenure_years} Years • {default_moratorium} Months Moratorium
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------
# 5. INTERACTIVE LOAN & EMI CALCULATOR
# -------------------------------------------------------------
calc_col1, calc_col2, calc_col3, calc_col4 = st.columns(4)

with calc_col1:
    desired_loan = st.number_input(
        "Requested Loan Amount (₹)",
        min_value=1_000.0,
        max_value=float(max_loan_cap),
        value=float(max_loan_cap),
        step=5_000.0,
        format="%.0f",
        help="Defaulted to 90% of Project Cost. Cannot exceed 90% under the 10/90 financing framework."
    )

with calc_col2:
    interest_rate = st.number_input(
        "Interest Rate (% p.a.)",
        min_value=0.1,
        max_value=25.0,
        value=float(default_rate),
        step=0.1,
        help=f"Rule Default: {default_rate}% for {scheme_title} ({matched_rule})."
    )

with calc_col3:
    tenure_years = st.number_input(
        "Tenure (Years)",
        min_value=1.0,
        max_value=15.0,
        value=float(default_tenure_years),
        step=1.0,
        help=f"Rule Default: {default_tenure_years} years for {scheme_title} ({matched_rule})."
    )

with calc_col4:
    moratorium_months = st.number_input(
        "Moratorium Period (Months)",
        min_value=0,
        max_value=int(tenure_years * 12) - 1,
        value=int(default_moratorium),
        step=1,
        help=f"Rule Default: {default_moratorium} months for {scheme_title} ({matched_rule}). Principal repayments are paused during this period."
    )

tenure_months = int(tenure_years * 12)

# Calculation Engine
monthly_emi = calculate_emi(desired_loan, interest_rate, tenure_months)
quarterly_schedule_result = build_quarterly_schedule(desired_loan, interest_rate, tenure_months, moratorium_months)

sched_df = quarterly_schedule_result.get("schedule", pd.DataFrame())
quarterly_payment = quarterly_schedule_result.get("quarterly_payment", 0.0)
total_interest = quarterly_schedule_result.get("total_interest", 0.0)
total_principal = quarterly_schedule_result.get("total_principal", desired_loan)
total_repayment = quarterly_schedule_result.get("total_repayment", desired_loan + total_interest)
moratorium_monthly_interest = (desired_loan * (interest_rate / 100.0)) / 12.0

# -------------------------------------------------------------
# 6. SUMMARY METRIC CARDS
# -------------------------------------------------------------
st.markdown(f"#### 📊 {t('Repayment Overview', lang)}")

kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
with kpi_c1:
    kpi_card("Loan Amount (90%)", format_currency(desired_loan), f"Margin: {format_currency(current_cost - desired_loan)}")
with kpi_c2:
    kpi_card("Monthly EMI Equivalent", format_currency(monthly_emi), f"Standard Amortized EMI")
with kpi_c3:
    kpi_card("Moratorium Interest", format_currency(moratorium_monthly_interest), f"Per month for first {moratorium_months} months")
with kpi_c4:
    kpi_card("Quarterly Repayment", format_currency(quarterly_payment) if quarterly_payment > 0 else "N/A", f"Post-moratorium payment")

kpi_c5, kpi_c6, kpi_c7, kpi_c8 = st.columns(4)
with kpi_c5:
    kpi_card("Applicable Rate", f"{interest_rate:.1f}%", f"{scheme_title}")
with kpi_c6:
    kpi_card("Tenure Duration", f"{tenure_months} Mo ({int(tenure_years)} Yrs)", f"Total repayment period")
with kpi_c7:
    kpi_card("Total Interest Payable", format_currency(total_interest), f"{(total_interest / desired_loan * 100):.1f}% of principal" if desired_loan > 0 else "")
with kpi_c8:
    kpi_card("Total Repayment Amount", format_currency(total_repayment), f"Principal + Total Interest")

# Moratorium explanatory callout
st.markdown(
    f"""
    <div style="background-color: #F8FAFC; border-left: 4px solid #0D9488; padding: 0.75rem 1rem; border-radius: 4px; margin-top: 0.85rem; margin-bottom: 1.5rem;">
        <span style="font-weight: 600; color: #0F766E;">📌 Moratorium Feature Explained:</span>
        <span style="color: #334155; font-size: 0.9rem;">
            During the initial <strong>{moratorium_months} months</strong> moratorium, the borrower pays only the accrued interest of <strong>{format_currency(moratorium_monthly_interest)}/month</strong>.
            Principal repayment commences in Month {moratorium_months + 1}, allowing the business to stabilize cash flows before servicing full amortized dues.
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------
# 7. VISUAL REPAYMENT ANALYTICS (PLOTLY CHARTS)
# -------------------------------------------------------------
st.markdown("---")
st.markdown(f"### 📈 {t('Visual Repayment Timeline & Breakdown', lang)}")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    fig_timeline = go.Figure()
    if not sched_df.empty:
        fig_timeline.add_trace(go.Scatter(
            x=sched_df["Quarter"],
            y=sched_df["Closing Principal"],
            mode="lines+markers",
            name="Outstanding Principal",
            line=dict(color="#2563EB", width=3),
            marker=dict(size=6)
        ))
        fig_timeline.add_trace(go.Scatter(
            x=sched_df["Quarter"],
            y=sched_df["Cumulative Interest"],
            mode="lines+markers",
            name="Cumulative Interest",
            line=dict(color="#0D9488", width=2.5, dash="dot"),
            marker=dict(size=5)
        ))
    fig_timeline.update_layout(
        title="Outstanding Principal & Interest Accrual Over Time",
        xaxis_title="Repayment Quarter",
        yaxis_title="Amount (₹)",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(color="#1E293B", family="Inter, sans-serif"),
        title_font=dict(family="Playfair Display, serif", color="#1E293B", size=16),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

with chart_col2:
    labels = ["Principal Loan Amount", "Total Interest Payable"]
    values = [desired_loan, total_interest]
    colors = ["#2563EB", "#0D9488"]

    fig_pie = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="label+percent",
        hoverinfo="label+value"
    )])
    fig_pie.update_layout(
        title="Total Repayment Breakdown (Principal vs Interest)",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(color="#1E293B", family="Inter, sans-serif"),
        title_font=dict(family="Playfair Display, serif", color="#1E293B", size=16),
        annotations=[dict(text=f"Total<br>{format_currency(total_repayment)}", x=0.5, y=0.5, font_size=13, showarrow=False)]
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# -------------------------------------------------------------
# 8. SCHEME COMPARISON MATRIX (MICRO FINANCE VS TERM LOAN)
# -------------------------------------------------------------
st.markdown("---")
st.markdown(f"### 🏛️ {t('Scheme Comparison Matrix', lang)}")
st.caption("Compare how both SIH Schemes evaluate for your desired loan amount.")

comp_micro_schedule = build_quarterly_schedule(desired_loan, 6.5, 3 * 12, 3)
comp_term_schedule = build_quarterly_schedule(desired_loan, 8.0, 7 * 12, 6)

comp_data = [
    {
        "Feature": "Eligibility Rule",
        "Micro Finance Scheme": "Project Cost ≤ ₹1.40 Lakh (Logic A)",
        "Term Loan Scheme": "₹1.40 Lakh < Cost ≤ ₹50.00 Lakh (Logic B)",
    },
    {
        "Feature": "Selection Status for Current Project",
        "Micro Finance Scheme": "✅ SELECTED" if matched_rule == "Logic A" else "Alternative",
        "Term Loan Scheme": "✅ SELECTED" if matched_rule == "Logic B" else "Alternative",
    },
    {
        "Feature": "Annual Interest Rate",
        "Micro Finance Scheme": "6.5% p.a.",
        "Term Loan Scheme": "8.0% p.a.",
    },
    {
        "Feature": "Tenure Duration",
        "Micro Finance Scheme": "3 Years (36 Months)",
        "Term Loan Scheme": "7 Years (84 Months)",
    },
    {
        "Feature": "Moratorium Period",
        "Micro Finance Scheme": "3 Months",
        "Term Loan Scheme": "6 Months",
    },
    {
        "Feature": "Monthly EMI Equivalent",
        "Micro Finance Scheme": format_currency(calculate_emi(desired_loan, 6.5, 36)),
        "Term Loan Scheme": format_currency(calculate_emi(desired_loan, 8.0, 84)),
    },
    {
        "Feature": "Moratorium Monthly Interest",
        "Micro Finance Scheme": format_currency((desired_loan * 0.065) / 12.0),
        "Term Loan Scheme": format_currency((desired_loan * 0.080) / 12.0),
    },
    {
        "Feature": "Total Interest Accrued",
        "Micro Finance Scheme": format_currency(comp_micro_schedule.get("total_interest", 0.0)),
        "Term Loan Scheme": format_currency(comp_term_schedule.get("total_interest", 0.0)),
    },
    {
        "Feature": "Total Repayment",
        "Micro Finance Scheme": format_currency(comp_micro_schedule.get("total_repayment", 0.0)),
        "Term Loan Scheme": format_currency(comp_term_schedule.get("total_repayment", 0.0)),
    },
]

st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)

# -------------------------------------------------------------
# 9. BUSINESS AFFORDABILITY & CASH FLOW CHECK
# -------------------------------------------------------------
st.markdown("---")
st.markdown(f"### 💼 {t('Business Debt Affordability & Cash Flow Analysis', lang)}")

aff_col1, aff_col2 = st.columns(2)

total_monthly_commitment = existing_emi + monthly_emi
if monthly_net_profit > 0:
    foir = (total_monthly_commitment / monthly_net_profit) * 100.0
else:
    foir = 100.0 if total_monthly_commitment > 0 else 0.0

cash_buffer_after_emi = monthly_net_profit - total_monthly_commitment

with aff_col1:
    st.markdown("#### Monthly Operating Profile")
    st.markdown(f"- **Average Monthly Revenue:** {format_currency(monthly_business_income)}")
    st.markdown(f"- **Monthly Operating Expenses & COGS:** {format_currency(monthly_operating_expenses)}")
    st.markdown(f"- **Monthly Net Profit (Available Surplus):** {format_currency(monthly_net_profit)}")
    
    if monthly_net_profit <= 0:
        st.warning("⚠️ Baseline net profit in records is ₹0 or negative. Loan approval may require external collateral or guarantor backing.")
    elif foir < 40.0:
        st.success(f"✅ **{t('LOW RISK', lang)} (FOIR {foir:.1f}%)**: {t('Repayment is comfortably below 40% of business profit. High approval likelihood.', lang)}")
    elif foir < 65.0:
        st.warning(f"⚠️ **{t('MODERATE RISK', lang)} (FOIR {foir:.1f}%)**: {t('Repayment consumes a moderate share of profit. Budgeting controls recommended.', lang)}")
    else:
        st.error(f"🚨 **{t('HIGH RISK', lang)} (FOIR {foir:.1f}%)**: {t('Debt service obligations exceed 65% of net profit. Risk of cash-flow distress.', lang)}")

with aff_col2:
    st.markdown(f"#### {t('Debt Servicing Impact', lang)}")
    if existing_principal > 0:
        st.markdown(f"- **{t('Existing Loan Principal', lang)}:** {format_currency(existing_principal)}")
        st.markdown(f"- **{t('Existing Monthly EMI', lang)}:** {format_currency(existing_emi)}")
    else:
        st.markdown(f"- **{t('Existing Debt', lang)}:** {t('None found in active records.', lang)}")
        
    st.markdown(f"- **{t('New Proposed EMI', lang)}:** {format_currency(monthly_emi)}")
    st.markdown(f"- **{t('Combined Monthly Debt Service', lang)}:** {format_currency(total_monthly_commitment)}")
    st.markdown(f"- **{t('Estimated Cash Buffer Remaining', lang)}:** {format_currency(cash_buffer_after_emi)}")
    st.markdown(f"- **{t('Debt Burden Ratio (FOIR)', lang)}:** **{foir:.1f}%**")

# -------------------------------------------------------------
# 10. DETAILED QUARTERLY REPAYMENT SCHEDULE TABLE
# -------------------------------------------------------------
st.markdown("---")
st.markdown(f"### 📅 {t('Detailed Amortization Schedule (Quarterly)', lang)}")

if not sched_df.empty:
    display_df = sched_df.copy()
    currency_cols = [
        "Opening Principal", "Interest", "Principal Repaid", "Total Payment",
        "Closing Principal", "Cumulative Interest", "Cumulative Repayment"
    ]
    for col in currency_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: format_currency(x))
            
    st.dataframe(translate_df(display_df, lang), hide_index=True, use_container_width=True)
    
    csv_data = sched_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=t("📥 Download Amortization Schedule (CSV)", lang),
        data=csv_data,
        file_name=f"bizmetrics_loan_schedule_{int(desired_loan)}.csv",
        mime="text/csv",
        use_container_width=False
    )
else:
    st.info("Enter a valid loan amount and project cost to generate the schedule.")
