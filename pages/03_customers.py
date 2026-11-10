import io
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
from customer_qr_bills import render_customer_qr_and_bills, get_customer_bills, get_customer_qr, clear_customer_profile_cache
from utils.database import (
    get_customer_master_table_df,
    get_customer_kpi_summary,
    add_customer_to_db,
    edit_customer_in_db,
    delete_customer_from_db,
    get_customer_detail_from_db,
    DEFAULT_SHOP_ID,
)

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
render_header(
    "Customer Management & Intelligence",
    "Comprehensive database-driven customer management: directory, credit ledgers, RFM segmentation, and digital QR passes."
)

lang = get_current_language()
shop_id = st.session_state.get("shop_id", DEFAULT_SHOP_ID)

# ------------------------------------------------------------------------------
# 1. FETCH DATABASE-DRIVEN DATA & KPIS
# ------------------------------------------------------------------------------
try:
    kpis = get_customer_kpi_summary(shop_id)
    df_cust = get_customer_master_table_df(shop_id)
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    kpis = {
        "total_customers": 0, "active_customers": 0, "new_customers": 0,
        "repeat_customers": 0, "repeat_pct": 0.0, "outstanding_dues": 0.0, "total_revenue": 0.0
    }
    df_cust = pd.DataFrame()

# ------------------------------------------------------------------------------
# 2. TOP 6 DATABASE-DRIVEN KPI CARDS
# ------------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
with c1:
    kpi_card(
        "Total Customers",
        f"{kpis.get('total_customers', 0)}",
        "Registered accounts in database"
    )
with c2:
    kpi_card(
        "Active Customers",
        f"{kpis.get('active_customers', 0)}",
        "Purchased within last 90 days"
    )
with c3:
    kpi_card(
        "New Customers",
        f"{kpis.get('new_customers', 0)}",
        "Joined or ≤2 orders in last 240 days"
    )

c4, c5, c6 = st.columns(3)
with c4:
    rep_cnt = kpis.get("repeat_customers", 0)
    rep_pct = kpis.get("repeat_pct", 0.0)
    kpi_card(
        "Repeat Customers",
        f"{rep_cnt} ({rep_pct:.1f}%)",
        "Multiple verified sales in ledger"
    )
with c5:
    kpi_card(
        "Outstanding Customer Dues",
        format_currency(kpis.get("outstanding_dues", 0.0)),
        "Total pending ledger receivables"
    )
with c6:
    kpi_card(
        "Total Customer Revenue",
        format_currency(kpis.get("total_revenue", 0.0)),
        "Cumulative verified purchase volume"
    )

render_html("<div style='height: 0.85rem;'></div>")

# ------------------------------------------------------------------------------
# 3. MAIN WORKSPACE TABS
# ------------------------------------------------------------------------------
tab_dir, tab_manage, tab_profile, tab_intel = st.tabs([
    t("📇 Customer Records & Directory", lang),
    t("➕ Manage Customers", lang),
    t("👤 View Customer Profile & QR Pass", lang),
    t("🎯 RFM & Churn Intelligence", lang),
])

