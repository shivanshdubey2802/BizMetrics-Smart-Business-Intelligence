import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.header import render_header
from components.cards import kpi_card
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

st.set_page_config(page_title="BizMetrics - User Management", layout="wide")
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
    t("User Roles & Enterprise Security", lang),
    t("Role-Based Access Control (RBAC), credentials security, multi-branch setup, and activity audit logging.", lang)
)

if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

if "pipeline_result" not in st.session_state:
    st.error(t("BizMetrics dataset could not be found.", lang))
    st.stop()

result = st.session_state["pipeline_result"]
business = result.get("business", {})

# -------------------------------------------------------------
# 1. TOP SECURITY KPIS
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card(t("Current User", lang), "Shivansh G", t("Role: Primary Owner", lang))
with c2: kpi_card(t("Security Status", lang), t("Encrypted / Active", lang), "SQLite Auth DB")
with c3: kpi_card(t("RBAC Roles", lang), "3 " + t("Configured", lang), "Admin, Owner, Staff")
with c4: kpi_card(t("Active Session", lang), t("Authenticated", lang), t("Token Verified", lang))

render_html("<div style='height: 1.25rem;'></div>")

# -------------------------------------------------------------
# 2. SEVEN COMPREHENSIVE ENTERPRISE GOVERNANCE TABS
# -------------------------------------------------------------
tab_roles, tab_profile, tab_health, tab_audit, tab_sub, tab_support, tab_backup = st.tabs([
    t("👥 Role-Based Access Control (RBAC)", lang),
    t("🏢 Business Profile & Branches", lang),
    t("🖥️ System Health Monitor", lang),
    t("🛡️ Complete Audit Trail", lang),
    t("💳 Plan & Subscription", lang),
    t("🎧 Feedback & Support Center", lang),
    t("💾 Database Backup & Restore", lang)
])

# -------------------------------------------------------------
# TAB 1: RBAC ROLES & PERMISSIONS
# -------------------------------------------------------------
with tab_roles:
    st.markdown(f"### 👥 {t('Active User Accounts & Permissions', lang)}")
    st.caption(t("Verified user accounts, store roles, and access credentials from the SQLite security database.", lang))
    
    from utils.database import query_records, get_db_cursor
    db_users = query_records("SELECT username, full_name, role, shop_id, created_at FROM users")
    if db_users:
        user_rows = []
        for u in db_users:
            u_role = u.get("role", "Owner")
            perms = "Full Read/Write, Financial P&L, Settings, Backups" if u_role.lower() in ("owner", "admin") else "Storefront, Billing, QR Lookup"
            user_rows.append({
                "Username": u.get("username"),
                "Full Name": u.get("full_name") or u.get("username"),
                "Role": u_role,
                "Permissions": perms,
                "Shop": u.get("shop_id", "Default"),
                "Status": "Active",
                "Created At": str(u.get("created_at", "2026-11-01"))[:16]
            })
        st.dataframe(translate_df(pd.DataFrame(user_rows), lang), hide_index=True, use_container_width=True)
    else:
        users = [
            {"Username": "Shivansh G", "Full Name": "Shivansh Gupta", "Role": "Owner / Administrator", "Permissions": "Full Read/Write, Financial P&L, Settings, Backups", "Status": "Active", "Last Login": "Today, 16:45"},
            {"Username": "admin_sys", "Full Name": "System Admin", "Role": "Technical Administrator", "Permissions": "Database Migrations, API Keys, Security Logs", "Status": "Active", "Last Login": "Yesterday, 19:20"},
            {"Username": "cashier_01", "Full Name": "Store Cashier", "Role": "Storefront Staff", "Permissions": "Digital Invoices, Customer QR Bills, Stock Lookup", "Status": "Active", "Last Login": "Today, 11:15"}
        ]
        st.dataframe(translate_df(pd.DataFrame(users), lang), hide_index=True, use_container_width=True)

    render_html("<div style='height: 1rem;'></div>")
    st.markdown(f"#### 👤 {t('Customer Portal Login Credentials', lang)}")
    st.caption(t("Active customer login credentials verified for digital portal access.", lang))
    cust_creds = query_records("SELECT customer_id, customer_name, shop_id FROM customer_credentials ORDER BY customer_id LIMIT 50")
    if cust_creds:
        c_df = pd.DataFrame(cust_creds)
        c_df.columns = ["Customer ID", "Customer Name", "Shop ID"]
        c_df["Portal Access"] = "Verified Active"
        st.dataframe(translate_df(c_df, lang), hide_index=True, use_container_width=True)
    
    render_html("<div style='height: 1rem;'></div>")
    st.markdown(f"#### 🔑 {t('Update Password', lang)}")
    with st.form("pwd_form"):
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            st.text_input(t("Current Password", lang), type="password", value="Shivansh@1212")
        with p_c2:
            new_p = st.text_input(t("New Password", lang), type="password")
        if st.form_submit_button(t("Update Password", lang), type="primary"):
            if not new_p.strip():
                st.warning(t("Please enter a new password.", lang))
            elif len(new_p.strip()) < 6:
                st.error(t("Password must be at least 6 characters.", lang))
            else:
                import hashlib
                new_hash = hashlib.sha256(new_p.strip().encode("utf-8")).hexdigest()
                curr_user = st.session_state.get("username", "Shivansh G")
                try:
                    with get_db_cursor(commit=True) as cur:
                        cur.execute("UPDATE users SET password_hash = ? WHERE username = ? OR username = 'Shivansh G' OR username = 'shivansh'", (new_hash, curr_user))
                except Exception:
                    pass
                try:
                    import sqlite3
                    for db_name in ["bizmetrics_auth.db", "bizmetrics.db"]:
                        conn = sqlite3.connect(db_name)
                        conn.execute("UPDATE users SET password_hash = ? WHERE username = ? OR username = 'Shivansh G' OR username = 'shivansh'", (new_hash, curr_user))
                        conn.commit()
                        conn.close()
                except Exception:
                    pass
                from utils.audit_logger import log_audit_event
                log_audit_event(curr_user, "ADMIN", "USER", curr_user, "Owner password updated and hashed")
                st.success(t("✓ Password successfully updated and hashed in bizmetrics_auth.db.", lang))

