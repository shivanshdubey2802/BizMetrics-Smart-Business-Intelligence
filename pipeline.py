import pandas as pd
import numpy as np

def load_master_csv(csv_file):
    """
    1. Load Data
    Reads the single master CSV.
    """
    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded {csv_file} successfully.")
        return df
    except Exception as e:
        print(f"Error loading master CSV: {e}")
        return pd.DataFrame()

def normalize_sku(value):
    if pd.isna(value):
        return "UNKNOWN_SKU"
    return str(value).strip().upper().replace(" ", "")

def validate_and_clean(data):
    """
    2. Validate
    Handles missing values, dates/amounts, and duplicate data.
    """
    if data is None or data.empty:
        return data

    print("Validating and cleaning data...")
    data.columns = data.columns.str.strip().str.lower()
    data = data.loc[:, ~data.columns.duplicated(keep='first')].copy()

    # Normalize SKU / Product_ID
    if 'product_id' in data.columns:
        data['product_id'] = data['product_id'].apply(normalize_sku)
    elif 'SKU' in data.columns:
        data['SKU'] = data['SKU'].apply(normalize_sku)
        data['product_id'] = data['SKU'] # Standardize to Product_ID

    product_col = "product_name"
    if product_col in data.columns:
        data[product_col] = (
            data[product_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        data["Display_Product"] = data.apply(
            lambda row: row[product_col] if row[product_col] != "" else (row.get('product_id', 'Unnamed Product')),
            axis=1
        )
    else:
        data["Display_Product"] = data.get('product_id', 'Unnamed Product')

    # Clean string amounts (e.g. ₹100,000 -> 100000, 51.7% -> 51.7)
    keywords = ['amount', 'price', 'cost', 'emi', 'principal', 'margin', 'rate', 'discount', 'balance']
    amount_cols = [
        c for c in data.columns
        if any(k in c.lower() for k in keywords)
    ]

    for col in amount_cols:
        # Regex replace and explicitly replace column with a float64 Series to handle Arrow/string dtypes safely
        cleaned = data[col].astype(str).str.replace(r'[₹,%]', '', regex=True).str.strip()
        data[col] = pd.Series(pd.to_numeric(cleaned, errors='coerce'), index=data.index, dtype='float64')

    # Clean date columns globally
    date_cols = ['date', 'due_date', 'payment_date', 'registration_date', 'start_date', 'next_payment_date', 'next_due_date']
    for d_col in date_cols:
        if d_col in data.columns:
            data[d_col] = pd.to_datetime(data[d_col], errors='coerce')

    # Ensure expected inventory, loan, and financial columns exist with safe defaults if omitted
    default_numeric_cols = {
        'current_stock': 0.0,
        'minimum_stock': 0.0,
        'maximum_stock': 100.0,
        'reorder_level': 0.0,
        'purchase_price': 0.0,
        'selling_price': 0.0,
        'quantity': 1.0,
        'discount_percent': 0.0,
        'credit_amount': 0.0,
        'amount': 0.0,
        'principal_amount': 0.0,
        'interest_rate': 0.0,
        'monthly_emi': 0.0,
        'outstanding_principal': 0.0,
        'tenure_months': 0.0,
        'total_ordered_amount': 0.0,
        'outstanding_balance': 0.0,
    }
    for col, def_val in default_numeric_cols.items():
        if col not in data.columns:
            data[col] = pd.Series(def_val, index=data.index, dtype='float64')

    # Explicitly ensure receivable columns are float64 Series BEFORE assigning numeric values
    for col in ['total_amount', 'total_paid_amount', 'outstanding_amount']:
        if col in data.columns:
            cleaned = data[col].astype(str).str.replace(r'[₹,%]', '', regex=True).str.strip()
            data[col] = pd.Series(pd.to_numeric(cleaned, errors='coerce'), index=data.index, dtype='float64')
        else:
            data[col] = pd.Series(0.0, index=data.index, dtype='float64')

    # Dynamically calculate Receivables Outstanding and Status
    is_rec = data['record_type'].astype(str).str.lower() == 'receivable'
    if is_rec.any():
        today = pd.Timestamp.today().normalize()

        # Calculate Outstanding
        inv_amt = pd.to_numeric(data.loc[is_rec, 'total_amount'], errors='coerce').fillna(0.0).astype('float64')
        paid_amt = pd.to_numeric(data.loc[is_rec, 'total_paid_amount'], errors='coerce').fillna(0.0).astype('float64')

        # Fix potential overpayments or negative amounts
        inv_amt = inv_amt.clip(lower=0.0)
        paid_amt = paid_amt.clip(lower=0.0, upper=inv_amt)
        data.loc[is_rec, 'total_amount'] = inv_amt
        data.loc[is_rec, 'total_paid_amount'] = paid_amt

        outstanding = (inv_amt - paid_amt).astype('float64')
        data.loc[is_rec, 'outstanding_amount'] = outstanding

        # Calculate Status
        due_dates = pd.to_datetime(data.loc[is_rec, 'due_date'], errors='coerce')

        statuses = []
        days_overdues = []

        for out_val, due_dt in zip(outstanding, due_dates):
            if out_val <= 0:
                statuses.append("Paid")
                days_overdues.append(0.0)
            elif pd.isna(due_dt):
                statuses.append("Pending")
                days_overdues.append(0.0)
            else:
                days_diff = float((today - due_dt).days)
                if days_diff > 0:
                    statuses.append("Overdue")
                    days_overdues.append(days_diff)
                elif days_diff >= -7:
                    statuses.append("Due Soon")
                    days_overdues.append(0.0)
                else:
                    statuses.append("Pending")
                    days_overdues.append(0.0)

        if 'status' not in data.columns:
            data['status'] = pd.Series("", index=data.index, dtype='object')
        else:
            data['status'] = data['status'].astype('object')
        data.loc[is_rec, 'status'] = statuses

        if 'days_overdue' not in data.columns:
            data['days_overdue'] = pd.Series(0.0, index=data.index, dtype='float64')
        else:
            data['days_overdue'] = pd.Series(pd.to_numeric(data['days_overdue'], errors='coerce').fillna(0.0), index=data.index, dtype='float64')
        data.loc[is_rec, 'days_overdue'] = [float(x) for x in days_overdues]

    return data

def analyze_business(data):
    """
    3. Business Profile Engine
    """
    biz_df = data[data['record_type'] == 'Business']
    if biz_df.empty:
        return {"Shop_Name": "Unknown", "Owner_Name": "Unknown"}

    # Just take the first row for the business profile
    row = biz_df.iloc[0]
    return {
        "Shop_Name": row.get("Shop_Name", "Unknown"),
        "Owner_Name": row.get("Owner_Name", "Unknown"),
        "sector": row.get("sector", "Unknown"),
        "Business_Size": row.get("Business_Size", "Unknown"),
        "status": "Active"
    }

def calculate_financials(data):
    """
    4. Financial Engine
    """
    if data.empty or 'record_type' not in data.columns:
        sales_df = pd.DataFrame()
        expenses_df = pd.DataFrame()
        inv_df = pd.DataFrame()
        loan_df = pd.DataFrame()
    else:
        sales_df = data[data['record_type'] == 'Sale'].copy()
        expenses_df = data[data['record_type'] == 'Expense'].copy()
        inv_df = data[data['record_type'] == 'Inventory'].copy()
        loan_df = data[data['record_type'] == 'Loan'].copy()

    # Pre-compute product costs and selling prices
    product_costs = {}
    product_selling_prices = {}
    for _, row in inv_df.iterrows():
        pid = row.get('product_id') or row.get('SKU')
        if pd.isna(pid): continue
        pid = normalize_sku(pid)
        cost_str = str(row.get('purchase_price', '0')).replace('₹', '').replace(',', '').strip()
        product_costs[pid] = pd.to_numeric(cost_str, errors='coerce')
        sell_str = str(row.get('selling_price', '0')).replace('₹', '').replace(',', '').strip()
        product_selling_prices[pid] = pd.to_numeric(sell_str, errors='coerce')

    revenue = 0
    cogs = 0

    # Calculate Revenue and exact COGS
    if not sales_df.empty:
        sales_df['Quantity_Num'] = pd.to_numeric(sales_df['quantity'], errors='coerce').fillna(0)

        # Calculate revenue strictly from Qty * Selling_Price * (1 - discount/100)
        if 'discount_percent' in sales_df.columns:
            sales_df['Discount_Num'] = pd.to_numeric(sales_df['discount_percent'], errors='coerce').fillna(0)
        else:
            sales_df['Discount_Num'] = 0

        # Vectorized revenue and COGS calculation
        sales_df['Normalized_PID'] = sales_df.get('product_id', '').apply(normalize_sku)

        sales_df['Sell_Price'] = sales_df['Normalized_PID'].map(product_selling_prices).fillna(0)
        sales_df['Cost_Price'] = sales_df['Normalized_PID'].map(product_costs).fillna(0)

        revenue_series = sales_df['Quantity_Num'] * sales_df['Sell_Price'] * (1 - (sales_df['Discount_Num'] / 100.0))
        cogs_series = sales_df['Quantity_Num'] * sales_df['Cost_Price']

        revenue += revenue_series.sum()
        cogs += cogs_series.sum()

    # Operating Expenses (Rent, Wages, etc.)
    # Exclude loan principal/interest if mistakenly added as expense
    if 'amount' in expenses_df.columns:
        categories_to_exclude = ['loan', 'interest', 'inventory', 'repayment', 'principal']
        valid_expenses = expenses_df[
            ~expenses_df.get('category', pd.Series(dtype=str)).astype(str).str.lower().str.contains('|'.join(categories_to_exclude), na=False)
        ]
        expenses = pd.to_numeric(
            valid_expenses['amount'].astype(str).str.replace('₹', '').str.replace(',', '').str.strip(), errors='coerce'
        ).sum()
    else:
        expenses = 0

    gross_profit = revenue - cogs
    operating_profit = gross_profit - expenses

    # Interest Expense
    interest_expense = 0
    if not loan_df.empty:
        if 'outstanding_principal' in loan_df.columns and 'interest_rate' in loan_df.columns:
            for _, row in loan_df.iterrows():
                principal = pd.to_numeric(str(row['outstanding_principal']).replace('₹', '').replace(',', '').strip(), errors='coerce')
                rate = pd.to_numeric(str(row['interest_rate']).replace('%', '').strip(), errors='coerce')
                if pd.notna(principal) and pd.notna(rate):
                    # Monthly interest assumption for the demo
                    interest_expense += principal * (rate / 100.0) / 12.0

    profit_before_tax = operating_profit - interest_expense

    # Taxes (Demo assumption: 5% flat on positive profit)
    taxes = max(profit_before_tax, 0) * 0.05

    net_profit = profit_before_tax - taxes

    # If revenue is exactly zero, we handle None or 0 gracefully
    gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
    net_margin = (net_profit / revenue * 100) if revenue > 0 else 0

    return {
        "total_revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "total_expenses": expenses,
        "operating_profit": operating_profit,
        "interest_expense": interest_expense,
        "profit_before_tax": profit_before_tax,
        "taxes": taxes,
        "net_profit": net_profit,
        "gross_margin": gross_margin,
        "profit_margin": net_margin,
        "cash_flow": net_profit
    }

def analyze_receivables(data):
    """
    5. Customer Engine / Receivables
    """
    rec_df = data[data['record_type'].astype(str).str.lower() == 'receivable']

    if rec_df.empty:
        return {
            "total_outstanding": 0.0,
            "total_invoiced": 0.0,
            "total_paid": 0.0,
            "collection_rate": 0.0,
            "overdue": 0.0,
            "due_soon": 0.0,
            "pending": 0.0,
            "days_sales_outstanding": 0
        }

    total_invoiced = pd.to_numeric(rec_df['total_amount'], errors='coerce').sum()
    total_paid = pd.to_numeric(rec_df['total_paid_amount'], errors='coerce').sum()
    total_outstanding = pd.to_numeric(rec_df['outstanding_amount'], errors='coerce').sum()

    collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0.0

    overdue = 0.0
    due_soon = 0.0
    pending = 0.0

    if 'status' in rec_df.columns:
        status_col = rec_df['status'].astype(str).str.strip().str.lower()
        outstanding_col = pd.to_numeric(rec_df['outstanding_amount'], errors='coerce').fillna(0)

        overdue = outstanding_col[status_col == 'overdue'].sum()
        due_soon = outstanding_col[status_col == 'due soon'].sum()
        pending = outstanding_col[status_col == 'pending'].sum()

    return {
        "total_outstanding": float(total_outstanding),
        "total_invoiced": float(total_invoiced),
        "total_paid": float(total_paid),
        "collection_rate": float(collection_rate),
        "overdue": float(overdue),
        "due_soon": float(due_soon),
        "pending": float(pending),
        "days_sales_outstanding": 0 # Not calculated
    }

def analyze_payables(data):
    """
    6. Vendor Engine / Payables
    """
    pay_df = data[data['record_type'] == 'Payable']
    if 'outstanding_amount' in pay_df.columns:
        total_payables = pd.to_numeric(pay_df['outstanding_amount'], errors='coerce').sum()
    else:
        total_payables = 0

    return {
        "total_payables": total_payables,
        "overdue_payables": 0 # Simplified
    }

def analyze_inventory(data):
    """
    7. Inventory Engine
    """
    inv_df = data[data['record_type'] == 'Inventory']

    total_items = len(inv_df)
    low_stock = 0
    dead_stock_val = 0

def analyze_inventory(df, include_ml=True):
    inv = df[df['record_type'] == 'Inventory'].copy()
    sales_df = df[df['record_type'] == 'Sale'].copy()

    if inv.empty:
        return {"total_skus": 0, "low_stock_items": 0, "dead_stock_value": 0, "items": [], "ml_recommendations": []}

    cur_stock = pd.to_numeric(inv['current_stock'], errors='coerce').fillna(0)
    min_stock = pd.to_numeric(inv['minimum_stock'], errors='coerce').fillna(0)
    max_stock = pd.to_numeric(inv['maximum_stock'], errors='coerce').fillna(100)
    price = pd.to_numeric(inv['purchase_price'].astype(str).str.replace('₹', '').str.replace(',', ''), errors='coerce').fillna(0)

    total_val = (cur_stock * price).sum()
    low_stock = cur_stock <= min_stock

    dead_stock_mask = cur_stock > max_stock
    dead_stock_val = (cur_stock[dead_stock_mask] * price[dead_stock_mask]).sum()

    ml_recs = []
    diagnostics = {}
    fast_moving, slow_moving, dead_stock, avg_turnover, avg_days = 0, 0, 0, 0, 0
    if include_ml:
        try:
            # Import the ML stack only when inventory forecasting is requested.
            from inventory_ml import InventoryML, generate_inventory_recommendations

            # Pre-process sales df quantities
            if not sales_df.empty:
                sales_df['quantity'] = pd.to_numeric(sales_df['quantity'], errors='coerce').fillna(0)

            ml_engine = InventoryML()
            predictions, diagnostics = ml_engine.predict_demand(sales_df, inv)
            recs_df = generate_inventory_recommendations(inv, sales_df, predictions, diagnostics)
            ml_recs = recs_df.to_dict('records')

            # Calculate new KPIs based on ML classifications (case-insensitive)
            cls_lower = recs_df['Classification'].astype(str).str.lower()
            fast_moving = int(cls_lower.str.contains('fast').sum())
            slow_moving = int(cls_lower.str.contains('slow').sum())
            dead_stock = int(cls_lower.str.contains('dead').sum())
            avg_turnover = float(recs_df['Sales_30_Days'].sum() / len(recs_df)) if len(recs_df) > 0 else 0.0
            avg_days = float(recs_df['Days_Remaining'].replace(999, np.nan).mean())

        except Exception as e:
            print(f"ML Engine error: {e}")

    # Enhance the original items payload
    items = inv.to_dict('records')
    for item in items:
        item['stock_status'] = 'Low Stock' if pd.to_numeric(item.get('current_stock', 0), errors='coerce') <= pd.to_numeric(item.get('minimum_stock', 0), errors='coerce') else 'Healthy'

    return {
        "total_skus": len(inv),
        "total_value": total_val,
        "low_stock_items": low_stock.sum(),
        "dead_stock_value": dead_stock_val,
        "fast_moving": fast_moving,
        "slow_moving": slow_moving,
        "dead_stock_count": dead_stock,
        "avg_turnover": avg_turnover,
        "avg_days_remaining": avg_days,
        "items": items,
        "ml_recommendations": ml_recs,
        "ml_diagnostics": diagnostics
    }

def forecast_demand(data):
    """
    8. Forecasting Engine
    """
    # Simple heuristic forecasting based on historical sales
    sales_df = data[data['record_type'] == 'Sale']
    if 'total_amount' in sales_df.columns:
        hist_revenue = pd.to_numeric(sales_df['total_amount'], errors='coerce').sum()
    else:
        hist_revenue = 0

    # Assume a 10% month-over-month growth for the forecast
    return {
        "next_month_projected_sales": hist_revenue * 1.10,
        "upcoming_festivals": ["Diwali", "Dussehra"],
        "recommended_stock_increase": "15%"
    }

def detect_risks(financial, receivables, payables, inventory, forecast, customers=None):
    """
    9. Risk Engine
    """
    risks = []
    score = 100

    # Financial Risk
    margin = financial.get("profit_margin", 0)
    if margin < 10:
        score -= 20
        risks.append({"category": "Financial", "risk": "Low Margin", "severity": "HIGH", "action": "Review pricing strategy", "reason": f"declining profit margin ({margin:.1f}%)"})
    elif margin < 20:
        score -= 10
        risks.append({"category": "Financial", "risk": "Suboptimal Margin", "severity": "MEDIUM", "action": "Optimize costs", "reason": f"margin is at {margin:.1f}%"})

    # Receivables Risk
    overdue = receivables.get("overdue", 0)
    if overdue > 50000:
        score -= 25
        risks.append({"category": "Receivables/Credit", "risk": "High Overdue Receivables", "severity": "HIGH", "action": "Follow up on payments immediately", "reason": f"high outstanding receivables (₹{overdue:,.2f})"})
    elif overdue > 5000:
        score -= 10
        risks.append({"category": "Receivables/Credit", "risk": "Moderate Overdue Receivables", "severity": "MEDIUM", "action": "Send payment reminders", "reason": f"overdue payments (₹{overdue:,.2f})"})

    # Inventory Risk
    low_stock = inventory.get("low_stock_items", 0)
    if low_stock > 10:
        score -= 15
        risks.append({"category": "Inventory", "risk": "Severe Inventory Shortage", "severity": "HIGH", "action": "Urgent restock needed", "reason": f"{low_stock} low-stock SKUs"})
    elif low_stock > 5:
        score -= 5
        risks.append({"category": "Inventory", "risk": "Inventory Shortage", "severity": "MEDIUM", "action": "Reorder top moving items", "reason": f"{low_stock} low-stock SKUs"})

    dead_stock_val = inventory.get("dead_stock_value", 0)
    if dead_stock_val > 20000:
        score -= 10
        risks.append({"category": "Inventory", "risk": "Excessive Dead Stock", "severity": "MEDIUM", "action": "Liquidate old inventory", "reason": f"excessive inventory value (₹{dead_stock_val:,.2f})"})

    # Customer Risk
    if customers:
        active = customers.get("active_customers", 0)
        total_rev = customers.get("total_revenue", 0)
        if active > 0 and customers.get("high_value_customers", 0) > 0:
            top_customers = [c for c in customers.get("customers", []) if c.get("Segment") == "High-Value Customer"]
            if top_customers:
                top_cust_rev = sum([c.get("Total_Spent", 0) for c in top_customers])
                if total_rev > 0 and (top_cust_rev / total_rev) > 0.5:
                    score -= 15
                    risks.append({"category": "Customer", "risk": "Customer Concentration", "severity": "HIGH", "action": "Diversify customer base", "reason": "over 50% revenue from top customers"})

    # Payables / Operational Risk
    payables_total = payables.get("total_payables", 0)
    cash = financial.get("cash_flow", 0)
    if payables_total > (cash * 2) and cash > 0:
        score -= 15
        risks.append({"category": "Operational", "risk": "High Payables Burden", "severity": "HIGH", "action": "Renegotiate payment terms", "reason": "payables exceed 2x cash flow"})

    return {
        "score": max(0, min(100, score)),
        "risk_list": risks
    }

def analyze_loans(data):
    """
    Loan Engine
    """
    loan_df = data[data['record_type'] == 'Loan'].copy()

    total_principal = 0
    outstanding_principal = 0
    monthly_emi = 0
    total_interest_paid = 0
    loans = []

    if not loan_df.empty:
        for _, row in loan_df.iterrows():
            def clean_amt(val):
                return pd.to_numeric(str(val).replace('₹', '').replace(',', '').strip(), errors='coerce') if pd.notna(val) else 0

            principal = clean_amt(row.get('principal_amount', 0))
            outstanding = clean_amt(row.get('outstanding_principal', 0))
            emi = clean_amt(row.get('monthly_emi', 0))
            rate = pd.to_numeric(str(row.get('interest_rate', 0)).replace('%', '').strip(), errors='coerce') if pd.notna(row.get('interest_rate')) else 0

            total_principal += principal
            outstanding_principal += outstanding
            monthly_emi += emi

            # Rough estimation of total interest paid so far based on principal reduction
            principal_paid = principal - outstanding
            if principal_paid > 0 and emi > 0:
                # Approximate number of months paid
                months_paid = principal_paid / (emi - (outstanding * (rate / 100.0) / 12.0))
                if months_paid > 0:
                     total_interest_paid += (emi * months_paid) - principal_paid

            loans.append({
                "Loan_Name": row.get('loan_type', 'Unknown Loan'),
                "Lender": row.get('loan_provider', 'Unknown'),
                "Principal": principal,
                "Outstanding": outstanding,
                "interest_rate": rate,
                "Monthly_Payment": emi,
                "start_date": str(row.get('start_date', 'N/A')),
                "End_Date": "N/A", # Needs tenure
                "status": "Active" if outstanding > 0 else "Closed"
            })

    # Calculate monthly interest burden on current outstanding
    monthly_interest = 0
    for l in loans:
        monthly_interest += l['Outstanding'] * (l['interest_rate'] / 100.0) / 12.0

    return {
        "total_principal": total_principal,
        "outstanding_principal": outstanding_principal,
        "monthly_interest": monthly_interest,
        "total_interest_paid": total_interest_paid,
        "monthly_emi": monthly_emi,
        "active_loans": len([l for l in loans if l['status'] == 'Active']),
        "loans": loans
    }

def analyze_data_quality(data):
    """
    Data Quality Engine - Context Aware Scoring
    """
    if data is None or data.empty:
        return {"score": 0, "total_records": 0, "missing_values": 0, "duplicate_records": 0,
                "invalid_values": 0, "columns_analyzed": 0, "columns": [], "recommendations": []}

    total_records = len(data)
    recommendations = set()
    cols_data = []

    # Define required fields per record type
    req_map = {
        'sale': ['sale_id', 'date', 'product_id', 'quantity', 'selling_price'],
        'inventory': ['product_id', 'product_name', 'current_stock', 'minimum_stock', 'reorder_level', 'purchase_price', 'selling_price'],
        'receivable': ['customer_id', 'credit_amount', 'due_date', 'amount_paid', 'payment_status'],
        'expense': ['expense_id', 'category', 'amount'],
        'loan': ['loan_id', 'principal_amount', 'interest_rate', 'monthly_emi', 'start_date', 'outstanding_principal'],
        'scheme': ['scheme_name', 'type'],
        'customer': ['customer_id', 'customer_name', 'contact_number', 'city']
    }

    # 1. Context-aware missing values (30%)
    total_required_expected = 0
    total_required_missing = 0

    # Dictionary to track legitimate missing vs total for column-level table
    col_required_expected = {c: 0 for c in data.columns}
    col_required_missing = {c: 0 for c in data.columns}

    if 'record_type' in data.columns:
        for rtype, group in data.groupby(data['record_type'].astype(str).str.lower()):
            req_cols = req_map.get(rtype, [])
            for c in req_cols:
                if c in data.columns:
                    expected = len(group)
                    missing = group[c].isna().sum() + (group[c].astype(str).str.strip() == '').sum()

                    total_required_expected += expected
                    total_required_missing += missing
                    col_required_expected[c] += expected
                    col_required_missing[c] += missing

    missing_penalty = 0
    if total_required_expected > 0:
        missing_penalty = (total_required_missing / total_required_expected) * 30
        if missing_penalty > 0:
            recommendations.add("Some records are missing required fields specific to their transaction type.")

    # 2. Duplicate records (20%)
    dup_penalty = 0
    total_dups = 0
    key_cols = ['sale_id', 'product_id', 'customer_id', 'expense_id', 'loan_id']
    for kc in key_cols:
        if kc in data.columns:
            # Check for duplicates, ignoring NaNs
            valid_mask = data[kc].notna() & (data[kc].astype(str).str.strip() != '')
            dups = data.loc[valid_mask, kc].duplicated().sum()
            total_dups += dups
            if dups > 0:
                recommendations.add(f"Duplicate transaction identifiers detected in {kc}. Review these before financial reporting.")

    if total_records > 0:
        # A 5% duplicate rate loses all 20 points
        dup_rate = total_dups / total_records
        dup_penalty = min(20, (dup_rate / 0.05) * 20)

    # 3. Invalid dates (15%) & 4. Invalid numerics (15%)
    date_penalty = 0
    num_penalty = 0
    total_invalid = 0

    date_cols = ['date', 'due_date', 'payment_date', 'registration_date', 'start_date', 'next_payment_date', 'next_due_date']
    num_cols = ['quantity', 'selling_price', 'purchase_price', 'amount', 'credit_amount', 'amount_paid', 'outstanding_amount', 'principal_amount', 'monthly_emi', 'current_stock', 'minimum_stock']

    col_invalid_count = {c: 0 for c in data.columns}

    for c in data.columns:
        invalid_count = 0
        if c in date_cols:
            orig_notna = data[c].notna() & (data[c].astype(str).str.strip() != '')
            coerced = pd.to_datetime(data[c], errors='coerce')
            invalid_count = (orig_notna & coerced.isna()).sum()
            if invalid_count > 0:
                recommendations.add(f"Some records contain invalid dates in '{c}'. Correct these to improve trend calculations.")

        elif c in num_cols:
            orig_notna = data[c].notna() & (data[c].astype(str).str.strip() != '')
            coerced = pd.to_numeric(data[c], errors='coerce')
            unparseable = orig_notna & coerced.isna()
            negative = coerced < 0
            invalid_count = (unparseable | negative).sum()
            if invalid_count > 0:
                recommendations.add(f"Invalid numeric values (negative or unparseable text) detected in '{c}'.")

        col_invalid_count[c] = invalid_count
        total_invalid += invalid_count

    if total_records > 0:
        date_invalid = sum(col_invalid_count[c] for c in date_cols if c in col_invalid_count)
        date_rate = date_invalid / total_records
        date_penalty = min(15, (date_rate / 0.05) * 15)

        num_invalid = sum(col_invalid_count[c] for c in num_cols if c in col_invalid_count)
        num_rate = num_invalid / total_records
        num_penalty = min(15, (num_rate / 0.05) * 15)

    # 5. Missing Important IDs (10%)
    id_penalty = 0
    missing_ids = 0
    for id_col in ['customer_id', 'product_id', 'business_id']:
        if id_col in data.columns:
            missing_ids += col_required_missing.get(id_col, 0)

    if total_required_expected > 0:
        id_rate = missing_ids / total_required_expected
        id_penalty = min(10, (id_rate / 0.05) * 10)

    # 6. Schema Completeness (10%)
    schema_penalty = 0
    expected_core_cols = ['record_type', 'date', 'product_id', 'quantity', 'total_amount']
    missing_schema = [c for c in expected_core_cols if c not in data.columns]
    if missing_schema:
        schema_penalty = 10
        recommendations.add("Dataset is missing fundamental core columns (e.g. record_type, date, total_amount).")

    if not recommendations:
        recommendations.add("Data quality is strong. No major integrity issues were detected.")

    score = 100 - (missing_penalty + dup_penalty + date_penalty + num_penalty + id_penalty + schema_penalty)
    score = max(0, min(100, score))

    # Build columns data
    for col in data.columns:
        expected = col_required_expected.get(col, 0)
        req_missing = col_required_missing.get(col, 0)
        invalid = col_invalid_count.get(col, 0)

        if expected > 0:
            missing_pct = (req_missing / expected) * 100
        else:
            missing_pct = 0

        quality = "Good"
        if missing_pct > 20 or invalid > (total_records * 0.05):
            quality = "Critical"
        elif missing_pct > 5 or invalid > 0:
            quality = "Warning"

        cols_data.append({
            "Column": col,
            "Missing": req_missing,
            "Missing_Pct": missing_pct,
            "Invalid": invalid,
            "Unique": data[col].nunique(),
            "Quality": quality
        })

    return {
        "score": score,
        "total_records": total_records,
        "missing_values": total_required_missing,
        "duplicate_records": total_dups,
        "invalid_values": total_invalid,
        "columns_analyzed": len(data.columns),
        "columns": cols_data,
        "recommendations": list(recommendations)
    }

def check_scheme_eligibility(business, financial, customers=None):
    """
    10. Scheme Engine
    """
    schemes = [
        {"scheme_name": "MUDRA Yojana", "eligible": True, "missing_docs": ["Updated GST Return", "Business Pan Card"], "type": "GOVT"},
        {"scheme_name": "PMEGP", "eligible": business.get("sector", "") == "Manufacturing", "reason": "Manufacturing sector only", "type": "GOVT"}
    ]

    # Business promotional schemes
    promotions = []

    # Data-driven recommendations
    if customers:
        high_val = customers.get("high_value_customers", 0)
        if high_val > 0:
            promotions.append({
                "Scheme Name": "Bulk Purchase Scheme",
                "Target Customers": "High-volume customers",
                "Target Products": "Top selling products",
                "Reason": "Customers with high historical order quantities may respond to volume incentives.",
                "Recommended Period": "End of month",
                "Expected Objective": "Increase order volume",
                "Priority": "High",
                "Type": "DATA-DRIVEN"
            })

        inactive = customers.get("total_customers", 0) - customers.get("active_customers", 0)
        if inactive > 10:
            promotions.append({
                "Scheme Name": "Win-back Campaign",
                "Target Customers": "Inactive Customers",
                "Target Products": "Standard inventory",
                "Reason": f"You have {inactive} inactive customers who haven't purchased recently.",
                "Recommended Period": "Immediate",
                "Expected Objective": "Customer reactivation",
                "Priority": "Medium",
                "Type": "DATA-DRIVEN"
            })

    # Market-based recommendations
    promotions.append({
        "Scheme Name": "Diwali Special Offer",
        "Target Customers": "All retail customers",
        "Target Products": "Electronics / High-margin items",
        "Reason": "Major Indian festival driving significant retail sales.",
        "Recommended Period": "Pre-Diwali week",
        "Expected Objective": "Boost seasonal revenue",
        "Priority": "High",
        "Type": "MARKET-BASED"
    })

    return {
        "govt_schemes": schemes,
        "promotions": promotions
    }



def calculate_health_score(financial, receivables, payables, inventory, forecast):
    """
    12. Health Score Engine
    """
    score = 100

    if financial.get("profit_margin", 0) < 20:
        score -= 10
    if receivables.get("overdue", 0) > 5000:
        score -= 10
    if inventory.get("low_stock_items", 0) > 0:
        score -= 10
    if inventory.get("dead_stock_value", 0) > 5000:
        score -= 10
    if payables.get("total_payables", 0) > 30000:
        score -= 10

    return max(0, min(100, score))

def analyze_customers(data):
    """
    13. Customer Engine (CRM)
    """
    if data.empty or 'record_type' not in data.columns:
        return {"total_customers": 0, "active_customers": 0, "new_customers": 0, "high_value_customers": 0, "total_revenue": 0, "aov": 0, "customers": []}

    sales_df = data[data['record_type'] == 'Sale'].copy()
    cust_df = data[data['record_type'] == 'Receivable'].copy() # We mapped Customers to Receivable in consolidate script

    if cust_df.empty:
        return {"total_customers": 0, "active_customers": 0, "new_customers": 0, "high_value_customers": 0, "total_revenue": 0, "aov": 0, "customers": []}

    # Clean sales amounts
    if not sales_df.empty:
        sales_df['Quantity_Num'] = pd.to_numeric(sales_df['quantity'], errors='coerce').fillna(0)

        # Pre-compute product selling prices for accurate revenue (we can also just use Total_Amount if it's there and valid, but prompt asked for strict math)
        # However, the strict math is Qty * SP * (1-Discount/100).
        # Let's extract numbers from 'selling_price' and 'total_amount'
        def extract_num(val):
            return pd.to_numeric(str(val).replace('₹', '').replace(',', '').strip(), errors='coerce')

        sales_df['Selling_Price_Num'] = sales_df['selling_price'].apply(extract_num).fillna(0)

        if 'discount_percent' in sales_df.columns:
            sales_df['Discount_Num'] = pd.to_numeric(sales_df['discount_percent'], errors='coerce').fillna(0)
        else:
            sales_df['Discount_Num'] = 0

        sales_df['Revenue'] = sales_df['Quantity_Num'] * sales_df['Selling_Price_Num'] * (1 - (sales_df['Discount_Num'] / 100.0))
        if 'date' in sales_df.columns:
            sales_df['Date_Parsed'] = pd.to_datetime(sales_df['date'], errors='coerce')
        else:
            sales_df['Date_Parsed'] = pd.NaT
    else:
        sales_df = pd.DataFrame(columns=['customer_id', 'Revenue', 'Quantity_Num', 'Date_Parsed', 'product_id'])

    customers_list = []
    total_customers = len(cust_df)
    active_customers = 0
    new_customers = 0
    high_value_customers = 0
    total_revenue = 0
    total_orders_global = 0

    now = pd.to_datetime('2026-08-30')

    # Optimize by pre-aggregating sales
    sales_agg = {}
    if not sales_df.empty and 'customer_id' in sales_df.columns:
        agg_df = sales_df.groupby('customer_id').agg(
            orders=('Revenue', 'size'),
            spent=('Revenue', 'sum'),
            qty_purchased=('Quantity_Num', 'sum'),
            first_purchase=('Date_Parsed', 'min'),
            last_purchase=('Date_Parsed', 'max')
        ).reset_index()

        # Most purchased product
        if 'product_id' in sales_df.columns:
            prod_counts = sales_df.groupby(['customer_id', 'product_id'])['Quantity_Num'].sum().reset_index()
            idx = prod_counts.groupby('customer_id')['Quantity_Num'].idxmax()
            most_purchased_df = prod_counts.loc[idx].set_index('customer_id')['product_id']
            agg_df['most_purchased'] = agg_df['customer_id'].map(most_purchased_df)

        sales_agg = agg_df.set_index('customer_id').to_dict(orient='index')

    for _, c_row in cust_df.iterrows():
        c_id = c_row.get('customer_id', 'UNKNOWN')
        c_name = c_row.get('customer_name', 'Unknown')
        c_business = c_row.get('business_name', 'Unknown')
        c_phone = c_row.get('mobile_number', c_row.get('contact_number', c_row.get('phone', '')))
        c_phone = str(c_phone).strip().replace('.0', '') if pd.notna(c_phone) else ''
        if not (len(c_phone) == 10 and c_phone[0] in '6789' and c_phone.isdigit()):
            c_phone = ""
        c_email = c_row.get('email', 'N/A')
        c_city = c_row.get('city', 'Unknown')
        c_type = c_row.get('customer_type', 'Unknown')
        c_reg = pd.to_datetime(c_row.get('registration_date', None), errors='coerce')
        c_rating = c_row.get('customer_rating', 0)

        c_stats = sales_agg.get(c_id, {})
        orders = c_stats.get('orders', 0)
        spent = c_stats.get('spent', 0)
        qty_purchased = c_stats.get('qty_purchased', 0)
        first_purchase = c_stats.get('first_purchase', pd.NaT)
        last_purchase = c_stats.get('last_purchase', pd.NaT)
        most_purchased = c_stats.get('most_purchased', "N/A")
        if pd.isna(most_purchased):
            most_purchased = "N/A"

        aov = (spent / orders) if orders > 0 else 0

        # Segmentation Logic
        days_since_last = (now - last_purchase).days if pd.notna(last_purchase) else 999
        days_since_reg = (now - c_reg).days if pd.notna(c_reg) else 999

        if orders == 0:
            segment = "Inactive Customer"
            status = "Inactive"
        elif days_since_last > 60:
            segment = "Inactive Customer"
            status = "Inactive"
        elif orders == 1:
            segment = "One-Time Customer"
            status = "Active"
        elif days_since_last > 30:
            segment = "At-Risk Customer"
            status = "At Risk"
        elif spent > 50000:
            segment = "High-Value Customer"
            status = "Active"
        else:
            segment = "Regular Customer"
            status = "Active"

        if days_since_reg <= 30:
            status = "New"
            if segment not in ["High-Value Customer"]:
                segment = "New Customer"

        if status in ["Active", "New"]:
            active_customers += 1
        if segment == "New Customer":
            new_customers += 1
        if segment == "High-Value Customer":
            high_value_customers += 1

        total_revenue += spent
        total_orders_global += orders

        customers_list.append({
            "customer_id": c_id,
            "customer_name": c_name,
            "business_name": c_business,
            "Mobile_Number": c_phone,
            "email": c_email,
            "city": c_city,
            "customer_type": c_type,
            "registration_date": c_reg.strftime('%Y-%m-%d') if pd.notna(c_reg) else "N/A",
            "customer_rating": c_rating,
            "Total_Orders": orders,
            "Total_Spent": spent,
            "AOV": aov,
            "Total_Quantity": qty_purchased,
            "First_Purchase_Date": first_purchase.strftime('%Y-%m-%d') if pd.notna(first_purchase) else "N/A",
            "Last_Purchase_Date": last_purchase.strftime('%Y-%m-%d') if pd.notna(last_purchase) else "N/A",
            "Most_Purchased_Product": most_purchased,
            "Segment": segment,
            "status": status
        })

    # Sort customers by spent descending
    customers_list.sort(key=lambda x: x['Total_Spent'], reverse=True)

    return {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "new_customers": new_customers,
        "high_value_customers": high_value_customers,
        "total_revenue": total_revenue,
        "total_orders": total_orders_global,
        "aov": (total_revenue / total_orders_global) if total_orders_global > 0 else 0,
        "customers": customers_list
    }

def run_pipeline(data, include_inventory_ml=False):
    """
    Main orchestration pipeline that runs all engines in sequence.
    """
    print("Starting Unified Rural Business Pipeline...")

    data = validate_and_clean(data)

    business = analyze_business(data)
    financial = calculate_financials(data)
    receivables = analyze_receivables(data)
    payables = analyze_payables(data)
    inventory = analyze_inventory(data, include_ml=include_inventory_ml)
    forecast = forecast_demand(data)
    customers = analyze_customers(data)

    risks = detect_risks(financial, receivables, payables, inventory, forecast, customers)
    schemes = check_scheme_eligibility(business, financial, customers)
    loans = analyze_loans(data)
    data_quality = analyze_data_quality(data)
    health_score = calculate_health_score(financial, receivables, payables, inventory, forecast)

    context = {
        "business": business,
        "financial": financial,
        "receivables": receivables,
        "payables": payables,
        "inventory": inventory,
        "forecast": forecast,
        "risks": risks,
        "schemes": schemes,
        "loans": loans,
        "data_quality": data_quality,
        "health_score": health_score
    }


    result = {
        "business": business,
        "financial": financial,
        "receivables": receivables,
        "payables": payables,
        "inventory": inventory,
        "forecast": forecast,
        "customers": customers,
        "risks": risks,
        "schemes": schemes,
        "loans": loans,
        "data_quality": data_quality,
        "health_score": health_score
    }

    print("Pipeline execution complete.")
    return result

if __name__ == "__main__":
    from utils.data_loader import find_master_csv, find_demo_csv
    p = find_master_csv() or find_demo_csv()
    if p:
        df = pd.read_csv(p)
        res = run_pipeline(df)
        print("Pipeline execution succeeded on:", p.name)
