"""
BizMetrics Database Backup and Safe Restore Manager
Supports manual & scheduled timestamped SQLite database backups,
pre-restore integrity checks, automated rollback snapshots,
and comprehensive database health diagnostics.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import datetime
import uuid
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from utils.database import DB_PATH, get_connection, get_db_cursor
from utils.audit_logger import log_audit_event

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def calculate_file_checksum(filepath: Path | str) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_database_backup(backup_type: str = "Manual", notes: str = "", username: str = "Shivansh G") -> dict[str, Any]:
    """
    Creates a full atomic backup of bizmetrics.db using SQLite's online backup API.
    Computes checksum, logs audit entry, and registers the backup in database_backups.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"bizmetrics_backup_{timestamp}_{backup_type.lower()}.db"
    backup_target = BACKUP_DIR / backup_filename

    # Perform online SQLite backup to ensure consistency even under active WAL
    source_conn = get_connection()
    dest_conn = sqlite3.connect(str(backup_target))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()

    file_size = backup_target.stat().st_size
    checksum = calculate_file_checksum(backup_target)
    backup_id = f"BAK-{timestamp}-{uuid.uuid4().hex[:4].upper()}"

    # Record in database
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO database_backups (backup_id, filename, file_size, backup_type, checksum, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (backup_id, backup_filename, file_size, backup_type, checksum, notes),
        )

    log_audit_event(
        username=username,
        action_type="BACKUP",
        entity_type="DATABASE",
        entity_id=backup_id,
        details=f"Created {backup_type} backup: {backup_filename} ({file_size / 1024:.1f} KB)",
    )

    return {
        "success": True,
        "backup_id": backup_id,
        "filename": backup_filename,
        "path": str(backup_target),
        "file_size": file_size,
        "checksum": checksum,
        "timestamp": timestamp,
    }


def list_database_backups() -> pd.DataFrame:
    """Retrieve all available backup snapshots."""
    try:
        with get_db_cursor(commit=False) as cur:
            rows = cur.execute(
                "SELECT backup_id, filename, file_size, backup_type, checksum, notes, created_at FROM database_backups ORDER BY created_at DESC"
            ).fetchall()
            if rows:
                df = pd.DataFrame([dict(r) for r in rows])
                # Check if file still exists on disk
                df["exists_on_disk"] = df["filename"].apply(lambda f: (BACKUP_DIR / str(f)).exists())
                return df
    except Exception:
        pass

    # Fallback: scan disk folder directly
    files = list(BACKUP_DIR.glob("*.db"))
    records = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        records.append({
            "backup_id": f.stem,
            "filename": f.name,
            "file_size": f.stat().st_size,
            "backup_type": "Manual",
            "checksum": calculate_file_checksum(f)[:16],
            "notes": "Found on disk",
            "created_at": datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "exists_on_disk": True,
        })
    return pd.DataFrame(records) if records else pd.DataFrame(columns=[
        "backup_id", "filename", "file_size", "backup_type", "checksum", "notes", "created_at", "exists_on_disk"
    ])


def verify_backup_file(file_path: Path | str) -> tuple[bool, str]:
    """
    Validates that a file is a genuine, uncorrupted SQLite database with valid schemas.
    """
    p = Path(file_path)
    if not p.exists() or p.stat().st_size == 0:
        return False, "File does not exist or is 0 bytes."

    # Check SQLite header
    with open(p, "rb") as f:
        header = f.read(16)
        if header != b"SQLite format 3\x00":
            return False, "Invalid SQLite header. The file is not a valid SQLite database."

    # Test opening and running integrity check
    try:
        conn = sqlite3.connect(str(p))
        cur = conn.cursor()
        res = cur.execute("PRAGMA integrity_check;").fetchone()
        if not res or res[0] != "ok":
            conn.close()
            return False, f"Integrity check failed: {res[0] if res else 'Unknown'}"

        # Verify key tables exist
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        required = {"shops", "products", "sales_transactions"}
        missing = required - set(tables)
        if missing:
            return False, f"Database is missing critical BizMetrics tables: {missing}"

        return True, "Integrity check passed. All primary schemas verified."
    except Exception as e:
        return False, f"Verification failed with exception: {str(e)}"


def restore_database_backup(backup_filename: str, username: str = "Shivansh G") -> tuple[bool, str]:
    """
    Safely restores bizmetrics.db from a verified backup file.
    Always takes an automatic safety snapshot of the current DB before overwriting!
    """
    backup_source = BACKUP_DIR / backup_filename
    if not backup_source.exists():
        return False, f"Backup file {backup_filename} not found in backups directory."

    is_valid, msg = verify_backup_file(backup_source)
    if not is_valid:
        return False, f"Restore aborted: {msg}"

    # Step 1: Automatic pre-restore safety snapshot
    safety_snap = create_database_backup(backup_type="Safety_Pre_Restore", notes="Auto-snapshot before restore", username=username)

    # Step 2: Atomic restore using SQLite backup API
    try:
        src_conn = sqlite3.connect(str(backup_source))
        dest_conn = get_connection()
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()

        log_audit_event(
            username=username,
            action_type="RESTORE",
            entity_type="DATABASE",
            entity_id=backup_filename,
            details=f"Database restored from {backup_filename}. Safety snapshot: {safety_snap.get('filename')}",
        )
        return True, f"Successfully restored database from {backup_filename}. Pre-restore safety snapshot saved as {safety_snap.get('filename')}."
    except Exception as e:
        return False, f"Restore failed during SQLite copy: {str(e)}"


def check_database_health() -> dict[str, Any]:
    """
    Runs diagnostic checks on bizmetrics.db:
    Integrity check, foreign keys, table row counts, file size, WAL status.
    """
    diagnostics = {}
    db_file = DB_PATH
    diagnostics["file_exists"] = db_file.exists()
    diagnostics["file_size_mb"] = round(db_file.stat().st_size / (1024 * 1024), 3) if db_file.exists() else 0.0

    conn = get_connection()
    try:
        cur = conn.cursor()
        # 1. Integrity check
        ic = cur.execute("PRAGMA integrity_check;").fetchone()
        diagnostics["integrity_check"] = ic[0] if ic else "unknown"

        # 2. Foreign keys check
        fk = cur.execute("PRAGMA foreign_key_check;").fetchall()
        diagnostics["foreign_key_violations"] = len(fk)

        # 3. Journal mode
        jm = cur.execute("PRAGMA journal_mode;").fetchone()
        diagnostics["journal_mode"] = jm[0] if jm else "unknown"

        # 4. Table row counts
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        table_counts = {}
        for t in tables:
            try:
                cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                table_counts[t] = cnt
            except Exception:
                table_counts[t] = -1
        diagnostics["tables"] = table_counts
        diagnostics["total_tables"] = len(tables)
        diagnostics["status"] = "Healthy" if diagnostics["integrity_check"] == "ok" and diagnostics["foreign_key_violations"] == 0 else "Needs Attention"
    except Exception as e:
        diagnostics["status"] = "Error"
        diagnostics["error"] = str(e)
    finally:
        conn.close()

    return diagnostics