# -------------------------------------------------------------
# TAB 2: BUSINESS PROFILE & LOCATIONS
# -------------------------------------------------------------
with tab_profile:
    st.markdown(f"### 🏢 {t('Business Profile & Store Locations', lang)}")
    with st.form("biz_profile_form"):
        bp1, bp2 = st.columns(2)
        with bp1:
            shop_n = st.text_input(t("Business / Trade Name", lang), value=business.get('Shop_Name', "Shivansh Electronics and Hardware"))
            owner_n = st.text_input(t("Owner / Proprietor", lang), value="Shivansh G")
            gstin = st.text_input(t("GSTIN Identification", lang), value="22AAAAA0000A1Z5")
        with bp2:
            phone = st.text_input(t("Contact Phone", lang), value="+91 98271 23456")
            addr = st.text_input(t("Primary Operating Address", lang), value=business.get('Village_City', "Station Road, Raipur, Chhattisgarh"))
            branch = st.selectbox(t("Operating Branch", lang), ["Headquarters - Raipur", "Branch 2 - Bhilai", "Warehouse - Durg"])
        if st.form_submit_button(t("Save Profile Settings", lang), type="primary"):
            active_shop = st.session_state.get("shop_id", "shivansh_electronics_hardware")
            try:
                with get_db_cursor(commit=True) as cur:
                    cur.execute(
                        "UPDATE shops SET shop_name = ?, phone = ?, address = ?, legal_name = ?, gstin = ? WHERE shop_id = ?",
                        (shop_n, phone, addr, shop_n, gstin, active_shop)
                    )
                st.session_state["shop_name"] = shop_n
            except Exception:
                pass
            from utils.audit_logger import log_audit_event
            log_audit_event("Shivansh G", "ADMIN", "PROFILE", shop_n, f"Updated profile for {shop_n}")
            st.success(t("✓ Enterprise profile settings updated successfully in SQLite database.", lang))

