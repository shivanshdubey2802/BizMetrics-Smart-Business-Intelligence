import pytest
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pipeline import analyze_customers
from customer_qr_bills import _get_customer_profile, _whatsapp_phone, _whatsapp_url, get_customer_qr
from io import BytesIO
from PIL import Image

def test_customer_metrics():
    # Setup mock dataframe matching the required columns
    data = pd.DataFrame([
        # Customers
        {"record_type": "Receivable", "customer_id": "C1", "customer_name": "Customer 1", "registration_date": "2026-08-01"},
        {"record_type": "Receivable", "customer_id": "C2", "customer_name": "Customer 2", "registration_date": "2024-01-01"}, # Old reg -> not new
        {"record_type": "Receivable", "customer_id": "C3", "customer_name": "Customer 3", "registration_date": "2024-01-01"}, # Inactive
        
        # Sales for C1 (3 orders, total spent 60k)
        {"record_type": "Sale", "customer_id": "C1", "quantity": 1, "selling_price": "20000", "discount_percent": 0, "date": "2026-08-15", "product_id": "P1"},
        {"record_type": "Sale", "customer_id": "C1", "quantity": 2, "selling_price": "10000", "discount_percent": 0, "date": "2026-08-20", "product_id": "P2"},
        {"record_type": "Sale", "customer_id": "C1", "quantity": 1, "selling_price": "25000", "discount_percent": 20, "date": "2026-08-28", "product_id": "P1"}, # 20k
        
        # Sales for C2 (1 order, total spent 1000)
        {"record_type": "Sale", "customer_id": "C2", "quantity": 1, "selling_price": "1000", "discount_percent": 0, "date": "2026-08-29", "product_id": "P1"},
        
        # Sales for C3 (1 order, long ago)
        {"record_type": "Sale", "customer_id": "C3", "quantity": 1, "selling_price": "1000", "discount_percent": 0, "date": "2025-01-01", "product_id": "P1"},
    ])
    
    res = analyze_customers(data)
    
    assert res['total_customers'] == 3
    
    # C1: 60k spent -> High-Value
    # C2: 1k spent, 1 order -> One-Time
    # C3: Old order -> Inactive
    
    c1 = next(c for c in res['customers'] if c['customer_id'] == 'C1')
    c2 = next(c for c in res['customers'] if c['customer_id'] == 'C2')
    c3 = next(c for c in res['customers'] if c['customer_id'] == 'C3')
    
    assert c1['Total_Spent'] == 60000
    assert c1['Total_Orders'] == 3
    assert c1['AOV'] == 20000
    assert c1['Segment'] == "High-Value Customer" # Priority check for high value even if New
    assert c1['status'] == "New"
    assert c1['Most_Purchased_Product'] == "P1" # qty 2 (1+1) vs P2 qty 2 (2). Actually P1 and P2 both 2. P1 is first or whatever index max gives.
    
    assert c2['Total_Spent'] == 1000
    assert c2['Total_Orders'] == 1
    assert c2['Segment'] == "One-Time Customer"
    assert c2['status'] == "Active"
    
    assert c3['Segment'] == "Inactive Customer"
    assert c3['status'] == "Inactive"
    
def test_empty_customers():
    data = pd.DataFrame()
    res = analyze_customers(data)
    assert res['total_customers'] == 0
    assert res['total_revenue'] == 0
    
def test_unmatched_sales():
    data = pd.DataFrame([
        {"record_type": "Receivable", "customer_id": "C1"},
        {"record_type": "Sale", "customer_id": "C2", "quantity": 1, "selling_price": "100"}
    ])
    res = analyze_customers(data)
    # C1 has 0 sales
    assert res['total_customers'] == 1
    assert res['customers'][0]['Total_Orders'] == 0
    assert res['customers'][0]['Total_Spent'] == 0
    assert res['total_revenue'] == 0


def test_customer_mobile_and_whatsapp_helpers():
    assert _whatsapp_phone("987-654-3210") == "919876543210"
    assert _whatsapp_phone("+919876543210") == "919876543210"
    assert _whatsapp_phone("12345") == ""

    url = _whatsapp_url("Demo Customer", "9876543210")
    assert url.startswith("https://wa.me/919876543210?text=")
    assert "Demo%20Customer" in url
    assert "Shivansh%20Electronics%20%26%20Hardware" in url
    assert _whatsapp_url("Demo Customer", "nan") == ""


def test_customer_qr_is_valid_png():
    qr_bytes = get_customer_qr("CUST001")
    image = Image.open(BytesIO(qr_bytes))
    image.load()
    assert image.format == "PNG"


def test_customer_profile_lookup_prefers_customer_record(monkeypatch):
    import customer_qr_bills

    customer_qr_bills.st.session_state["raw_data"] = pd.DataFrame([
        {"record_type": "Sale", "customer_id": "CUST001", "mobile_number": pd.NA},
        {"record_type": "Receivable", "customer_id": "CUST001", "mobile_number": "9876543210"},
    ])
    profile = _get_customer_profile("CUST001")
    assert profile["mobile_number"] == "9876543210"