# ==============================================================================
# TAB 1: CUSTOMER RECORDS & DIRECTORY
# ==============================================================================
with tab_dir:
    st.markdown(f"### 📇 {t('Customer Directory & Ledger Records', lang)}")
    st.caption(t("All metrics and records are synchronized directly with live database transactions.", lang))

    if df_cust.empty:
        st.info(t("No customer records currently exist in the database. Use the 'Manage Customers' tab to add your first customer.", lang))
    else:
        # Search & Filter Controls
        f1, f2, f3, f4 = st.columns([1.8, 1.0, 1.0, 1.0])
        with f1:
            search_query = st.text_input(
                t("Search by ID, Name, Mobile or Business", lang),
                value="",
                placeholder="e.g. CUST001, Shivansh, 98765...",
                key="cust_dir_search_input"
            ).strip().lower()

        with f2:
            city_list = ["All"] + sorted([c for c in df_cust["city"].dropna().unique() if str(c).strip()])
            sel_city = st.selectbox(t("City", lang), city_list, key="cust_dir_city_filter")

        with f3:
            type_list = ["All"] + sorted([t_val for t_val in df_cust["customer_type"].dropna().unique() if str(t_val).strip()])
            sel_type = st.selectbox(t("Customer Type", lang), type_list, key="cust_dir_type_filter")

        with f4:
            status_list = ["All", "Active", "New", "At Risk", "Inactive"]
            sel_status = st.selectbox(t("Customer Status", lang), status_list, key="cust_dir_status_filter")

        # Apply Filters
        filtered_df = df_cust.copy()
        if search_query:
            id_match = filtered_df["customer_id"].astype(str).str.lower().str.contains(search_query)
            name_match = filtered_df["customer_name"].astype(str).str.lower().str.contains(search_query)
            mob_match = filtered_df["contact_number"].astype(str).str.lower().str.contains(search_query)
            biz_match = filtered_df["business_name"].astype(str).str.lower().str.contains(search_query)
            filtered_df = filtered_df[id_match | name_match | mob_match | biz_match]

        if sel_city != "All":
            filtered_df = filtered_df[filtered_df["city"] == sel_city]

        if sel_type != "All":
            filtered_df = filtered_df[filtered_df["customer_type"] == sel_type]

        if sel_status != "All":
            filtered_df = filtered_df[filtered_df["customer_status"] == sel_status]

        # Results Count
        st.markdown(
            f"<div style='font-size: 0.82rem; color: #64748B; margin-bottom: 0.4rem; font-weight: 500;'>"
            f"{t('Showing', lang)} <b>{len(filtered_df)}</b> {t('of', lang)} <b>{len(df_cust)}</b> {t('customer records', lang)}"
            f"</div>",
            unsafe_allow_html=True
        )

        # Build Display DataFrame with EXACT 11 REQUIRED COLUMNS
        display_df = pd.DataFrame()
        display_df["Customer ID"] = filtered_df["customer_id"]
        display_df["Customer Name"] = filtered_df["customer_name"]
        display_df["Mobile Number"] = filtered_df["contact_number"].fillna("").astype(str)
        display_df["Email"] = filtered_df["email"].fillna("").astype(str)
        display_df["City"] = filtered_df["city"].fillna("Raipur").astype(str)
        display_df["Customer Type"] = filtered_df["customer_type"].fillna("Retail Customer").astype(str)
        display_df["Total Purchases"] = filtered_df["total_purchases"].apply(lambda v: format_currency(float(v or 0.0)))
        display_df["Total Paid"] = filtered_df["total_paid"].apply(lambda v: format_currency(float(v or 0.0)))
        display_df["Outstanding Amount"] = filtered_df["outstanding_amount"].apply(lambda v: format_currency(float(v or 0.0)))
        display_df["Last Purchase Date"] = filtered_df["last_purchase_date"].fillna("").apply(
            lambda d: str(d)[:10] if str(d).strip() and str(d) != "None" else "Never"
        )
        display_df["Customer Status"] = filtered_df["customer_status"]

        st.dataframe(
            translate_df(display_df, lang),
            use_container_width=True,
            hide_index=True
        )

        # Export Buttons
        render_html("<div style='height: 0.5rem;'></div>")
        e_col1, e_col2, _ = st.columns([1.2, 1.4, 2.4])
        with e_col1:
            # CSV Export
            csv_buffer = display_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📥 {t('Export to CSV', lang)}",
                data=csv_buffer,
                file_name=f"bizmetrics_customers_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="btn_export_cust_csv",
                use_container_width=True
            )

        with e_col2:
            # Excel (.xlsx) Export
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                display_df.to_excel(writer, sheet_name="Customers", index=False)
            st.download_button(
                label=f"📊 {t('Export to Excel (.xlsx)', lang)}",
                data=excel_buffer.getvalue(),
                file_name=f"bizmetrics_customers_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_export_cust_excel",
                use_container_width=True
            )