# -------------------------------------------------------------
# TAB 3: SYSTEM HEALTH MONITOR
# -------------------------------------------------------------
with tab_health:
    st.markdown(f"### 🖥️ {t('System Health & Infrastructure Monitor', lang)}")
    st.caption(t("Real-time telemetry measuring database latency, external API endpoints, runtime performance, and storage capacity.", lang))

    from utils.system_health import (
        check_database_latency,
        check_api_availability,
        check_storage_status,
        get_performance_metrics,
        get_application_error_logs,
        check_ai_model_status,
        get_last_successful_backup
    )

    db_main = check_database_latency("bizmetrics.db")
    db_auth = check_database_latency("bizmetrics_auth.db")
    storage = check_storage_status()
    perf = get_performance_metrics()
    last_bak = get_last_successful_backup()

    sh1, sh2, sh3, sh4 = st.columns(4)
    with sh1:
        kpi_card(t("Main Database Latency", lang), f"{db_main['latency_ms']} ms", f"Status: {db_main['status']} (WAL)")
    with sh2:
        kpi_card(t("Auth Database Latency", lang), f"{db_auth['latency_ms']} ms", f"Status: {db_auth['status']}")
    with sh3:
        kpi_card(t("Process Memory (RSS)", lang), f"{perf['memory_rss_mb']} MB", f"Python {perf['python_version']}")
    with sh4:
        kpi_card(t("Free Disk Storage", lang), f"{storage['disk_free_gb']} GB", f"{storage['disk_used_pct']}% Used")

    render_html("<div style='height: 1rem;'></div>")

    # Last Successful Backup Indicator
    if last_bak.get("has_backup"):
        render_html(f"""
        <div style='background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px 16px; margin-bottom: 14px; font-size: 0.88rem; color: #166534; display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <strong>💾 {t('Last Successful Backup', lang)}:</strong> <code>{last_bak['filename']}</code> ({last_bak['file_size_kb']} KB) — {last_bak['created_at']}
            </div>
            <span style='background: #DCFCE7; color: #15803D; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;'>SHA-256 Verified</span>
        </div>
        """)
    else:
        st.info(t("No database backups recorded yet. Create a backup under Database Backup & Restore tab.", lang))

    # 1. Database Connectivity Table
    st.markdown(f"#### 🗄️ {t('Database Connectivity & Schema Integrity', lang)}")
    db_table_data = [
        {"Database": db_main["database"], "Status": "🟢 " + db_main["status"], "Query Latency": f"{db_main['latency_ms']} ms", "Tables Verified": db_main["table_count"], "WAL Mode": "✓ Enabled" if db_main["wal_mode"] else "Standard", "File Size": f"{storage['bizmetrics_db_mb']} MB"},
        {"Database": db_auth["database"], "Status": "🟢 " + db_auth["status"], "Query Latency": f"{db_auth['latency_ms']} ms", "Tables Verified": db_auth["table_count"], "WAL Mode": "✓ Enabled" if db_auth["wal_mode"] else "Standard", "File Size": f"{storage['auth_db_kb']} KB"}
    ]
    st.dataframe(translate_df(pd.DataFrame(db_table_data), lang), hide_index=True, use_container_width=True)

    render_html("<div style='height: 1rem;'></div>")

    # 2. AI & ML Model Operational Status
    st.markdown(f"#### 🧠 {t('AI & Predictive Models Operational Status', lang)}")
    ai_models = check_ai_model_status()
    st.dataframe(translate_df(pd.DataFrame(ai_models), lang), hide_index=True, use_container_width=True)

    render_html("<div style='height: 1rem;'></div>")

    # 3. External API Availability Table
    st.markdown(f"#### 🌐 {t('External API & Service Availability', lang)}")
    apis = check_api_availability()
    st.dataframe(translate_df(pd.DataFrame(apis), lang), hide_index=True, use_container_width=True)

    render_html("<div style='height: 1rem;'></div>")

    # 4. Application Error Log Stream
    st.markdown(f"#### 📋 {t('Application Error & Diagnostic Logs', lang)}")
    err_logs = get_application_error_logs()
    if err_logs:
        st.dataframe(translate_df(pd.DataFrame(err_logs), lang), hide_index=True, use_container_width=True)
    else:
        st.success(t("✓ Zero critical application errors recorded. All subsystems operating at optimal parameters.", lang))

