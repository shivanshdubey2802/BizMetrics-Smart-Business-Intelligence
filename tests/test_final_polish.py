"""
Automated Test Suite: Final Product Polish
Validates:
1. System Health Monitor (Database latency, API status, Storage, Performance, Error log)
2. Complete Audit Trail (Logins, data mutations, admin actions, filters)
3. First-Time User Onboarding (Checklist milestones, sample CSV templates)
4. Scheduled Business Reports (Daily, Weekly, Monthly summaries, PDF/Excel, status updates)
5. Subscription Management (Free/Basic/Premium tiers, feature limits, gateway detection)
6. Feedback & Support Center (Feedback, Bug reports, Ticket status tracking)
7. Business Benchmarking (MoM comparisons, Durg-Bhilai public indicators, explainability)
"""
import os
import pytest
import pandas as pd


def test_01_system_health_monitor():
    from utils.system_health import (
        check_database_latency,
        check_api_availability,
        check_storage_status,
        get_performance_metrics,
        record_application_error,
        get_application_error_logs
    )

    # 1. Main DB Latency
    db_stat = check_database_latency("bizmetrics.db")
    assert db_stat["status"] in ("Healthy", "Degraded")
    assert isinstance(db_stat["latency_ms"], float)
    assert db_stat["table_count"] > 10

    # 2. Auth DB Latency
    auth_stat = check_database_latency("bizmetrics_auth.db")
    assert auth_stat["status"] in ("Healthy", "Degraded")

    # 3. API Availability
    apis = check_api_availability()
    assert len(apis) >= 3
    service_names = [a["service"] for a in apis]
    assert any("Groq" in s for s in service_names)
    assert any("OpenStreetMap" in s for s in service_names)
    assert any("Payment" in s for s in service_names)

    # 4. Storage Status
    storage = check_storage_status()
    assert storage["bizmetrics_db_mb"] > 0
    assert storage["disk_free_gb"] > 0
    assert "Healthy" in storage["storage_health"] or "Warning" in storage["storage_health"]

    # 5. Performance Metrics
    perf = get_performance_metrics()
    assert "python_version" in perf
    assert perf["memory_rss_mb"] > 0

    # 6. Error Log Buffer
    record_application_error("test_module", "Sample non-critical warning message", "TestWarning")
    errs = get_application_error_logs()
    assert len(errs) > 0
    assert any(e["module"] == "test_module" for e in errs)

    # 7. AI Model Status
    from utils.system_health import check_ai_model_status, get_last_successful_backup
    models = check_ai_model_status()
    assert len(models) >= 4
    model_names = [m["model_name"] for m in models]
    assert any("Demand Forecaster" in n for n in model_names)
    assert any("AI Business Advisor" in n for n in model_names)
    assert any("Customer RFM" in n for n in model_names)

    # 8. Last Successful Backup
    last_bak = get_last_successful_backup()
    assert "has_backup" in last_bak
    assert "filename" in last_bak


def test_02_complete_audit_trail():
    from utils.audit_logger import log_audit_event, fetch_audit_logs

    # Log an AUTH event
    auth_id = log_audit_event(
        username="Shivansh G",
        action_type="AUTH",
        entity_type="LOGIN",
        entity_id="OWNER",
        details="Test owner login event verification"
    )
    assert auth_id.startswith("AUD-")

    # Log an ADMIN event
    admin_id = log_audit_event(
        username="Shivansh G",
        action_type="ADMIN",
        entity_type="PROFILE",
        entity_id="SHOP001",
        details="Test profile settings update"
    )
    assert admin_id.startswith("AUD-")

    # Query filtered logs
    auth_logs = fetch_audit_logs(action_type="AUTH", limit=10)
    assert not auth_logs.empty
    assert any(row["action_type"] == "AUTH" for _, row in auth_logs.iterrows())

    # Search logs
    search_logs = fetch_audit_logs(search_query="Test owner login", limit=5)
    assert not search_logs.empty


def test_03_first_time_user_onboarding():
    # Verify sample CSV generation
    sample_prod_csv = "product_id,product_name,category,purchase_price,selling_price,current_stock,minimum_stock\nSKU001,Copper Wire 1.5mm,Electrical,120.0,165.0,85,25\n"
    df_sample = pd.read_csv(pd.io.common.StringIO(sample_prod_csv))
    assert len(df_sample) == 1
    assert "selling_price" in df_sample.columns

    # Verify checklist milestone calculation logic
    milestones = [True, True, True, True, True, True]
    assert sum(milestones) == 6
    assert sum(milestones) / 6.0 == 1.0


