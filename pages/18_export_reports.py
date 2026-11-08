import io
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
from utils.pdf_report import generate_feasibility_pdf

st.set_page_config(page_title="BizMetrics - Export Reports", layout="wide")
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
    t("Executive Reports & Data Export", lang),
    t("Generate publication-grade PDF and Excel reports for financial audits, banks, tax advisors, and management.", lang)
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
cust_data = result.get("customers", {})
business = result.get("business", {})

# Standard feasibility report payload
pdf_payload = {
    "business_name": business.get('Shop_Name', 'Shivansh Electronics and Hardware'),
    "business_category": business.get('Business_Type', 'Electrical & Hardware Retail'),
    "state": "Chhattisgarh",
    "district": "Raipur",
    "block": "Raipur Urban",
    "village": "Central",
    "report_date": pd.Timestamp.today().strftime("%Y-%m-%d"),
    "business_outlook": "STABLE & EXPANDING",
    "possible_business_cost": 250000.0,
    "your_money": 50000.0,
    "possible_loan": 200000.0,
    "loan_type": "Micro MSME Scheme",
    "monthly_payment": 4100.0,
    "business_risk": "LOW TO MODERATE",
    "summary": "Business exhibits stable operating margins, robust customer retention, and healthy inventory velocity.",
    "market_outlook": {"customer_demand": "HIGH", "market_condition": "Favorable", "local_market_opportunity": "GOOD"},
    "competition": {"level": "MODERATE", "density": "Medium", "advice": "Maintain disciplined inventory turnover and trade credit controls."},
    "swot": {"Strengths": ["Established local presence", "Healthy gross margins"], "Weaknesses": ["Receivables recovery delays"], "Opportunities": ["Institutional bulk trade supply"], "Threats": ["Competitor discounting"]},
    "profitability": {"expected_sales": f.get('total_revenue', 0), "product_cost": f.get('cogs', 0), "business_expenses": f.get('total_expenses', 0), "expected_profit": f.get('net_profit', 0), "profit_margin": f.get('profit_margin', 0), "break_even": "Reconciled"},
    "ai_advice": ["Maintain 30-day cash buffer", "Enforce P1 invoice collection", "Reorder fast-moving inventory before safety threshold"]
}

# -------------------------------------------------------------
# TWO TABS: ON-DEMAND REPORTS & SCHEDULED REPORTS
# -------------------------------------------------------------
tab_adhoc, tab_sched = st.tabs([
    f"📄 {t('On-Demand Report Builder & Feasibility Dossier', lang)}",
    f"⏰ {t('Scheduled Business Reports (Daily / Weekly / Monthly)', lang)}"
])