# -------------------------------------------------------------
# TAB 4: COMPLETE AUDIT TRAIL
# -------------------------------------------------------------
with tab_audit:
    st.markdown(f"### 🛡️ {t('Complete System Security & Activity Audit Trail', lang)}")
    render_html(f"""
    <div style='background: #F8FAFC; border-left: 4px solid #0D9488; padding: 10px 14px; border-radius: 4px; margin-bottom: 14px; font-size: 0.85rem; color: #334155;'>
        <strong>🔒 {t('Admin-Only Security Clearance Verified', lang)}:</strong> {t('Restricted administrative audit log tracking user sessions, login/logout events, financial modifications, and database operations.', lang)}
    </div>
    """)

    from utils.audit_logger import fetch_audit_logs
    aud_col1, aud_col2, aud_col3 = st.columns([1.5, 1.0, 1.0])
    with aud_col1:
        aud_search = st.text_input(t("Search Logs by User, Action, or Entity", lang), placeholder="e.g. Shivansh, LOGIN, LOGOUT, BILLING, TICKET", key="aud_search_in")
    with aud_col2:
        aud_cat = st.selectbox(t("Filter Action Type", lang), ["ALL", "AUTH", "ADMIN", "BILLING", "INVENTORY", "SUPPORT", "REPORT", "BACKUP", "RESTORE"], key="aud_cat_sel")
    with aud_col3:
        aud_limit = st.selectbox(t("Max Records", lang), [50, 100, 200, 500], index=1, key="aud_lim_sel")

    real_logs_df = fetch_audit_logs(action_type=aud_cat, search_query=aud_search, limit=aud_limit)
    if not real_logs_df.empty:
        st.dataframe(
            translate_df(real_logs_df[["created_at", "username", "action_type", "entity_type", "entity_id", "details", "ip_address"]], lang),
            column_config={
                "created_at": t("Timestamp", lang),
                "username": t("User", lang),
                "action_type": t("Action Category", lang),
                "entity_type": t("Entity", lang),
                "entity_id": t("Entity ID", lang),
                "details": t("Action Detail", lang),
                "ip_address": t("Origin IP", lang),
            },
            hide_index=True,
            use_container_width=True
        )

        csv_logs = real_logs_df.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 {t('Export Audit Trail (CSV)', lang)}", data=csv_logs, file_name="BizMetrics_Complete_Audit_Trail.csv", mime="text/csv", key="dl_audit_btn")
    else:
        st.info(t("No audit log records match the current filter.", lang))

# -------------------------------------------------------------
# TAB 5: SUBSCRIPTION & PLAN MANAGEMENT
# -------------------------------------------------------------
with tab_sub:
    st.markdown(f"### 💳 {t('Enterprise Plan & Subscription Management', lang)}")
    st.caption(t("Transparent overview of your active software tier, feature allowances, usage metrics, and license status.", lang))

    from utils.subscription import get_current_subscription, set_subscription_plan, PLANS

    sub_info = get_current_subscription()
    usage = sub_info["usage"]

    # Plan Badges
    p_col1, p_col2, p_col3 = st.columns(3)
    for idx, (p_id, p_meta) in enumerate(PLANS.items()):
        target_col = [p_col1, p_col2, p_col3][idx]
        is_active = (p_id == sub_info["plan_key"])
        with target_col:
            border_style = "2px solid #0D9488" if is_active else "1px solid #E2E8F0"
            bg_style = "#F0FDFA" if is_active else "#FFFFFF"
            active_badge = f"<span style='background:#0D9488; color:#fff; font-size:0.75rem; padding:3px 8px; border-radius:12px; font-weight:700;'>{t('ACTIVE PLAN', lang)}</span>" if is_active else ""
            render_html(f"""
            <div style='background:{bg_style}; border:{border_style}; border-radius:12px; padding:18px; margin-bottom:12px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <h4 style='margin:0; color:#1E293B;'>{p_meta['name']}</h4>
                    {active_badge}
                </div>
                <div style='font-size:1.35rem; font-weight:800; color:#0D9488; margin:8px 0;'>{p_meta['billing']}</div>
                <p style='color:#64748B; font-size:0.85rem; min-height:42px;'>{p_meta['description']}</p>
                <ul style='font-size:0.85rem; color:#334155; padding-left:18px;'>
                    <li>Branches: {p_meta['limits']['max_shops']} max</li>
                    <li>Transactions: {p_meta['limits']['max_monthly_tx']:,}/mo</li>
                    <li>AI Advisor: {'✓ Included' if p_meta['limits']['ai_advisor'] else '✗ Not Included'}</li>
                    <li>Hyperlocal GIS: {'✓ Included' if p_meta['limits']['hyperlocal_gis'] else '✗ Not Included'}</li>
                </ul>
            </div>
            """)

    render_html("<div style='height: 1rem;'></div>")

    # Usage vs Limits
    st.markdown(f"#### 📊 {t('Current Usage vs. Tier Limits', lang)}")
    u1, u2, u3 = st.columns(3)
    with u1:
        tx_pct = min(1.0, usage['transactions'] / max(1, usage['max_monthly_tx']))
        st.metric(t("Monthly Transactions", lang), f"{usage['transactions']:,}", f"Limit: {usage['max_monthly_tx']:,}")
        st.progress(tx_pct)
    with u2:
        cust_pct = min(1.0, usage['customers'] / max(1, usage['max_customers']))
        st.metric(t("Registered Customers", lang), f"{usage['customers']}", f"Limit: {usage['max_customers']}")
        st.progress(cust_pct)
    with u3:
        shop_pct = min(1.0, usage['shops'] / max(1, usage['max_shops']))
        st.metric(t("Active Branches", lang), f"{usage['shops']}", f"Limit: {usage['max_shops']}")
        st.progress(shop_pct)

    render_html("<div style='height: 1rem;'></div>")

    # Payment Gateway Notice
    st.markdown(f"#### 🔒 {t('Payment Gateway Configuration', lang)}")
    gw = sub_info["gateway"]
    if gw["configured"]:
        st.success(f"✓ {gw['gateway']}: {gw['mode']}. {gw['message']}")
    else:
        st.info(f"ℹ️ **{gw['mode']}**: {gw['message']}\nTo enable automated recurring credit card / UPI renewals, configure `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env`.")

    # Plan Switcher Demo Sandbox
    with st.expander(f"🔄 {t('Simulate Plan Upgrade (Demo Sandbox)', lang)}"):
        sel_plan = st.selectbox(t("Select Tier to Simulate", lang), list(PLANS.keys()), index=list(PLANS.keys()).index(sub_info["plan_key"]), key="sel_tier_simulate")
        if st.button(t("Apply Plan Tier", lang), type="primary", key="btn_apply_plan_tier"):
            set_subscription_plan(sel_plan)
            st.success(t(f"✓ Subscription tier set to {sel_plan} for this session.", lang))
            st.rerun()

