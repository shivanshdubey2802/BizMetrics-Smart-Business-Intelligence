# Durg–Bhilai Genuine Local Dataset Integration

## Overview
This directory contains location-specific datasets for **Durg, Bhilai Nagar, Bhilai Charoda, Risali, Jamul, Kumhari, and Ahiwara** in the Durg District of Chhattisgarh, India. All data points originate from public, authentic sources, including the **Census of India 2011**, **District Durg Official Administration (durg.gov.in)**, and **OpenStreetMap (ODbL)**.

---

## Directory Organization

```
data/durg_bhilai/
  ├── raw/
  │   ├── census_2011_durg_bhilai_raw.json
  │   ├── durg_bhilai_localities_raw.json
  │   ├── osm_durg_bhilai_pois_raw.json
  │   └── durg_district_economic_indicators_raw.json
  ├── processed/
  │   ├── durg_bhilai_consolidated.json
  │   └── dataset_sources.csv
  ├── geographic/
  │   └── durg_bhilai_localities.csv
  ├── demographics/
  │   └── durg_bhilai_census_demographics.csv
  ├── business_directory/
  │   └── durg_bhilai_business_directory.csv
  ├── economic_indicators/
  │   └── durg_district_economy.csv
  ├── metadata/
  │   └── dataset_sources.json
  └── README.md
```

---

## Dataset 1: Census Demographics (`demographics/durg_bhilai_census_demographics.csv`)

- **Dataset Name**: Durg District & Urban Local Bodies Primary Census Abstract (PCA)
- **Original Source**: Office of the Registrar General & Census Commissioner, India (ORGI), Ministry of Home Affairs
- **Source URL**: https://censusindia.gov.in/nada/index.php/catalog/357 and https://durg.gov.in/en/demography/
- **License**: Government Open Data License - India (GODL)
- **Geographic Coverage**: Durg District, Durg Municipal Corp (60 Wards), Bhilai Nagar Municipal Corp (70 Wards), Bhilai Charoda Municipal Corp (40 Wards), Risali Municipal Corp (40 Wards), Jamul Nagar Palika (20 Wards), Kumhari Nagar Palika (24 Wards), Ahiwara Nagar Palika (15 Wards), Patan Block, Dhamdha Block.
- **Reference Year**: **2011** (Decennial Census enumeration baseline; not presented as 2026 projection).
- **Download / Ingestion Date**: 2026-11-06
- **Fields**:
  - `demographic_id`: Unique identifier (e.g. `DEMO-BHILAI-NAGAR`)
  - `area_name`: Municipal corporation, municipality, or district name
  - `admin_type`: Administrative status (`District`, `Municipal Corporation`, `Municipality`, `Tehsil`)
  - `district`: Parent district (`Durg`)
  - `total_population`: Enumerated head count
  - `male_population` / `female_population`: Gender split
  - `urban_population` / `rural_population`: Sectoral population
  - `total_households`: Total occupied residential households
  - `literacy_rate`: Percentage literacy among age 7+
  - `workforce_total`: Total worker population
  - `main_workers` / `marginal_workers`: Employment stability categorization
  - `cultivators`, `agricultural_labourers`, `household_industry`, `other_workers`: Industrial worker split
  - `source`: Official provenance citation
  - `notes`: Administrative details and highlights
- **Preprocessing**: Structured from raw Census 2011 Primary Census Abstract table rows, normalized column headers into standard snake_case, verified sum of gender and sectoral breakdowns.
- **Limitations**: Decennial census baseline reflects official 2011 counts; subsequent local delimitation (such as Risali bifurcation from Bhilai Nagar in 2019) is noted in the administrative metadata.

---

## Dataset 2: OpenStreetMap Local Business Directory (`business_directory/durg_bhilai_business_directory.csv`)

