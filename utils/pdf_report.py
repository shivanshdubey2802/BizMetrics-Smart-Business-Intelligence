from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _resolve_font_path(filename: str) -> str | None:
    candidates = [
        Path(filename),
        Path("/usr/share/fonts/truetype/dejavu") / filename,
        Path("/usr/share/fonts/truetype/liberation2") / filename,
        Path("/usr/share/fonts") / filename,
        Path("C:/Windows/Fonts") / filename,
        Path("C:/Windows/Fonts") / filename.lower(),
        Path("C:/Windows/Fonts") / filename.capitalize(),
    ]
    seen = set()
    for candidate in candidates:
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            return str(candidate)
    return None


def _money(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "₹0"
    return f"₹{numeric:,.0f}"


def _safe(value: Any, default: str = "Not available") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _build_table(data: list[dict[str, Any]], columns: list[str], regular_font_name: str = "Helvetica", bold_font_name: str = "Helvetica-Bold") -> Table:
    normalized_rows = []
    for row in data:
        normalized_row = {}
        for key, value in row.items():
            normalized_row[str(key)] = value
        normalized_rows.append(normalized_row)

    rows = []
    for row in normalized_rows:
        row_values = []
        for col in columns:
            value = row.get(col) if col in row else row.get(col.lower()) if col.lower() in row else row.get(col.upper()) if col.upper() in row else None
            row_values.append(_safe(value, "-"))
        rows.append(row_values)

    if rows:
        table = Table([columns] + rows)
    else:
        table = Table([columns, ["No data available"]])
    table.hAlign = "LEFT"
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D7A06A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                ("FONTNAME", (0, 1), (-1, -1), regular_font_name),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def generate_feasibility_pdf(report_data: dict[str, Any]) -> bytes:
    regular_font = _resolve_font_path("DejaVuSans.ttf") or _resolve_font_path("dejavu-sans.ttf") or _resolve_font_path("LiberationSans-Regular.ttf")
    bold_font = _resolve_font_path("DejaVuSans-Bold.ttf") or _resolve_font_path("dejavu-sans-bold.ttf") or _resolve_font_path("LiberationSans-Bold.ttf")

    regular_font_name = "DejaVuSans" if regular_font else "Helvetica"
    bold_font_name = "DejaVuSans-Bold" if bold_font else "Helvetica-Bold"

    if regular_font:
        pdfmetrics.registerFont(TTFont("DejaVuSans", regular_font))
    if bold_font:
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_font))

    base_style = ParagraphStyle("BaseStyle", fontName=regular_font_name, fontSize=10, leading=12, spaceAfter=3)
    bold_style = ParagraphStyle("BoldStyle", fontName=bold_font_name, fontSize=10, leading=12, spaceAfter=3)
    heading_style = ParagraphStyle("HeadingStyle", fontName=bold_font_name, fontSize=16, leading=18, textColor=colors.HexColor("#9D4330"), spaceAfter=6)
    subheading_style = ParagraphStyle("SubheadingStyle", fontName=regular_font_name, fontSize=11, leading=14, textColor=colors.HexColor("#4B5563"), spaceAfter=5)
    title_style = ParagraphStyle("TitleStyle", fontName=bold_font_name, fontSize=22, leading=24, textColor=colors.HexColor("#9D4330"), spaceAfter=8)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    elements = []

    def add_heading(title: str, level: int = 1):
        style = heading_style if level == 1 else subheading_style
        elements.append(Paragraph(title, style))
        elements.append(Spacer(1, 8 * mm))

    title = Paragraph("BizMetrics Feasibility Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 5 * mm))

    business_name = _safe(report_data.get("business_name"), "Not available")
    business_category = _safe(report_data.get("business_category"), "Not available")
    state = _safe(report_data.get("state"), "Not available")
    district = _safe(report_data.get("district"), "Not available")
    block = _safe(report_data.get("block"), "Not available")
    village = _safe(report_data.get("village"), "Not available")
    report_date = _safe(report_data.get("report_date"), "Not available")

    elements.append(Paragraph(f"Business: {business_name}", base_style))
    elements.append(Paragraph(f"Category: {business_category}", base_style))
    elements.append(Paragraph(f"Location: {village}, {block}, {district}, {state}", base_style))
    elements.append(Paragraph(f"Report Date: {report_date}", base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("1. BUSINESS INFORMATION")
    info_table = Table(
        [
            ["Business Name", business_name],
            ["Proposed Business / Category", business_category],
            ["State", state],
            ["District", district],
            ["Block", block],
            ["Village", village],
            ["Report Date", report_date],
        ],
        colWidths=[55 * mm, 110 * mm],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E7D7C2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, -1), regular_font_name),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 8 * mm))

    add_heading("2. EXECUTIVE SUMMARY")
    summary = report_data.get("summary") or "Demand and commercial viability appear reasonable for this business context."
    outlook = _safe(report_data.get("business_outlook"), "GOOD OPPORTUNITY")
    possible_cost = _safe(report_data.get("possible_business_cost"), "₹0")
    your_money = _safe(report_data.get("your_money"), "₹0")
    possible_loan = _safe(report_data.get("possible_loan"), "₹0")
    loan_type = _safe(report_data.get("loan_type"), "Not available")
    monthly_payment = _safe(report_data.get("monthly_payment"), "₹0")
    business_risk = _safe(report_data.get("business_risk"), "Medium")
    elements.append(Paragraph(f"Business Outlook: {outlook}", bold_style))
    elements.append(Paragraph(f"Possible Business Cost: {_money(possible_cost)}", base_style))
    elements.append(Paragraph(f"Your Money: {_money(your_money)}", base_style))
    elements.append(Paragraph(f"Possible Loan: {_money(possible_loan)}", base_style))
    elements.append(Paragraph(f"Loan Type: {loan_type}", base_style))
    elements.append(Paragraph(f"Monthly Payment: {_money(monthly_payment)}", base_style))
    elements.append(Paragraph(f"Business Risk: {business_risk}", base_style))
    elements.append(Paragraph(summary, base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("3. MARKET OUTLOOK")
    market = report_data.get("market_outlook") or {}
    market_rows = [
        ["Customer demand", _safe(market.get("customer_demand"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["Market condition", _safe(market.get("market_condition"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["Local market opportunity", _safe(market.get("local_market_opportunity"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["5 km market info", _safe(market.get("km_5"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["10 km market info", _safe(market.get("km_10"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["Distribution channels", _safe(market.get("distribution_channels"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["Demand vs competition", _safe(market.get("demand_vs_competition"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
        ["Underserved opportunity", _safe(market.get("underserved_opportunity"), "Exact local geographic data was not available; this section uses the best available business data/estimate.")],
    ]
    elements.append(_build_table([{"field": r[0], "value": r[1]} for r in market_rows], ["Field", "Value"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("4. COMPETITION")
    competition = report_data.get("competition") or {}
    competition_rows = [
        ["Competition level", _safe(competition.get("level"), "Not available")],
        ["Competitor density", _safe(competition.get("density"), "Not available")],
        ["Competition explanation", _safe(competition.get("explanation"), "Not available")],
        ["Pricing position", _safe(competition.get("pricing_position"), "Not available")],
        ["Competitive advice", _safe(competition.get("advice"), "Not available")],
    ]
    elements.append(_build_table([{"field": r[0], "value": r[1]} for r in competition_rows], ["Aspect", "Detail"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("5. MONTH-BY-MONTH MARKET CONDITION")
    monthly_market = report_data.get("monthly_market_conditions") or []
    month_table_data = [{"Month": row.get("Month", "-"), "Market Condition": row.get("Market Condition", "-"), "Advice": row.get("Advice", "-")} for row in monthly_market]
    elements.append(_build_table(month_table_data, ["Month", "Market Condition", "Advice"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("6. BUSINESS RISK")
    risk_rows = report_data.get("risk_summary") or []
    risk_data = [{"risk": row.get("risk", "-"), "status": row.get("status", "-"), "explanation": row.get("explanation", "-")} for row in risk_rows]
    elements.append(_build_table(risk_data, ["Risk", "Status", "Explanation"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("7. BUSINESS STRENGTHS AND WEAKNESSES")
    swot = report_data.get("swot") or {}
    strengths = swot.get("Strengths") or ["No strength details available."]
    weaknesses = swot.get("Weaknesses") or ["No weakness details available."]
    opportunities = swot.get("Opportunities") or ["No opportunity details available."]
    threats = swot.get("Threats") or ["No threat details available."]
    swot_table = Table(
        [
            ["Strengths", "; ".join(str(item) for item in strengths)],
            ["Weaknesses", "; ".join(str(item) for item in weaknesses)],
            ["Opportunities", "; ".join(str(item) for item in opportunities)],
            ["Threats", "; ".join(str(item) for item in threats)],
        ],
        colWidths=[40 * mm, 110 * mm],
    )
    swot_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E7D7C2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, -1), regular_font_name),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(swot_table)
    elements.append(Spacer(1, 8 * mm))

    add_heading("8. PRICING & SALES")
    pricing = report_data.get("pricing") or {}
    pricing_rows = [
        ["Recommended price / reference price", _money(pricing.get("recommended_price") or pricing.get("reference_price"))],
        ["Expected margin", _safe(pricing.get("expected_margin"), "Not available")],
        ["Pricing explanation", _safe(pricing.get("pricing_explanation"), "Not available")],
        ["Recommended sales channels", "; ".join(str(item) for item in (pricing.get("sales_channels") or [])) if pricing.get("sales_channels") else "Not available"],
    ]
    elements.append(_build_table([{"label": r[0], "value": r[1]} for r in pricing_rows], ["Item", "Detail"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("9. BUSINESS COST")
    cost_data = report_data.get("business_cost") or {}
    cost_rows = [[label, _money(value)] for label, value in cost_data.items() if label != "Total Business Cost"]
    total_cost = _money(cost_data.get("Total Business Cost") or sum(float(v) for _, v in cost_rows if isinstance(v, (int, float))))
    cost_rows.append(["Total Business Cost", total_cost])
    elements.append(_build_table([{"label": r[0], "value": r[1]} for r in cost_rows], ["Expense", "Amount"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("10. LOAN STRUCTURE")
    loan_structure = report_data.get("sih_structure") or {}
    loan_scheme = report_data.get("loan_scheme") or {}
    repayment = report_data.get("repayment") or {}
    elements.append(Paragraph(f"Your Money: {_money(loan_structure.get('your_money'))}", bold_style))
    elements.append(Paragraph(f"Business Cost: {_money(loan_structure.get('maximum_project_cost'))}", base_style))
    elements.append(Paragraph(f"Possible Loan: {_money(loan_structure.get('possible_loan'))}", base_style))
    elements.append(Paragraph(f"Loan Type: {_safe(loan_scheme.get('loan_type'), 'Not available')}", base_style))
    elements.append(Paragraph(f"Interest Rate: {_safe(loan_scheme.get('interest_rate'), 'Not available')}%", base_style))
    elements.append(Paragraph(f"Loan Period: {_safe(loan_scheme.get('loan_period'), 'Not available')} years", base_style))
    elements.append(Paragraph(f"Payment Starts After: {_safe(loan_scheme.get('moratorium'), 'Not available')} months", base_style))
    elements.append(Paragraph(f"Monthly Payment: {_money(repayment.get('monthly_payment'))}", base_style))
    elements.append(Paragraph(f"Total Interest: {_money(repayment.get('total_interest'))}", base_style))
    elements.append(Paragraph(f"Total Repayment: {_money(repayment.get('total_repayment'))}", base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("11. REPAYMENT DETAILS")
    schedule_rows = repayment.get("schedule") or []
    schedule_table = [
        ["Quarter", "Opening Balance", "Interest", "Principal Repaid", "Payment", "Closing Balance"]
    ]
    for row in schedule_rows:
        schedule_table.append([
            _safe(row.get("Quarter"), "-"),
            _money(row.get("Opening Balance")),
            _money(row.get("Interest")),
            _money(row.get("Principal Repaid")),
            _money(row.get("Payment")),
            _money(row.get("Closing Balance")),
        ])
    elements.append(_build_table([{"Quarter": r[0], "Opening Balance": r[1], "Interest": r[2], "Principal Repaid": r[3], "Payment": r[4], "Closing Balance": r[5]} for r in schedule_table[1:]], ["Quarter", "Opening Balance", "Interest", "Principal Repaid", "Payment", "Closing Balance"], regular_font_name, bold_font_name))
    elements.append(Paragraph("During the moratorium, Principal Repaid = ₹0 and the interest treatment follows the application's existing modeling assumption.", base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("12. PROFITABILITY")
    profitability = report_data.get("profitability") or {}
    profit_rows = [
        ["Expected Sales", _money(profitability.get("expected_sales"))],
        ["Product Cost", _money(profitability.get("product_cost"))],
        ["Business Expenses", _money(profitability.get("business_expenses"))],
        ["Expected Profit", _money(profitability.get("expected_profit"))],
        ["Profit Margin", _safe(profitability.get("profit_margin"), "Not available")],
        ["Break-Even", _safe(profitability.get("break_even"), "Not available")],
        ["Loan affordability", _safe(profitability.get("loan_affordability"), "Not available")],
    ]
    elements.append(_build_table([{"field": r[0], "value": r[1]} for r in profit_rows], ["Item", "Value"], regular_font_name, bold_font_name))
    elements.append(Spacer(1, 8 * mm))

    add_heading("13. WHAT-IF ANALYSIS")
    what_if = report_data.get("what_if") or []
    if what_if:
        elements.append(_build_table([{"Scenario": row.get("Scenario", "-"), "Result": row.get("Result", "-")} for row in what_if], ["Scenario", "Result"], regular_font_name, bold_font_name))
    else:
        elements.append(Paragraph("No what-if analysis available for this scenario.", base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("14. FINAL DECISION")
    decision = _safe(report_data.get("decision"), "MAYBE — CHECK A FEW THINGS FIRST")
    elements.append(Paragraph(decision, ParagraphStyle("DecisionStyle", fontName=bold_font_name, fontSize=14, leading=18, textColor=colors.HexColor("#9D4330"), spaceAfter=6)))
    elements.append(Paragraph("Demand appears good, competition is manageable and the estimated loan payment appears affordable.", base_style))
    elements.append(Spacer(1, 8 * mm))

    add_heading("15. AI BUSINESS ADVICE")
    ai_advice = report_data.get("ai_advice") or []
    if ai_advice:
        advice_items = [Paragraph(f"{index}. {item}", base_style) for index, item in enumerate(ai_advice, 1)]
        for advice in advice_items:
            elements.append(advice)
    else:
        elements.append(Paragraph("No AI business advice available.", base_style))

    try:
        doc.build(elements)
    except Exception:
        raise
    return buffer.getvalue()