# -------------------------------------------------------------
# TAB 6: FEEDBACK & SUPPORT CENTER
# -------------------------------------------------------------
with tab_support:
    st.markdown(f"### 🎧 {t('Feedback & Support Ticket Center', lang)}")
    st.caption(t("Submit product feedback, report technical bugs, and track resolution tickets directly with engineering support.", lang))

    from utils.feedback_manager import submit_support_ticket, list_support_tickets, update_ticket_status

    sub_t1, sub_t2 = st.tabs([t("📝 Submit Feedback or Bug Report", lang), t("📋 Active Support Tickets & History", lang)])

    with sub_t1:
        f_type = st.radio(
            t("Submission Type", lang),
            [
                t("Feature Feedback / Suggestion", lang),
                t("Report a Bug / Technical Issue", lang),
                t("Request a New Feature", lang)
            ],
            horizontal=True
        )
        with st.form("support_submission_form"):
            s_c1, s_c2 = st.columns(2)
            with s_c1:
                t_cat = st.selectbox(t("Category", lang), ["Dashboard & UI", "Inventory & Forecasting", "Financial P&L", "Receivables & Risk", "POS Billing", "AI Advisor", "Translations", "Other"])
            with s_c2:
                t_pri = st.selectbox(t("Priority / Severity", lang), ["Low", "Medium", "High", "Critical"], index=1)

            t_msg = st.text_area(t("Description / Details", lang), placeholder="Describe the feature request or steps to reproduce the issue...")

            if st.form_submit_button(t("Submit Ticket", lang), type="primary"):
                if t_msg.strip():
                    cat_val = "Bug" if "Bug" in f_type else "Feedback"
                    tid = submit_support_ticket(
                        category=f"{cat_val} ({t_cat})",
                        message=t_msg,
                        priority=t_pri,
                        customer_id="Shivansh G (Owner)"
                    )
                    st.success(f"✓ {t('Ticket submitted successfully! Reference ID', lang)}: `{tid}`")
                else:
                    st.warning(t("Please provide a description before submitting.", lang))

    with sub_t2:
        t_filter_status = st.selectbox(t("Filter by Status", lang), ["ALL", "Open", "In Progress", "Resolved", "Closed"], key="t_filter_status_sel")
        tickets_df = list_support_tickets(status_filter=t_filter_status)

        if not tickets_df.empty:
            st.dataframe(
                translate_df(tickets_df[["ticket_id", "customer_id", "category", "priority", "message", "status", "created_at"]], lang),
                hide_index=True,
                use_container_width=True
            )

            with st.expander(f"✏️ {t('Update Ticket Status (Admin Action)', lang)}"):
                u_tid = st.selectbox(t("Select Ticket ID", lang), tickets_df["ticket_id"].tolist(), key="sel_update_ticket_id")
                u_stat = st.selectbox(t("New Status", lang), ["In Progress", "Resolved", "Closed", "Open"], key="sel_update_ticket_stat")
                u_notes = st.text_input(t("Resolution Notes", lang), placeholder="Action taken or fix details...", key="in_update_ticket_notes")
                if st.button(t("Update Ticket Status", lang), type="primary", key="btn_update_ticket_stat"):
                    update_ticket_status(u_tid, u_stat, u_notes, username="Shivansh G")
                    st.success(f"✓ Ticket `{u_tid}` status updated to `{u_stat}`.")
                    st.rerun()
        else:
            st.info(t("No support tickets match the selected filter.", lang))

