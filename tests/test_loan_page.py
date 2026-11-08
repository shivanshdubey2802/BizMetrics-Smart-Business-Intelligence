import pytest
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.sih_finance import select_scheme, calculate_emi, build_quarterly_schedule, financing_capacity

def test_logic_a_micro_finance_scheme_selection():
    """Logic A: If Project Cost <= ₹1.40 Lakh -> Selects Micro Finance Scheme (6.5% interest, 3-year tenure, 3-month moratorium)."""
    # Test values <= 140,000
    for cost in [1000.0, 50000.0, 100000.0, 140000.0]:
        scheme = select_scheme(cost)
        assert scheme["name"] == "Micro Finance"
        assert scheme["supported"] is True
        assert scheme["interest_rate"] == 6.5
        assert scheme["tenure_years"] == 3
        assert scheme["moratorium_months"] == 3

def test_logic_b_term_loan_scheme_selection():
    """Logic B: If Project Cost > ₹1.40 Lakh and <= ₹50.00 Lakh -> Selects Term Loan Scheme (8% interest, 7-year tenure, 6-month moratorium)."""
    # Test values > 140,000 and <= 5,000,000
    for cost in [140001.0, 200000.0, 500000.0, 1500000.0, 5000000.0]:
        scheme = select_scheme(cost)
        assert scheme["name"] == "Term Loan"
        assert scheme["supported"] is True
        assert scheme["interest_rate"] == 8.0
        assert scheme["tenure_years"] == 7
        assert scheme["moratorium_months"] == 6

def test_project_cost_ceiling_unsupported():
    """Project Cost exceeding ₹50.00 Lakh must be marked unsupported."""
    for cost in [5000001.0, 10000000.0]:
        scheme = select_scheme(cost)
        assert scheme["supported"] is False

def test_emi_calculation_for_micro_finance():
    """Verify EMI for Micro Finance Scheme under Logic A (e.g. ₹90,000 loan for ₹100,000 project cost, 6.5%, 3 years)."""
    loan = 90000.0
    rate = 6.5
    months = 3 * 12
    emi = calculate_emi(loan, rate, months)
    assert emi > 0
    # Expected EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    r = (rate / 100.0) / 12.0
    expected = loan * r * ((1 + r) ** months) / (((1 + r) ** months) - 1)
    assert abs(emi - expected) < 0.01

def test_emi_calculation_for_term_loan():
    """Verify EMI for Term Loan Scheme under Logic B (e.g. ₹450,000 loan for ₹500,000 project cost, 8.0%, 7 years)."""
    loan = 450000.0
    rate = 8.0
    months = 7 * 12
    emi = calculate_emi(loan, rate, months)
    assert emi > 0
    assert round(emi, 2) == 7013.80

def test_quarterly_schedule_moratorium_logic_a():
    """Verify quarterly repayment schedule with 3-month moratorium for Micro Finance Scheme."""
    loan = 90000.0
    result = build_quarterly_schedule(loan, 6.5, 36, 3)
    assert result["valid"] is True
    sched = result["schedule"]
    assert not sched.empty
    # First quarter should be moratorium (only interest repaid, no principal)
    q1 = sched.iloc[0]
    assert q1["Status"] == "MORATORIUM"
    assert q1["Principal Repaid"] == 0.0
    assert abs(result["final_balance"]) < 0.01

def test_quarterly_schedule_moratorium_logic_b():
    """Verify quarterly repayment schedule with 6-month moratorium for Term Loan Scheme."""
    loan = 450000.0
    result = build_quarterly_schedule(loan, 8.0, 84, 6)
    assert result["valid"] is True
    sched = result["schedule"]
    assert not sched.empty
    # First two quarters should be moratorium
    assert sched.iloc[0]["Status"] == "MORATORIUM"
    assert sched.iloc[1]["Status"] == "MORATORIUM"
    assert sched.iloc[0]["Principal Repaid"] == 0.0
    assert sched.iloc[1]["Principal Repaid"] == 0.0
    assert sched.iloc[2]["Status"] == "REPAYMENT"
    assert abs(result["final_balance"]) < 0.01
