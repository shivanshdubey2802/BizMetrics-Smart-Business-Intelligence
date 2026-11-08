import pytest
import pandas as pd
from utils.translations import (
    t,
    normalize_lang,
    get_current_language,
    set_current_language,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
)
from ai_advisor import (
    detect_language,
    identify_query_language,
    DeterministicFallback,
    normalize_language,
)
from components.charts import get_base_layout
from utils.pdf_report import generate_feasibility_pdf

def test_language_normalization():
    """Verify normalization of language strings and aliases."""
    assert normalize_lang("English") == "English"
    assert normalize_lang("en") == "English"
    assert normalize_lang("हिंदी") == "हिंदी"
    assert normalize_lang("हिन्दी") == "हिंदी"
    assert normalize_lang("Hindi") == "हिंदी"
    assert normalize_lang("hi") == "हिंदी"
    assert normalize_lang("Hinglish") == "Hinglish"
    assert normalize_lang("hinglish") == "Hinglish"
    assert normalize_lang(None) == "English"
    assert normalize_lang("unknown") == "English"


def test_translations_dictionary_completeness():
    """Verify presence and accuracy of mandatory business translations across all 3 languages."""
    assert "English" in TRANSLATIONS
    assert "हिंदी" in TRANSLATIONS
    assert "Hinglish" in TRANSLATIONS

    # Test exact prompt examples
    # 1. Total Revenue
    assert t("Total Revenue", "English") == "Total Revenue"
    assert t("Total Revenue", "हिंदी") == "कुल राजस्व"
    assert t("Total Revenue", "Hinglish") == "Total Kamai"

    # 2. Outstanding Payments
    assert t("Outstanding Payments", "English") == "Outstanding Payments"
    assert t("Outstanding Payments", "हिंदी") == "बकाया भुगतान"
    assert t("Outstanding Payments", "Hinglish") == "Baaki Payment"

    # 3. Customer Purchase History
    assert t("Customer Purchase History", "English") == "Customer Purchase History"
    assert t("Customer Purchase History", "हिंदी") == "ग्राहक खरीद इतिहास"
    assert t("Customer Purchase History", "Hinglish") == "Customer ki Purchase History"

    # 4. Low Stock Alert
    assert t("Low Stock Alert", "English") == "Low Stock Alert"
    assert t("Low Stock Alert", "हिंदी") == "कम स्टॉक अलर्ट"
    assert t("Low Stock Alert", "Hinglish") == "Stock Kam Hone Ka Alert"

    # 5. Download Invoice
    assert t("Download Invoice", "English") == "Download Invoice"
    assert t("Download Invoice", "हिंदी") == "इनवॉइस डाउनलोड करें"
    assert t("Download Invoice", "Hinglish") == "Invoice Download Karo"

    # Test Sidebar modules
    assert t("Dashboard", "English") == "Dashboard"
    assert t("Dashboard", "हिंदी") == "डैशबोर्ड"
    assert t("Financial", "English") == "Financial"
    assert t("Financial", "हिंदी") == "वित्तीय स्थिति"
    assert t("Customers", "English") == "Customers"
    assert t("Customers", "हिंदी") == "ग्राहक"


def test_translation_graceful_fallback():
    """Unknown keys must fall back safely to raw text without raising exceptions."""
    assert t("UNKNOWN_CUSTOM_METRIC_123", "हिंदी") == "UNKNOWN_CUSTOM_METRIC_123"
    assert t("UNKNOWN_CUSTOM_METRIC_123", "Hinglish") == "UNKNOWN_CUSTOM_METRIC_123"
    assert t("", "हिंदी") == ""
    assert t(None, "हिंदी") == ""


def test_ai_advisor_multilingual_detection():
    """Verify language detection across English, Hindi (Devanagari), and Hinglish (Roman-script)."""
    # English questions
    assert identify_query_language("Why did my sales decrease?") == "English"
    assert identify_query_language("Which products should I reorder?") == "English"

    # Devanagari Hindi questions
    assert identify_query_language("मेरी बिक्री कम क्यों हुई?") == "हिंदी"
    assert identify_query_language("मुझे कौन से उत्पाद दोबारा ऑर्डर करने चाहिए?") == "हिंदी"

    # Hinglish questions (Roman-script Hindi)
    assert identify_query_language("Meri sales pichle mahine se kam kyu hai?") == "Hinglish"
    assert identify_query_language("Kaunsa stock dobara mangwana chahiye?") == "Hinglish"
    assert identify_query_language("Mere kitne payment pending hain?") == "Hinglish"

    # Legacy detect_language backward compatibility check
    assert detect_language("What business should I start?") == "English"
    assert detect_language("मुझे कितना ऋण मिल सकता है?") == "Hindi (हिंदी)"
    assert detect_language("Mere paas 50 hazar margin hai, kitna loan mil sakta hai?") == "Hindi (हिंदी)"
    assert detect_language("Meri sales pichle mahine se kam kyu hai?", selected_language="Hinglish") == "Hinglish"


def test_deterministic_fallback_in_hinglish():
    """Verify natural, conversational Hinglish outputs from DeterministicFallback."""
    context = {
        "financials": {"profit_margin": 8.0},
        "inventory": {"low_stock_items": 3},
        "upcoming_festivals": [{"name": "Diwali", "days_until": 15, "season": "Autumn"}],
        "receivables": {"overdue": 10000},
        "customers": {"at_risk": 5}
    }

    # Financial intent in Hinglish
    res_fin = DeterministicFallback.generate("margin", context, ["FINANCIAL"], language="Hinglish")
    assert res_fin["language"] == "Hinglish"
    assert "Kam Munafa" in res_fin["recommendation"]
    assert "Aapka Net Profit Margin" in res_fin["recommendation"]
    assert len(res_fin["recommendations"]) > 0
    rec = res_fin["recommendations"][0]
    assert "Dukaan ke kharche" in rec["action"]

    # Inventory intent in Hinglish
    res_inv = DeterministicFallback.generate("stock", context, ["INVENTORY"], language="Hinglish")
    assert "Stock Kam Hone Ka" in res_inv["recommendation"]
    assert "Fast-selling items" in res_inv["recommendations"][0]["action"]


def test_chart_base_layout_font_support():
    """Verify that Plotly base layout includes Devanagari-capable font family."""
    layout = get_base_layout()
    font_family = layout.get("font", {}).get("family", "")
    assert "Devanagari" in font_family or "Nirmala" in font_family


def test_pdf_report_generates_with_multilingual_data():
    """Verify that ReportLab PDF generation works cleanly with localized strings."""
    sample_data = {
        "business_name": "Shivansh Electronics (शिवंश इलेक्ट्रॉनिक्स)",
        "business_category": "Electronics & Hardware",
        "state": "Chhattisgarh",
        "district": "Durg",
        "block": "Durg City",
        "village": "Ganjpara",
        "report_date": "2026-11-07",
        "business_outlook": "GOOD OPPORTUNITY / बढ़िया अवसर",
        "possible_business_cost": 200000.0,
        "your_money": 20000.0,
        "possible_loan": 180000.0,
        "loan_type": "Micro Finance Scheme",
        "monthly_payment": 3720.0,
        "business_risk": "MEDIUM",
        "summary": "Local demand is strong and loan payments are affordable.",
    }
    pdf_bytes = generate_feasibility_pdf(sample_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

