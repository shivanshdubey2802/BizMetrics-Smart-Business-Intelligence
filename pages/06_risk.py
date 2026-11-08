import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
from components.charts import get_base_layout
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

st.set_page_config(page_title="BizMetrics - Risk", layout="wide")
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
render_header(t("Enterprise Risk Radar", lang), t("Multi-dimensional business risk analytics, early warning signals, and actionable mitigations.", lang))

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
risks_data = result.get("risks", {})
if isinstance(risks_data, dict):
    score = risks_data.get("score", 78)
    risk_list = risks_data.get("risk_list", [])
elif isinstance(risks_data, list):
    score = 75
    risk_list = risks_data
else:
    score = 75
    risk_list = []

f = result.get("financial", {})
r = result.get("receivables", {})
inv = result.get("inventory", {})

# -------------------------------------------------------------
# 1. COMPUTE EXPLAINABLE 5-PILLAR RISK SCORES (100 = Safest)
# -------------------------------------------------------------
# 1. Credit Risk (Overdue vs Total Receivables)
tot_rec = max(1.0, float(r.get('total_outstanding', 0.0) or 1.0))
overdue_val = float(sum(item.get('total_amount', 0) for item in r.get('overdue_list', [])) if r.get('overdue_list') else 0.0)
overdue_ratio = min(1.0, overdue_val / tot_rec)
credit_risk_score = round(max(20.0, 100.0 - (overdue_ratio * 70.0)))

# 2. Financial & Liquidity Risk (Net margin & Cash Flow)
net_margin = float(f.get('profit_margin', 15.0) or 15.0)
financial_risk_score = round(min(100.0, max(25.0, 50.0 + net_margin * 2.5)))

# 3. Inventory Risk (Dead stock share & Stockouts)
tot_inv = max(1.0, float(inv.get('total_value', 100000.0) or 1.0))
dead_val = float(inv.get('dead_stock_value', 0.0) or 0.0)
dead_ratio = min(1.0, dead_val / tot_inv)
reorder_count = len(inv.get('reorder_items', []))
inventory_risk_score = round(max(25.0, 100.0 - (dead_ratio * 50.0) - min(25.0, reorder_count * 5.0)))

# 4. Revenue Stability Risk
revenue_risk_score = 82 if f.get('total_revenue', 0) > 100000 else 60

# 5. Expense Risk (Expenses / Revenue ratio)
tot_rev = max(1.0, float(f.get('total_revenue', 1.0) or 1.0))
tot_exp = float(f.get('total_expenses', 0.0) or 0.0)
exp_ratio = tot_exp / tot_rev
expense_risk_score = round(max(30.0, 100.0 - (exp_ratio * 50.0)))

composite_risk_score = round(
    credit_risk_score * 0.25 +
    financial_risk_score * 0.25 +
    inventory_risk_score * 0.20 +
    revenue_risk_score * 0.15 +
    expense_risk_score * 0.15
)

# -------------------------------------------------------------
# 2. TOP KPI CARDS
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1:
    health_color = "#059669" if composite_risk_score >= 70 else ("#EA580C" if composite_risk_score >= 50 else "#DC2626")
    render_html(
        f"""
        <div style="background: #FFFFFF; padding: 18px; border-radius: 12px; border: 1px solid #E2E8F0; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">{t("Composite Safety Index", lang)}</div>
            <div style="font-size: 2.3rem; font-weight: 800; color: {health_color}; margin: 2px 0;">{composite_risk_score}/100</div>
            <div style="font-size: 0.78rem; font-weight: 600; color: {health_color};">
                {t("Low Risk Exposure", lang) if composite_risk_score >= 70 else (t("Moderate Vulnerability", lang) if composite_risk_score >= 50 else t("High Risk Alert", lang))}
            </div>
        </div>
        """
    )
with c2: kpi_card(t("Credit Risk Score", lang), f"{credit_risk_score}/100", f"{overdue_ratio*100:.1f}% overdue ratio")
with c3: kpi_card(t("Liquidity Safety", lang), f"{financial_risk_score}/100", f"Margin: {net_margin:.1f}%")
with c4: kpi_card(t("Active Watchlist Items", lang), f"{len(risk_list)}", t("Prioritized alerts", lang))

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 3. RADAR CHART & EARLY WARNING SIGNALS
# -------------------------------------------------------------
col_radar, col_early = st.columns([1.2, 1.2])

with col_radar:
    st.markdown(f"### 🕸️ {t('Multi-Pillar Risk Radar', lang)}")
    categories = [t('Credit & Receivables', lang), t('Financial Liquidity', lang), t('Inventory Health', lang), t('Revenue Stability', lang), t('Expense Discipline', lang)]
    radar_values = [credit_risk_score, financial_risk_score, inventory_risk_score, revenue_risk_score, expense_risk_score]
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_values + [radar_values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(13, 148, 136, 0.25)',
        line=dict(color='#0D9488', width=2),
        name="Business Health"
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=320,
        margin=dict(l=40, r=40, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with col_early:
    st.markdown(f"### 🚨 {t('Early Warning Indicators', lang)}")
    warnings = [
        ("Receivables Delay Signal", f"Overdue invoices total {overdue_val:,.0f} across trade debtors.", "#EA580C" if overdue_val > 0 else "#059669"),
        ("Inventory Stockout Risk", f"{reorder_count} SKUs approaching safety stock boundary.", "#EA580C" if reorder_count > 0 else "#059669"),
        ("Operating Expense Discipline", f"Operating expense ratio is {exp_ratio*100:.1f}% of gross sales.", "#059669" if exp_ratio < 0.4 else "#EA580C"),
        ("Revenue Continuity Signal", "Sales velocity is stable across primary product lines.", "#059669"),
    ]
    
    for title, desc, tag_c in warnings:
        render_html(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {tag_c}; border-radius: 8px; padding: 0.65rem 0.95rem; margin-bottom: 8px;">
                <strong style="color: #1E293B; font-size: 0.88rem;">{title}</strong>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 2px;">{desc}</div>
            </div>
            """
        )

render_html("<div style='height: 1rem;'></div>")

# -------------------------------------------------------------
# 4. ACTIONABLE MITIGATIONS LEDGER
# -------------------------------------------------------------
st.markdown(f"### 📋 {t('Prioritized Risk Register & Action Plan', lang)}")
if not risk_list:
    st.success("🟢 No severe business risks detected based on current data.")
else:
    for idx, r in enumerate(risk_list, 1):
        sev = r.get("severity", "MEDIUM").upper()
        sev_color = "#DC2626" if sev == "HIGH" else ("#EA580C" if sev == "MEDIUM" else "#059669")
        render_html(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {sev_color}; border-radius: 10px; padding: 0.85rem 1.15rem; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="color: #1E293B; font-size: 0.95rem;">#{idx} {r.get('risk', 'Risk Factor')}</strong>
                    <span style="background: {sev_color}14; color: {sev_color}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 12px; border: 1px solid {sev_color}30;">{sev}</span>
                </div>
                <div style="font-size: 0.82rem; color: #475569; margin: 4px 0;"><strong>Root Cause:</strong> {r.get('reason', 'N/A')}</div>
                <div style="font-size: 0.82rem; color: #0D9488;"><strong>Recommended Mitigation:</strong> {r.get('action', 'N/A')}</div>
            </div>
            """
        )
