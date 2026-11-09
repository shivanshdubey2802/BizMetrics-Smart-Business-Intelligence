# Gupta Hardware Mart - Complete Data Architecture

## Overview
This dataset contains sample data for **Gupta Hardware Mart**, a micro-scale hardware retail business in Durg, Chhattisgarh. The data is structured following the **Rural Business Advisory System** guidelines.

---

## Dataset Files

### 1. **01_business_profile.csv**
**Purpose:** Foundational business information
- Business ID, Shop name, Owner details
- Location (city, village, state)
- Sector classification
- Investment tracking
- Employee count

**Usage:**
- Scheme eligibility filtering
- Location-based recommendations
- Business size classification

---

### 2. **02_products_inventory.csv**
**Purpose:** Product master and real-time inventory status
- Product ID, name, category
- Cost, selling price, profit margin
- Current stock, minimum/maximum levels
- Reorder level tracking
- Supplier mapping

**Key Metrics (Python calculates these):**
```
Profit Margin = (Selling Price - Purchase Price) / Purchase Price × 100
Dead Stock Flag = IF Current_Stock > Maximum_Stock
Stock-out Risk = IF Current_Stock < Reorder_Level
```

---

### 3. **03_sales_transactions.csv**
**Purpose:** Complete sales history with payment tracking
- Sale ID, date, customer, product
- Quantity, price, discount
- Total amount, payment mode
- Payment status, credit amount
- Notes (project/context)

**August 2026 Data:** 35 transactions
- Cash sales: 45%
- Credit sales: 40%
- UPI/Digital: 15%
- **Total Revenue:** ₹80,441
- **Outstanding Credit:** ₹30,219

**Key Metrics (Python calculates):**
```
Daily Revenue = SUM(sales per day)
Product-wise Revenue = SUM(sales by product)
Credit Sales Ratio = Credit Sales / Total Sales × 100
Average Transaction Value = Total Revenue / Number of Transactions
```

---

### 4. **04_expenses.csv**
**Purpose:** Track all business operating costs
- Expense ID, date, category
- Amount, payment status
- Fixed vs. variable classification

**August 2026 Expenses:** ₹79,400
- Rent (Fixed): ₹18,000
- Salaries (Fixed): ₹30,000
- EMI (Fixed): ₹9,500
- Electricity & utilities (Variable): ₹7,700
- Transport & maintenance (Variable): ₹6,200
- Miscellaneous: ₹8,000

**Key Metrics (Python calculates):**
```
Total Fixed Costs = SUM(Fixed Expenses)
Total Variable Costs = SUM(Variable Expenses)
Cost as % of Revenue = (Total Costs / Revenue) × 100
Debt Burden = Monthly EMI / Monthly Revenue × 100
```

---

### 5. **05_customers_receivables.csv**
**Purpose:** Customer credit management and payment tracking
- Customer ID, name, contact
- Total credit sales, payments, outstanding
- Days overdue classification
- Payment status

**Key Customers:**
- **CUST001** (Rajesh Sharma - Contractor): ₹16,320 sales, ₹9,720 outstanding
- **CUST003** (Ahmed Khan): ₹13,600 sales, ₹5,040 outstanding (8 days overdue)
- **CUST006** (Nirmal Construction): ₹9,020 sales, 100% outstanding (12 days overdue)

**Receivables Aging:**
```
Current (0-7 days):      ₹14,195 (47%)
Attention (8-30 days):   ₹7,945 (26%)
Overdue (31-60 days):    ₹9,020 (30%)
High Risk (60+ days):    ₹0
```

**Key Metrics (Python calculates):**
```
Outstanding Receivables = Credit Sales - Payments Received
Days Sales Outstanding = (Outstanding / Daily Revenue) × Days
Receivable Ageing = Classify by Days Overdue
Collection Rate = Payments / Credit Sales × 100
```

---

### 6. **06_vendors_payables.csv**
**Purpose:** Supplier management and payment obligations
- Vendor ID, name, contact
- Total ordered, paid, outstanding
- Days overdue, payment status

**Key Suppliers:**
- **SUPP001** (Sharma Steel): ₹28,000 ordered, ₹10,000 outstanding (5 days overdue)
- **SUPP004** (Timber House): ₹11,400 ordered, ₹7,600 outstanding (18 days overdue)
- **SUPP006** (Paint & Chemical): ₹6,600 ordered, ₹3,000 outstanding (8 days overdue)

