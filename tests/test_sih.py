import pytest
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pipeline import calculate_financials
from utils.sih_finance import build_quarterly_schedule, calculate_emi, financing_capacity, select_scheme
from utils.hyperlocal_intelligence import (
    buyer_concentration,
    competitor_density,
    demand_competition_matrix,
    distribution_channels,
    localized_swot,
    market_reach,
    pricing_intelligence,
    supply_chain_risk,
    filter_within_radius,
    get_location_coordinates,
    haversine_km,
    supplier_intelligence,
    valid_coordinates,
)
from utils.voice_input import transcribe_audio

def test_sih_10_90():
    margin = 50000
    project_cost = margin / 0.10
    loan = project_cost * 0.90
    assert project_cost == 500000
    assert loan == 450000

def test_sih_10_90_small():
    margin = 10000
    project_cost = margin / 0.10
    loan = project_cost * 0.90
    assert project_cost == 100000
    assert loan == 90000

def test_sih_max_project_cost():
    margin = 50000
    proposed_cost = 600000
    max_cost = margin / 0.10
    is_valid = proposed_cost <= max_cost
    assert max_cost == 500000
    assert is_valid == False

def test_sih_micro_scheme():
    project_cost = 140000
    if project_cost <= 140000:
        scheme = "Micro"
        interest = 6.5
        tenure = 3
        moratorium = 3
    else:
        scheme = "Term"
        interest = 8.0
        tenure = 7
        moratorium = 6
        
    assert scheme == "Micro"
    assert interest == 6.5
    assert tenure == 3
    assert moratorium == 3

def test_sih_term_scheme():
    project_cost = 140001
    if project_cost <= 140000:
        scheme = "Micro"
        interest = 6.5
        tenure = 3
        moratorium = 3
    else:
        scheme = "Term"
        interest = 8.0
        tenure = 7
        moratorium = 6
        
    assert scheme == "Term"
    assert interest == 8.0
    assert tenure == 7
    assert moratorium == 6

def test_revenue_cogs_profit():
    # Construct a dataframe specifically for the calculate_financials
    rows = [
        {"record_type": "Inventory", "product_id": "P1", "SKU": "P1", "purchase_price": "100", "selling_price": "200"},
        {"record_type": "Sale", "product_id": "P1", "quantity": "10", "discount_percent": "10"},
        {"record_type": "Expense", "category": "Rent", "amount": "100"},
        {"record_type": "Loan", "outstanding_principal": "1000", "principal_amount": "1000", "interest_rate": "12.0", "monthly_emi": "100"}
    ]
    df = pd.DataFrame(rows)
    fin = calculate_financials(df)
    
    # Qty(10) * Sell(200) * (1-0.10) = 1800
    assert fin['total_revenue'] == 1800
    # Qty(10) * Cost(100) = 1000
    assert fin['cogs'] == 1000
    
    # Gross Profit = 1800 - 1000 = 800
    assert fin['gross_profit'] == 800
    
    # Operating Profit = 800 - 100 = 700
    assert fin['operating_profit'] == 700
    
    # Interest (1000 * 12% / 12) = 10
    assert fin['interest_expense'] == 10
    
    # PBT = 700 - 10 = 690
    assert fin['profit_before_tax'] == 690
    
    # Tax = 690 * 0.05 = 34.5
    assert fin['taxes'] == 34.5
    
    # Net = 690 - 34.5 = 655.5
    assert fin['net_profit'] == 655.5

def test_emi():
    principal = 450000
    rate = 8.0
    tenure_years = 7
    r_monthly = (rate / 100) / 12
    n_months = tenure_years * 12
    emi = principal * r_monthly * ((1 + r_monthly)**n_months) / (((1 + r_monthly)**n_months) - 1)
    
    # Standard formula verification
    assert emi > 0
    assert round(emi, 2) == 7013.80

def test_quarterly_schedule():
    principal = 450000
    rate = 8.0
    tenure_years = 7
    moratorium_months = 6
    
    r_quarterly = (rate / 100) / 4
    quarters_total = tenure_years * 4
    moratorium_quarters = moratorium_months // 3
    repayment_quarters = quarters_total - moratorium_quarters
    
    # Moratorium interest accumulation
    current_principal = principal
    for _ in range(moratorium_quarters):
        current_principal += current_principal * r_quarterly
        
    amortized_principal = current_principal
    q_pmt = amortized_principal * r_quarterly * ((1 + r_quarterly)**repayment_quarters) / (((1 + r_quarterly)**repayment_quarters) - 1)
    
    # Repayment
    for _ in range(repayment_quarters):
        interest = current_principal * r_quarterly
        principal_repaid = q_pmt - interest
        current_principal -= principal_repaid
        
    assert abs(current_principal) < 1.0

def test_feasibility_score():
    opp_score = 80
    fin_score = 90
    overall = (opp_score * 0.5) + (fin_score * 0.5)
    assert overall == 85.0


def test_financing_capacity_10_90():
    capacity = financing_capacity(50000)
    assert capacity["maximum_project_cost"] == 500000
    assert capacity["maximum_loan"] == 450000


