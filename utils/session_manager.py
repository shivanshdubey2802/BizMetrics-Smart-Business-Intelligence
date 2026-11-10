"""
BizMetrics Production Session Persistence Manager
Provides secure, cryptographically signed, database-backed session tokens
that persist across browser refreshes and multi-page Streamlit navigation.
"""
from __future__ import annotations

import hmac
import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st

APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / "bizmetrics.db"
AUTH_DB_PATH = APP_ROOT / "bizmetrics_auth.db"

# Secret key for HMAC signing (uses environment variable if present, or persistent file-based key)
SECRET_KEY_FILE = APP_ROOT / ".session_secret"
if not SECRET_KEY_FILE.exists():
    SECRET_KEY_FILE.write_text(secrets.token_hex(32), encoding="utf-8")

SESSION_SECRET_KEY = os.environ.get("BIZMETRICS_SECRET_KEY", SECRET_KEY_FILE.read_text(encoding="utf-8").strip()).encode("utf-8")

# Session validity duration
DEFAULT_SESSION_DURATION = timedelta(days=7)


def _get_db_connection(target_path: Path = DB_PATH) -> sqlite3.Connection:
    try:
        from utils.database import get_connection
        return get_connection(target_path)
    except Exception:
        conn = sqlite3.connect(str(target_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = DELETE;")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA synchronous = NORMAL;")
        except Exception:
            pass
        return conn


def init_session_tables() -> None:
    """Ensure user_sessions table and indexes exist in both main and auth databases."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS user_sessions (
        session_token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        shop_id TEXT NOT NULL,
        shop_name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token, is_active);
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id, is_active);
    """
    for db_file in (DB_PATH, AUTH_DB_PATH):
        try:
            conn = _get_db_connection(db_file)
            conn.executescript(create_sql)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning initializing session table in {db_file}: {e}")


def _sign_token(raw_token: str) -> str:
    """Generate an HMAC-SHA256 signature for the token."""
    sig = hmac.new(SESSION_SECRET_KEY, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw_token}.{sig}"


def _verify_token(signed_token: str) -> Optional[str]:
    """Verify HMAC signature of a signed token; returns raw_token if valid, None otherwise."""
    if not signed_token or "." not in signed_token:
        return None
    raw_token, sig = signed_token.rsplit(".", 1)
    expected_sig = hmac.new(SESSION_SECRET_KEY, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return raw_token
    return None


def create_authenticated_session(
    user_id: str,
    username: str,
    role: str,
    shop_id: str = "shivansh_electronics_hardware",
    shop_name: str = "Shivansh Electronics and Hardware",
    duration: timedelta = DEFAULT_SESSION_DURATION,
) -> str:
    """
    Creates a new persistent, signed session record in the database
    and registers it in streamlit session state and query parameters.
    """
    init_session_tables()
    raw_token = secrets.token_urlsafe(32)
    signed_token = _sign_token(raw_token)

    now = datetime.now(timezone.utc)
    expires_at = (now + duration).isoformat()
    created_at = now.isoformat()

    insert_sql = """
    INSERT INTO user_sessions (
        session_token, user_id, username, role, shop_id, shop_name,
        created_at, expires_at, last_active, is_active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """

    for db_file in (DB_PATH, AUTH_DB_PATH):
        try:
            conn = _get_db_connection(db_file)
            conn.execute(
                insert_sql,
                (raw_token, user_id, username, role, shop_id, shop_name, created_at, expires_at, created_at),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error persisting session token to {db_file}: {e}")

    # Set in st.session_state
    norm_role = role.strip().lower()
    st.session_state["session_token"] = signed_token
    st.session_state["user_id"] = user_id
    st.session_state["username"] = username
    st.session_state["user_role"] = norm_role
    st.session_state["shop_id"] = shop_id
    st.session_state["shop_name"] = shop_name

    if norm_role in ("owner", "admin"):
        st.session_state["owner_authenticated"] = True
        st.session_state["customer_authenticated"] = False
    elif norm_role == "customer":
        st.session_state["customer_authenticated"] = True
        st.session_state["owner_authenticated"] = False
        st.session_state["customer_id"] = user_id
        st.session_state["customer_name"] = username

    # Set in browser URL query params for persistence across browser refreshes
    try:
        st.query_params["session"] = signed_token
    except Exception:
        pass

    return signed_token


def validate_session_token(signed_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates a signed session token against HMAC signature and database records.
    Returns session dict if active and unexpired, None otherwise.
    """
    raw_token = _verify_token(signed_token)
    if not raw_token:
        return None

    query_sql = """
    SELECT session_token, user_id, username, role, shop_id, shop_name,
           created_at, expires_at, is_active
    FROM user_sessions
    WHERE session_token = ? AND is_active = 1
    """

    row = None
    for db_file in (DB_PATH, AUTH_DB_PATH):
        try:
            conn = _get_db_connection(db_file)
            row = conn.execute(query_sql, (raw_token,)).fetchone()
            if row:
                # Update last active timestamp
                conn.execute(
                    "UPDATE user_sessions SET last_active = CURRENT_TIMESTAMP WHERE session_token = ?",
                    (raw_token,),
                )
                conn.commit()
                conn.close()
                break
            conn.close()
        except Exception:
            continue

    if not row:
        return None

    # Check expiration
    try:
        expires_at_str = row["expires_at"]
        # Handle ISO strings with or without timezone
        if "+" in expires_at_str or "Z" in expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
        else:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()

        if now > expires_at:
            invalidate_session(signed_token)
            return None
    except Exception:
        pass

    return {
        "session_token": signed_token,
        "raw_token": raw_token,
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "shop_id": row["shop_id"],
        "shop_name": row["shop_name"],
    }


def invalidate_session(signed_token: Optional[str] = None) -> None:
    """Invalidates an active session in the database and cleans session state and query parameters."""
    raw_token = None
    if signed_token:
        raw_token = _verify_token(signed_token)
    elif "session_token" in st.session_state:
        raw_token = _verify_token(st.session_state["session_token"])
    elif "session" in st.query_params:
        raw_token = _verify_token(st.query_params.get("session"))

    if raw_token:
        update_sql = "UPDATE user_sessions SET is_active = 0 WHERE session_token = ?"
        for db_file in (DB_PATH, AUTH_DB_PATH):
            try:
                conn = _get_db_connection(db_file)
                conn.execute(update_sql, (raw_token,))
                conn.commit()
                conn.close()
            except Exception:
                pass

    # Clear session state keys
    for key in (
        "session_token",
        "user_id",
        "username",
        "user_role",
        "owner_authenticated",
        "customer_authenticated",
        "customer_profile",
        "customer_id",
        "customer_name",
        "pipeline_result",
        "raw_data",
    ):
        st.session_state.pop(key, None)

    # Clear query parameters
    try:
        if "session" in st.query_params:
            del st.query_params["session"]
    except Exception:
        pass


def restore_authenticated_session() -> bool:
    """
    Attempts to restore authentication state if lost due to browser refresh.
    Reads persistent signed token from URL query parameters and validates against database.
    Returns True if user is currently authenticated (either already in session_state or restored),
    False otherwise.
    """
    # 1. Already authenticated in current in-memory turn
    role = st.session_state.get("user_role")
    if role in ("owner", "admin") and st.session_state.get("owner_authenticated", False):
        return True
    if role == "customer" and st.session_state.get("customer_authenticated", False):
        return True

    # 2. Check persistent token in URL query params
    token_candidate = None
    try:
        token_candidate = st.query_params.get("session")
    except Exception:
        pass

    if not token_candidate and "session_token" in st.session_state:
        token_candidate = st.session_state["session_token"]

    if not token_candidate:
        return False

    session_info = validate_session_token(token_candidate)
    if not session_info:
        # Invalid or expired token: clean up
        try:
            if "session" in st.query_params:
                del st.query_params["session"]
        except Exception:
            pass
        return False

    # 3. Re-hydrate session state
    norm_role = session_info["role"].strip().lower()
    st.session_state["session_token"] = session_info["session_token"]
    st.session_state["user_id"] = session_info["user_id"]
    st.session_state["username"] = session_info["username"]
    st.session_state["user_role"] = norm_role
    st.session_state["shop_id"] = session_info["shop_id"]
    st.session_state["shop_name"] = session_info["shop_name"]

    if norm_role in ("owner", "admin"):
        st.session_state["owner_authenticated"] = True
        st.session_state["customer_authenticated"] = False
        if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
            try:
                from utils.data_loader import refresh_application_data
                refresh_application_data(session_info.get("shop_id"))
            except Exception:
                pass
    elif norm_role == "customer":
        st.session_state["customer_authenticated"] = True
        st.session_state["owner_authenticated"] = False
        st.session_state["customer_id"] = session_info["user_id"]
        st.session_state["customer_name"] = session_info["username"]
        if "customer_profile" not in st.session_state:
            try:
                from components.customer_portal import get_customer_dashboard_data
                st.session_state["customer_profile"] = get_customer_dashboard_data(
                    session_info.get("shop_id", "shivansh_electronics_hardware"),
                    session_info["user_id"],
                )
            except Exception:
                pass

    return True


def ensure_authenticated_session(required_role: str = "owner") -> bool:
    """
    Comprehensive guard for page scripts.
    Checks and restores authentication across browser refreshes.
    If not authenticated or role mismatch, switches cleanly to app.py.
    """
    is_auth = restore_authenticated_session()
    current_role = st.session_state.get("user_role", "")

    if not is_auth:
        try:
            st.switch_page("app.py")
        except Exception:
            st.stop()
        return False

    req_role = required_role.lower()
    if req_role == "owner" and current_role not in ("owner", "admin"):
        try:
            st.switch_page("app.py")
        except Exception:
            st.stop()
        return False
    elif req_role == "customer" and current_role != "customer":
        try:
            st.switch_page("app.py")
        except Exception:
            st.stop()
        return False

    return True

