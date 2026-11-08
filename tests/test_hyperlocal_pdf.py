from io import BytesIO

from utils.pdf_report import generate_feasibility_pdf


def test_generate_feasibility_pdf_returns_bytes_and_contains_sections():
    report_data = {
        "business_name": "Demo Grocery",
        "business_category": "Grocery Shop",
        "state": "Chhattisgarh",
        "district": "Durg",
        "block": "Bhilai",
        "village": "Rasmada",
        "report_date": "2026-09-05",
        "business_outlook": "GOOD OPPORTUNITY",
        "possible_business_cost": 500000,
        "your_money": 50000,
        "possible_loan": 450000,
        "loan_type": "Term Loan",
        "monthly_payment": 7014,
        "business_risk": "Medium",
        "summary": "Demand appears good and costs are manageable.",
        "market_outlook": {
            "customer_demand": "Good",
            "market_condition": "Average",
            "local_market_opportunity": "Strong local demand",
            "km_5": "High local demand",
            "km_10": "Moderate expansion potential",
            "distribution_channels": "Local retail, WhatsApp",
            "demand_vs_competition": "Demand available with moderate competition",
            "underserved_opportunity": "Opportunity in daily essentials",
        },
        "competition": {
            "level": "Medium",
            "density": "Moderate",
            "explanation": "Competition exists but is manageable.",
            "pricing_position": "Competitive",
            "advice": "Use service and convenience to stand out.",
        },
        "monthly_market_conditions": [
            {"Month": "January", "Market Condition": "Good", "Advice": "Keep normal stock"},
            {"Month": "February", "Market Condition": "Average", "Advice": "Control inventory"},
        ],
        "risk_summary": [
            {"risk": "Demand Risk", "status": "LOW", "explanation": "Stable local demand."},
            {"risk": "Financial Risk", "status": "MEDIUM", "explanation": "Take care with cash flow."},
        ],
        "swot": {
            "Strengths": ["Strong local demand"],
            "Weaknesses": ["Initial investment needed"],
            "Opportunities": ["Village expansion"],
            "Threats": ["Seasonal demand shift"],
        },
        "pricing": {
            "recommended_price": 120,
            "expected_margin": 20,
            "pricing_explanation": "Keep a small premium for convenience.",
            "sales_channels": ["Direct sales", "WhatsApp"],
        },
        "business_cost": {
            "Equipment": 100000,
            "Inventory": 50000,
            "Shop Setup": 30000,
            "Licensing": 5000,
            "Working Capital": 10000,
            "Total Business Cost": 195000,
        },
        "sih_structure": {
            "your_money": 50000,
            "maximum_project_cost": 500000,
            "possible_loan": 450000,
            "explanation": "Under the 10%/90% structure, the entrepreneur contributes approximately 10% and the financing agency can provide up to 90%.",
        },
        "loan_scheme": {
            "loan_type": "Term Loan",
            "interest_rate": 8,
            "loan_period": 7,
            "moratorium": 6,
            "possible_loan": 450000,
        },
        "repayment": {
            "monthly_payment": 7014,
            "total_interest": 120000,
            "total_repayment": 570000,
            "schedule": [
                {"Quarter": "Q1", "Opening Balance": 450000, "Interest": 9000, "Principal Repaid": 0, "Payment": 9000, "Closing Balance": 450000},
                {"Quarter": "Q2", "Opening Balance": 450000, "Interest": 9000, "Principal Repaid": 15000, "Payment": 24000, "Closing Balance": 435000},
            ],
        },
        "profitability": {
            "expected_sales": 1000000,
            "product_cost": 650000,
            "business_expenses": 180000,
            "expected_profit": 170000,
            "profit_margin": 17,
            "break_even": "₹80,000",
            "loan_affordability": "Affordable",
        },
        "what_if": [
            {"Scenario": "Customer volume +10%", "Result": "Profit +₹15,000"},
            {"Scenario": "Selling price -5%", "Result": "Profit -₹12,000"},
        ],
        "decision": "YES — GOOD OPPORTUNITY",
        "ai_advice": [
            "Start with controlled inventory.",
            "Keep enough cash for the first few months.",
        ],
    }

    pdf_bytes = generate_feasibility_pdf(report_data)

    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
