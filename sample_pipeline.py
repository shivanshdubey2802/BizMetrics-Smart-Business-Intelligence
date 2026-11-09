"""
Sample Python Pipeline for Gupta Hardware Mart
Demonstrates how to load and process the CSV data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

class RuralBusinessAdvisor:
    """Main pipeline class for business advisory system"""

    def __init__(self, data_path: str):
        """Initialize with path to CSV files"""
        self.data_path = Path(data_path)
        self.business = None
        self.products = None
        self.sales = None
        self.expenses = None
        self.customers = None
        self.vendors = None
        self.loans = None

        # Calculated metrics storage
        self.financial_metrics = {}
        self.inventory_metrics = {}
        self.receivables_metrics = {}
        self.risk_indicators = []

    def load_data(self):
        """Load all CSV files"""
        print("📁 Loading business data...")

        try:
            self.business = pd.read_csv(self.data_path / '01_business_profile.csv')
            self.products = pd.read_csv(self.data_path / '02_products_inventory.csv')
            self.sales = pd.read_csv(self.data_path / '03_sales_transactions.csv')
            self.expenses = pd.read_csv(self.data_path / '04_expenses.csv')
            self.customers = pd.read_csv(self.data_path / '05_customers_receivables.csv')
            self.vendors = pd.read_csv(self.data_path / '06_vendors_payables.csv')
            self.loans = pd.read_csv(self.data_path / '07_loans_emi.csv')

            # Clean currency columns (remove ₹ symbol)
            self._clean_currency()

            print("✅ Data loaded successfully")
            self.display_business_profile()

        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            return False
        return True

    def _clean_currency(self):
        """Remove ₹ symbol and convert to float"""
        currency_cols = {
            'sales': ['total_amount', 'selling_price', 'discount_percent', 'credit_amount'],
            'expenses': ['amount'],
            'customers': ['Total_Credit_Sales', 'Total_Payments', 'outstanding_amount'],
            'vendors': ['Total_Ordered', 'Total_Paid', 'outstanding_amount'],
            'products': ['purchase_price', 'selling_price', 'current_stock', 'maximum_stock', 'minimum_stock'],
            'loans': ['principal_amount', 'monthly_emi', 'outstanding_principal']
        }

        for df_name, cols in currency_cols.items():
            df = getattr(self, df_name, None)
            if df is not None:
                for col in cols:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.replace('₹', '').str.replace(',', '').astype(float)

    def display_business_profile(self):
        """Display business overview"""
        if self.business is not None:
            b = self.business.iloc[0]
            print("\n" + "="*60)
            print(f"📊 BUSINESS PROFILE: {b['Shop_Name']}")
            print("="*60)
            print(f"Owner: {b['Owner_Name']}")
            print(f"Location: {b['Village_Town']}, {b['State']}")
            print(f"Sector: {b['sector']} | Size: {b['Business_Size']}")
            print(f"Active Since: {b['Business_Start_Date']}")
            print(f"Investment: ₹{b['Initial_Investment']:,} → ₹{b['Current_Investment']:,}")
            print(f"Employees: {b['Number_of_Employees']}")
            print("="*60 + "\n")

    # =============== FINANCIAL ENGINE ===============

    def calculate_financial_metrics(self):
        """Calculate all financial metrics"""
        print("💰 Calculating financial metrics...")

        # Revenue
        total_revenue = self.sales['total_amount'].sum()
        cash_sales = self.sales[self.sales['payment_mode'] == 'Cash']['total_amount'].sum()
        credit_sales = self.sales[self.sales['payment_mode'] == 'Credit']['total_amount'].sum()
        digital_sales = self.sales[self.sales['payment_mode'].isin(['UPI', 'Digital'])]['total_amount'].sum()

        # Expenses
        total_expenses = self.expenses['amount'].sum()
        fixed_costs = self.expenses[self.expenses['is_fixed'] == 'Yes']['amount'].sum()
        variable_costs = self.expenses[self.expenses['is_fixed'] == 'No']['amount'].sum()

        # EMI (from loans)
        total_emi = self.loans['monthly_emi'].sum()

        # Profit
        net_profit = total_revenue - total_expenses
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

        # COGS approximation (from product costs)
        cogs = self._estimate_cogs()
        gross_profit = total_revenue - cogs
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        # ROI
        investment = self.business.iloc[0]['Current_Investment']
        annual_profit = net_profit * 12  # Annualize August profit
        roi = (annual_profit / investment * 100) if investment > 0 else 0

        # Break-even
        contribution_margin_ratio = (gross_margin / 100)
        breakeven_revenue = fixed_costs / contribution_margin_ratio if contribution_margin_ratio > 0 else 0

        # Cash flow
        collected_cash = self.sales[self.sales['payment_status'] == 'Completed']['total_amount'].sum()
        paid_expenses = self.expenses[self.expenses['payment_status'] == 'Paid']['amount'].sum()
        cash_flow = collected_cash - paid_expenses

        # Debt burden
        debt_burden_ratio = (total_emi / total_revenue * 100) if total_revenue > 0 else 0

        self.financial_metrics = {
            'total_revenue': total_revenue,
            'cash_sales': cash_sales,
            'credit_sales': credit_sales,
            'digital_sales': digital_sales,
            'total_expenses': total_expenses,
            'fixed_costs': fixed_costs,
            'variable_costs': variable_costs,
            'cogs': cogs,
            'gross_profit': gross_profit,
            'gross_margin': gross_margin,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'total_emi': total_emi,
            'debt_burden_ratio': debt_burden_ratio,
            'roi': roi,
            'breakeven_revenue': breakeven_revenue,
            'cash_flow': cash_flow,
        }

        print("✅ Financial metrics calculated")
        self.display_financial_summary()

    def _estimate_cogs(self):
        """Estimate COGS from sales and product margins"""
        total_cogs = 0
        for _, sale in self.sales.iterrows():
            product = self.products[self.products['product_id'] == sale['product_id']]
            if not product.empty:
                cost = product.iloc[0]['purchase_price'] * sale['quantity']
                total_cogs += cost
        return total_cogs

    def display_financial_summary(self):
        """Display financial metrics"""
        m = self.financial_metrics
        print("\n" + "="*60)
        print("💵 AUGUST 2026 FINANCIAL SUMMARY")
        print("="*60)
        print(f"Total Revenue:        ₹{m['total_revenue']:>12,.0f}")
        print(f"  ├─ Cash Sales:      ₹{m['cash_sales']:>12,.0f} ({m['cash_sales']/m['total_revenue']*100:.0f}%)")
        print(f"  ├─ Credit Sales:    ₹{m['credit_sales']:>12,.0f} ({m['credit_sales']/m['total_revenue']*100:.0f}%)")
        print(f"  └─ Digital Sales:   ₹{m['digital_sales']:>12,.0f} ({m['digital_sales']/m['total_revenue']*100:.0f}%)")
        print(f"\nGross Profit:         ₹{m['gross_profit']:>12,.0f} ({m['gross_margin']:.1f}%)")
        print(f"Total Expenses:       ₹{m['total_expenses']:>12,.0f}")
        print(f"  ├─ Fixed Costs:     ₹{m['fixed_costs']:>12,.0f} ({m['fixed_costs']/m['total_expenses']*100:.0f}%)")
        print(f"  └─ Variable Costs:  ₹{m['variable_costs']:>12,.0f} ({m['variable_costs']/m['total_expenses']*100:.0f}%)")
        print(f"\nNet Profit:           ₹{m['net_profit']:>12,.0f}")
        print(f"Profit Margin:        {m['profit_margin']:>12.2f}% {'🔴 CRITICAL' if m['profit_margin'] < 5 else '🟢 HEALTHY'}")
        print(f"\nDebt Burden Ratio:    {m['debt_burden_ratio']:>12.2f}% {'🟡 CAUTION' if m['debt_burden_ratio'] > 15 else '🟢 SAFE'}")
        print(f"Break-even Revenue:   ₹{m['breakeven_revenue']:>12,.0f}")
        print(f"ROI (Annualized):     {m['roi']:>12.2f}%")
        print("="*60 + "\n")

    # =============== RECEIVABLES ENGINE ===============

    def analyze_receivables(self):
        """Analyze customer receivables"""
        print("👥 Analyzing receivables...")

        total_receivables = self.customers['outstanding_amount'].sum()
        overdue_receivables = self.customers[self.customers['payment_status'].isin(['Attention', 'Overdue'])]['outstanding_amount'].sum()

        # Ageing bucket
        normal = self.customers[self.customers['Days_Overdue'] <= 7]['outstanding_amount'].sum()
        attention = self.customers[(self.customers['Days_Overdue'] > 7) & (self.customers['Days_Overdue'] <= 30)]['outstanding_amount'].sum()
        overdue = self.customers[self.customers['Days_Overdue'] > 30]['outstanding_amount'].sum()

        # DSO
        daily_revenue = self.financial_metrics['total_revenue'] / 30
        dso = (total_receivables / daily_revenue) if daily_revenue > 0 else 0

        self.receivables_metrics = {
            'total_receivables': total_receivables,
            'overdue_receivables': overdue_receivables,
            'normal': normal,
            'attention': attention,
            'overdue': overdue,
            'days_sales_outstanding': dso,
        }

        print("✅ Receivables analyzed")
        self.display_receivables_summary()

    def display_receivables_summary(self):
        """Display receivables analysis"""
        m = self.receivables_metrics
        total_rev = self.financial_metrics['total_revenue']
        print("\n" + "="*60)
        print("📋 RECEIVABLES ANALYSIS")
        print("="*60)
        print(f"Total Outstanding:   ₹{m['total_receivables']:>12,.0f} ({m['total_receivables']/total_rev*100:.1f}% of revenue)")
        print(f"  ├─ Normal (0-7d):   ₹{m['normal']:>12,.0f} ({m['normal']/m['total_receivables']*100:.1f}%)")
        print(f"  ├─ Attention (8-30d):₹{m['attention']:>12,.0f} ({m['attention']/m['total_receivables']*100:.1f}%)")
        print(f"  └─ Overdue (30+d):  ₹{m['overdue']:>12,.0f} ({m['overdue']/m['total_receivables']*100:.1f}%)")
        print(f"\nDays Sales Outstanding: {m['days_sales_outstanding']:.1f} days")
        print(f"Collection Risk:     {'🔴 HIGH' if m['overdue'] > total_rev*0.1 else '🟡 MEDIUM' if m['overdue'] > total_rev*0.05 else '🟢 LOW'}")

        # Worst customers
        print("\n⚠️  Problem Customers:")
        problem_customers = self.customers[self.customers['outstanding_amount'] > total_rev*0.05].sort_values('outstanding_amount', ascending=False)
        for _, cust in problem_customers.iterrows():
            print(f"  • {cust['customer_name']}: ₹{cust['outstanding_amount']:,.0f} ({cust['Days_Overdue']:.0f} days overdue)")

        print("="*60 + "\n")

    # =============== INVENTORY ENGINE ===============

    def analyze_inventory(self):
        """Analyze inventory status"""
        print("📦 Analyzing inventory...")

        low_stock = self.products[self.products['current_stock'] < self.products['reorder_level']]
        dead_stock = self.products[self.products['current_stock'] > self.products['maximum_stock']]

        total_inventory_value = (self.products['current_stock'] * self.products['purchase_price']).sum()

        self.inventory_metrics = {
            'total_items': len(self.products),
            'low_stock_items': len(low_stock),
            'dead_stock_items': len(dead_stock),
            'total_inventory_value': total_inventory_value,
            'low_stock': low_stock,
            'dead_stock': dead_stock,
        }

        print("✅ Inventory analyzed")
        self.display_inventory_summary()

    def display_inventory_summary(self):
        """Display inventory analysis"""
        m = self.inventory_metrics
        print("\n" + "="*60)
        print("📦 INVENTORY STATUS")
        print("="*60)
        print(f"Total SKUs:          {m['total_items']}")
        print(f"Total Inventory Value: ₹{m['total_inventory_value']:>12,.0f}")
        print(f"\n⚠️  LOW STOCK ITEMS ({m['low_stock_items']}):")
        for _, prod in m['low_stock'].iterrows():
            print(f"  • {prod['product_name']}: {prod['current_stock']:.0f} units (reorder at {prod['reorder_level']:.0f})")

        print(f"\n⚠️  DEAD STOCK ITEMS ({m['dead_stock_items']}):")
        for _, prod in m['dead_stock'].iterrows():
            value = prod['current_stock'] * prod['purchase_price']
            print(f"  • {prod['product_name']}: {prod['current_stock']:.0f} units = ₹{value:,.0f} stuck")

        print("="*60 + "\n")

    # =============== RISK ENGINE ===============

    def detect_risks(self):
        """Automatic risk detection"""
        print("⚠️  Detecting risks...")

        self.risk_indicators = []
        m = self.financial_metrics
        total_rev = m['total_revenue']

        # Financial risks
        if m['profit_margin'] < 5:
            self.risk_indicators.append({
                'risk': 'Thin Profit Margin',
                'severity': 'CRITICAL',
                'value': f"{m['profit_margin']:.2f}%",
                'action': 'Review pricing or reduce discounts'
            })

        if m['debt_burden_ratio'] > 15:
            self.risk_indicators.append({
                'risk': 'High Debt Burden',
                'severity': 'CAUTION',
                'value': f"{m['debt_burden_ratio']:.2f}%",
                'action': 'Avoid new borrowing'
            })

        # Receivables risk
        if self.receivables_metrics['overdue_receivables'] > total_rev * 0.1:
            self.risk_indicators.append({
                'risk': 'High Overdue Receivables',
                'severity': 'HIGH',
                'value': f"₹{self.receivables_metrics['overdue_receivables']:,.0f}",
                'action': 'Accelerate collections'
            })

        # Inventory risk
        if self.inventory_metrics['low_stock_items'] > 0:
            self.risk_indicators.append({
                'risk': 'Low Stock Warning',
                'severity': 'MEDIUM',
                'value': f"{self.inventory_metrics['low_stock_items']} items",
                'action': 'Place reorder immediately'
            })

        if self.inventory_metrics['dead_stock_items'] > 0:
            self.risk_indicators.append({
                'risk': 'Dead Stock',
                'severity': 'MEDIUM',
                'value': f"₹{self.inventory_metrics['dead_stock'].apply(lambda x: x['current_stock'] * x['purchase_price']).sum():,.0f}",
                'action': 'Plan promotional clearance'
            })

        print("✅ Risk detection complete")
        self.display_risk_summary()

    def display_risk_summary(self):
        """Display risk indicators"""
        print("\n" + "="*60)
        print("🚨 RISK SUMMARY")
        print("="*60)

        if not self.risk_indicators:
            print("✅ No risks detected!")
        else:
            for risk in sorted(self.risk_indicators, key=lambda x: {'CRITICAL': 0, 'HIGH': 1, 'CAUTION': 2}.get(x['severity'], 3)):
                emoji = '🔴' if risk['severity'] == 'CRITICAL' else '🟠' if risk['severity'] == 'HIGH' else '🟡'
                print(f"{emoji} {risk['risk']}: {risk['value']}")
                print(f"   → {risk['action']}")

        print("="*60 + "\n")

    # =============== MAIN PIPELINE ===============

    def run_full_analysis(self):
        """Run complete business analysis pipeline"""
        print("\n" + "🚀 "*15)
        print("RURAL BUSINESS ADVISOR - GUPTA HARDWARE MART")
        print("🚀 "*15 + "\n")

        if self.load_data():
            self.calculate_financial_metrics()
            self.analyze_receivables()
            self.analyze_inventory()
            self.detect_risks()

            print("✅ ANALYSIS COMPLETE - Ready for LLM Advisor")
            return self.get_advisor_context()
        return None

    def get_advisor_context(self):
        """Generate context for AI advisor"""
        return {
            'business': self.business.to_dict('records')[0],
            'financial': self.financial_metrics,
            'receivables': self.receivables_metrics,
            'inventory': self.inventory_metrics,
            'risks': self.risk_indicators,
        }


# =============== USAGE EXAMPLE ===============

if __name__ == "__main__":
    # Initialize pipeline
    advisor = RuralBusinessAdvisor(data_path='.')

    # Run full analysis
    context = advisor.run_full_analysis()

    # The context is now ready to be passed to LLM for advice generation
    print("\n📤 Context ready for LLM Advisor:")
    print(f"   - Financial metrics: {list(advisor.financial_metrics.keys())}")
    print(f"   - Receivables analysis: {list(advisor.receivables_metrics.keys())}")
    print(f"   - Inventory analysis: {list(advisor.inventory_metrics.keys())}")
    print(f"   - Risk indicators: {len(advisor.risk_indicators)} identified")
