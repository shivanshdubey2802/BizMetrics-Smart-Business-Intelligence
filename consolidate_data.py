import pandas as pd
import glob

def consolidate():
    dfs = []
    print("Reading distinct CSV files...")

    # 1. Business Profile
    try:
        b = pd.read_csv('01_business_profile.csv', on_bad_lines='skip')
        b['record_type'] = 'Business'
        dfs.append(b)
    except Exception as e:
        print(f"Failed to read business profile: {e}")

    # 2. Inventory
    try:
        p = pd.read_csv('02_products_inventory.csv', on_bad_lines='skip')
        p['record_type'] = 'Inventory'
        dfs.append(p)
    except Exception as e:
        print(f"Failed to read inventory: {e}")

    # 3. Sales
    try:
        s = pd.read_csv('03_sales_transactions.csv', on_bad_lines='skip')
        s['record_type'] = 'Sale'
        dfs.append(s)
    except Exception as e:
        print(f"Failed to read sales: {e}")

    # 4. Expenses
    try:
        e = pd.read_csv('04_expenses.csv', on_bad_lines='skip')
        e['record_type'] = 'Expense'
        dfs.append(e)
    except Exception as exc:
        print(f"Failed to read expenses: {exc}")

    # 5. Customers
    try:
        c = pd.read_csv('05_customers_receivables.csv', on_bad_lines='skip')
        c['record_type'] = 'Receivable'
        dfs.append(c)
    except Exception as exc:
        print(f"Failed to read customers: {exc}")

    # 6. Vendors
    try:
        v = pd.read_csv('06_vendors_payables.csv', on_bad_lines='skip')
        v['record_type'] = 'Payable'
        dfs.append(v)
    except Exception as exc:
        print(f"Failed to read vendors: {exc}")

    # 7. Loans
    try:
        l = pd.read_csv('07_loans_emi.csv', on_bad_lines='skip')
        l['record_type'] = 'Loan'
        dfs.append(l)
    except Exception as exc:
        print(f"Failed to read loans: {exc}")

    master_df = pd.concat(dfs, ignore_index=True)
    master_df.to_csv('rural_business_master_data.csv', index=False)
    print(f"Consolidated data into rural_business_master_data.csv with {len(master_df)} rows and {len(master_df.columns)} columns.")

if __name__ == "__main__":
    consolidate()
