import streamlit as st
import pandas as pd
from pathlib import Path
import hashlib
from pipeline import analyze_inventory, run_pipeline, validate_and_clean

def find_master_csv():
    """Finds the master CSV robustly from the project root."""
    candidate_roots = [
        Path(__file__).resolve().parent.parent,          # sih-main (utils/..)
        Path.cwd(),                                     # current working directory
        Path.cwd() / "sih-main",                        # if cwd is sih-main final
        Path(__file__).resolve().parent.parent.parent,  # sih-main final
        Path(__file__).resolve().parent,                # utils
    ]
    
    csv_names = [
        "rural_business_master_data.csv",
        "dataural_business_master_data.csv",
    ]
    
    seen = set()
    for root in candidate_roots:
        if not root or str(root) in seen:
            continue
        seen.add(str(root))
        for name in csv_names:
            p1 = root / name
            if p1.is_file():
                return p1.resolve()
            p2 = root / "data" / name
            if p2.is_file():
                return p2.resolve()
                
    # Fallback: search within candidate directories
    for root in candidate_roots:
        if root.is_dir():
            for found in root.glob("**/rural_business_master_data.csv"):
                if found.is_file():
                    return found.resolve()
            
    return None

def generate_missing_mobile_numbers(df, csv_path):
    """Persist one canonical demo mobile number per customer ID."""
    modified = False

    customer_id_col = next((col for col in df.columns if col.lower() in {'customer_id', 'customerid'}), None)
    record_type_col = next((col for col in df.columns if col.lower() == 'record_type'), None)
    mobile_col = next((col for col in df.columns if col.lower() == 'mobile_number'), None)
    source_contact_col = next((col for col in df.columns if col.lower() in {
        'contact_number', 'mobile', 'phone', 'phone_number', 'customer_phone'
    }), None)

    if mobile_col is None:
        mobile_col = 'Mobile_Number'
        df[mobile_col] = None
        modified = True

    df[mobile_col] = df[mobile_col].astype("string")

    if mobile_col is not None and not modified:
        # Fast exit if mobile numbers are already populated
        existing_vals = df[mobile_col].dropna()
        if len(existing_vals) == len(df) and not (existing_vals.str.strip() == "").any():
            return df

    if customer_id_col is None:
        return df

    for idx, row in df.iterrows():
        record_type = str(row.get(record_type_col, '')).strip().lower() if record_type_col else ''
        if record_type not in ['receivable', 'customer']:
            continue

        cust_id = str(row.get(customer_id_col, '')).strip()
        if not cust_id or cust_id == 'nan':
            continue

        existing_mobile = row.get(mobile_col, '')
        source_mobile = row.get(source_contact_col, '') if source_contact_col else ''
        existing = str(existing_mobile).strip()
        if not existing or existing.lower() in {'nan', 'none'}:
            existing = str(source_mobile).strip()
        if existing.endswith('.0'):
            existing = existing[:-2]

        digits_only = ''.join(c for c in existing if c.isdigit())
        if len(digits_only) == 10 and digits_only[0] in '6789':
            if str(row.get(mobile_col, '')).strip() != digits_only:
                df.at[idx, mobile_col] = digits_only
                modified = True
        else:
            hash_val = int(hashlib.sha256(cust_id.encode()).hexdigest(), 16)
            last_9 = f"{(hash_val % 1000000000):09d}"
            first_digit = str(6 + (hash_val % 4))
            demo_num = first_digit + last_9
            df.at[idx, mobile_col] = demo_num
            modified = True

    # Return cleaned in-memory dataframe without repeatedly mutating file on disk
    return df

@st.cache_data(show_spinner=False)
def load_master_data(csv_path, file_signature):
    """Load and clean the master data once per CSV version."""
    df = pd.read_csv(csv_path, dtype={"Mobile_Number": "string", "Contact_Number": "string"})
    df = generate_missing_mobile_numbers(df, csv_path)
    return validate_and_clean(df)


