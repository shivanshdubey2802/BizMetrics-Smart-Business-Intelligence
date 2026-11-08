"""
BizMetrics Smart Data Import Center
Handles CSV and Excel (.xlsx) file uploads, automatic column mapping using
fuzzy synonyms, data validation, duplicate detection, import logs,
and downloadable error reports.
"""
from __future__ import annotations

import csv
import datetime
import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Optional
import pandas as pd
from utils.database import get_db_cursor, DEFAULT_SHOP_ID
from utils.audit_logger import log_audit_event


# Standard Schemas and Synonyms for supported target tables
TARGET_TABLE_SCHEMAS: dict[str, dict[str, Any]] = {
    "products": {
        "primary_key": "product_id",
        "required_fields": ["product_id", "product_name", "selling_price"],
        "columns": {
            "product_id": ["product_id", "id", "sku", "item_code", "product_code", "pid", "code"],
            "product_name": ["product_name", "name", "item_name", "product", "item", "title", "description"],
            "category": ["category", "cat", "group", "product_type", "type", "department"],
            "purchase_price": ["purchase_price", "cost_price", "cost", "buy_price", "purchase_rate", "cogs"],
            "selling_price": ["selling_price", "price", "sale_price", "unit_price", "mrp", "rate"],
            "unit": ["unit", "uom", "measuring_unit", "package"],
        },
    },
    "customers": {
        "primary_key": "customer_id",
        "required_fields": ["customer_id", "customer_name"],
        "columns": {
            "customer_id": ["customer_id", "id", "cid", "cust_id", "client_id", "code"],
            "customer_name": ["customer_name", "name", "client_name", "customer", "client", "contact_person"],
            "business_name": ["business_name", "company", "firm_name", "shop_name", "organization", "firm"],
            "contact_number": ["contact_number", "phone", "mobile", "contact", "telephone", "cell"],
            "email": ["email", "mail", "email_address"],
            "city": ["city", "town", "locality", "location", "district"],
            "customer_type": ["customer_type", "type", "category", "segment", "buyer_type"],
            "outstanding_amount": ["outstanding_amount", "balance", "due_amount", "outstanding", "udhaar"],
        },
    },
    "expenses": {
        "primary_key": "expense_id",
        "required_fields": ["expense_id", "date", "category", "amount"],
        "columns": {
            "expense_id": ["expense_id", "id", "ref_no", "voucher_no", "bill_no", "code"],
            "date": ["date", "expense_date", "txn_date", "bill_date"],
            "category": ["category", "expense_head", "type", "head", "group"],
            "description": ["description", "particulars", "remarks", "notes", "details"],
            "amount": ["amount", "cost", "expense_amount", "total", "value"],
            "payment_status": ["payment_status", "status", "paid_status"],
            "is_fixed": ["is_fixed", "fixed_cost", "recurring"],
        },
    },
    "vendors": {
        "primary_key": "vendor_id",
        "required_fields": ["vendor_id", "vendor_name"],
        "columns": {
            "vendor_id": ["vendor_id", "id", "supplier_id", "supp_id", "code"],
            "vendor_name": ["vendor_name", "name", "supplier_name", "supplier", "firm_name", "company"],
            "material_type": ["material_type", "category", "items_supplied", "materials", "type"],
            "total_ordered_amount": ["total_ordered_amount", "ordered_amount", "orders", "total_orders"],
            "total_paid_amount": ["total_paid_amount", "paid_amount", "paid"],
            "outstanding_balance": ["outstanding_balance", "balance", "due_amount", "payable", "outstanding"],
            "credit_days_allowed": ["credit_days_allowed", "credit_days", "credit_period", "terms"],
        },
    },
}


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    """
    Parses an uploaded CSV or XLSX file into a pandas DataFrame.
    Uses pure-python XML parsing for Excel files to avoid external C dependencies.
    """
    filename = str(uploaded_file.name).lower()
    content_bytes = uploaded_file.getvalue()

    if filename.endswith(".csv") or filename.endswith(".txt"):
        for encoding in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
            try:
                uploaded_file.seek(0)
                return pd.read_csv(io.BytesIO(content_bytes), encoding=encoding, dtype=str)
            except Exception:
                continue
        # Fallback with python standard csv
        lines = content_bytes.decode("utf-8", errors="ignore").splitlines()
        reader = csv.reader(lines)
        rows = list(reader)
        if rows:
            return pd.DataFrame(rows[1:], columns=rows[0])
        return pd.DataFrame()

    elif filename.endswith(".xlsx") or filename.endswith(".xlsm"):
        # Pure-Python XLSX Parser using zipfile and ElementTree
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                # 1. Read shared strings
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in tree.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                        t_node = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                        shared_strings.append(t_node.text if t_node is not None else "")

                # 2. Read first sheet
                sheet_xml = z.read("xl/worksheets/sheet1.xml")
                tree = ET.fromstring(sheet_xml)
                sheet_data = tree.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData")

                all_rows = []
                for row_el in sheet_data.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                    row_vals = []
                    for c in row_el.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        cell_type = c.get("t")
                        v_el = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        val = v_el.text if v_el is not None else ""
                        if cell_type == "s" and val.isdigit() and int(val) < len(shared_strings):
                            row_vals.append(shared_strings[int(val)])
                        else:
                            row_vals.append(val)
                    if any(row_vals):
                        all_rows.append(row_vals)

                if all_rows:
                    headers = [str(h).strip() for h in all_rows[0]]
                    # Pad rows that are shorter than headers
                    data_rows = []
                    for r in all_rows[1:]:
                        padded = r + [""] * (len(headers) - len(r))
                        data_rows.append(padded[:len(headers)])
                    return pd.DataFrame(data_rows, columns=headers)
        except Exception as e:
            print(f"Error parsing XLSX with internal parser: {e}")
            return pd.DataFrame()

    return pd.DataFrame()