# ==============================================================================
# TAB 2: MANAGE CUSTOMERS (ADD / EDIT / DELETE)
# ==============================================================================
with tab_manage:
    st.markdown(f"### ⚙️ {t('Customer Account Operations', lang)}")
    st.caption(t("Add new accounts, update contact and credit profiles, or safely delete accounts with relationship checks.", lang))

    action_mode = st.radio(
        t("Select Operation", lang),
        ["Add New Customer", "Edit Customer Details", "Delete Customer"],
        format_func=lambda x: t(x, lang),
        horizontal=True,
        key="cust_manage_action_mode"
    )

    render_html("<div style='height: 0.5rem;'></div>")

    # --------------------------------------------------------------------------
    # SUB-OPERATION A: ADD NEW CUSTOMER
    # --------------------------------------------------------------------------
    if action_mode == "Add New Customer":
        st.markdown(f"#### ➕ {t('Add New Customer Account', lang)}")
        with st.form("form_add_new_customer", clear_on_submit=True):
            a_col1, a_col2 = st.columns(2)
            with a_col1:
                new_cid = st.text_input(
                    t("Customer ID (leave blank to auto-generate)", lang),
                    placeholder="e.g. CUST041",
                    key="add_cid"
                ).strip().upper()
                new_cname = st.text_input(
                    t("Customer Full Name *", lang),
                    placeholder="e.g. Anand Sharma",
                    key="add_cname"
                ).strip()
                new_bname = st.text_input(
                    t("Business / Shop Name", lang),
                    placeholder="e.g. Sharma Hardware Store",
                    key="add_bname"
                ).strip()
                new_mob = st.text_input(
                    t("Mobile Number (10 digits) *", lang),
                    placeholder="e.g. 9876543210",
                    key="add_mob"
                ).strip()

            with a_col2:
                new_email = st.text_input(
                    t("Email Address", lang),
                    placeholder="e.g. anand@example.com",
                    key="add_email"
                ).strip()
                new_city = st.text_input(
                    t("City", lang),
                    value="Raipur",
                    placeholder="e.g. Raipur, Bhilai, Durg",
                    key="add_city"
                ).strip()
                new_type = st.selectbox(
                    t("Customer Type", lang),
                    ["Retail Customer", "Wholesaler", "Contractor", "Institutional Buyer", "Walk-in"],
                    key="add_type"
                )
                new_addr = st.text_input(
                    t("Address / Locality", lang),
                    placeholder="e.g. Station Road Commercial Complex",
                    key="add_addr"
                ).strip()
                new_due = st.number_input(
                    t("Initial Ledger Outstanding Balance (₹)", lang),
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    key="add_due"
                )

            submitted_add = st.form_submit_button(
                f"✅ {t('Create Customer Account', lang)}",
                type="primary",
                use_container_width=True
            )

            if submitted_add:
                if not new_cname:
                    st.error(t("⚠️ Customer name is required.", lang))
                elif not new_mob:
                    st.error(t("⚠️ Mobile number is required.", lang))
                else:
                    success, msg, created_id = add_customer_to_db(
                        customer_name=new_cname,
                        contact_number=new_mob,
                        email=new_email,
                        city=new_city,
                        customer_type=new_type,
                        business_name=new_bname,
                        address=new_addr,
                        customer_id=new_cid or None,
                        outstanding_amount=new_due,
                        shop_id=shop_id
                    )
                    if success:
                        st.success(f"🎉 {t(msg, lang)} (ID: <b>{created_id}</b>)")
                        clear_customer_profile_cache()
                        st.rerun()
                    else:
                        st.error(f"❌ {t(msg, lang)}")

    # --------------------------------------------------------------------------
    # SUB-OPERATION B: EDIT CUSTOMER DETAILS
    # --------------------------------------------------------------------------
    elif action_mode == "Edit Customer Details":
        st.markdown(f"#### ✏️ {t('Edit Existing Customer Profile', lang)}")

        if df_cust.empty:
            st.info(t("No customers available to edit.", lang))
        else:
            cust_options = {
                r["customer_id"]: f"{r['customer_id']} — {r['customer_name']} ({r.get('business_name') or r['city']})"
                for _, r in df_cust.iterrows()
            }
            edit_cid = st.selectbox(
                t("Select Customer to Edit", lang),
                options=list(cust_options.keys()),
                format_func=lambda x: cust_options[x],
                key="edit_select_cid"
            )

            curr_detail = get_customer_detail_from_db(edit_cid, shop_id=shop_id) or {}

            with st.form("form_edit_customer"):
                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    e_name = st.text_input(
                        t("Customer Full Name *", lang),
                        value=curr_detail.get("customer_name", ""),
                        key="edit_cname"
                    ).strip()
                    e_bname = st.text_input(
                        t("Business / Shop Name", lang),
                        value=curr_detail.get("business_name", ""),
                        key="edit_bname"
                    ).strip()
                    e_mob = st.text_input(
                        t("Mobile Number *", lang),
                        value=str(curr_detail.get("contact_number") or ""),
                        key="edit_mob"
                    ).strip()
                    e_email = st.text_input(
                        t("Email Address", lang),
                        value=curr_detail.get("email", ""),
                        key="edit_email"
                    ).strip()

                with e_col2:
                    e_city = st.text_input(
                        t("City", lang),
                        value=curr_detail.get("city", "Raipur"),
                        key="edit_city"
                    ).strip()

                    all_types = ["Retail Customer", "Wholesaler", "Contractor", "Institutional Buyer", "Walk-in"]
                    c_type_val = curr_detail.get("customer_type", "Retail Customer")
                    t_idx = all_types.index(c_type_val) if c_type_val in all_types else 0
                    e_type = st.selectbox(t("Customer Type", lang), all_types, index=t_idx, key="edit_type")

                    e_addr = st.text_input(
                        t("Address / Locality", lang),
                        value=curr_detail.get("address", ""),
                        key="edit_addr"
                    ).strip()
                    e_due = st.number_input(
                        t("Ledger Outstanding Balance (₹)", lang),
                        min_value=0.0,
                        value=float(curr_detail.get("outstanding_amount") or 0.0),
                        step=100.0,
                        key="edit_due"
                    )

                submitted_edit = st.form_submit_button(
                    f"💾 {t('Save Customer Changes', lang)}",
                    type="primary",
                    use_container_width=True
                )

                if submitted_edit:
                    if not e_name:
                        st.error(t("⚠️ Customer name cannot be empty.", lang))
                    else:
                        success, msg = edit_customer_in_db(
                            customer_id=edit_cid,
                            customer_name=e_name,
                            contact_number=e_mob,
                            email=e_email,
                            city=e_city,
                            customer_type=e_type,
                            business_name=e_bname,
                            address=e_addr,
                            outstanding_amount=e_due,
                            shop_id=shop_id
                        )
                        if success:
                            st.success(f"✅ {t(msg, lang)}")
                            clear_customer_profile_cache(edit_cid)
                            st.rerun()
                        else:
                            st.error(f"❌ {t(msg, lang)}")

    # --------------------------------------------------------------------------
    # SUB-OPERATION C: DELETE CUSTOMER
    # --------------------------------------------------------------------------
    elif action_mode == "Delete Customer":
        st.markdown(f"#### 🗑️ {t('Delete Customer Account', lang)}")

        if df_cust.empty:
            st.info(t("No customers available to delete.", lang))
        else:
            del_options = {
                r["customer_id"]: f"{r['customer_id']} — {r['customer_name']} (Orders: {r.get('total_orders', 0)}, Dues: {format_currency(r.get('outstanding_amount', 0))})"
                for _, r in df_cust.iterrows()
            }
            del_cid = st.selectbox(
                t("Select Customer to Remove", lang),
                options=list(del_options.keys()),
                format_func=lambda x: del_options[x],
                key="del_select_cid"
            )

            # Audit check on relationship references
            from utils.database import get_db_cursor
            with get_db_cursor(commit=False) as cur:
                cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE customer_id = ?", (del_cid,))
                sales_ref_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM receivables WHERE customer_id = ? AND LOWER(status) NOT IN ('settled', 'paid')", (del_cid,))
                rec_ref_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM customer_support_tickets WHERE customer_id = ?", (del_cid,))
                ticket_ref_count = cur.fetchone()[0]

            render_html(
                f"""
                <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 1rem; margin: 0.8rem 0;">
                    <div style="font-weight: 700; color: #1E293B; margin-bottom: 0.5rem;">🔗 {t('Database Relationship Inspection', lang)}:</div>
                    <div style="display: flex; gap: 24px; font-size: 0.9rem;">
                        <div>📦 <b>{sales_ref_count}</b> {t('Sales Transactions', lang)}</div>
                        <div>⚠️ <b>{rec_ref_count}</b> {t('Unsettled Receivables', lang)}</div>
                        <div>💬 <b>{ticket_ref_count}</b> {t('Support Tickets', lang)}</div>
                    </div>
                </div>
                """
            )

            has_relations = (sales_ref_count > 0 or rec_ref_count > 0)
            if has_relations:
                st.warning(
                    t("⚠️ Notice: This account has existing sales records or unsettled receivables. "
                      "Standard deletion is blocked to protect accounting integrity. You may force-delete to cascade remove all associated records.", lang)
                )

            confirm_force = st.checkbox(
                t("I understand and confirm deletion of this customer and associated records.", lang),
                key="chk_confirm_del"
            )

            if st.button(f"🗑️ {t('Delete Customer Account', lang)}", type="primary", key="btn_exec_del_customer"):
                if has_relations and not confirm_force:
                    st.error(t("⚠️ Please check the confirmation checkbox to force-delete this customer.", lang))
                else:
                    success, msg, details = delete_customer_from_db(del_cid, force=confirm_force, shop_id=shop_id)
                    if success:
                        st.success(f"✅ {t(msg, lang)}")
                        clear_customer_profile_cache(del_cid)
                        st.rerun()
                    else:
                        st.error(f"❌ {t(msg, lang)}")