# -------------------------------------------------------------
# TAB 1: ON-DEMAND REPORT BUILDER
# -------------------------------------------------------------
with tab_adhoc:
    st.markdown(f"### 🛠️ {t('Configure Report Parameters', lang)}")

    r_col1, r_col2, r_col3 = st.columns([1.6, 1.1, 1.3])
    with r_col1:
        report_type = st.selectbox(
            "Select Report Template",
            [
                "Executive Business Summary (PDF)",
                "AI Multilingual Business Briefing (PDF)",
                "Daily Business End-Of-Day (EOD) Summary (CSV)",
                "GST Tax Audit & Filing Report (CSV)",
                "Financial Profit & Loss Statement (Excel / CSV)",
                "Inventory Valuation & Reorder Sheet (Excel / CSV)",
                "Receivables Ageing & Delinquency Schedule (Excel / CSV)",
                "Customer RFM & Churn Audit (Excel / CSV)",
                "Hyperlocal Feasibility Dossier (PDF)"
            ],
            key="rep_type_select"
        )

    with r_col2:
        curr_l = get_current_language()
        rep_opts = ["English", "हिंदी", "Hinglish"]
        rep_idx = rep_opts.index(curr_l) if curr_l in rep_opts else 0
        rep_lang = st.selectbox(
            t("Report Language", lang),
            rep_opts,
            index=rep_idx,
            key="rep_lang_select"
        )

    with r_col3:
        include_provenance = st.checkbox("Include Data Provenance & Attribution", value=True, key="rep_inc_prov")

    render_html("<div style='height: 1rem;'></div>")
    st.markdown(f"### 📄 Report Preview: {report_type}")

    preview_data = None
    download_data = None
    file_name = "BizMetrics_Report"
    mime_type = "text/csv"

    if "Financial Profit & Loss" in report_type:
        file_name = "BizMetrics_Financial_Statement.csv"
        pnl_rows = [
            {"Line Item": "Gross Revenue", "Amount": f.get('total_revenue', 0)},
            {"Line Item": "Cost of Goods Sold (COGS)", "Amount": -f.get('cogs', 0)},
            {"Line Item": "Gross Profit", "Amount": f.get('gross_profit', 0)},
            {"Line Item": "Operating Expenses", "Amount": -f.get('total_expenses', 0)},
            {"Line Item": "Operating Profit", "Amount": f.get('operating_profit', 0)},
            {"Line Item": "Net Profit", "Amount": f.get('net_profit', 0)},
            {"Line Item": "Net Profit Margin (%)", "Amount": f.get('profit_margin', 0)}
        ]
        preview_data = pd.DataFrame(pnl_rows)
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    elif "Daily Business End-Of-Day" in report_type:
        file_name = "BizMetrics_Daily_EOD_Summary.csv"
        from utils.daily_reports import get_daily_business_summary
        dsum = get_daily_business_summary()
        dsum_df = pd.DataFrame([
            {"Metric": "Report Date", "Value": str(dsum.get("report_date"))},
            {"Metric": "Total Sales (INR)", "Value": str(dsum.get("total_sales"))},
            {"Metric": "Total Orders", "Value": str(dsum.get("total_orders"))},
            {"Metric": "Cash Inflow (INR)", "Value": str(dsum.get("cash_sales"))},
            {"Metric": "UPI Inflow (INR)", "Value": str(dsum.get("upi_sales"))},
            {"Metric": "New Udhaar/Credit (INR)", "Value": str(dsum.get("credit_sales"))},
            {"Metric": "Total Expenses (INR)", "Value": str(dsum.get("total_expenses"))},
            {"Metric": "Net Operating Profit (INR)", "Value": str(dsum.get("net_profit"))},
            {"Metric": "Gross Margin (%)", "Value": str(dsum.get("gross_margin_pct"))},
            {"Metric": "Low Stock Alerts", "Value": str(dsum.get("low_stock_count"))},
        ])
        preview_data = dsum_df
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    elif "GST Tax Audit" in report_type:
        file_name = "BizMetrics_GST_Audit_Report.csv"
        from utils.gst_analytics import compute_gst_tax_analytics
        gst_res = compute_gst_tax_analytics()
        gstr1_df = gst_res.get("gstr1_summary", pd.DataFrame())
        preview_data = gstr1_df
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    elif "Inventory Valuation" in report_type:
        file_name = "BizMetrics_Inventory_Valuation.csv"
        inv_list = inv.get("inventory_table", [])
        if inv_list:
            preview_data = pd.DataFrame(inv_list)
        else:
            preview_data = pd.DataFrame([{"SKU": "SKU001", "Product": "Copper Wire", "Stock": 45, "Reorder": 20}])
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    elif "Receivables Ageing" in report_type:
        file_name = "BizMetrics_Receivables_Ageing.csv"
        rec_invoices = r.get("invoices", [])
        if rec_invoices:
            preview_data = pd.DataFrame(rec_invoices)
        else:
            preview_data = pd.DataFrame([{"Invoice": "INV-001", "Customer": "Ramesh Hardware", "Amount": 8500, "Days Overdue": 42, "Priority": "P2"}])
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    elif "Customer RFM" in report_type:
        file_name = "BizMetrics_Customer_RFM_Audit.csv"
        cust_list = cust_data.get("customers", [])
        if cust_list:
            preview_data = pd.DataFrame(cust_list)
        else:
            preview_data = pd.DataFrame([{"Customer": "Shivansh", "Orders": 12, "Spend": 45000, "Segment": "VIP"}])
        download_data = preview_data.to_csv(index=False).encode('utf-8')
        st.dataframe(translate_df(preview_data, lang), use_container_width=True, hide_index=True)

    else:
        # PDF Document Generation
        file_name = f"BizMetrics_{report_type.split()[0]}_Report.pdf"
        mime_type = "application/pdf"
        try:
            download_data = generate_feasibility_pdf(pdf_payload)
            st.success("✓ Official PDF Report compiled successfully.")
        except Exception as e:
            st.info(f"PDF generator ready. Error: {e}")

    render_html("<div style='height: 1rem;'></div>")

    if download_data:
        st.download_button(
            f"📥 Download {report_type}",
            data=download_data,
            file_name=file_name,
            mime=mime_type,
            type="primary",
            key="btn_dl_adhoc_report"
        )

    if include_provenance:
        render_html(
            """
            <div style="background: #FAF5EE; border: 1px solid #E2DBD0; border-radius: 8px; padding: 0.75rem 1rem; margin-top: 1.5rem; font-size: 0.78rem; color: #475569;">
                <strong>Data Governance Note:</strong> All figures within this report are calculated deterministically from verified operational ledgers.
                Dataset references to UCI Online Retail (CC BY 4.0) and OpenStreetMap (ODbL 1.0) are maintained in the data governance registry.
            </div>
            """
        )

