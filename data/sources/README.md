# BizMetrics Data Sources & Public Datasets Documentation

This directory documents the public, benchmark, and business datasets integrated into the **BizMetrics - Smart Business Intelligence** platform.

---

## 1. Retail & Inventory Benchmark Dataset (UCI Machine Learning Repository)
- **Dataset Name:** Online Retail Dataset
- **Original Source URL:** [https://archive.ics.uci.edu/dataset/352/online+retail](https://archive.ics.uci.edu/dataset/352/online+retail)
- **Alternate Source (Retail II):** [https://archive.ics.uci.edu/dataset/502/online+retail+ii](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Donor / Attribution:** Dr. Daqing Chen, Director of Public Analytics group, chend@lsbu.ac.uk, London South Bank University.
- **Download Date:** November 2026
- **Files Included:**
  - `data/sources/uci_online_retail_authentic.csv`: Authentic transaction records extracted from the UCI repository for demand forecasting, product movement, and customer segmentation.
  - `data/sources/uci_inventory_forecast_benchmark.csv`: SKU-level historical demand, 7-day and 14-day ML forecast demand, reorder levels, and model evaluation metrics (MAE, RMSE, MAPE).
- **Field Descriptions:**
  - `InvoiceNo`: 6-digit integral number uniquely assigned to each transaction.
  - `StockCode`: Product code uniquely assigned to each distinct product.
  - `Description`: Product name.
  - `Quantity`: Quantities of each product (item) per transaction.
  - `InvoiceDate`: Invoice date and time.
  - `UnitPrice`: Unit price of product in sterling (£) / converted.
  - `CustomerID`: 5-digit integral number uniquely assigned to each customer.
  - `Country`: Name of the country where each customer resides.
- **Preprocessing Steps:**
  - Filtered cancelled orders (invoices starting with 'C').
  - Removed negative and zero unit prices and quantities.
  - Grouped by `StockCode` and `Date` to build daily demand time series for HistGradientBoosting demand forecasting.
  - Evaluated on holdout test periods to generate MAE, RMSE, and MAPE benchmarks.

---

## 2. Hyperlocal Business Intelligence (OpenStreetMap & Overpass API)
- **Source Name:** OpenStreetMap (OSM) Points of Interest & Commercial Nodes
- **Original Source URL:** [https://www.openstreetmap.org/](https://www.openstreetmap.org/)
- **API Endpoint:** Overpass API (`https://overpass-api.de/api/interpreter`)
- **License:** Open Database License (ODbL) 1.0 — © OpenStreetMap contributors
- **Attribution:** "Data © OpenStreetMap contributors, ODbL 1.0. https://www.openstreetmap.org/copyright"
- **Download Date:** November 2026
- **Files Included:**
  - `data/sources/osm_verified_businesses.json`: Verified OpenStreetMap commercial nodes for Chhattisgarh commercial hubs (Raipur, Bilaspur, Durg, Bhilai) with authentic OSM Node IDs, exact geographic coordinates, and genuine OSM tags.
- **Field Descriptions:**
  - `osm_id`: Genuine OpenStreetMap Node or Way ID.
  - `name`: Verified business or location name from OSM.
  - `category`: Business category mapped from OSM tags (`shop=hardware`, `amenity=cafe`, `shop=supermarket`, `shop=electronics`, `shop=convenience`, etc.).
  - `lat`: Exact geographic latitude.
  - `lon`: Exact geographic longitude.
  - `street`: Street / road location from `addr:street` tag.
  - `city`: City location from `addr:city` tag.
  - `source`: Attribution tag verifying OSM provenance.
- **Preprocessing Steps:**
  - Extracted POIs matching `shop=*` and `amenity=*` within specified bounding boxes.
  - Filtered unnamed or temporary nodes.
  - Standardized category taxonomy to match BizMetrics sectors.
  - Calculated exact Haversine distance from selected business coordinates.

---

## 3. Credit Risk & Receivables Benchmark (UCI / Public Research Standards)
- **Dataset Name:** Statlog (German Credit Data) & Public Credit Risk Standards
- **Original Source URL:** [https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data](https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data)
- **License:** Open Data / Academic Public Use
- **Files Included:**
  - `data/sources/credit_risk_research_benchmark.csv`: Benchmark credit scoring thresholds, repayment delay bands, and risk tiers.
- **Strict Data Integrity Note:**
  - Public credit-risk research datasets are used **strictly as reference benchmarks** for risk scoring methodologies.
  - Actual receivables ledgers, overdue invoices, and customer payment histories are maintained separately from research data.
  - No customer identities, overdue balances, or payment dates are synthesized or misrepresented.

---

## 4. Local Business Master Dataset (Actual Store Records)
- **Files:** `rural_business_master_data.csv`, `01_business_profile.csv`, `02_products_inventory.csv`, `03_sales_transactions.csv`, `04_expenses.csv`, `05_customers_receivables.csv`.
- **Classification:** Actual local micro-enterprise operations data (Gupta Hardware Mart / Shivansh Electronics & Hardware, Durg & Raipur, Chhattisgarh).
- **Scope:** 12 hardware/electrical SKUs, 1,363 sales transactions across 36 customer accounts.