# ==============================================================================
# TAB 3: VIEW CUSTOMER PROFILE & QR PASS
# ==============================================================================
with tab_profile:
    st.markdown(f"### 👤 {t('Customer Profile & Digital QR Pass', lang)}")
    st.caption(t("Inspect individual customer ledger records, generated store check-in QR, and real purchase history.", lang))

    if df_cust.empty:
        st.info(t("No customer records available to inspect.", lang))
    else:
        inspect_options = {
            r["customer_id"]: f"{r['customer_id']} — {r['customer_name']} ({r.get('business_name') or r['city']})"
            for _, r in df_cust.iterrows()
        }
        selected_cid = st.selectbox(
            t("Select Customer:", lang),
            options=list(inspect_options.keys()),
            format_func=lambda x: inspect_options[x],
            key="profile_tab_select_cid"
        )

        if selected_cid:
            render_customer_qr_and_bills(str(selected_cid))

# ==============================================================================
# TAB 4: RFM & CHURN INTELLIGENCE
# ==============================================================================
with tab_intel:
    st.markdown(f"### 🎯 {t('RFM Behavior Analysis & Retention Playbook', lang)}")
    st.caption(t("Automated segmentation based on live transaction recency, purchase frequency, and monetary contribution.", lang))

    if df_cust.empty:
        st.info(t("No transaction history available for RFM modeling.", lang))
    else:
        # Dynamic RFM Scoring
        intel_df = df_cust.copy()
        today = pd.Timestamp.today().normalize()
        last_dt = pd.to_datetime(intel_df["last_purchase_date"], errors="coerce")
        intel_df["Days_Since_Last_Order"] = (today - last_dt).dt.days.fillna(120).clip(lower=0).astype(int)

        n_rows = len(intel_df)
        q_count = min(5, max(2, n_rows))

        try:
            intel_df["R_Score"] = pd.qcut(intel_df["Days_Since_Last_Order"].rank(method="first", ascending=False), q=q_count, labels=False) + 1
            intel_df["F_Score"] = pd.qcut(intel_df["total_orders"].rank(method="first"), q=q_count, labels=False) + 1
            intel_df["M_Score"] = pd.qcut(intel_df["total_purchases"].rank(method="first"), q=q_count, labels=False) + 1
        except Exception:
            intel_df["R_Score"] = 3
            intel_df["F_Score"] = 3
            intel_df["M_Score"] = 3

        def _assign_segment(r):
            rs, fs, ms = r["R_Score"], r["F_Score"], r["M_Score"]
            if rs >= 4 and fs >= 4 and ms >= 4:
                return "Champions"
            elif fs >= 3 and ms >= 3:
                return "Loyal Customers"
            elif rs >= 4 and fs <= 2:
                return "Potential Loyalists"
            elif rs <= 2 and (fs >= 3 or ms >= 3):
                return "At Risk"
            return "Hibernating"

        intel_df["RFM_Segment"] = intel_df.apply(_assign_segment, axis=1)

        def _calc_churn_risk(r):
            days = r["Days_Since_Last_Order"]
            orders = r["total_orders"]
            if days > 75 or (days > 45 and orders <= 2):
                return "High Churn Risk", "#EF4444"
            elif days > 35:
                return "Medium Churn Risk", "#EA580C"
            return "Low Churn Risk", "#059669"

        churn_tuples = intel_df.apply(_calc_churn_risk, axis=1)
        intel_df["Churn_Risk"] = [c[0] for c in churn_tuples]
        intel_df["Churn_Color"] = [c[1] for c in churn_tuples]

        col_rfm1, col_rfm2 = st.columns([1.3, 1.0])
        with col_rfm1:
            st.markdown(f"#### 📊 {t('Customer Distribution by RFM Segment', lang)}")
            rfm_summary = intel_df.groupby("RFM_Segment").agg(
                Customer_Count=("customer_id", "count"),
                Total_Revenue=("total_purchases", "sum"),
            ).reset_index()

            fig_rfm = go.Figure(go.Bar(
                x=[t(str(x), lang) for x in rfm_summary["RFM_Segment"]],
                y=rfm_summary["Total_Revenue"],
                text=rfm_summary["Customer_Count"].apply(lambda n: f"{n} {t('Customers', lang)}"),
                textposition="auto",
                marker_color=["#059669", "#2563EB", "#0D9488", "#EA580C", "#94A3B8"]
            ))
            base_layout = get_base_layout()
            base_layout.pop("title", None)
            base_layout.update(dict(height=320, yaxis_title=f"{t('Total Revenue', lang)} (₹)", margin=dict(l=20, r=20, t=20, b=20)))
            fig_rfm.update_layout(**base_layout)
            st.plotly_chart(fig_rfm, use_container_width=True)

        with col_rfm2:
            st.markdown(f"#### 💡 {t('Recommended Retention Actions', lang)}")
            render_html(
                f"""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #059669;">🏆 {t('Champions', lang)}:</strong> {t('Offer exclusive volume trade discounts and express delivery.', lang)}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #2563EB;">🤝 {t('Loyal Customers', lang)}:</strong> {t('Upsell high-margin specialized hardware and seasonal stock.', lang)}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #0D9488;">🌱 {t('Potential Loyalists', lang)}:</strong> {t('Share WhatsApp product catalog to encourage repeat purchases.', lang)}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #EA580C;">🚨 {t('At Risk', lang)}:</strong> {t('Direct owner check-in call to address open invoices or delivery delays.', lang)}
                    </div>
                    <div>
                        <strong style="color: #64748B;">💤 {t('Hibernating', lang)}:</strong> {t('Reactivate with targeted festive credit terms or clearance offers.', lang)}
                    </div>
                </div>
                """
            )

        render_html("<div style='height: 0.8rem;'></div>")
        st.markdown(f"#### 🚨 {t('Churn Risk Radar', lang)}")
        radar_cols = ["customer_id", "customer_name", "business_name", "Days_Since_Last_Order", "total_orders", "total_purchases", "Churn_Risk"]
        radar_df = intel_df[radar_cols].sort_values(by="Days_Since_Last_Order", ascending=False).copy()
        radar_df["total_purchases"] = radar_df["total_purchases"].apply(lambda v: format_currency(float(v or 0.0)))
        radar_df.columns = [
            t("Customer ID", lang),
            t("Customer Name", lang),
            t("Business Name", lang),
            t("Days Since Last Order", lang),
            t("Orders", lang),
            t("Total Spend", lang),
            t("Churn Risk", lang)
        ]
        st.dataframe(translate_df(radar_df, lang), use_container_width=True, hide_index=True)