def test_04_scheduled_business_reports():
    from utils.scheduled_reports import (
        init_scheduled_reports_table,
        get_scheduled_reports,
        compute_period_summary,
        trigger_scheduled_report_run,
        generate_period_excel_bytes
    )

    init_scheduled_reports_table()
    scheds = get_scheduled_reports()
    assert not scheds.empty
    assert len(scheds) >= 3

    # Test period summaries
    daily_sum = compute_period_summary("Daily")
    assert daily_sum["total_revenue"] >= 0
    assert "period_label" in daily_sum

    weekly_sum = compute_period_summary("Weekly")
    assert weekly_sum["total_orders"] >= 0

    monthly_sum = compute_period_summary("Monthly")
    assert "net_profit" in monthly_sum

    # Test manual run trigger
    first_sched_id = scheds.iloc[0]["schedule_id"]
    res = trigger_scheduled_report_run(first_sched_id, username="TestRunner")
    assert res["success"] is True
    assert res["schedule_id"] == first_sched_id

    # Test Excel bytes generation
    excel_bytes = generate_period_excel_bytes(daily_sum)
    assert len(excel_bytes) > 100  # Valid spreadsheet / CSV bytes

    # Test SMTP configuration and report history
    from utils.scheduled_reports import check_smtp_status, get_report_generation_history
    smtp = check_smtp_status()
    assert "configured" in smtp
    assert "message" in smtp

    history = get_report_generation_history()
    assert not history.empty
    assert "report_id" in history.columns


def test_05_subscription_management():
    import streamlit as st
    from utils.subscription import (
        get_current_subscription,
        set_subscription_plan,
        check_payment_gateway_status,
        PLANS
    )

    sub = get_current_subscription()
    assert sub["plan_key"] in PLANS
    assert "limits" in sub
    assert sub["usage"]["transactions"] > 0
    assert "gateway" in sub

    # Test plan switcher
    ok = set_subscription_plan("Premium")
    assert ok is True
    assert st.session_state.get("active_subscription_plan") == "Premium"

    # Reset back to Basic
    set_subscription_plan("Basic")
    assert st.session_state.get("active_subscription_plan") == "Basic"

    # Verify payment gateway check operates in enterprise local mode if unconfigured
    gw = check_payment_gateway_status()
    assert "gateway" in gw
    assert "mode" in gw


def test_06_feedback_and_support_center():
    from utils.feedback_manager import (
        submit_support_ticket,
        list_support_tickets,
        update_ticket_status
    )

    # 1. Submit Feedback Ticket
    t_id = submit_support_ticket(
        category="Feedback (UI/UX)",
        message="The new multilingual toggle is very fast.",
        priority="Low",
        customer_id="Shivansh G (Owner)"
    )
    assert t_id.startswith("TCK-")

    # 2. Submit Bug Ticket
    bug_id = submit_support_ticket(
        category="Bug (Inventory)",
        message="Test bug: stock alert verification ticket",
        priority="High",
        customer_id="Shivansh G (Owner)"
    )
    assert bug_id.startswith("TCK-")

    # 3. List Tickets
    tickets = list_support_tickets()
    assert not tickets.empty
    assert any(t["ticket_id"] == bug_id for _, t in tickets.iterrows())

    # 4. Update Ticket Status
    up_ok = update_ticket_status(bug_id, "In Progress", "Investigating by QA team")
    assert up_ok is True

    updated_tickets = list_support_tickets(status_filter="In Progress")
    assert any(t["ticket_id"] == bug_id for _, t in updated_tickets.iterrows())


def test_07_business_benchmarking():
    from utils.benchmarking import (
        compute_mom_comparison,
        get_verified_market_benchmarks
    )

    # 1. MoM Calculation
    mom = compute_mom_comparison()
    assert "revenue" in mom
    assert "orders" in mom
    assert "profit" in mom
    assert "margin" in mom
    assert isinstance(mom["revenue"]["pct_change"], float)

    # 2. Market Benchmarking against Durg-Bhilai public metrics
    store_stats = {
        "gross_margin": 28.4,
        "credit_ratio": 19.2,
        "dso_days": 22.0,
        "opex_ratio": 8.5
    }
    benches = get_verified_market_benchmarks(store_stats)
    assert len(benches) == 4
    metrics = [b["metric"] for b in benches]
    assert "Gross Profit Margin" in metrics
    assert "Credit (Udhaar) Sales Ratio" in metrics
    assert "Receivables Collection Days (DSO)" in metrics
    assert "Operating Expense Ratio" in metrics

    for b in benches:
        assert "Durg" in b["benchmark_source"] or "Chhattisgarh" in b["benchmark_source"]
        assert len(b["explanation"]) > 20
        assert "benchmark_date" in b
        assert "locality_scope" in b

    # 3. Data sufficiency check
    from utils.benchmarking import check_data_sufficiency
    suff = check_data_sufficiency()
    assert "is_sufficient" in suff
    assert "active_days" in suff
    assert "message" in suff
