"""
BizMetrics - Single-file Customer QR + Bill Integration
Generated from:
  - 05_customers_receivables.csv
  - 03_sales_transactions.csv

This file is self-contained for the QR images. It does NOT require
the QR PNG files to be present separately.

Usage in Streamlit:
    from customer_qr_bills import get_customer_qr, get_customer_bills
    st.image(get_customer_qr("CUST001"))
    bills = get_customer_bills("CUST001")
"""

import base64
import io
from io import BytesIO
from PIL import Image
from pathlib import Path
import pandas as pd
import streamlit as st
import qrcode
import urllib.parse
from urllib.parse import quote


def _normalize_mobile(value):
    if pd.isna(value):
        return "Not Available"
    mobile = str(value).strip()
    if mobile.endswith(".0"):
        mobile = mobile[:-2]
    digits = "".join(character for character in mobile if character.isdigit())
    return digits if len(digits) == 10 and digits[0] in "6789" else "Not Available"


def _whatsapp_phone(value):
    """Return an Indian number in wa.me format, or an empty string."""
    if pd.isna(value):
        return ""
    phone = str(value).strip().replace(" ", "").replace("-", "")
    if phone.endswith(".0"):
        phone = phone[:-2]
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("91") and len(phone) == 12:
        local = phone[2:]
    elif len(phone) == 10 and phone[0] in "6789":
        local = phone
    else:
        return ""
    return "91" + local if len(local) == 10 and local[0] in "6789" and local.isdigit() else ""


def _whatsapp_url(customer_name, mobile_number):
    phone = _whatsapp_phone(mobile_number)
    if not phone:
        return ""
    message = (
        f"Hello {customer_name},\n\n"
        "Here is your digital customer QR profile from Shivansh Electronics & Hardware.\n\n"
        "Please keep this QR for future reference.\n\n"
        "Thank you."
    )
    return f"https://wa.me/{phone}?text={quote(message)}"


def get_all_customers():
    """Returns all available customers for lookup and switching."""
    try:
        from utils.database import query_records
        db_rows = query_records(
            "SELECT customer_id, customer_name, business_name, contact_number FROM customers ORDER BY customer_id"
        )
        if db_rows:
            cust_list = []
            for r in db_rows:
                cid = str(r["customer_id"]).strip()
                cname = str(r.get("customer_name") or "Customer").strip()
                bname = str(r.get("business_name") or "").strip()
                mob = str(r.get("contact_number") or "").strip()
                cust_list.append({
                    "id": cid,
                    "name": cname,
                    "business": bname,
                    "mobile": mob,
                    "display": f"{cid} — {cname} ({bname})" if bname else f"{cid} — {cname}"
                })
            return cust_list
    except Exception:
        pass

    from pathlib import Path
    cand_csvs = [
        Path("05_customers_receivables.csv"),
        Path("data/05_customers_receivables.csv"),
        Path(__file__).resolve().parent / "05_customers_receivables.csv",
        Path(__file__).resolve().parent / "data" / "05_customers_receivables.csv",
    ]
    for p in cand_csvs:
        if p.is_file():
            try:
                df = pd.read_csv(p)
                cid_col = next((c for c in df.columns if c.lower() in ["customer_id", "customerid"]), None)
                cname_col = next((c for c in df.columns if c.lower() in ["customer_name", "customername"]), None)
                bname_col = next((c for c in df.columns if c.lower() in ["business_name", "businessname"]), None)
                mobile_col = next((c for c in df.columns if c.lower() in ["contact_number", "mobile_number", "phone"]), None)
                if cid_col:
                    cust_list = []
                    for _, row in df.iterrows():
                        cid = str(row[cid_col]).strip()
                        cname = str(row[cname_col]).strip() if cname_col else "Customer"
                        bname = str(row[bname_col]).strip() if bname_col else ""
                        mob = str(row[mobile_col]).strip() if mobile_col else ""
                        cust_list.append({
                            "id": cid,
                            "name": cname,
                            "business": bname,
                            "mobile": mob,
                            "display": f"{cid} — {cname} ({bname})" if bname else f"{cid} — {cname}"
                        })
                    return cust_list
            except Exception:
                pass

    # Fallback to raw_data if CSV not directly accessible
    raw_data = st.session_state.get("raw_data", pd.DataFrame())
    if not raw_data.empty:
        cid_col = next((c for c in raw_data.columns if c.lower() in ["customer_id", "customerid"]), None)
        if cid_col:
            unique_ids = raw_data[cid_col].dropna().unique().tolist()
            cust_list = []
            for u_id in unique_ids:
                u_str = str(u_id).strip()
                if u_str and u_str.lower() != "nan":
                    cust_list.append({
                        "id": u_str,
                        "name": f"Customer {u_str}",
                        "business": "",
                        "mobile": "",
                        "display": f"{u_str}"
                    })
            return cust_list

    return [{"id": "CUST001", "name": "Suresh Patel", "business": "Suresh Retail Shop", "mobile": "9876543337", "display": "CUST001 — Suresh Patel (Suresh Retail Shop)"}]