**Total Payables:** ₹22,760

**Key Metrics (Python calculates):**
```
Outstanding Payables = Total Ordered - Total Paid
Vendor Ageing = Classify by Days Overdue
Payable Turnover = (Total Payments / Total Ordered) × 100
```

---

### 7. **07_loans_emi.csv**
**Purpose:** Debt and obligation tracking
- Loan ID, provider, principal amount
- Interest rate, tenure
- Monthly EMI, dates
- Outstanding principal

**Current Loans:**
1. **SIDBI Loan:** ₹5,00,000 principal, ₹9,500 EMI
   - 36 months paid, 12 months remaining
   - Outstanding: ₹2,85,000

2. **SBI Working Capital:** ₹2,00,000 principal, ₹6,200 EMI
   - 15 months into 36-month tenure
   - Outstanding: ₹1,24,000

**Total Monthly Debt Obligation:** ₹15,700

**Key Metrics (Python calculates):**
```
Total Debt Burden = SUM(Monthly EMI)
Debt Burden Ratio = Total EMI / Monthly Revenue × 100
Loan Repayment Status = Months Remaining
```

---

### 8. **08_festival_calendar.csv**
**Purpose:** Seasonality and demand pattern reference
- Festival name, type, dates
- Expected demand effect
- Affected sectors

**Demand Pattern (for Hardware):**
- High: Diwali, Wedding Season (Nov-Jan), Post-monsoon (Oct-Nov)
- Medium: Summer, Monsoon repairs
- Low: Monsoon season (Jun-Aug)

**Key Metrics (Python uses for forecasting):**
```
Festival Flag = IF date in festival range
Season Classification = Map month to season
Demand Multiplier = Apply expected effect to baseline demand
```

---

### 9. **09_sector_rules.csv**
**Purpose:** Hardware sector-specific intelligence
- Seasonality patterns for sub-categories
- Typical profit margins
- Inventory turnover rates
- Weather effects
- Festival effects

**Hardware Sub-categories:**
- Building Materials: 15-25% margin, 8-10 turnover/year
- Tools & Equipment: 50-80% margin, 12-15 turnover/year
- Electrical Supplies: 60-90% margin, 10-12 turnover/year
- Plumbing: 50-70% margin, 8-10 turnover/year
- Paints & Chemicals: 60-100% margin, 6-8 turnover/year

---

## Financial Summary - August 2026

### Revenue Side
```
Total Sales:              ₹80,441
├── Cash Sales:          ₹37,347 (46%)
├── Credit Sales:        ₹30,219 (38%)
└── UPI/Digital:         ₹12,875 (16%)

Outstanding Receivables: ₹30,219
```

### Expense Side
```
Total Expenses:          ₹79,400
├── Fixed Costs:         ₹57,500 (72%)
│   ├── Rent:           ₹18,000
│   ├── Salaries:       ₹30,000
│   └── EMI:            ₹9,500
└── Variable Costs:      ₹21,900 (28%)
    ├── Utilities:      ₹7,700
    └── Transport/Maint: ₹6,200
```

### Profitability Metrics
```
Gross Revenue:          ₹80,441
Less: Expenses:         ₹79,400
_______________________
Net Profit (August):    ₹1,041
Profit Margin:          1.29%
```

### Cash Flow Concerns
```
Monthly Revenue:        ₹80,441
Monthly Expenses:       ₹79,400
Outstanding Receivables: ₹30,219 (not yet collected)
Total Payables:         ₹22,760 (due to suppliers)
_________________________________________________
Effective Cash Position: TIGHT (receivables > payables)
```

---

## Risk Indicators (Automatic Detection)

### 🔴 **High Priority Risks**

1. **Thin Margins**
   - Profit margin: 1.29% (Critical)
   - Recommendation: Review product mix, reduce discounts

2. **Receivable Pressure**
   - Outstanding: ₹30,219 (38% of monthly revenue)
   - Overdue amount: ₹9,020 (11% of revenue)
   - Action: Accelerate collections from CUST006, CUST005

3. **High Fixed Cost Ratio**
   - Fixed costs: ₹57,500 (71% of expenses)
   - Low margin leaves little buffer
   - Action: Monitor cash flow closely

4. **Debt Service Pressure**
   - Monthly EMI: ₹15,700
   - Monthly profit: ₹1,041
   - Debt burden: 19.5% of revenue
   - Action: Avoid additional borrowing until margin improves

