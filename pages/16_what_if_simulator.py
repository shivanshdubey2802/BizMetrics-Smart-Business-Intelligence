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

st.set_page_config(page_title="BizMetrics - What-If Simulator", layout="wide")
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
    t("What-If Decision Simulator", lang),
    t("Simulate strategic price changes, sales volume shifts, supplier costs, and overhead variations.", lang)
)

if "pipeline_result" not in st.session_state:
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

# Baseline numbers
base_rev = float(f.get("total_revenue", 200000.0) or 200000.0)
base_cogs = float(f.get("cogs", 140000.0) or 140000.0)
base_exp = float(f.get("total_expenses", 30000.0) or 30000.0)
base_gp = base_rev - base_cogs
base_np = base_gp - base_exp
base_margin = (base_np / max(1.0, base_rev)) * 100

# -------------------------------------------------------------
# 1. INTERACTIVE PARAMETER SLIDERS
# -------------------------------------------------------------
st.markdown(f"### 🎛️ {t('Strategic Levers & Assumptions', lang)}")

col_s1, col_s2, col_s3, col_s4 = st.columns(4)

with col_s1:
    price_change_pct = st.slider("Product Selling Price (Δ %)", min_value=-25, max_value=25, value=0, step=1, help="Simulate a general markup or discount")
with col_s2:
    volume_change_pct = st.slider("Sales Volume (Δ %)", min_value=-50, max_value=50, value=10, step=5, help="Simulate customer footfall & order volume changes")
with col_s3:
    cost_change_pct = st.slider("Supplier Cost / COGS (Δ %)", min_value=-20, max_value=20, value=0, step=1, help="Simulate raw material or procurement price changes")
with col_s4:
    expense_change_pct = st.slider("Operating Expenses (Δ %)", min_value=-30, max_value=30, value=0, step=5, help="Simulate changes in rent, electricity, marketing or wages")

# -------------------------------------------------------------
# 2. SIMULATION ENGINE CALCULATIONS
# -------------------------------------------------------------
p_mult = 1.0 + (price_change_pct / 100.0)
v_mult = 1.0 + (volume_change_pct / 100.0)
c_mult = 1.0 + (cost_change_pct / 100.0)
e_mult = 1.0 + (expense_change_pct / 100.0)

# Simulated metrics
sim_rev = base_rev * p_mult * v_mult
sim_cogs = base_cogs * c_mult * v_mult
sim_gp = sim_rev - sim_cogs
sim_exp = base_exp * e_mult
sim_np = sim_gp - sim_exp
sim_margin = (sim_np / max(1.0, sim_rev)) * 100

# Deltas
delta_rev = sim_rev - base_rev
delta_np = sim_np - base_np
delta_margin = sim_margin - base_margin

# Break-even simulation
sim_cm_ratio = max(0.05, sim_gp / max(1.0, sim_rev))
sim_bep_rev = sim_exp / sim_cm_ratio

# -------------------------------------------------------------
# 3. SIMULATED KPI RESULTS ROW
# -------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Simulated Revenue", format_currency(sim_rev), f"{delta_rev:+,.0f} ({delta_rev/base_rev*100:+.1f}%)")
with k2:
    kpi_card("Simulated Net Profit", format_currency(sim_np), f"{delta_np:+,.0f} ({delta_np/max(1, abs(base_np))*100:+.1f}%)")
with k3:
    kpi_card("Simulated Net Margin", f"{sim_margin:.1f}%", f"{delta_margin:+.1f}% vs baseline")
with k4:
    kpi_card("Simulated Break-Even", format_currency(sim_bep_rev), f"Safety buffer: {((sim_rev - sim_bep_rev)/max(1, sim_rev)*100):.1f}%")

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 4. SIDE-BY-SIDE SCENARIO COMPARISON CHART
# -------------------------------------------------------------
col_chart, col_narrative = st.columns([1.5, 1.0])

with col_chart:
    st.markdown(f"### 📊 {t('Baseline vs Simulated Financial Scenario', lang)}")
    categories = ["Revenue", "COGS", "Operating Expenses", "Net Profit"]
    base_values = [base_rev, base_cogs, base_exp, base_np]
    sim_values = [sim_rev, sim_cogs, sim_exp, sim_np]
    
    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        x=categories,
        y=base_values,
        name="Current Baseline",
        marker_color="#94A3B8"
    ))
    fig_comp.add_trace(go.Bar(
        x=categories,
        y=sim_values,
        name="Simulated Scenario",
        marker_color="#0D9488"
    ))
    base_l = get_base_layout()
    base_l.pop('title', None)
    base_l.update(dict(
        barmode='group',
        height=340,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis_title="Amount (₹)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    ))
    fig_comp.update_layout(**base_l)
    st.plotly_chart(fig_comp, use_container_width=True)

with col_narrative:
    st.markdown(f"### 💡 {t('Strategic Executive Impact', lang)}")
    
    sentiment_color = "#059669" if delta_np >= 0 else "#DC2626"
    sentiment_label = "POSITIVE VALUE CREATION" if delta_np >= 0 else "MARGIN COMPRESSION RISK"
    
    render_html(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {sentiment_color}; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-size: 0.75rem; font-weight: 700; color: {sentiment_color};">{sentiment_label}</div>
            <h4 style="margin: 4px 0 8px 0; color: #1E293B;">Net Profit Impact: {format_currency(delta_np)}</h4>
            <p style="font-size: 0.85rem; color: #475569; line-height: 1.5; margin: 0 0 10px 0;">
                Under your chosen levers (Price: <strong>{price_change_pct:+d}%</strong>, Volume: <strong>{volume_change_pct:+d}%</strong>, COGS: <strong>{cost_change_pct:+d}%</strong>, Opex: <strong>{expense_change_pct:+d}%</strong>),
                bottom-line profit moves from <strong>{format_currency(base_np)}</strong> to <strong>{format_currency(sim_np)}</strong>.
            </p>
            <div style="background: #FAF5EE; border: 1px solid #E2DBD0; border-radius: 8px; padding: 0.65rem 0.85rem; font-size: 0.8rem; color: #334155;">
                • <strong>Break-Even Shift:</strong> Monthly revenue must reach <strong>{format_currency(sim_bep_rev)}</strong> to cover fixed overhead.<br>
                • <strong>Operating Cushion:</strong> Revenue sits <strong>{((sim_rev - sim_bep_rev)/max(1, sim_rev)*100):.1f}%</strong> above break-even.
            </div>
        </div>
        """
    )