_CUSTOMER_PROFILE_CACHE = {}

def clear_customer_profile_cache(customer_id: str | None = None):
    """Invalidates cached customer profile."""
    if customer_id:
        _CUSTOMER_PROFILE_CACHE.pop(str(customer_id).strip(), None)
    else:
        _CUSTOMER_PROFILE_CACHE.clear()

def _get_customer_profile(customer_id):
    c_id = str(customer_id).strip()
    raw_data = st.session_state.get("raw_data", None)
    if raw_data is not None and isinstance(raw_data, pd.DataFrame) and not raw_data.empty:
        cid_col = next((c for c in raw_data.columns if c.lower() in ["customer_id", "customerid"]), None)
        if cid_col:
            customer_rows = raw_data[raw_data[cid_col].astype(str).str.strip() == c_id]
            if not customer_rows.empty:
                return dict(_fetch_customer_profile_uncached(c_id))
    if c_id in _CUSTOMER_PROFILE_CACHE:
        return dict(_CUSTOMER_PROFILE_CACHE[c_id])
    prof = _fetch_customer_profile_uncached(c_id)
    _CUSTOMER_PROFILE_CACHE[c_id] = prof
    return dict(prof)

def _fetch_customer_profile_uncached(customer_id):
    c_id = str(customer_id).strip()
    profile = {}

    # 1. Check raw_data in session state first if available
    raw_data = st.session_state.get("raw_data", None)
    if raw_data is not None and isinstance(raw_data, pd.DataFrame) and not raw_data.empty:
        cid_col = next((c for c in raw_data.columns if c.lower() in ["customer_id", "customerid"]), None)
        if cid_col:
            customer_rows = raw_data[raw_data[cid_col].astype(str).str.strip() == c_id]
            if not customer_rows.empty:
                rec_col = next((c for c in customer_rows.columns if c.lower() == "record_type"), None)
                if rec_col:
                    preferred = customer_rows[customer_rows[rec_col].astype(str).str.lower().isin(["receivable", "customer"])]
                    if not preferred.empty:
                        customer_rows = preferred
                row_dict = customer_rows.iloc[0].to_dict()
                return {
                    "customer_id": row_dict.get(cid_col, c_id),
                    "Customer_ID": row_dict.get(cid_col, c_id),
                    "customer_name": row_dict.get("Customer_Name", row_dict.get("customer_name", "Customer")),
                    "Customer_Name": row_dict.get("Customer_Name", row_dict.get("customer_name", "Customer")),
                    "business_name": row_dict.get("Business_Name", row_dict.get("business_name", "")),
                    "Business_Name": row_dict.get("Business_Name", row_dict.get("business_name", "")),
                    "mobile_number": str(row_dict.get("Contact_Number", row_dict.get("Mobile_Number", row_dict.get("mobile_number", "")))),
                    "Mobile_Number": str(row_dict.get("Contact_Number", row_dict.get("Mobile_Number", row_dict.get("mobile_number", "")))),
                    "email": row_dict.get("Email", row_dict.get("email", "")),
                    "city": row_dict.get("City", row_dict.get("city", "Raipur")),
                    "City": row_dict.get("City", row_dict.get("city", "Raipur")),
                    "customer_type": row_dict.get("Customer_Type", row_dict.get("customer_type", "Retail Customer")),
                    "Customer_Type": row_dict.get("Customer_Type", row_dict.get("customer_type", "Retail Customer")),
                    "registration_date": str(row_dict.get("Registration_Date", row_dict.get("registration_date", "2024-01-01"))),
                    "customer_rating": float(row_dict.get("Customer_Rating", row_dict.get("customer_rating", 4.5))),
                    "outstanding_amount": float(row_dict.get("Outstanding_Amount", row_dict.get("outstanding_amount", 0.0))),
                }

    # 1b. Check centralized relational database
    try:
        from utils.database import get_customer_detail_from_db
        db_cust = get_customer_detail_from_db(c_id)
        if db_cust:
            return {
                "customer_id": db_cust.get("customer_id", c_id),
                "Customer_ID": db_cust.get("customer_id", c_id),
                "customer_name": db_cust.get("customer_name", "Customer"),
                "Customer_Name": db_cust.get("customer_name", "Customer"),
                "business_name": db_cust.get("business_name", ""),
                "Business_Name": db_cust.get("business_name", ""),
                "mobile_number": str(db_cust.get("contact_number", "")),
                "Mobile_Number": str(db_cust.get("contact_number", "")),
                "email": db_cust.get("email", ""),
                "address": db_cust.get("address", ""),
                "city": db_cust.get("city", "Raipur"),
                "City": db_cust.get("city", "Raipur"),
                "customer_type": db_cust.get("customer_type", "Retail Customer"),
                "Customer_Type": db_cust.get("customer_type", "Retail Customer"),
                "registration_date": str(db_cust.get("registration_date", "2024-01-01")),
                "customer_rating": float(db_cust.get("customer_rating", 4.5)),
                "outstanding_amount": float(db_cust.get("outstanding_amount", 0.0)),
            }
    except Exception:
        pass

    # 2. Read 05_customers_receivables.csv
    from pathlib import Path
    cand_csvs = [
        Path("05_customers_receivables.csv"),
        Path("data/05_customers_receivables.csv"),
        Path(__file__).resolve().parent / "05_customers_receivables.csv",
        Path(__file__).resolve().parent / "data" / "05_customers_receivables.csv",
    ]
    for p in cand_csvs:
        if p.is_file():
            try:
                cdf = pd.read_csv(p)
                cid_col = next((c for c in cdf.columns if c.lower() in ["customer_id", "customerid"]), None)
                if cid_col:
                    matches = cdf[cdf[cid_col].astype(str).str.strip() == c_id]
                    if not matches.empty:
                        r = matches.iloc[0].to_dict()
                        profile = {
                            "customer_id": r.get(cid_col, c_id),
                            "Customer_ID": r.get(cid_col, c_id),
                            "customer_name": r.get("Customer_Name", r.get("customer_name", "Customer")),
                            "Customer_Name": r.get("Customer_Name", r.get("customer_name", "Customer")),
                            "business_name": r.get("Business_Name", r.get("business_name", "")),
                            "Business_Name": r.get("Business_Name", r.get("business_name", "")),
                            "mobile_number": str(r.get("Contact_Number", r.get("Mobile_Number", r.get("mobile_number", "")))),
                            "Mobile_Number": str(r.get("Contact_Number", r.get("Mobile_Number", r.get("mobile_number", "")))),
                            "email": r.get("Email", r.get("email", "")),
                            "city": r.get("City", r.get("city", "Raipur")),
                            "City": r.get("City", r.get("city", "Raipur")),
                            "customer_type": r.get("Customer_Type", r.get("customer_type", "Retail Customer")),
                            "Customer_Type": r.get("Customer_Type", r.get("customer_type", "Retail Customer")),
                            "registration_date": str(r.get("Registration_Date", r.get("registration_date", "2024-01-01"))),
                            "customer_rating": float(r.get("Customer_Rating", r.get("customer_rating", 4.5))),
                            "outstanding_amount": float(r.get("Outstanding_Amount", r.get("outstanding_amount", 0.0))),
                        }
                        return profile
            except Exception:
                pass

    # 2. Check raw_data in session state
    raw_data = st.session_state.get("raw_data", pd.DataFrame())
    if raw_data.empty:
        try:
            from utils.data_loader import refresh_application_data
            refresh_application_data()
            raw_data = st.session_state.get("raw_data", pd.DataFrame())
        except Exception:
            pass

    if not raw_data.empty:
        cid_col = next((c for c in raw_data.columns if c.lower() in ["customer_id", "customerid"]), None)
        if cid_col:
            customer_rows = raw_data[raw_data[cid_col].astype(str).str.strip() == c_id]
            if not customer_rows.empty:
                rec_col = next((c for c in customer_rows.columns if c.lower() == "record_type"), None)
                if rec_col:
                    preferred = customer_rows[customer_rows[rec_col].astype(str).str.lower().isin(["receivable", "customer"])]
                    if not preferred.empty:
                        customer_rows = preferred
                row_dict = customer_rows.iloc[0].to_dict()
                return {
                    "customer_id": c_id,
                    "Customer_ID": c_id,
                    "customer_name": row_dict.get("Customer_Name", row_dict.get("customer_name", "Customer")),
                    "business_name": row_dict.get("Business_Name", row_dict.get("business_name", "")),
                    "mobile_number": str(row_dict.get("Mobile_Number", row_dict.get("mobile_number", row_dict.get("Contact_Number", "")))),
                    "email": row_dict.get("Email", row_dict.get("email", "")),
                    "city": row_dict.get("City", row_dict.get("city", "Raipur")),
                    "customer_type": row_dict.get("Customer_Type", row_dict.get("customer_type", "Retail Customer")),
                    "registration_date": str(row_dict.get("Registration_Date", row_dict.get("registration_date", "2024-01-01"))),
                    "customer_rating": float(row_dict.get("Customer_Rating", row_dict.get("customer_rating", 4.5))),
                    "outstanding_amount": float(row_dict.get("Outstanding_Amount", row_dict.get("outstanding_amount", 0.0))),
                }

    # 1b. Check centralized relational database
    try:
        from utils.database import get_customer_detail_from_db
        db_cust = get_customer_detail_from_db(c_id)
        if db_cust:
            return {
                "customer_id": db_cust.get("customer_id", c_id),
                "Customer_ID": db_cust.get("customer_id", c_id),
                "customer_name": db_cust.get("customer_name", "Customer"),
                "Customer_Name": db_cust.get("customer_name", "Customer"),
                "business_name": db_cust.get("business_name", ""),
                "Business_Name": db_cust.get("business_name", ""),
                "mobile_number": str(db_cust.get("contact_number", "")),
                "Mobile_Number": str(db_cust.get("contact_number", "")),
                "email": db_cust.get("email", ""),
                "address": db_cust.get("address", ""),
                "city": db_cust.get("city", "Raipur"),
                "City": db_cust.get("city", "Raipur"),
                "customer_type": db_cust.get("customer_type", "Retail Customer"),
                "Customer_Type": db_cust.get("customer_type", "Retail Customer"),
                "registration_date": str(db_cust.get("registration_date", "2024-01-01")),
                "customer_rating": float(db_cust.get("customer_rating", 4.5)),
                "outstanding_amount": float(db_cust.get("outstanding_amount", 0.0)),
            }
    except Exception:
        pass

    return {
        "customer_id": c_id,
        "customer_name": f"Customer {c_id}",
        "business_name": "Retail Store Client",
        "mobile_number": "9876543337",
        "email": "customer@example.com",
        "city": "Raipur",
        "customer_type": "Retailer",
        "registration_date": "2024-01-01",
        "customer_rating": 4.5,
        "outstanding_amount": 0.0,
    }