def auto_map_columns(file_columns: list[str], target_table: str) -> dict[str, str]:
    """
    Automatically maps uploaded file column headers to standard target table schema fields.
    Returns {target_field: matching_file_column}.
    """
    schema = TARGET_TABLE_SCHEMAS.get(target_table, {})
    col_synonyms = schema.get("columns", {})
    mapping = {}

    clean_file_cols = {re.sub(r'[^a-zA-Z0-9]', '', str(c).lower()): c for c in file_columns}

    for target_field, synonyms in col_synonyms.items():
        matched = None
        # 1. Exact match
        for syn in synonyms:
            clean_syn = re.sub(r'[^a-zA-Z0-9]', '', syn.lower())
            if clean_syn in clean_file_cols:
                matched = clean_file_cols[clean_syn]
                break

        # 2. Substring match
        if not matched:
            for syn in synonyms:
                for clean_col, orig_col in clean_file_cols.items():
                    if syn in orig_col.lower() or orig_col.lower() in syn:
                        matched = orig_col
                        break
                if matched:
                    break

        if matched:
            mapping[target_field] = matched

    return mapping


def validate_and_preview_import(
    df: pd.DataFrame,
    target_table: str,
    column_mapping: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Validates uploaded data against target table rules and detects duplicates against existing records.
    Returns (annotated_preview_df, validation_summary).
    """
    schema = TARGET_TABLE_SCHEMAS.get(target_table, {})
    primary_key = schema.get("primary_key", "")
    required_fields = schema.get("required_fields", [])

    # Fetch existing primary keys from target table
    existing_keys = set()
    with get_db_cursor(commit=False) as cur:
        try:
            rows = cur.execute(f"SELECT {primary_key} FROM {target_table}").fetchall()
            existing_keys = {str(r[0]).strip().upper() for r in rows if r[0]}
        except Exception:
            pass

    records = []
    valid_count = 0
    duplicate_count = 0
    error_count = 0

    seen_in_batch = set()

    for idx, row in df.iterrows():
        row_status = "Valid"
        reasons = []

        # Check mapped required fields
        for req in required_fields:
            mapped_col = column_mapping.get(req)
            if not mapped_col or mapped_col not in df.columns:
                row_status = "Error"
                reasons.append(f"Missing mapped column for '{req}'")
            else:
                val = str(row.get(mapped_col, "")).strip()
                if not val or val.lower() == "nan":
                    row_status = "Error"
                    reasons.append(f"Required field '{req}' is empty")

        # Check primary key and duplicates
        pk_col = column_mapping.get(primary_key)
        pk_val = str(row.get(pk_col, "")).strip() if pk_col and pk_col in df.columns else ""

        if pk_val:
            pk_upper = pk_val.upper()
            if pk_upper in existing_keys:
                row_status = "Duplicate"
                reasons.append(f"ID '{pk_val}' already exists in database")
            elif pk_upper in seen_in_batch:
                row_status = "Duplicate"
                reasons.append(f"Duplicate ID '{pk_val}' within this file")
            seen_in_batch.add(pk_upper)

        if row_status == "Valid":
            valid_count += 1
        elif row_status == "Duplicate":
            duplicate_count += 1
        else:
            error_count += 1

        rec = dict(row)
        rec["_import_status"] = row_status
        rec["_validation_notes"] = "; ".join(reasons) if reasons else "Passed"
        records.append(rec)

    annotated_df = pd.DataFrame(records)
    summary = {
        "total_rows": len(df),
        "valid_rows": valid_count,
        "duplicate_rows": duplicate_count,
        "error_rows": error_count,
        "can_import": valid_count > 0,
    }
    return annotated_df, summary


def execute_import_to_database(
    annotated_df: pd.DataFrame,
    target_table: str,
    column_mapping: dict[str, str],
    file_name: str = "upload.csv",
    file_type: str = "CSV",
    skip_duplicates: bool = True,
    shop_id: str = DEFAULT_SHOP_ID,
    username: str = "Shivansh G",
) -> dict[str, Any]:
    """
    Executes the validated batch import into the SQLite database atomically.
    Logs result in import_logs and audit_logs tables.
    """
    schema = TARGET_TABLE_SCHEMAS.get(target_table, {})
    primary_key = schema.get("primary_key", "")
    import_id = f"IMP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    rows_to_insert = []
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    error_details = []

    for _, row in annotated_df.iterrows():
        status = row.get("_import_status")
        if status == "Error":
            error_count += 1
            error_details.append(f"Row skipped: {row.get('_validation_notes')}")
            continue
        if status == "Duplicate" and skip_duplicates:
            duplicate_count += 1
            continue

        # Build clean row payload according to mapping
        item_dict = {"shop_id": shop_id}
        for target_col, source_col in column_mapping.items():
            val = row.get(source_col)
            # Numeric cleanup for price/stock/amount fields
            if any(num_word in target_col.lower() for num_word in ["price", "cost", "stock", "amount", "rating"]):
                try:
                    clean_s = str(val).replace("₹", "").replace(",", "").replace("%", "").strip()
                    item_dict[target_col] = float(clean_s) if clean_s and clean_s.lower() != "nan" else 0.0
                except ValueError:
                    item_dict[target_col] = 0.0
            else:
                item_dict[target_col] = str(val).strip() if val and str(val).lower() != "nan" else ""

        rows_to_insert.append(item_dict)

    if not rows_to_insert:
        return {"success": False, "message": "No valid rows found to import.", "imported": 0}

    with get_db_cursor(commit=True) as cur:
        for it in rows_to_insert:
            cols = list(it.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            vals = [it[c] for c in cols]
            cur.execute(
                f"""
                INSERT INTO {target_table} ({col_names})
                VALUES ({placeholders})
                ON CONFLICT({primary_key}) DO UPDATE SET
                    {', '.join([f"{c} = excluded.{c}" for c in cols if c != primary_key])}
                """,
                vals,
            )
            imported_count += 1

            # Auto-create inventory entry if target is products
            if target_table == "products":
                cur.execute(
                    """
                    INSERT INTO inventory (product_id, current_stock, minimum_stock, maximum_stock, reorder_level, status)
                    VALUES (?, 50.0, 10.0, 200.0, 20.0, 'Healthy')
                    ON CONFLICT(product_id) DO NOTHING;
                    """,
                    (it["product_id"],),
                )

        # Log to import_logs
        cur.execute(
            """
            INSERT INTO import_logs (
                import_id, shop_id, file_name, file_type, target_table, total_rows,
                imported_rows, duplicate_rows, error_rows, status, error_details, imported_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                shop_id,
                file_name,
                file_type,
                target_table,
                len(annotated_df),
                imported_count,
                duplicate_count,
                error_count,
                "Completed" if error_count == 0 else "Completed with warnings",
                "\n".join(error_details[:10]),
                username,
            ),
        )

    log_audit_event(
        username=username,
        action_type="IMPORT",
        entity_type=target_table.upper(),
        entity_id=import_id,
        details=f"Imported {imported_count} rows from {file_name} into {target_table} (Duplicates: {duplicate_count}, Errors: {error_count})",
        shop_id=shop_id,
    )

    return {
        "success": True,
        "import_id": import_id,
        "imported": imported_count,
        "duplicates": duplicate_count,
        "errors": error_count,
        "message": f"Successfully imported {imported_count} records into {target_table}.",
    }