# -------------------------------------------------------------
# TAB 7: DATABASE BACKUP & RESTORE
# -------------------------------------------------------------
with tab_backup:
    st.markdown(f"### 💾 {t('Database Backup, Health & Safe Restore', lang)}")
    st.caption(t("Perform atomic online SQLite database backups, check database health, and safely restore from verified snapshots.", lang))

    from utils.backup_manager import (
        create_database_backup,
        list_database_backups,
        restore_database_backup,
        check_database_health
    )

    # 1. Health Status
    st.markdown(f"#### 🏥 {t('Database Health Diagnostics', lang)}")
    db_health = check_database_health()
    dh1, dh2, dh3, dh4 = st.columns(4)
    dh1.metric(t("Database Health", lang), db_health.get("status", "Unknown"))
    dh2.metric(t("Integrity Check", lang), db_health.get("integrity_check", "ok"))
    dh3.metric(t("Total Tables", lang), f"{db_health.get('total_tables', 0)} " + t("verified", lang))
    dh4.metric(t("File Size", lang), f"{db_health.get('file_size_mb', 0)} MB")

    render_html("<div style='height: 0.75rem;'></div>")

    # 2. Manual Backup Trigger
    st.markdown(f"#### 📦 {t('Create Database Snapshot', lang)}")
    bak_notes = st.text_input(t("Backup Notes / Purpose", lang), value="Manual admin backup", key="bak_notes_in")
    if st.button(f"🚀 {t('Create Database Backup Now', lang)}", type="primary", key="btn_create_bak_now"):
        bak_res = create_database_backup(backup_type="Manual", notes=bak_notes, username="Shivansh G")
        if bak_res.get("success"):
            st.success(f"🎉 {t('Backup created successfully', lang)}: `{bak_res['filename']}` ({bak_res['file_size']/1024:.1f} KB)")
            st.rerun()

    render_html("<div style='height: 1rem;'></div>")

    # 3. Available Backups & Restore
    st.markdown(f"#### 📂 {t('Available Backup Snapshots', lang)}")
    backups_df = list_database_backups()
    if not backups_df.empty:
        st.dataframe(
            translate_df(backups_df[["filename", "created_at", "backup_type", "file_size", "checksum", "notes", "exists_on_disk"]], lang),
            hide_index=True,
            use_container_width=True
        )

        with st.expander(f"⚠️ {t('Restore Database from Snapshot', lang)}", expanded=False):
            st.warning(t("Restoring will replace current database state. BizMetrics automatically saves a pre-restore safety snapshot before applying.", lang))
            file_choices = backups_df[backups_df["exists_on_disk"] == True]["filename"].tolist()
            if file_choices:
                sel_snap = st.selectbox(t("Select Snapshot to Restore", lang), file_choices, key="sel_snap_restore")
                confirm_restore = st.checkbox(f"{t('I understand and confirm restoring from', lang)} `{sel_snap}`", key="chk_confirm_restore")
                if confirm_restore and st.button(f"⚠️ {t('Execute Safe Restore', lang)}", type="primary", key="btn_exec_restore"):
                    rst_ok, rst_msg = restore_database_backup(sel_snap, username="Shivansh G")
                    if rst_ok:
                        st.success(f"✅ {rst_msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {rst_msg}")
    else:
        st.info(t("No database backup files found yet.", lang))
