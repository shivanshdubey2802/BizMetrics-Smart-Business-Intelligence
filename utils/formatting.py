from utils.translations import (
    TRANSLATIONS as _GLOBAL_TRANSLATIONS,
    t as _global_t,
    get_current_language,
    normalize_lang,
)

TRANSLATIONS = _GLOBAL_TRANSLATIONS.copy()
# Preserve legacy alias
TRANSLATIONS["हिन्दी"] = TRANSLATIONS["हिंदी"]

def t(key, lang=None):
    """Translation function supporting English, हिंदी, and Hinglish."""
    return _global_t(key, lang)

def format_currency(value, language="English"):
    if value is None:
        return "N/A"
    
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "N/A"
        
    abs_val = abs(val)
    
    if abs_val >= 10000000:
        formatted = f"₹{val / 10000000:,.2f} Crore"
    elif abs_val >= 100000:
        formatted = f"₹{val / 100000:,.2f} Lakh"
    else:
        # Quick hack for Indian formatting
        s, *d = str(int(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        formatted = f"₹{r}"
        if d and d[1]:
            formatted += "." + d[1]

    return formatted