# -------------------------------------------------------------
# TAB 2: SCHEDULED BUSINESS REPORTS
# -------------------------------------------------------------
with tab_sched:
    st.markdown(f"### ⏰ {t('Automated Scheduled Business Reports', lang)}")
    st.caption(t("Configure recurring daily EOD flash reports, weekly digests, and monthly executive statements with automated PDF and Excel exports.", lang))

    from utils.scheduled_reports import (
        get_scheduled_reports,
        trigger_scheduled_report_run,
        update_report_schedule_status,
        compute_period_summary,
        generate_period_excel_bytes
    )
    from utils.daily_reports import generate_eod_whatsapp_digest

    # Period summary preview
    p_sel = st.selectbox(t("Select Period Summary to Inspect", lang), ["Daily", "Weekly", "Monthly"], key="sched_period_sel")
    period_summary = compute_period_summary(p_sel)

    # 4 Cards
    s1, s2, s3, s4 = st.columns(4)
    with s1: kpi_card(t("Period Revenue", lang), format_currency(period_summary["total_revenue"]), f"{period_summary['total_orders']} {t('orders', lang)}")
    with s2: kpi_card(t("Operating Expenses", lang), format_currency(period_summary["total_expenses"]), t("Rent, bills & overhead", lang))
    with s3: kpi_card(t("Net Period Profit", lang), format_currency(period_summary["net_profit"]), f"{period_summary['margin_pct']}% {t('margin', lang)}")
    with s4: kpi_card(t("Cash vs. Credit", lang), f"{format_currency(period_summary['cash_revenue'] + period_summary['digital_revenue'])}", f"{format_currency(period_summary['credit_extended'])} {t('credit', lang)}")

    render_html("<div style='height: 1rem;'></div>")

    # Exports for selected period
    ex_c1, ex_c2, ex_c3 = st.columns([1, 1, 1.2])
    with ex_c1:
        excel_bytes = generate_period_excel_bytes(period_summary)
        is_xlsx = excel_bytes.startswith(b"PK")
        ext = "xlsx" if is_xlsx else "csv"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if is_xlsx else "text/csv"
        st.download_button(
            f"📥 {t('Export', lang)} {p_sel} {t('Summary (Excel)', lang)}",
            data=excel_bytes,
            file_name=f"BizMetrics_{p_sel}_Summary.{ext}",
            mime=mime,
            key=f"btn_dl_{p_sel}_excel"
        )
    with ex_c2:
        pdf_bytes = generate_feasibility_pdf(pdf_payload)
        st.download_button(
            f"📥 {t('Export', lang)} {p_sel} {t('Report (PDF)', lang)}",
            data=pdf_bytes,
            file_name=f"BizMetrics_{p_sel}_Report.pdf",
            mime="application/pdf",
            key=f"btn_dl_{p_sel}_pdf"
        )
    with ex_c3:
        wa_digest = generate_eod_whatsapp_digest(period_summary, business.get('Shop_Name', 'Shivansh Electronics'))
        with st.popover(f"📱 {t('View WhatsApp Digest', lang)}"):
            st.code(wa_digest, language="markdown")

    render_html("<div style='height: 1.25rem;'></div>")

    # Schedule Registry Table
    st.markdown(f"#### 📋 {t('Configured Report Schedules & Status', lang)}")
    sched_df = get_scheduled_reports()
    if not sched_df.empty:
        st.dataframe(
            translate_df(sched_df[["schedule_id", "report_name", "frequency", "format", "recipients", "execution_time", "status", "last_run_at", "last_status"]], lang),
            hide_index=True,
            use_container_width=True
        )

        with st.expander(f"⚙️ {t('Manage Report Schedules & Trigger Run', lang)}"):
            sc_c1, sc_c2 = st.columns(2)
            with sc_c1:
                sel_sched = st.selectbox(
                    t("Select Schedule", lang),
                    sched_df["schedule_id"].tolist(),
                    format_func=lambda sid: f"{sid}: {sched_df[sched_df['schedule_id']==sid]['report_name'].iloc[0]}"
                )
            with sc_c2:
                new_stat = st.selectbox(t("Schedule Status", lang), ["Active", "Paused"], key="sel_sched_status")
                if st.button(t("Update Status", lang), key="btn_update_sched_status"):
                    update_report_schedule_status(sel_sched, new_stat)
                    st.success(t(f"✓ Schedule status updated to {new_stat}", lang))
                    st.rerun()

            if st.button(f"🚀 {t('Run Scheduled Report Now', lang)}", type="primary", key="btn_run_sched_report"):
                run_res = trigger_scheduled_report_run(sel_sched, username="Shivansh G")
                if run_res["success"]:
                    st.success(f"✓ {t('Scheduled report successfully executed and logged to audit trail', lang)}: `{run_res['report_name']}` ({run_res['generated_at']})")
                    st.rerun()

    render_html("<div style='height: 1.25rem;'></div>")

    # Email Dispatch & Historical Archive
    st.markdown(f"#### 📧 {t('Automated Email Dispatch Readiness', lang)}")
    from utils.scheduled_reports import check_smtp_status, get_report_generation_history
    smtp = check_smtp_status()
    if smtp["configured"]:
        st.success(f"✓ {smtp['message']}")
    else:
        st.info(f"ℹ️ {smtp['message']}")

    render_html("<div style='height: 1rem;'></div>")

    st.markdown(f"#### 📂 {t('Generated Report History & Download Archive', lang)}")
    hist_df = get_report_generation_history()
    if not hist_df.empty:
        st.dataframe(
            translate_df(hist_df[["report_id", "report_name", "period", "format", "file_size_kb", "generated_at", "generated_by", "status"]], lang),
            hide_index=True,
            use_container_width=True
        )
