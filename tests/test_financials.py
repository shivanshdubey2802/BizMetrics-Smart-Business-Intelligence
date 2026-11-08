import pytest
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pipeline import calculate_financials

def test_financial_reconciliation():
    data = pd.DataFrame([
        {"record_type": "Sale", "quantity": 2, "product_id": "PROD1", "discount_percent": 0},
        {"record_type": "Inventory", "product_id": "PROD1", "purchase_price": 30000, "selling_price": 50000},
        {"record_type": "Expense", "amount": 20000, "category": "Rent"},
        {"record_type": "Loan", "outstanding_principal": 500000, "interest_rate": "12%"}
    ])
    res = calculate_financials(data)
    assert res['total_revenue'] == 100000
    assert res['cogs'] == 60000
    assert res['gross_profit'] == 40000
    assert res['total_expenses'] == 20000
    assert res['operating_profit'] == 20000
    assert res['interest_expense'] == 5000
    assert res['profit_before_tax'] == 15000
    assert res['taxes'] == 15000 * 0.05
    assert res['net_profit'] == 15000 - (15000 * 0.05)

def test_zero_revenue():
    data = pd.DataFrame([
        {"record_type": "Sale", "quantity": 0, "product_id": "PROD1", "discount_percent": 0},
        {"record_type": "Inventory", "product_id": "PROD1", "purchase_price": 30000, "selling_price": 50000}
    ])
    res = calculate_financials(data)
    assert res['total_revenue'] == 0
    assert res['profit_margin'] == 0
    assert res['gross_margin'] == 0

def test_loan_principal_exclusion():
    data = pd.DataFrame([
        {"record_type": "Sale", "quantity": 1, "product_id": "PROD1", "discount_percent": 0},
        {"record_type": "Inventory", "product_id": "PROD1", "purchase_price": 0, "selling_price": 100000},
        {"record_type": "Expense", "amount": 10000, "category": "Loan Repayment"},
        {"record_type": "Expense", "amount": 5000, "category": "Principal"},
        {"record_type": "Expense", "amount": 2000, "category": "Inventory purchase"},
        {"record_type": "Loan", "outstanding_principal": 100000, "interest_rate": "12%"}
    ])
    res = calculate_financials(data)
    assert res['total_revenue'] == 100000
    assert res['total_expenses'] == 0 
    assert res['interest_expense'] == 1000

def test_edge_cases():
    # Empty dataset
    assert calculate_financials(pd.DataFrame())['total_revenue'] == 0

    # Missing discount, missing price, duplicate transaction
    data = pd.DataFrame([
        {"record_type": "Sale", "quantity": 2, "product_id": "PROD1"},
        {"record_type": "Sale", "quantity": 2, "product_id": "PROD1"}, # Duplicate
        {"record_type": "Inventory", "product_id": "PROD1", "selling_price": 100},
        {"record_type": "Sale", "quantity": 1, "product_id": "PROD2"}, # Missing price in inventory
        {"record_type": "Inventory", "product_id": "PROD3", "selling_price": 100}, # Missing SKU in sales
        # Negative profit
        {"record_type": "Expense", "amount": 1000, "category": "Misc"}
    ])
    res = calculate_financials(data)
    # Revenue = 4 * 100 = 400
    assert res['total_revenue'] == 400
    assert res['cogs'] == 0
    assert res['total_expenses'] == 1000
    assert res['operating_profit'] == -600
    assert res['taxes'] == 0 # No negative tax
    assert res['net_profit'] == -600