@st.cache_data(show_spinner=False)
def get_customer_qr(customer_id: str):
    """Return the customer's QR as PNG bytes."""
    key = str(customer_id).strip()

    # Generate QR dynamically
    import qrcode
    from io import BytesIO
    import urllib.parse

    base_url = "https://bizmetrics.app/customer/"
    url = urllib.parse.urljoin(base_url, urllib.parse.quote(key))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def load_bills_and_products():
    raw_data = st.session_state.get("raw_data", pd.DataFrame())
    if raw_data.empty:
        try:
            from utils.data_loader import refresh_application_data
            refresh_application_data()
            raw_data = st.session_state.get("raw_data", pd.DataFrame())
        except Exception:
            pass

    # If raw_data is available from master CSV
    if not raw_data.empty:
        rec_col = next((c for c in raw_data.columns if c.lower() == "record_type"), None)
        if rec_col:
            is_sale = raw_data[rec_col].astype(str).str.lower() == "sale"
            is_inv = raw_data[rec_col].astype(str).str.lower() == "inventory"
            sales_df = raw_data[is_sale].copy()
            products_df = raw_data[is_inv].copy()
            col_map = {
                "sale_id": "Sale_ID", "customer_id": "Customer_ID", "product_id": "Product_ID",
                "quantity": "Quantity", "selling_price": "Selling_Price", "discount_percent": "Discount_Percent",
                "date": "Date", "payment_mode": "Payment_Mode", "payment_status": "Payment_Status",
                "credit_amount": "Credit_Amount", "product_name": "Product_Name", "notes": "Notes",
                "total_amount": "Total_Amount"
            }
            sales_df = sales_df.rename(columns={c: col_map[c.lower()] for c in sales_df.columns if c.lower() in col_map})
            products_df = products_df.rename(columns={c: col_map[c.lower()] for c in products_df.columns if c.lower() in col_map})
            if not sales_df.empty and "Customer_ID" in sales_df.columns:
                return sales_df, products_df

    # Fallback to direct CSVs
    from pathlib import Path
    sales_df = pd.DataFrame()
    products_df = pd.DataFrame()
    for s_p in [Path("03_sales_transactions.csv"), Path("data/03_sales_transactions.csv"), Path(__file__).resolve().parent / "03_sales_transactions.csv"]:
        if s_p.is_file():
            try:
                sales_df = pd.read_csv(s_p)
                break
            except Exception:
                pass
    for p_p in [Path("02_products_inventory.csv"), Path("data/02_products_inventory.csv"), Path(__file__).resolve().parent / "02_products_inventory.csv"]:
        if p_p.is_file():
            try:
                products_df = pd.read_csv(p_p)
                break
            except Exception:
                pass
    return sales_df, products_df