def test_scheme_boundaries_and_limits():
    assert select_scheme(140000)["name"] == "Micro Finance"
    assert select_scheme(140001)["name"] == "Term Loan"
    assert select_scheme(5000000)["supported"] is True
    assert select_scheme(5000001)["supported"] is False


def test_scheme_parameters():
    micro = select_scheme(140000)
    term = select_scheme(140001)
    assert (micro["interest_rate"], micro["tenure_years"], micro["moratorium_months"]) == (6.5, 3, 3)
    assert (term["interest_rate"], term["tenure_years"], term["moratorium_months"]) == (8.0, 7, 6)


def test_quarterly_schedule_validates_moratorium_and_identity():
    result = build_quarterly_schedule(450000, 8, 84, 6)
    schedule = result["schedule"]
    assert result["valid"] is True
    assert (schedule.loc[schedule["Status"] == "MORATORIUM", "Principal Repaid"] == 0).all()
    assert abs(result["final_balance"]) < 0.01
    assert abs(result["total_principal"] - 450000) < 0.01
    assert abs(result["total_repayment"] - result["total_principal"] - result["total_interest"]) < 0.01


def test_repayment_changes_with_loan_rate_and_tenure():
    base = build_quarterly_schedule(450000, 8, 84, 6)
    larger = build_quarterly_schedule(500000, 8, 84, 6)
    higher_rate = build_quarterly_schedule(450000, 10, 84, 6)
    longer = build_quarterly_schedule(450000, 8, 96, 6)
    assert calculate_emi(500000, 8, 84) != calculate_emi(450000, 8, 84)
    assert higher_rate["total_interest"] != base["total_interest"]
    assert longer["total_repayment"] != base["total_repayment"]
    assert larger["total_repayment"] != base["total_repayment"]


def test_hyperlocal_market_and_gap_helpers():
    frame = pd.DataFrame([
        {"Category": "Food", "City": "Village A", "Customer_ID": "A", "Total_Amount": 800, "Selling_Price": "₹1,000", "Purchase_Price": "₹700", "Lead_Time_Days": 10},
        {"Category": "Food", "City": "Village A", "Customer_ID": "A", "Total_Amount": 200, "Selling_Price": "₹1,200", "Purchase_Price": "₹800", "Lead_Time_Days": 10},
        {"Category": "Food", "City": "Village B", "Customer_ID": "B", "Total_Amount": 100, "Selling_Price": "₹800", "Purchase_Price": "₹500", "Lead_Time_Days": 5},
    ])
    reach = market_reach(frame, "Village A", "District")
    assert reach["5_km"]["estimated_consumers"] == 1
    assert reach["10_km"]["estimated_consumers"] == 2
    assert demand_competition_matrix(85, 20)["opportunity_gap"] == "Potentially Underserved"
    assert demand_competition_matrix(85, 80)["opportunity_gap"] == "Highly Saturated"


def test_hyperlocal_transparent_pricing_risk_and_swot():
    frame = pd.DataFrame([
        {"Category": "Food", "Customer_ID": "A", "Total_Amount": 900, "Selling_Price": 1000, "Purchase_Price": 700, "Lead_Time_Days": 10},
        {"Category": "Food", "Customer_ID": "B", "Total_Amount": 100, "Selling_Price": 1200, "Purchase_Price": 800, "Lead_Time_Days": 10},
    ])
    assert pricing_intelligence(frame, "Food")["reference_price"] == 1100
    assert buyer_concentration(frame)["risk_level"] == "High"
    assert supply_chain_risk(frame, "Food")["level"] == "Medium"
    channels = distribution_channels("Food")
    assert channels[0]["source"] == "Category-based recommendation"
    swot = localized_swot(80, 20, 25, 300000, 60, "Potentially Underserved", "Medium", "High")
    assert set(swot) == {"Strengths", "Weaknesses", "Opportunities", "Threats"}
    assert swot["Threats"]


def test_geographic_helpers_and_supplier_fallback():
    assert valid_coordinates(21.2, 81.6)
    assert not valid_coordinates(91, 81.6)
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.195, rel=0.001)
    frame = pd.DataFrame([{"Customer_ID": "A", "Latitude": 0, "Longitude": 0}, {"Customer_ID": "B", "Latitude": 1, "Longitude": 1}])
    assert len(filter_within_radius(frame, 0, 0, 5)) == 1
    assert get_location_coordinates("Village", "Block", "District", "State")["confidence"] == "Needs Verification"
    supplier = supplier_intelligence(pd.DataFrame([{"Supplier_ID": "S1"}, {"Supplier_ID": "S1"}, {"Supplier_ID": "S2"}]))
    assert supplier["supplier_count"] == 2
    assert supplier["dependency"] == "Medium"


def test_voice_adapter_and_regional_language_configuration():
    assert transcribe_audio(b"") ["status"] == "empty"
    from ai_advisor import SUPPORTED_LANGUAGES
    assert SUPPORTED_LANGUAGES["Marathi"] == "mr"
    assert SUPPORTED_LANGUAGES["Assamese"] == "as"
