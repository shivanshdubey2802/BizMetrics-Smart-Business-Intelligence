import pytest
import pandas as pd
from ai_advisor import (
    BizMetricsContextBuilder,
    DeterministicFallback,
    IndiaMarketCalendar,
    IntentDetector,
    detect_language,
)

def test_intent_detection():
    # Financial
    assert "FINANCIAL" in IntentDetector.detect("Why did my profit fall?")
    # Inventory
    assert "INVENTORY" in IntentDetector.detect("What should I reorder?")
    # Receivables
    assert "RECEIVABLES" in IntentDetector.detect("Who has outstanding payments?")
    # Festival
    assert "FESTIVAL" in IntentDetector.detect("Prepare for the next festival.")
    # Sales
    assert "SALES" in IntentDetector.detect("How to improve sales?")
    # Customers
    assert "CUSTOMER" in IntentDetector.detect("Which customers should I target?")
    # General Fallback
    assert "GENERAL" in IntentDetector.detect("Hello!")

def test_festival_proximity():
    # Anchor date: August 30, 2026
    current_date = pd.to_datetime("2026-08-30")
    upcoming = IndiaMarketCalendar.get_upcoming_festivals(current_date, horizon_days=45)
    
    # Should find Janmashtami (Sept 4), Ganesh Chaturthi (Sept 14), Onam (Sept 24), Navratri (Oct 10)
    names = [f["name"] for f in upcoming]
    assert "Janmashtami" in names
    assert "Ganesh Chaturthi" in names
    assert "Onam" in names
    assert "Navratri" in names
    
    # Check days logic
    janmashtami = next(f for f in upcoming if f["name"] == "Janmashtami")
    assert janmashtami["days_until"] == 5

def test_deterministic_fallback():
    context = {
        "financials": {"profit_margin": 8.0},
        "inventory": {"low_stock_items": 3},
        "upcoming_festivals": [{"name": "Diwali", "days_until": 15, "season": "Autumn"}],
        "receivables": {"overdue": 10000},
        "customers": {"at_risk": 5}
    }
    
    # Financial Intent
    res = DeterministicFallback.generate("margin", context, ["FINANCIAL"])
    assert "Low Margin Warning" in res["recommendation"]
    
    # Inventory & Festival Intent
    res = DeterministicFallback.generate("stock", context, ["INVENTORY", "FESTIVAL"])
    assert "Inventory Risk" in res["recommendation"]
    assert "Festive Preparation" in res["recommendation"]
    assert "Diwali" in res["recommendation"]
    
    # Receivables Intent
    res = DeterministicFallback.generate("payments", context, ["RECEIVABLES"])
    assert "Cashflow Risk" in res["recommendation"]
    
    # Customer Intent
    res = DeterministicFallback.generate("customers", context, ["CUSTOMER"])
    assert "Customer Retention" in res["recommendation"]


def test_language_detection_and_multilingual_intents():
    assert detect_language("What business should I start?") == "English"
    assert detect_language("मुझे कितना ऋण मिल सकता है?") == "Hindi (हिंदी)"
    assert detect_language("Mere paas 50 hazar margin hai, kitna loan mil sakta hai?") == "Hindi (हिंदी)"
    assert "RECEIVABLES" in IntentDetector.detect("मुझे कितना पैसा देना है?")
    assert "INVENTORY" in IntentDetector.detect("Mera stock kam hai")
    assert "LOAN" in IntentDetector.detect("मुझे EMI कितनी होगी?")
    assert "SCHEME" in IntentDetector.detect("Kaunsi scheme milegi?")
    assert "FEASIBILITY" in IntentDetector.detect("Kya mujhe ye business start karna chahiye?")


def test_context_builder_preserves_actual_financial_context():
    pipeline_result = {
        "business": {"Shop_Name": "Demo Shop", "sector": "Retail", "state": "Chhattisgarh"},
        "financial": {"total_revenue": 100000, "net_profit": 20000, "profit_margin": 20},
        "loans": {"monthly_emi": 7013.80, "outstanding_principal": 450000},
    }
    context = BizMetricsContextBuilder.build(pipeline_result, ["GENERAL"], pd.to_datetime("2026-09-05"))
    assert context["financials"]["revenue"] == 100000
    assert context["loans"]["outstanding_principal"] == 450000


def test_hindi_fallback_keeps_values_and_schema():
    context = {"financials": {"profit_margin": 8.0}}
    response = DeterministicFallback.generate("मेरा लाभ मार्जिन कम है", context, ["FINANCIAL"], "Hindi (हिंदी)")
    assert response["language"] == "Hindi (हिंदी)"
    assert response["recommendations"]
    assert "कम लाभ" in response["recommendation"]