@st.cache_data(show_spinner=False)
def get_cached_pipeline_result(csv_path, file_signature, include_inventory_ml=False):
    """Run deterministic pipeline work once per CSV version and ML mode."""
    clean_df = load_master_data(csv_path, file_signature)
    result = run_pipeline(clean_df, include_inventory_ml=include_inventory_ml)
    return clean_df, result


@st.cache_data(show_spinner=False)
def get_cached_inventory_analysis(_data, data_sig: str = ""):
    """Run inventory ML only when requested, returning fast cached analysis."""
    return analyze_inventory(_data, include_ml=True)


@st.cache_data(show_spinner=False)
def load_public_benchmark_datasets():
    """Load authentic public benchmark datasets (UCI Retail, Credit Risk, OSM)."""
    sources_dir = Path(__file__).resolve().parent.parent / "data" / "sources"
    results = {}
    
    uci_retail = sources_dir / "uci_online_retail_authentic.csv"
    if uci_retail.is_file():
        results["uci_retail"] = pd.read_csv(uci_retail)
        
    uci_fc = sources_dir / "uci_inventory_forecast_benchmark.csv"
    if uci_fc.is_file():
        results["uci_forecast"] = pd.read_csv(uci_fc)
        
    credit_risk = sources_dir / "credit_risk_research_benchmark.csv"
    if credit_risk.is_file():
        results["credit_risk"] = pd.read_csv(credit_risk)
        
    osm_file = sources_dir / "osm_verified_businesses.json"
    if osm_file.is_file():
        import json
        with open(osm_file, "r", encoding="utf-8") as f:
            results["osm_data"] = json.load(f)
            
    return results

def load_data_from_database(shop_id=None):
    """Load business data directly from the relational database."""
    try:
        from utils.database import get_consolidated_master_df, DEFAULT_SHOP_ID
        df = get_consolidated_master_df(shop_id or DEFAULT_SHOP_ID)
        if df is not None and not df.empty:
            df = generate_missing_mobile_numbers(df, "database")
            return validate_and_clean(df)
    except Exception as exc:
        print(f"Database load fallback to CSV: {exc}")
    return None


@st.cache_data(show_spinner=False)
def get_cached_database_pipeline_result(shop_id=None):
    """Run deterministic pipeline work once per database state."""
    db_clean = load_data_from_database(shop_id)
    if db_clean is not None and not db_clean.empty:
        result = run_pipeline(db_clean, include_inventory_ml=False)
        return db_clean, result
    return None, None


def refresh_application_data(force=False):
    """Refreshes the application data and pipeline results into session state."""
    # Fast path: If already loaded in session state and not forced, return immediately
    if not force and "pipeline_result" in st.session_state and "raw_data" in st.session_state:
        if st.session_state["pipeline_result"] and not st.session_state["raw_data"].empty:
            return

    # First attempt to load directly from centralized database using cached pipeline
    db_clean, db_result = get_cached_database_pipeline_result()
    if db_clean is not None and db_result is not None:
        st.session_state["pipeline_result"] = db_result
        st.session_state["raw_data"] = db_clean
        st.session_state["dataset_path"] = "SQLite Database (bizmetrics.db)"
        st.session_state["data_source_mode"] = "Relational Database"
        return

    # Fallback to CSV if database is not yet ready
    csv_path = find_master_csv()
    if csv_path is None:
        raise FileNotFoundError("rural_business_master_data.csv was not found.")
        
    file_stat = csv_path.stat()
    file_signature = (file_stat.st_mtime_ns, file_stat.st_size)
    clean_df, result = get_cached_pipeline_result(str(csv_path), file_signature, include_inventory_ml=False)
    
    st.session_state["pipeline_result"] = result
    st.session_state["raw_data"] = clean_df
    st.session_state["dataset_path"] = str(csv_path)
    st.session_state["data_source_mode"] = "CSV File"