@st.cache_data(show_spinner=False)
def get_customer_bills(customer_id: str):
    """Return all transaction/bill records for one customer with exact calculated amounts."""
    c_id = str(customer_id).strip()

    # Fast path: Direct indexed query from relational SQLite database (sub-millisecond)
    try:
        from utils.database import query_df
        sql = """
        SELECT
            s.sale_id as Sale_ID,
            s.customer_id as Customer_ID,
            s.product_id as Product_ID,
            s.quantity as Quantity,
            s.selling_price as Selling_Price,
            s.discount_percent as Discount_Percent,
            s.total_amount as Total_Amount,
            s.date as Date,
            s.payment_mode as Payment_Mode,
            s.payment_status as Payment_Status,
            s.credit_amount as Credit_Amount,
            s.notes as Notes,
            p.product_name as Product_Name
        FROM sales_transactions s
        LEFT JOIN products p ON s.product_id = p.product_id
        WHERE s.customer_id = ?
        ORDER BY s.date DESC
        """
        cust_sales = query_df(sql, (c_id,))
        if not cust_sales.empty:
            cust_sales["Quantity"] = pd.to_numeric(cust_sales["Quantity"], errors="coerce").fillna(1.0)
            cust_sales["Selling_Price"] = pd.to_numeric(cust_sales["Selling_Price"], errors="coerce").fillna(0.0)
            cust_sales["Discount_Percent"] = pd.to_numeric(cust_sales["Discount_Percent"], errors="coerce").fillna(0.0)
            cust_sales["Total_Amount"] = pd.to_numeric(cust_sales["Total_Amount"], errors="coerce").fillna(0.0)
            cust_sales["Credit_Amount"] = pd.to_numeric(cust_sales["Credit_Amount"], errors="coerce").fillna(0.0)
            cust_sales["Date"] = pd.to_datetime(cust_sales["Date"], errors="coerce")

            gross = cust_sales["Quantity"] * cust_sales["Selling_Price"]
            disc_amt = gross * cust_sales["Discount_Percent"] / 100.0
            cust_sales["Bill_Amount"] = gross - disc_amt

            stat = cust_sales["Payment_Status"].astype(str).str.lower()
            mode = cust_sales["Payment_Mode"].astype(str).str.lower()
            is_unpaid = stat.isin(["pending", "unpaid", "overdue"]) | ((mode == "credit") & (stat != "completed"))

            c_amt = cust_sales["Credit_Amount"]
            b_amt = cust_sales["Bill_Amount"]
            effective_credit = c_amt.where(c_amt > 0, b_amt)
            cust_sales["Outstanding"] = effective_credit.where(is_unpaid, 0.0)
            cust_sales["Paid_Amount"] = cust_sales["Bill_Amount"] - cust_sales["Outstanding"]
            return cust_sales.sort_values(by="Date", ascending=False)
    except Exception:
        pass

    # Fallback to cached master data if database is unavailable
    sales_df, products_df = load_bills_and_products()
    if sales_df.empty or "Customer_ID" not in sales_df.columns:
        return pd.DataFrame()

    c_id = str(customer_id).strip()
    sales_df["Customer_ID"] = sales_df["Customer_ID"].astype(str).str.strip()
    cust_sales = sales_df[sales_df["Customer_ID"] == c_id].copy()

    if cust_sales.empty:
        return cust_sales

    # Parse money
    def parse_money(s):
        if s is None:
            return 0.0
        return pd.to_numeric(
            s.astype(str)
             .str.replace("₹", "", regex=False)
             .str.replace(",", "", regex=False)
             .str.replace(" ", "", regex=False),
            errors="coerce"
        ).fillna(0.0)

    qty = pd.to_numeric(cust_sales.get("Quantity", pd.Series([1]*len(cust_sales))), errors="coerce").fillna(1)
    sp = parse_money(cust_sales.get("Selling_Price", pd.Series([0]*len(cust_sales))))
    disc = pd.to_numeric(cust_sales.get("Discount_Percent", pd.Series([0]*len(cust_sales))), errors="coerce").fillna(0)

    # Financial calculation (BizMetrics formula)
    gross = qty * sp
    disc_amt = gross * disc / 100.0
    final_amt = gross - disc_amt

    cust_sales["Bill_Amount"] = final_amt
    cust_sales["Date"] = pd.to_datetime(cust_sales.get("Date", pd.Series([None]*len(cust_sales))), errors="coerce")

    # Merge Product Names
    if not products_df.empty and "Product_ID" in products_df.columns and "Product_Name" in products_df.columns:
        product_map = products_df.set_index("Product_ID")["Product_Name"].to_dict()
        cust_sales["Product_Name"] = cust_sales["Product_ID"].map(product_map).fillna(cust_sales["Product_ID"])
    else:
        cust_sales["Product_Name"] = cust_sales.get("Product_ID", "")

    # Outstanding Logic
    outstanding = pd.Series([0.0]*len(cust_sales), index=cust_sales.index)

    for idx, row in cust_sales.iterrows():
        mode = str(row.get("Payment_Mode", "")).lower()
        status = str(row.get("Payment_Status", "")).lower()
        amt = row["Bill_Amount"]

        if status in ["pending", "unpaid", "overdue"]:
            out = parse_money(pd.Series([row.get("Credit_Amount", amt)])).iloc[0]
            outstanding[idx] = out if out > 0 else amt
        elif mode == "credit" and status != "completed":
            out = parse_money(pd.Series([row.get("Credit_Amount", amt)])).iloc[0]
            outstanding[idx] = out if out > 0 else amt
        else:
            outstanding[idx] = 0.0

    cust_sales["Outstanding"] = outstanding
    cust_sales["Paid_Amount"] = cust_sales["Bill_Amount"] - cust_sales["Outstanding"]

    cust_sales = cust_sales.sort_values(by="Date", ascending=False)
    return cust_sales