- **Dataset Name**: OpenStreetMap Commercial Points of Interest (POIs) - Durg & Bhilai Urban Cluster
- **Original Source**: OpenStreetMap Foundation & Community Contributors
- **Source URL**: https://www.openstreetmap.org/ / https://overpass-api.de/
- **License**: Open Database License (ODbL) 1.0 (Attribution: © OpenStreetMap contributors)
- **Geographic Coverage**: Durg, Bhilai Nagar, Bhilai Charoda, Risali, Jamul, Kumhari, Ahiwara, and CSIDC Borai Industrial Center (Latitude: 21.15°N to 21.36°N, Longitude: 81.18°E to 81.52°E).
- **Reference Year**: **2024**
- **Download / Extraction Date**: 2026-11-06
- **Fields**:
  - `business_id`: Stable BizMetrics primary key (`BIZ-DURG-001`, `BIZ-BHILAI-001`, etc.)
  - `osm_id`: Official positive integer OpenStreetMap node/way identifier
  - `business_name`: Registered / verified name on OpenStreetMap
  - `category`: Standardized category (`Hardware`, `Electronics`, `Grocery / Kirana`, `Hospital / Clinic`, `Bank / ATM`, `Educational Institution`, `Automobile & Spare Parts`, `Industrial & Commercial`, `Restaurant / Cafe`)
  - `sub_category`: Specific trade line
  - `latitude`, `longitude`: WGS84 geographic decimal coordinates
  - `locality`: Neighborhood/suburb (`Station Road`, `Supela`, `Civic Center`, `Nehru Nagar`, `Smriti Nagar`, `Power House`, `Ganjpara`, `Padmanabhpur`, `Borai`, `Hathkhoj`, etc.)
  - `city`: Standardized urban local body name
  - `ward`: Municipal ward name/number where available
  - `district`: `Durg`
  - `address`: Detailed street location
  - `source`: `OpenStreetMap (ODbL 1.0)`
  - `reference_year`: 2024
  - `contact_info`: Public telephone or hotline where officially mapped
- **Preprocessing**: Filtered by Durg district bounding box (21.00°N to 21.50°N, 81.10°E to 81.60°E); removed exact coordinate duplicates; verified category tags against standard OSM schemas (`shop=*`, `amenity=*`, `commercial=*`).
- **Limitations**: OpenStreetMap is community-maintained and reflects mapped establishments; unmapped small rural kiosks or unregistered street stalls are not represented.

---

## Dataset 3: Localities & Geographic Bounds (`geographic/durg_bhilai_localities.csv`)

- **Dataset Name**: Standardized Durg-Bhilai Locality Coordinates & Hub Radii
- **Original Source**: Survey of India / District Administration Durg / OpenStreetMap
- **Source URL**: https://durg.gov.in/
- **License**: Open Data / Public Domain
- **Geographic Coverage**: 17 urban nodes and commercial hubs across Durg district.
- **Reference Year**: 2024
- **Download Date**: 2026-11-06
- **Fields**:
  - `geo_id`: Primary key (`GEO-DURG-CTR`, `GEO-BHILAI-SUPELA`, etc.)
  - `area_name`: Recognized locality name
  - `geo_type`: Functional classification (`City Core`, `High-Density Retail`, `Township Hub`, `Industrial Area`, `Transit Corridor`, etc.)
  - `latitude`, `longitude`: Core centroid coordinates
  - `radius_km`: Standardized commercial catchment radius (1.0 to 4.0 km)
  - `parent_city`: Parent urban local body
  - `district`: `Durg`
  - `description`: Functional economic description
- **Preprocessing**: Verified coordinates against known physical landmarks (e.g. Supela Clock Tower, Durg Railway Junction, Civic Center Kala Mandir, CSIDC Borai Industrial Gate).

---

## Dataset 4: Economic Indicators (`economic_indicators/durg_district_economy.csv`)

- **Dataset Name**: Durg District Industrial, Banking, Mandi & MSME Indicators
- **Original Source**:
  - SAIL Annual Report (Bhilai Steel Plant)
  - State Level Bankers Committee (SLBC) Chhattisgarh / Canara Bank Lead Bank Office Durg
  - Ministry of MSME, Govt of India (Udyam Portal)
  - Chhattisgarh State Agricultural Marketing Board (CGSAMB)
  - CSIDC (Chhattisgarh State Industrial Development Corporation)
- **Source URL**: https://durg.gov.in/en/economy/ and https://slbcchhattisgarh.nic.in/
- **License**: Public Official Disclosures / Government Open Data
- **Reference Period**: 2023–2024
- **Download Date**: 2026-11-06
- **Fields**:
  - `indicator_id`: Key (`ECON-DURG-001` through `007`)
  - `category`: Functional domain (`Industrial Base`, `Banking & Credit`, `Enterprise & MSME`, `Agriculture & Mandi`, `Employment`)
  - `indicator_name`: Name of indicator
  - `unit`: Unit of measurement
  - `indicator_value`: Numerical value
  - `reference_period`: Exact financial / calendar year
  - `source`: Institutional publisher
  - `locality_scope`: Locality or district scope
  - `notes`: Key economic context
- **Preprocessing**: Collated from published economic survey reports, annual banking reviews, and official departmental disclosures.

---

## Strict Data Integrity Standards
1. **Zero Fabrication**: No synthetic coordinates, fabricated shop names, or artificial phone numbers.
2. **Clear Labeling**: Census figures are explicitly labeled with reference year **2011**.
3. **Partitioned Storage**: Public research datasets are stored in dedicated tables, completely isolated from internal customer transaction and ledger records.