### 🟡 **Medium Priority**

1. **Inventory Imbalance**
   - Dead stock risk: PROD005 (Doors) - 8 units at ₹2,500 each
   - High-value slow-moving items
   - Action: Plan promotional sales

2. **Vendor Payment Overdue**
   - SUPP004: 18 days overdue on ₹7,600
   - Risk of supply disruption
   - Action: Prioritize payment

### 🟢 **Healthy Indicators**

1. **Consistent Sales Activity**: 35 transactions in August
2. **Customer Base Diversity**: 10 regular customers with repeat purchases
3. **Balanced Payment Modes**: Mix of cash, credit, and digital
4. **Loan Repayment on Track**: No missed EMI payments

---

## Python Pipeline Requirements

### Phase 1: Data Ingestion & Validation
```python
- Load all CSV files
- Validate data integrity
- Handle missing values
- Create datetime indexes
```

### Phase 2: Financial Calculations
```python
- Revenue aggregation (daily, weekly, monthly, by product)
- Expense categorization
- Profit & margin calculations
- Cash flow analysis
- Break-even point
- ROI calculation
```

### Phase 3: Receivables/Payables
```python
- Outstanding amount calculation
- Ageing bucket classification
- Days overdue calculation
- Collection rate tracking
- Payment due alerts
```

### Phase 4: Inventory Management
```python
- Stock status review
- Reorder quantity calculation
- Dead stock identification
- Slow-moving items detection
- Safety stock recommendations
```

### Phase 5: Demand Forecasting
```python
- Historical sales pattern analysis
- Seasonal adjustment
- Festival impact calculation
- Product-level forecast (next 30/60/90 days)
- Recommended purchase quantities
```

### Phase 6: Risk Engine
```python
- Margin threshold check
- Receivable overdue alerts
- Stock-out risk detection
- Cash flow projection
- Debt burden calculation
```

### Phase 7: Scheme Eligibility (when scheme DB is added)
```python
- Match business profile against scheme criteria
- Calculate eligibility score
- Identify missing requirements
- Rank applicable schemes
```

### Phase 8: AI Advisor Context
```python
- Aggregate verified financial metrics
- Summarize inventory status
- Present forecast results
- List active risks
- Format for LLM prompt
```

### Phase 9: Language Output
```python
- Generate Hindi recommendations
- Generate English recommendations
- QR code linking to customer profiles
```

---

## Next Steps for Implementation

### Immediate (Week 1)
1. ✅ Data schemas defined (this document)
2. Create data loading module (`database.py`)
3. Implement financial calculations (`financial.py`)

### Short-term (Week 2-3)
4. Build inventory management (`inventory.py`)
5. Implement forecasting engine (`forecasting.py`)
6. Create risk detection rules (`rules.py`)

### Medium-term (Week 3-4)
7. Build RAG system for schemes and sector playbooks (`rag.py`)
8. Create LLM advisor wrapper (`advisor.py`)
9. Build Streamlit dashboard (`app.py`)

### Testing (Week 4)
10. Validate all calculations against sample data
11. Test pipeline end-to-end
12. Prepare for real business data ingestion

---

## CSV Import Sequence

When setting up the database, load in this order:

1. `01_business_profile.csv` → BUSINESS table
2. `02_products_inventory.csv` → PRODUCTS + INVENTORY tables
3. `08_festival_calendar.csv` → CALENDAR table
4. `09_sector_rules.csv` → SECTOR_CONFIG table
5. `05_customers_receivables.csv` → CUSTOMERS table
6. `06_vendors_payables.csv` → VENDORS table
7. `03_sales_transactions.csv` → SALES + SALE_ITEMS tables
8. `04_expenses.csv` → EXPENSES table
9. `07_loans_emi.csv` → LOANS table

---

## Contact & Usage

This data represents a **real-world scenario** based on GUPTA HARDWARE MART in Durg, Chhattisgarh.

**Business Details:**
- Shop Name: Gupta Hardware Mart
- Owner: Ramesh Kumar Gupta
- Location: Shanichari Bazar, Durg
- Contact: 9876543210 (sample)
- Sector: Hardware Retail
- Business Size: Micro (3-4 employees)
- Operating Since: March 2019

**Use this data to:**
- Test the complete advisory pipeline
- Train forecasting models
- Validate financial calculations
- Build customer/vendor management workflows
- Develop risk detection algorithms
- Create sample outputs for the Streamlit dashboard