def get_bill_summary(bills: pd.DataFrame):
    if bills.empty:
        return {
            "total_bills": 0,
            "total_purchase": 0.0,
            "avg_bill": 0.0,
            "last_purchase": "N/A",
            "outstanding": 0.0,
            "paid_amount": 0.0
        }

    tot_bills = len(bills)
    tot_purchase = bills["Bill_Amount"].sum()
    avg_bill = tot_purchase / tot_bills if tot_bills > 0 else 0.0
    outstanding = bills["Outstanding"].sum()
    paid = bills["Paid_Amount"].sum()

    last_p = bills["Date"].dropna().max()
    last_p_str = last_p.strftime("%Y-%m-%d") if pd.notnull(last_p) else "N/A"

    return {
        "total_bills": tot_bills,
        "total_purchase": tot_purchase,
        "avg_bill": avg_bill,
        "last_purchase": last_p_str,
        "outstanding": outstanding,
        "paid_amount": paid
    }

def render_customer_qr_and_bills(customer_id: str):
    """
    Drop-in Streamlit component:
      - Shows the selected customer's QR.
      - Shows every transaction/bill record for that customer.
      - Shows summary metrics.
    """
    customer_id = str(customer_id).strip()
    profile = _get_customer_profile(customer_id)
    mobile_number = profile.get("mobile_number", "")
    customer_name = profile.get("business_name", profile.get("customer_name", "Customer"))

    st.subheader("🔳 Customer QR")
    qr = get_customer_qr(customer_id)

    if qr:
        try:
            qr_image = Image.open(BytesIO(qr))
            qr_image.load()
            st.image(qr_image, width=280, caption=f"QR — {customer_id}")
        except Exception as e:
            st.warning(f"Unable to display customer QR: {e}")

        whatsapp_url = _whatsapp_url(customer_name, mobile_number)
        qr_actions = st.columns(2)
        with qr_actions[0]:
            st.download_button(
                "⬇ Download QR",
                data=qr,
                file_name=f"{customer_id}_QR.png",
                mime="image/png",
                width="stretch",
            )
        with qr_actions[1]:
            if whatsapp_url:
                st.link_button("💬 Send QR on WhatsApp", whatsapp_url, width="stretch")
            else:
                st.warning("⚠ WhatsApp unavailable")
        st.caption("After WhatsApp opens, attach the downloaded QR image and press Send.")
    else:
        st.warning(f"No QR found for {customer_id}.")

    bills = get_customer_bills(customer_id)
    summary = get_bill_summary(bills)
    st.subheader("👤 Digital Customer Profile")
    profile_columns = st.columns(2)
    profile_values = [
        ("Customer Name", customer_name),
        ("Customer ID", customer_id),
        ("Mobile Number", _normalize_mobile(mobile_number)),
        ("Customer Type", profile.get("customer_type", "Not Available")),
        ("Total Orders", summary["total_bills"]),
        ("Total Spent", f"₹{summary['total_purchase']:,.0f}"),
        ("Outstanding", f"₹{summary['outstanding']:,.0f}"),
    ]
    for index, (label, value) in enumerate(profile_values):
        with profile_columns[index % 2]:
            st.metric(label, str(value) if pd.notna(value) else "Not Available")

    st.divider()
    st.subheader("🧾 Purchase Summary")

    a, b, c, d, e = st.columns(5)
    a.metric("Total Bills", summary["total_bills"])
    b.metric("Total Purchase", f"₹{summary['total_purchase']:,.0f}")
    c.metric("Average Bill", f"₹{summary['avg_bill']:,.0f}")
    d.metric("Paid Amount", f"₹{summary['paid_amount']:,.0f}")
    e.metric("Outstanding", f"₹{summary['outstanding']:,.0f}")

    st.markdown(f"**Last Purchase:** {summary['last_purchase']}")

    if bills.empty:
        st.info("No purchase records found for this customer.")
        return

    st.divider()
    st.subheader("📊 Bill History")

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        date_sort = st.selectbox("Sort By", ["Latest", "Oldest", "Highest Amount", "Lowest Amount"], key=f"cqb_sort_{customer_id}")
    with f2:
        pm_opts = ["All"] + sorted([x for x in bills["Payment_Mode"].dropna().unique() if x])
        pm_filter = st.selectbox("Payment Mode", pm_opts, key=f"cqb_pm_{customer_id}")
    with f3:
        ps_opts = ["All"] + sorted([x for x in bills["Payment_Status"].dropna().unique() if x])
        ps_filter = st.selectbox("Payment Status", ps_opts, key=f"cqb_ps_{customer_id}")
    with f4:
        prod_opts = ["All"] + sorted([x for x in bills["Product_Name"].dropna().unique() if x])
        prod_filter = st.selectbox("Product", prod_opts, key=f"cqb_prod_{customer_id}")

    filtered_bills = bills.copy()
    if pm_filter != "All":
        filtered_bills = filtered_bills[filtered_bills["Payment_Mode"] == pm_filter]
    if ps_filter != "All":
        filtered_bills = filtered_bills[filtered_bills["Payment_Status"] == ps_filter]
    if prod_filter != "All":
        filtered_bills = filtered_bills[filtered_bills["Product_Name"] == prod_filter]

    if date_sort == "Latest":
        filtered_bills = filtered_bills.sort_values(by="Date", ascending=False)
    elif date_sort == "Oldest":
        filtered_bills = filtered_bills.sort_values(by="Date", ascending=True)
    elif date_sort == "Highest Amount":
        filtered_bills = filtered_bills.sort_values(by="Bill_Amount", ascending=False)
    elif date_sort == "Lowest Amount":
        filtered_bills = filtered_bills.sort_values(by="Bill_Amount", ascending=True)

    display_df = pd.DataFrame()
    display_df["Sale ID"] = filtered_bills["Sale_ID"]
    display_df["Date"] = filtered_bills["Date"].dt.strftime("%Y-%m-%d").fillna("N/A")
    display_df["Customer ID"] = filtered_bills["Customer_ID"]
    display_df["Product"] = filtered_bills["Product_Name"]
    display_df["Qty"] = filtered_bills.get("Quantity", 1)

    def fmt(val):
        try:
            return f"₹{float(val):,.2f}"
        except:
            return val

    display_df["Unit Price"] = filtered_bills.get("Selling_Price", 0).apply(fmt)
    display_df["Discount"] = filtered_bills.get("Discount_Percent", 0).astype(str) + "%"
    display_df["Bill Amount"] = filtered_bills["Bill_Amount"].apply(fmt)
    display_df["Payment"] = filtered_bills.get("Payment_Mode", "")
    display_df["Status"] = filtered_bills.get("Payment_Status", "")
    display_df["Outstanding"] = filtered_bills["Outstanding"].apply(fmt)
    display_df["Sale Type"] = filtered_bills.get("Notes", filtered_bills.get("record_type", ""))

    for col in display_df.columns:
        display_df[col] = display_df[col].fillna("").astype(str)

    st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()
    st.subheader("📄 Selected Bill Details")

    if not filtered_bills.empty:
        selected_sale_id = st.selectbox("Select a Bill / Sale ID to view details:", filtered_bills["Sale_ID"].tolist(), key=f"cqb_sale_{customer_id}")
        if selected_sale_id:
            bill_row = filtered_bills[filtered_bills["Sale_ID"] == selected_sale_id].iloc[0]

            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown(f"**Sale ID:** {bill_row.get('Sale_ID', 'N/A')}")
                st.markdown(f"**Customer:** {bill_row.get('Customer_ID', 'N/A')}")
                date_val = bill_row['Date'].strftime('%Y-%m-%d') if pd.notnull(bill_row['Date']) else 'N/A'
                st.markdown(f"**Date:** {date_val}")
                st.markdown(f"**Product:** {bill_row.get('Product_Name', 'N/A')}")
                st.markdown(f"**Quantity:** {bill_row.get('Quantity', '1')}")
                st.markdown(f"**Unit Price:** {fmt(bill_row.get('Selling_Price', 0))}")
            with bc2:
                st.markdown(f"**Discount:** {bill_row.get('Discount_Percent', 0)}%")
                st.markdown(f"**Total:** {fmt(bill_row['Bill_Amount'])}")
                st.markdown(f"**Payment Mode:** {bill_row.get('Payment_Mode', 'N/A')}")
                st.markdown(f"**Payment Status:** {bill_row.get('Payment_Status', 'N/A')}")
                st.markdown(f"**Outstanding:** {fmt(bill_row['Outstanding'])}")
                st.markdown(f"**Notes:** {bill_row.get('Notes', '')}")
    else:
        st.info("No bills match the selected filters.")
