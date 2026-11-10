import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd
import streamlit as st
from pipeline import analyze_inventory, run_pipeline, validate_and_clean

# Dataset Provenance Mode Constants
DATASET_MODE_ORIGINAL = "original"
DATASET_MODE_UPLOADED = "uploaded"
DATASET_MODE_DEMO = "demo"

DATASET_LABELS = {
    DATASET_MODE_ORIGINAL: "Original Business Dataset",
    DATASET_MODE_UPLOADED: "Uploaded Dataset",
    DATASET_MODE_DEMO: "Business Dataset",
}


def find_master_csv() -> Optional[Path]:
    """Finds the original private business master CSV robustly if configured or present locally."""
    # 1. First check explicit environment variable or cloud secret
    configured_path = os.getenv("BIZMETRICS_DATASET_PATH", "").strip()
    if not configured_path:
        try:
            if hasattr(st, "secrets") and "BIZMETRICS_DATASET_PATH" in st.secrets:
                configured_path = str(st.secrets["BIZMETRICS_DATASET_PATH"]).strip()
        except Exception:
            configured_path = ""

    if configured_path:
        p = Path(configured_path)
        if p.is_file():
            return p.resolve()

    candidate_roots = [
        Path(__file__).resolve().parent.parent,          # project root
        Path.cwd(),                                     # current working directory
        Path.cwd() / "sih-main",                        # if cwd is parent
        Path(__file__).resolve().parent.parent.parent,
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


def find_demo_csv() -> Optional[Path]:
    """Finds the bundled, non-sensitive synthetic demo dataset."""
    candidate_roots = [
        Path(__file__).resolve().parent.parent,          # project root
        Path.cwd(),
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent,
    ]
    demo_names = [
        "data/demo_business_master_data.csv",
        "demo_business_master_data.csv",
    ]
    seen = set()
    for root in candidate_roots:
        if not root or str(root) in seen:
            continue
        seen.add(str(root))
        for name in demo_names:
            p = root / name
            if p.is_file():
                return p.resolve()
            p_data = root / "data" / name
            if p_data.is_file():
                return p_data.resolve()

    for root in candidate_roots:
        if root.is_dir():
            for found in root.glob("**/demo_business_master_data.csv"):
                if found.is_file():
                    return found.resolve()

    return None


def generate_missing_mobile_numbers(df: pd.DataFrame, csv_path: Any) -> pd.DataFrame:
    """Persist one canonical demo mobile number per customer ID."""
    modified = False

    customer_id_col = next((col for col in df.columns if col.lower() in {"customer_id", "customerid"}), None)
    record_type_col = next((col for col in df.columns if col.lower() == "record_type"), None)
    mobile_col = next((col for col in df.columns if col.lower() == "mobile_number"), None)
    source_contact_col = next((col for col in df.columns if col.lower() in {
        "contact_number", "mobile", "phone", "phone_number", "customer_phone"
    }), None)

    if mobile_col is None:
        mobile_col = "Mobile_Number"
        df[mobile_col] = None
        modified = True

    df[mobile_col] = df[mobile_col].astype("string")

    if mobile_col is not None and not modified:
        existing_vals = df[mobile_col].dropna()
        if len(existing_vals) == len(df) and not (existing_vals.str.strip() == "").any():
            return df

    if customer_id_col is None:
        return df

    for idx, row in df.iterrows():
        record_type = str(row.get(record_type_col, "")).strip().lower() if record_type_col else ""
        if record_type not in ["receivable", "customer"]:
            continue

        cust_id = str(row.get(customer_id_col, "")).strip()
        if not cust_id or cust_id == "nan":
            continue

        existing_mobile = row.get(mobile_col, "")
        source_mobile = row.get(source_contact_col, "") if source_contact_col else ""
        existing = str(existing_mobile).strip()
        if not existing or existing.lower() in {"nan", "none"}:
            existing = str(source_mobile).strip()
        if existing.endswith(".0"):
            existing = existing[:-2]

        digits_only = "".join(c for c in existing if c.isdigit())
        if len(digits_only) == 10 and digits_only[0] in "6789":
            if str(row.get(mobile_col, "")).strip() != digits_only:
                df.at[idx, mobile_col] = digits_only
                modified = True
        else:
            hash_val = int(hashlib.sha256(cust_id.encode()).hexdigest(), 16)
            last_9 = f"{(hash_val % 1000000000):09d}"
            first_digit = str(6 + (hash_val % 4))
            demo_num = first_digit + last_9
            df.at[idx, mobile_col] = demo_num
            modified = True

    return df


@st.cache_data(show_spinner=False)
def load_master_data(csv_path: str, file_signature: tuple) -> pd.DataFrame:
    """Load and clean the master data once per CSV version."""
    df = pd.read_csv(csv_path, dtype={"Mobile_Number": "string", "Contact_Number": "string"})
    df = generate_missing_mobile_numbers(df, csv_path)
    return validate_and_clean(df)


@st.cache_data(show_spinner=False)
def get_cached_pipeline_result(csv_path: str, file_signature: tuple, include_inventory_ml: bool = False):
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
        from utils.database import DEFAULT_SHOP_ID, get_consolidated_master_df
        df = get_consolidated_master_df(shop_id or DEFAULT_SHOP_ID)
        if df is not None and not df.empty:
            df = generate_missing_mobile_numbers(df, "database")
            return validate_and_clean(df)
    except Exception as exc:
        print(f"Database load fallback: {exc}")
    return None


@st.cache_data(show_spinner=False)
def get_cached_database_pipeline_result(shop_id=None):
    """Run deterministic pipeline work once per database state."""
    db_clean = load_data_from_database(shop_id)
    if db_clean is not None and not db_clean.empty:
        result = run_pipeline(db_clean, include_inventory_ml=False)
        return db_clean, result
    return None, None


def validate_uploaded_dataset(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validates that an uploaded CSV has a compatible structure for BizMetrics.
    Returns (is_valid, error_message).
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return False, "The uploaded file is empty. Please upload a valid CSV file with business records."

    cols_lower = [str(c).strip().lower() for c in df.columns]

    # Best match: Contains 'record_type' column
    if "record_type" in cols_lower:
        rec_col = next(c for c in df.columns if str(c).strip().lower() == "record_type")
        vals = set(df[rec_col].dropna().astype(str).str.strip().str.lower().unique())
        recognized = {"sale", "sales", "transaction", "inventory", "product", "receivable", "customer", "expense", "payable", "vendor", "loan", "business"}
        if not vals.intersection(recognized):
            return False, (
                f"The 'record_type' column does not contain recognized BizMetrics record types "
                f"(expected values like: Sale, Inventory, Receivable, Expense, Payable, Loan). Found: {', '.join(list(vals)[:5])}"
            )
        return True, ""

    # Alternative match: Generic sales or transaction CSV without record_type column
    has_amount = any(c in cols_lower for c in ["total_amount", "amount", "price", "selling_price"])
    has_product = any(c in cols_lower for c in ["product_id", "product_name", "product", "item", "sku", "category"])

    if has_amount and has_product:
        return True, ""

    missing = []
    if not has_amount:
        missing.append("an amount column (e.g. 'total_amount', 'selling_price', or 'amount')")
    if not has_product:
        missing.append("a product column (e.g. 'product_name', 'product_id', or 'category')")

    return False, (
        f"Incompatible CSV structure. The uploaded file is missing {', and '.join(missing)}, "
        f"or a 'record_type' column. Please verify your CSV format or consult the sample template."
    )


def load_uploaded_dataset(uploaded_file) -> Tuple[bool, str]:
    """
    Parses and validates an uploaded file object from st.file_uploader.
    If valid, updates session state with pipeline result and sets mode to 'uploaded'.
    """
    if uploaded_file is None:
        return False, "No file provided."

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        err = f"Failed to parse CSV file: {exc}"
        st.session_state["dataset_upload_error"] = err
        return False, err

    is_valid, err_msg = validate_uploaded_dataset(df)
    if not is_valid:
        st.session_state["dataset_upload_error"] = err_msg
        return False, err_msg

    cols_lower = [str(c).strip().lower() for c in df.columns]
    if "record_type" not in cols_lower:
        df["record_type"] = "Sale"

    df = generate_missing_mobile_numbers(df, "uploaded_custom")
    clean_df = validate_and_clean(df)

    try:
        result = run_pipeline(clean_df, include_inventory_ml=False)
    except Exception as exc:
        err = f"Pipeline execution error on uploaded dataset: {exc}"
        st.session_state["dataset_upload_error"] = err
        return False, err

    file_name = getattr(uploaded_file, "name", "custom_uploaded_data.csv")
    st.session_state["uploaded_custom_df"] = clean_df
    st.session_state["raw_data"] = clean_df
    st.session_state["pipeline_result"] = result
    st.session_state["dataset_mode"] = DATASET_MODE_UPLOADED
    st.session_state["dataset_name"] = file_name
    st.session_state["dataset_path"] = f"Uploaded ({file_name})"
    st.session_state["data_source_mode"] = "User Uploaded File"
    st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_UPLOADED]
    st.session_state.pop("dataset_upload_error", None)

    return True, ""


def reset_to_default_dataset():
    """Clears uploaded dataset and falls back to original (if present) or demo dataset."""
    st.session_state.pop("uploaded_custom_df", None)
    st.session_state.pop("dataset_upload_error", None)
    refresh_application_data(force=True)


def get_dataset_provenance() -> Dict[str, Any]:
    """Returns metadata about the currently active dataset."""
    raw_df = st.session_state.get("raw_data")
    row_count = len(raw_df) if isinstance(raw_df, pd.DataFrame) else 0
    mode = st.session_state.get("dataset_mode", DATASET_MODE_ORIGINAL)
    name = st.session_state.get("dataset_name", "Primary Store Ledger")
    status_label = st.session_state.get("dataset_status_label", DATASET_LABELS.get(mode, "Business Dataset"))

    return {
        "mode": mode,
        "name": name,
        "status_label": status_label,
        "row_count": row_count,
        "is_demo": mode == DATASET_MODE_DEMO,
        "is_uploaded": mode == DATASET_MODE_UPLOADED,
        "is_original": mode == DATASET_MODE_ORIGINAL,
        "path": st.session_state.get("dataset_path", ""),
    }


def render_dataset_status_banner():
    """No-op: All visible dataset banners and demo mode badges are suppressed per UI requirements."""
    pass


def render_dataset_uploader_widget(in_sidebar: bool = True):
    """
    Renders a robust Dataset Manager widget with:
    - 59-column canonical schema validation & structure preview
    - Explicit Import/Confirm action to database
    - Mapping to SQLite tables (customers, sales_transactions, products, inventory, receivables, etc.)
    - Duplicate prevention & preservation of existing records
    - Persistent storage of uploaded files
    - Detailed import summary report (imported, skipped, errors)
    """
    with st.expander("📁 Dataset Manager", expanded=False):
        uploaded = st.file_uploader(
            "Upload Business CSV",
            type=["csv"],
            key="bizmetrics_dataset_file_uploader",
            help="Upload a consolidated business master CSV or sales transaction CSV to analyze your own store data."
        )

        if uploaded is not None:
            try:
                if hasattr(uploaded, "seek"):
                    uploaded.seek(0)
                preview_df = pd.read_csv(uploaded, dtype=str)
            except Exception as exc:
                st.error(f"❌ Failed to parse CSV: {exc}")
                preview_df = None

            if preview_df is not None:
                is_valid, err_msg = validate_uploaded_dataset(preview_df)
                if not is_valid:
                    st.error(f"❌ {err_msg}")
                else:
                    from utils.database import CONSOLIDATED_MASTER_COLUMNS, import_master_df_to_database
                    cols_lower = {str(c).strip().lower() for c in preview_df.columns}
                    matched_canonical = sum(1 for col in CONSOLIDATED_MASTER_COLUMNS if col.lower() in cols_lower)
                    is_canonical = (matched_canonical == len(CONSOLIDATED_MASTER_COLUMNS))

                    st.markdown(f"📄 **Selected:** `{uploaded.name}`")
                    if is_canonical:
                        st.caption(f"✓ Verified canonical 59-column schema ({len(preview_df)} records)")
                    else:
                        st.caption(f"✓ Valid business structure ({matched_canonical}/59 canonical columns matched, {len(preview_df)} records)")

                    st.dataframe(preview_df.head(3), height=110, use_container_width=True)

                    btn_label = f"📥 Import {len(preview_df)} Records to Database"
                    if st.button(btn_label, key="btn_confirm_dataset_import", type="primary", use_container_width=True):
                        with st.spinner("Importing records into database & synchronizing..."):
                            # 1. Save to persistent storage
                            uploads_dir = APP_ROOT / "data" / "uploads"
                            uploads_dir.mkdir(parents=True, exist_ok=True)
                            persisted_path = uploads_dir / uploaded.name
                            try:
                                uploaded.seek(0)
                                with open(persisted_path, "wb") as f:
                                    f.write(uploaded.getbuffer())
                            except Exception:
                                pass

                            # 2. Import into SQLite database atomically
                            shop_id = st.session_state.get("shop_id", "shivansh_electronics_hardware")
                            username = st.session_state.get("username", "Shivansh G")
                            summary = import_master_df_to_database(
                                preview_df,
                                shop_id=shop_id,
                                username=username,
                                file_name=uploaded.name,
                            )
                            st.session_state["last_dataset_import_summary"] = summary

                            # 3. Load into active session pipeline
                            uploaded.seek(0)
                            load_uploaded_dataset(uploaded)
                            st.success(f"✓ {summary['message']}")
                            st.rerun()

        if "last_dataset_import_summary" in st.session_state and st.session_state["last_dataset_import_summary"]:
            last_summary = st.session_state["last_dataset_import_summary"]
            st.markdown(
                f"""
                <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 6px 10px; margin-top: 6px; font-size: 0.8rem; color: #166534;">
                    <strong>✓ Import Summary:</strong><br>
                    • Imported: {last_summary.get('imported', 0)} records<br>
                    • Duplicates updated: {last_summary.get('duplicates', 0)} records<br>
                    • Skipped/Errors: {last_summary.get('errors', 0)}
                </div>
                """,
                unsafe_allow_html=True,
            )

        if "dataset_upload_error" in st.session_state and st.session_state["dataset_upload_error"]:
            st.error(f"❌ {st.session_state['dataset_upload_error']}")

        if st.session_state.get("dataset_mode") == DATASET_MODE_UPLOADED:
            if st.button("↺ Reset to Default Dataset", key="btn_reset_dataset_source", use_container_width=True):
                reset_to_default_dataset()
                st.session_state.pop("last_dataset_import_summary", None)
                st.rerun()


def refresh_application_data(force: bool = False):
    """
    Refreshes application data and pipeline results into session state.
    Loading Hierarchy:
    1. Active user-uploaded dataset (if present in session state)
    2. Original business dataset:
       a. Populated relational database (bizmetrics.db with business records)
       b. Local master CSV (rural_business_master_data.csv or configured path)
    3. Demo dataset (data/demo_business_master_data.csv) - non-sensitive synthetic data
    4. Safe empty schema fallback (guaranteed never to crash or raise FileNotFoundError)
    """
    # Fast path: If already loaded and not forced, return immediately
    if not force and "pipeline_result" in st.session_state and "raw_data" in st.session_state:
        if st.session_state["pipeline_result"] is not None and st.session_state["raw_data"] is not None:
            return

    # 1. User-uploaded custom dataset
    if "uploaded_custom_df" in st.session_state and st.session_state["uploaded_custom_df"] is not None:
        custom_df = st.session_state["uploaded_custom_df"]
        result = run_pipeline(custom_df, include_inventory_ml=False)
        st.session_state["raw_data"] = custom_df
        st.session_state["pipeline_result"] = result
        st.session_state["dataset_mode"] = DATASET_MODE_UPLOADED
        st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_UPLOADED]
        return

    # 2a. Primary original: Populated relational database with business transactions
    db_clean, db_result = get_cached_database_pipeline_result()
    if db_clean is not None and db_result is not None and not db_clean.empty:
        st.session_state["pipeline_result"] = db_result
        st.session_state["raw_data"] = db_clean
        st.session_state["dataset_path"] = "SQLite Database (bizmetrics.db)"
        st.session_state["data_source_mode"] = "Relational Database"
        st.session_state["dataset_mode"] = DATASET_MODE_ORIGINAL
        st.session_state["dataset_name"] = "bizmetrics.db"
        st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_ORIGINAL]
        return

    # 2b. Secondary original: Local master CSV if present
    csv_path = find_master_csv()
    if csv_path is not None:
        file_stat = csv_path.stat()
        file_signature = (file_stat.st_mtime_ns, file_stat.st_size)
        clean_df, result = get_cached_pipeline_result(str(csv_path), file_signature, include_inventory_ml=False)
        st.session_state["pipeline_result"] = result
        st.session_state["raw_data"] = clean_df
        st.session_state["dataset_path"] = str(csv_path)
        st.session_state["data_source_mode"] = "CSV File"
        st.session_state["dataset_mode"] = DATASET_MODE_ORIGINAL
        st.session_state["dataset_name"] = csv_path.name
        st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_ORIGINAL]
        return

    # 3. Tertiary: Non-sensitive synthetic demo dataset (for public cloud deployments)
    demo_path = find_demo_csv()
    if demo_path is not None:
        demo_stat = demo_path.stat()
        demo_sig = (demo_stat.st_mtime_ns, demo_stat.st_size)
        clean_df, result = get_cached_pipeline_result(str(demo_path), demo_sig, include_inventory_ml=False)
        st.session_state["pipeline_result"] = result
        st.session_state["raw_data"] = clean_df
        st.session_state["dataset_path"] = str(demo_path)
        st.session_state["data_source_mode"] = "Business Dataset"
        st.session_state["dataset_mode"] = DATASET_MODE_DEMO
        st.session_state["dataset_name"] = "Primary Ledger"
        st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_DEMO]
        return

    # 4. Final safety initialization: guaranteed valid empty pipeline state (never raise FileNotFoundError)
    from utils.database import get_consolidated_master_df
    empty_df = validate_and_clean(get_consolidated_master_df())
    empty_res = run_pipeline(empty_df, include_inventory_ml=False)
    st.session_state["pipeline_result"] = empty_res
    st.session_state["raw_data"] = empty_df
    st.session_state["dataset_path"] = "SQLite Database (bizmetrics.db)"
    st.session_state["data_source_mode"] = "Relational Database"
    st.session_state["dataset_mode"] = DATASET_MODE_ORIGINAL
    st.session_state["dataset_name"] = "bizmetrics.db (Empty Schema)"
    st.session_state["dataset_status_label"] = DATASET_LABELS[DATASET_MODE_ORIGINAL]
