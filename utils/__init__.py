"""
BizMetrics Utility Package
Ensures submodules like utils.translations are always fresh in long-running processes (e.g. Streamlit).
"""
import sys
import importlib

# Ensure utils.translations has translate_df
if "utils.translations" in sys.modules:
    _trans_mod = sys.modules["utils.translations"]
    if not hasattr(_trans_mod, "translate_df"):
        try:
            importlib.reload(_trans_mod)
        except Exception:
            pass

try:
    from utils.translations import (
        t,
        get_current_language,
        set_current_language,
        translate_df,
        translate_status,
        render_language_selector,
        normalize_lang,
    )
except Exception:
    def translate_df(df, lang=None):
        return df

__all__ = [
    "t",
    "get_current_language",
    "set_current_language",
    "translate_df",
    "translate_status",
    "render_language_selector",
    "normalize_lang",
]

