"""Transparent, data-backed helpers for Hyper-Local Opportunity analysis."""

from __future__ import annotations

from typing import Any
from functools import lru_cache
from pathlib import Path
import json
import math
import urllib.request
import urllib.error

import pandas as pd


def valid_coordinates(latitude: Any, longitude: Any) -> bool:
    try:
        return -90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180
    except (TypeError, ValueError):
        return False


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float | None:
    if not all(valid_coordinates(value, other) for value, other in ((latitude_a, longitude_a), (latitude_b, longitude_b))):
        return None
    radius = 6371.0088
    lat_a, lat_b = math.radians(float(latitude_a)), math.radians(float(latitude_b))
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(float(longitude_b) - float(longitude_a))
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def filter_within_radius(frame: pd.DataFrame, origin_latitude: float, origin_longitude: float, radius_km: float) -> pd.DataFrame:
    latitude_column = _column(frame, "latitude", "lat", "business_latitude")
    longitude_column = _column(frame, "longitude", "lon", "lng", "business_longitude")
    if latitude_column is None or longitude_column is None or not valid_coordinates(origin_latitude, origin_longitude):
        return frame.iloc[0:0].copy()
    distances = frame.apply(
        lambda row: haversine_km(origin_latitude, origin_longitude, row[latitude_column], row[longitude_column]),
        axis=1,
    )
    result = frame.loc[distances.notna() & (distances <= max(0.0, float(radius_km)))].copy()
    result["distance_km"] = distances.loc[result.index]
    return result


def extract_coordinates(frame: pd.DataFrame) -> tuple[float, float] | None:
    latitude_column = _column(frame, "latitude", "lat", "business_latitude")
    longitude_column = _column(frame, "longitude", "lon", "lng", "business_longitude")
    if latitude_column is None or longitude_column is None:
        return None
    for _, row in frame.iterrows():
        if valid_coordinates(row[latitude_column], row[longitude_column]):
            return float(row[latitude_column]), float(row[longitude_column])
    return None


@lru_cache(maxsize=256)
def get_location_coordinates(village: str = "", block: str = "", district: str = "", state: str = "") -> dict[str, Any]:
    """Coordinate adapter. Returns unavailable until a configured geocoder exists."""
    return {
        "latitude": None,
        "longitude": None,
        "source": "Geocoding unavailable; village/block proxy used",
        "confidence": "Needs Verification",
        "query": ", ".join(part for part in (village, block, district, state) if part),
    }


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    lookup = {str(column).lower(): column for column in frame.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def _numeric(frame: pd.DataFrame, *names: str) -> pd.Series:
    column = _column(frame, *names)
    if column is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(
        frame[column].astype(str).str.replace("₹", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce",
    ).dropna()


def market_reach(frame: pd.DataFrame, selected_village: str, selected_district: str, origin_coordinates: tuple[float, float] | None = None) -> dict[str, Any]:
    customer_column = _column(frame, "customer_id", "Customer_ID")
    city_column = _column(frame, "city", "City", "village", "Village")
    if customer_column is None:
        return {
            "5_km": {"estimated_consumers": None, "households": None, "source": "Data unavailable", "confidence": "Needs Verification", "interpretation": "Exact local consumer data is unavailable."},
            "10_km": {"estimated_consumers": None, "households": None, "source": "Data unavailable", "confidence": "Needs Verification", "interpretation": "Exact local consumer data is unavailable."},
            "analysis_level": "Needs Verification",
        }

    customer_rows = frame[frame[customer_column].notna()].copy()
    if origin_coordinates:
        five_rows = filter_within_radius(frame, origin_coordinates[0], origin_coordinates[1], 5)
        ten_rows = filter_within_radius(frame, origin_coordinates[0], origin_coordinates[1], 10)
        five_km = int(five_rows[customer_column].nunique()) if not five_rows.empty else 0
        ten_km = int(ten_rows[customer_column].nunique()) if not ten_rows.empty else 0
        return {
            "5_km": {"estimated_consumers": None, "known_customers": five_km, "households": None, "source": "Customer coordinates and Haversine distance", "confidence": "Medium", "interpretation": "Known customers within a true 5 km radius; this is not population."},
            "10_km": {"estimated_consumers": None, "known_customers": ten_km, "households": None, "source": "Customer coordinates and Haversine distance", "confidence": "Medium", "interpretation": "Known customers within a true 10 km radius; this is not population."},
            "analysis_level": "Coordinate-based radius",
        }
    if city_column and selected_village and selected_village != "Other (Estimated)":
        local_rows = customer_rows[customer_rows[city_column].astype(str).str.casefold() == str(selected_village).casefold()]
        level = "Village" if not local_rows.empty else "District-level fallback"
    else:
        local_rows = customer_rows.iloc[0:0]
        level = "District-level fallback"
    five_km = int(local_rows[customer_column].nunique()) if not local_rows.empty else None
    ten_km = int(customer_rows[customer_column].nunique()) if not customer_rows.empty else None
    source = "Local customer activity proxy" if ten_km is not None else "Data unavailable"
    confidence = "Low" if ten_km is not None else "Needs Verification"
    return {
        "5_km": {"estimated_consumers": five_km, "known_customers": five_km, "households": None, "source": source, "confidence": confidence, "interpretation": "Estimated nearby customer activity; not official population."},
        "10_km": {"estimated_consumers": ten_km, "known_customers": ten_km, "households": None, "source": source, "confidence": confidence, "interpretation": "Estimated wider customer activity; exact radius data is unavailable."},
        "analysis_level": level,
    }


def demand_competition_matrix(demand_score: float, competition_score: float) -> dict[str, str]:
    demand = "High" if demand_score >= 70 else "Medium" if demand_score >= 40 else "Low"
    competition = "High" if competition_score >= 70 else "Medium" if competition_score >= 40 else "Low"
    values = {
        ("High", "Low"): "BEST",
        ("High", "Medium"): "GOOD",
        ("High", "High"): "SATURATED",
        ("Medium", "Low"): "GOOD",
        ("Medium", "Medium"): "MODERATE",
        ("Medium", "High"): "RISKY",
        ("Low", "Low"): "WEAK",
        ("Low", "Medium"): "LOW",
        ("Low", "High"): "AVOID",
    }
    result = values[(demand, competition)]
    gap = {
        "BEST": "Potentially Underserved",
        "GOOD": "Moderately Underserved",
        "SATURATED": "Highly Saturated",
        "MODERATE": "Balanced",
        "RISKY": "Competitive",
        "WEAK": "Balanced",
        "LOW": "Competitive",
        "AVOID": "Highly Saturated",
    }[result]
    return {"demand_level": demand, "competition_level": competition, "matrix_result": result, "opportunity_gap": gap}


def competitor_density(frame: pd.DataFrame, category: str) -> dict[str, Any]:
    category_column = _column(frame, "category", "Category", "sector", "Sector")
    customer_column = _column(frame, "customer_id", "Customer_ID")
    if category_column is None:
        return {"estimated_similar_businesses": None, "level": "Needs Verification", "source": "Data unavailable", "confidence": "Needs Verification"}
    category_rows = frame[frame[category_column].astype(str).str.contains(str(category), case=False, na=False)]
    activity = int(category_rows[customer_column].nunique()) if customer_column and not category_rows.empty else len(category_rows)
    level = "Low" if activity < 10 else "Moderate" if activity < 50 else "High" if activity < 100 else "Very High"
    return {"estimated_similar_businesses": activity, "level": level, "source": "Category/customer activity proxy", "confidence": "Low" if activity else "Needs Verification"}


def category_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    category_column = _column(frame, "category", "Category", "sector", "Sector")
    if category_column is None:
        return pd.DataFrame(columns=["Category", "Observed Records"])
    rows = frame[frame[category_column].notna()].copy()
    if rows.empty:
        return pd.DataFrame(columns=["Category", "Observed Records"])
    comparison = rows.groupby(category_column).size().sort_values(ascending=False).head(5).reset_index(name="Observed Records")
    comparison.columns = ["Category", "Observed Records"]
    return comparison


def pricing_intelligence(frame: pd.DataFrame, category: str) -> dict[str, Any]:
    category_column = _column(frame, "category", "Category", "sector", "Sector")
    selected = frame if category_column is None else frame[frame[category_column].astype(str).str.contains(str(category), case=False, na=False)]
    prices = _numeric(selected, "selling_price", "Selling_Price")
    costs = _numeric(selected, "purchase_price", "Purchase_Price")
    if prices.empty:
        return {"reference_price": None, "lower_price": None, "upper_price": None, "recommended_price": None, "confidence": "Needs Verification", "source": "Data unavailable"}
    return {
        "reference_price": float(prices.median()),
        "lower_price": float(prices.quantile(0.25)),
        "upper_price": float(prices.quantile(0.75)),
        "recommended_price": float(prices.median()),
        "expected_margin": float((prices.median() - costs.median()) / prices.median() * 100) if not costs.empty and prices.median() else None,
        "confidence": "Medium" if len(prices) >= 5 else "Low",
        "source": "Observed category selling prices",
    }


def buyer_concentration(frame: pd.DataFrame) -> dict[str, Any]:
    customer_column = _column(frame, "customer_id", "Customer_ID")
    amount_column = _column(frame, "total_amount", "Total_Amount", "amount", "Amount")
    if customer_column is None or amount_column is None:
        return {"top_customer_share": None, "risk_level": "Needs Verification", "reason": "No customer revenue data is available."}
    sales = frame[frame[customer_column].notna()].copy()
    sales["_amount"] = pd.to_numeric(sales[amount_column], errors="coerce").fillna(0)
    totals = sales.groupby(customer_column)["_amount"].sum()
    total = totals.sum()
    if totals.empty or total <= 0:
        return {"top_customer_share": None, "risk_level": "Needs Verification", "reason": "No customer revenue data is available."}
    share = float(totals.max() / total * 100)
    level = "High" if share >= 40 else "Medium" if share >= 25 else "Low"
    return {"top_customer_share": share, "risk_level": level, "reason": f"Largest customer represents {share:.1f}% of observed customer revenue."}


def supply_chain_risk(frame: pd.DataFrame, category: str) -> dict[str, str]:
    lead_times = _numeric(frame, "lead_time_days", "Lead_Time_Days")
    if lead_times.empty:
        return {"level": "Needs Verification", "source": "Estimated from available business/category indicators", "reason": "Supplier-level lead-time data is unavailable."}
    average = float(lead_times.mean())
    level = "High" if average > 14 else "Medium" if average > 7 else "Low"
    return {"level": level, "source": "Observed supplier lead-time proxy", "reason": f"Average observed lead time is {average:.1f} days for available records."}


def supplier_intelligence(frame: pd.DataFrame) -> dict[str, Any]:
    supplier_column = _column(frame, "supplier_id", "Supplier_ID", "vendor_id", "Vendor_ID")
    purchase_column = _column(frame, "total_ordered_amount", "Total_Ordered_Amount", "purchase_amount", "Purchase_Amount")
    if supplier_column is None:
        return {"supplier_count": None, "primary_supplier": None, "primary_share": None, "dependency": "Needs Verification", "source": "Supplier identity data unavailable", "confidence": "Needs Verification"}
    suppliers = frame[frame[supplier_column].notna() & (frame[supplier_column].astype(str).str.lower() != "nan")].copy()
    if suppliers.empty:
        return {"supplier_count": None, "primary_supplier": None, "primary_share": None, "dependency": "Needs Verification", "source": "Supplier identity data unavailable", "confidence": "Needs Verification"}
    if purchase_column is not None:
        suppliers["_purchase"] = pd.to_numeric(suppliers[purchase_column], errors="coerce").fillna(0)
        totals = suppliers.groupby(supplier_column)["_purchase"].sum()
    else:
        totals = suppliers[supplier_column].value_counts().astype(float)
    total = totals.sum()
    primary = totals.idxmax()
    share = float(totals.max() / total * 100) if total else None
    dependency = "High" if share is not None and share >= 70 else "Medium" if share is not None and share >= 40 else "Low" if share is not None else "Needs Verification"
    return {"supplier_count": int(totals.size), "primary_supplier": str(primary), "primary_share": share, "dependency": dependency, "source": "Observed supplier records", "confidence": "Medium" if purchase_column is not None else "Low"}


def distribution_channels(category: str) -> list[dict[str, str]]:
    category = str(category).lower()
    if any(word in category for word in ("manufact", "hardware", "trading")):
        channels = [("Primary", "Local Retail"), ("Secondary", "Nearby Villages"), ("Expansion", "Local Dealers")]
    elif any(word in category for word in ("food", "dairy", "agriculture")):
        channels = [("Primary", "Direct-to-Consumer"), ("Secondary", "Weekly Market / Haat"), ("Expansion", "WhatsApp / Direct Orders")]
    else:
        channels = [("Primary", "Direct-to-Consumer"), ("Secondary", "Local Retail"), ("Expansion", "WhatsApp / Direct Orders")]
    return [{"role": role, "channel": channel, "source": "Category-based recommendation"} for role, channel in channels]


def localized_swot(demand_score: float, competition_score: float, margin: float, project_cost: float, loan_share: float, gap: str, supply_level: str, buyer_level: str) -> dict[str, list[str]]:
    return {
        "Strengths": (["Strong demand indicators"] if demand_score >= 70 else []) + (["Lower competition indicators"] if competition_score < 40 else []) + (["Healthy expected margin"] if margin >= 15 else []),
        "Weaknesses": (["Limited local demand evidence"] if demand_score < 55 else []) + (["High initial investment"] if project_cost > 500000 else []) + (["High loan dependency"] if loan_share >= 70 else []),
        "Opportunities": (["Potentially underserved market gap"] if gap in ("Potentially Underserved", "Moderately Underserved") else []) + ["Nearby village expansion"],
        "Threats": (["High competition"] if competition_score >= 70 else []) + (["Supply-chain risk requires monitoring"] if supply_level in ("Medium", "High") else []) + (["Buyer concentration risk"] if buyer_level == "High" else []),
    }


BUSINESS_CANDIDATES = (
    ("Grocery / Kirana", 120000, ("grocery", "kirana", "daily", "retail"), ("Retail & Grocery", "Local Trading"), "daily-use demand and repeat purchases"),
    ("Dairy", 200000, ("dairy", "milk"), ("Dairy & Agriculture", "Food & Beverage"), "daily-use demand when local supply is reliable"),
    ("Food Processing", 250000, ("food", "processing", "snack"), ("Manufacturing & Food Processing", "Food & Beverage"), "value-added local food demand"),
    ("Poultry", 180000, ("poultry", "chicken", "egg"), ("Poultry & Livestock",), "regular food demand with manageable scale"),
    ("Agriculture Supplies", 220000, ("agriculture", "farm", "seed", "fertilizer"), ("Dairy & Agriculture", "Local Trading"), "nearby farming activity and seasonal demand"),
    ("Electrical & Hardware", 300000, ("electrical", "hardware", "plumbing", "construction"), ("Electrical & Hardware", "Repair & Services"), "observed hardware and maintenance demand"),
    ("Mobile & Electronics", 180000, ("mobile", "electronics", "accessories"), ("Electronics & Mobile", "Repair & Services"), "repair and accessory demand with moderate stock"),
    ("Tailoring", 100000, ("tailor", "tailoring", "garment", "cloth", "textile"), ("Clothing & Tailoring", "Home-Based Business"), "service-led clothing and alteration demand"),
    ("Beauty / Personal Care", 140000, ("beauty", "salon", "personal", "cosmetic"), ("Beauty & Personal Care",), "repeat local personal-care services"),
    ("Small Food Outlet", 150000, ("food", "restaurant", "stall", "cafe"), ("Food & Beverage",), "direct local food purchases"),
    ("Stationery / Printing", 160000, ("stationery", "printing", "school", "office"), ("Education & Stationery", "Digital & Online Services"), "school and office service demand"),
    ("Transport / Delivery", 275000, ("transport", "delivery", "logistics"), ("Transport & Delivery",), "local movement and delivery needs"),
)


def rank_alternative_businesses(
    frame: pd.DataFrame,
    current_business: str,
    available_capital: float,
    village: str = "",
    block: str = "",
    district: str = "",
    state: str = "",
    seasonality_score: float = 50,
    risk_score: float = 60,
    business_interests: list[str] | None = None,
    open_to_any: bool = False,
) -> list[dict[str, Any]]:
    """Rank alternatives from available data and transparent business benchmarks."""
    current = str(current_business).casefold()
    category_column = _column(frame, "category", "Category", "sector", "Sector")
    city_column = _column(frame, "city", "City", "village", "Village")
    customer_column = _column(frame, "customer_id", "Customer_ID")
    record_type_column = _column(frame, "record_type", "Record_Type")
    inventory = frame.copy()
    if record_type_column:
        inventory = inventory[inventory[record_type_column].astype(str).str.casefold().eq("inventory")]

    location_terms = [str(value).casefold().strip() for value in (village, block, district, state) if str(value).strip()]
    location_matches = 0
    if city_column and location_terms:
        location_values = inventory[city_column].astype(str).str.casefold()
        location_matches = int(location_values.isin(location_terms).sum())
    location_level = "Village + Block" if location_matches >= 5 else "District-level estimate" if location_matches else "General benchmark"
    confidence = "High" if location_matches >= 5 else "Medium" if location_matches else "Low"

    ranked = []
    capital = max(0.0, float(available_capital or 0))
    interests = {str(interest).casefold() for interest in (business_interests or [])}
    for name, estimated_cost, keywords, candidate_interests, reason in BUSINESS_CANDIDATES:
        candidate_key = name.casefold()
        if candidate_key in current or any(keyword in current for keyword in keywords):
            continue

        observed_rows = inventory.iloc[0:0]
        if category_column:
            category_values = inventory[category_column].astype(str).str.casefold()
            observed_rows = inventory[category_values.apply(lambda value: any(keyword in value for keyword in keywords))]
        observed_count = len(observed_rows)
        demand_score = min(90.0, 45.0 + observed_count * 10.0 + (8.0 if location_matches else 0.0))
        if observed_count == 0:
            demand_score = 48.0 + (6.0 if name in ("Grocery / Kirana", "Small Food Outlet", "Dairy") else 0.0)
        competition_score = min(90.0, 25.0 + observed_count * 12.0)
        capital_fit = min(100.0, capital / estimated_cost * 100.0) if estimated_cost else 0.0
        risk_advantage = max(0.0, min(100.0, risk_score + (10.0 if capital_fit >= 80 else -10.0)))
        opportunity_gap = max(0.0, demand_score - competition_score + 50.0)
        base_score = (
            demand_score * 0.30
            + (100.0 - competition_score) * 0.20
            + opportunity_gap * 0.20
            + capital_fit * 0.15
            + float(seasonality_score) * 0.10
            + risk_advantage * 0.05
        )
        candidate_interest_text = " ".join(candidate_interests).casefold().replace("&", " ")
        interest_match = 50.0
        if not (open_to_any or not interests):
            interest_match = 100.0 if any(
                selected == candidate_interest.casefold()
                or selected.split()[0] in candidate_interest_text
                or candidate_interest_text in selected
                for selected in interests
                for candidate_interest in candidate_interests
            ) else 25.0
        score = round(max(0.0, min(100.0, base_score * 0.75 + interest_match * 0.25)))
        if capital_fit < 20:
            continue
        ranked.append({
            "business": name,
            "score": score,
            "demand": round(demand_score),
            "competition": round(competition_score),
            "capital_fit": round(capital_fit),
            "interest_match": round(interest_match),
            "seasonality": round(float(seasonality_score)),
            "opportunity_gap": round(opportunity_gap),
            "reason": reason,
            "data_basis": location_level,
            "confidence": confidence,
        })
    return sorted(ranked, key=lambda item: (-item["score"], item["business"]))


def monthly_business_seasonality(
    frame: pd.DataFrame,
    business_name: str,
    village: str = "",
    block: str = "",
    district: str = "",
    state: str = "",
) -> dict[str, Any]:
    """Build a normalized monthly demand profile using the most local usable data."""
    months = list(range(1, 13))
    month_names = {month: pd.Timestamp(2026, month, 1).strftime("%B") for month in months}
    empty = pd.DataFrame(columns=frame.columns)
    record_column = _column(frame, "record_type", "Record_Type")
    product_column = _column(frame, "product_id", "Product_ID")
    category_column = _column(frame, "category", "Category", "sector", "Sector")
    date_column = _column(frame, "date", "Date")
    quantity_column = _column(frame, "quantity", "Quantity")
    amount_column = _column(frame, "total_amount", "Total_Amount", "amount", "Amount")
    city_column = _column(frame, "city", "City", "village", "Village")
    if not record_column or not product_column or not date_column or not category_column:
        return {"rows": [], "best_months": ["Estimated"], "difficult_months": ["Estimated"], "confidence": "Low", "basis": "General seasonal estimate", "reliable": False}

    inventory = frame[frame[record_column].astype(str).str.casefold().eq("inventory")]
    category_values = inventory[category_column].astype(str).str.casefold()
    business_terms = [term for term in str(business_name).casefold().replace("/", " ").split() if len(term) > 2]
    category_mask = category_values.apply(lambda value: any(term in value for term in business_terms))
    product_ids = set(inventory.loc[category_mask, product_column].astype(str))
    sales = frame[frame[record_column].astype(str).str.casefold().eq("sale") & frame[product_column].astype(str).isin(product_ids)].copy()
    basis = "Business category across dataset"

    location_values = [str(value).casefold().strip() for value in (village, block, district, state) if str(value).strip()]
    if city_column and not sales.empty and location_values:
        local_sales = sales[sales[city_column].astype(str).str.casefold().isin(location_values)]
        if len(local_sales) >= 3:
            sales = local_sales
            basis = "Village/block historical category sales"
        elif len(local_sales) > 0:
            basis = "District-level historical category sales"
    if basis == "Business category across dataset" and len(sales) >= 3:
        basis = "State/category historical sales"

    if sales.empty or date_column not in sales.columns:
        return {"rows": [], "best_months": ["Estimated"], "difficult_months": ["Estimated"], "confidence": "Low", "basis": "General seasonal estimate", "reliable": False}
    sales["_month"] = pd.to_datetime(sales[date_column], errors="coerce").dt.month
    sales = sales[sales["_month"].notna()].copy()
    if sales.empty:
        return {"rows": [], "best_months": ["Estimated"], "difficult_months": ["Estimated"], "confidence": "Low", "basis": "General seasonal estimate", "reliable": False}
    quantity = pd.to_numeric(sales[quantity_column], errors="coerce").fillna(0) if quantity_column else pd.Series(1, index=sales.index)
    amount = pd.to_numeric(sales[amount_column], errors="coerce").fillna(0) if amount_column else quantity
    monthly = pd.DataFrame({"month": sales["_month"], "quantity": quantity, "amount": amount}).groupby("month").agg(quantity=("quantity", "sum"), amount=("amount", "sum"), transactions=("quantity", "size"))
    monthly = monthly.reindex(months, fill_value=0)
    raw_signal = monthly["quantity"] + monthly["amount"] / max(1.0, monthly["amount"].max()) * max(1.0, monthly["quantity"].max())
    if raw_signal.max() <= 0:
        scores = pd.Series(50.0, index=months)
    else:
        scores = (raw_signal / raw_signal.max() * 100).round().clip(0, 100)
    coverage = int(sales["_month"].nunique())
    confidence = "High" if coverage >= 8 and len(sales) >= 30 else "Medium" if coverage >= 4 and len(sales) >= 10 else "Low"
    best_value, difficult_value = scores.max(), scores.min()
    best_months = [month_names[month] for month in months if scores[month] == best_value]
    difficult_months = [month_names[month] for month in months if scores[month] == difficult_value]
    rows = []
    for month in months:
        score = int(scores[month])
        status = "Peak / Best" if score >= 80 else "Strong" if score >= 65 else "Average" if score >= 50 else "Weak" if score >= 35 else "Difficult"
        rows.append({"Month": month_names[month], "Demand Score": score, "Status": status, "Confidence": confidence})
    return {"rows": rows, "best_months": best_months, "difficult_months": difficult_months, "confidence": confidence, "basis": basis, "reliable": coverage >= 2}


OSM_SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "osm_verified_businesses.json"


@lru_cache(maxsize=1)
def load_osm_dataset() -> dict[str, Any]:
    """Loads the verified OpenStreetMap POI dataset from data/sources/osm_verified_businesses.json."""
    if OSM_SOURCES_FILE.exists():
        try:
            with open(OSM_SOURCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"metadata": {}, "cities": {}}


def _category_matches(poi_cat: str, target_cat: str) -> bool:
    if not target_cat:
        return True
    p, t = str(poi_cat).lower().strip(), str(target_cat).lower().strip()
    if p == t or p in t or t in p:
        return True
    synonyms = {
        "grocery": ["convenience", "kirana", "supermarket", "wholesale", "general store"],
        "hardware": ["hardware", "tools", "steel", "electrical", "plumbing"],
        "electronics": ["electronics", "mobile", "computer", "accessories"],
        "cafe": ["cafe", "coffee", "tea", "bakery", "bistro"],
        "food stall": ["fast_food", "food stall", "restaurant", "snack"],
        "clothing": ["clothes", "tailoring", "textile", "apparel"],
        "agriculture supplies": ["agriculture", "agro", "seeds", "fertilizer", "hardware"],
    }
    for key, words in synonyms.items():
        if key in t:
            if any(w in p for w in words):
                return True
        if key in p:
            if any(w in t for w in words):
                return True
    return False


def query_osm_businesses(
    city: str = "Raipur",
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_km: float = 3.0,
    category: str | None = None,
    try_live_api: bool = False,
) -> dict[str, Any]:
    """
    Retrieves genuine OpenStreetMap commercial records and opportunities within the specified radius.
    Preserves strict data integrity: does not fabricate coordinates or business names.
    Falls back gracefully to verified OSM nodes when offline.
    """
    osm_data = load_osm_dataset()
    cities = osm_data.get("cities", {})

    durg_bhilai_centers = {
        "Durg": [21.1904, 81.2849],
        "Bhilai": [21.2144, 81.3788],
        "Bhilai Nagar": [21.1938, 81.3509],
        "Bhilai Charoda": [21.2255, 81.4245],
        "Risali": [21.1680, 81.3320],
        "Jamul": [21.2480, 81.3450],
        "Kumhari": [21.2680, 81.5120],
        "Ahiwara": [21.3600, 81.3850],
    }

    if city in durg_bhilai_centers:
        default_lat, default_lon = durg_bhilai_centers[city]
    else:
        city_info = cities.get(city) or cities.get("Raipur", {})
        default_lat, default_lon = city_info.get("center", [21.2514, 81.6296])

    lat = center_lat if (center_lat is not None and valid_coordinates(center_lat, center_lon or 0)) else default_lat
    lon = center_lon if (center_lon is not None and valid_coordinates(lat, center_lon)) else default_lon

    all_raw_pois = []
    source_label = "Verified OpenStreetMap POI Dataset (ODbL 1.0)"
    attribution = osm_data.get("metadata", {}).get("attribution", "© OpenStreetMap contributors")
    license_name = osm_data.get("metadata", {}).get("license", "Open Database License (ODbL) 1.0")
    is_live = False

    # 1. First attempt to query SQLite database local_business_directory
    try:
        from utils.database import get_local_businesses_df
        db_filter_city = city if city in durg_bhilai_centers else None
        db_pois_df = get_local_businesses_df(city=db_filter_city)
        if not db_pois_df.empty:
            for _, r in db_pois_df.iterrows():
                p_cat = str(r["category"])
                is_opp = "hub" in p_cat.lower() or "commercial" in p_cat.lower()
                all_raw_pois.append({
                    "osm_id": r.get("osm_id", "local"),
                    "name": r["business_name"],
                    "category": p_cat,
                    "sub_category": r.get("sub_category", ""),
                    "osm_tag": f"shop={p_cat.lower()}",
                    "lat": float(r["latitude"]),
                    "lon": float(r["longitude"]),
                    "street": r.get("address") or r.get("locality") or f"{r['city']} Market",
                    "city": r["city"],
                    "locality": r.get("locality", ""),
                    "ward": r.get("ward", ""),
                    "type": "opportunity" if is_opp else "competitor",
                    "source": f"OpenStreetMap Node #{r.get('osm_id', 'local')} ({r.get('city')})",
                    "reference_year": r.get("reference_year", 2024),
                })
            source_label = "Verified Durg-Bhilai OpenStreetMap Directory (Database / ODbL 1.0)"
    except Exception:
        pass

    # Optional live Overpass query if explicitly requested
    if try_live_api:
        overpass_url = "https://overpass-api.de/api/interpreter"
        radius_m = int(radius_km * 1000)
        query = f"""
        [out:json][timeout:3];
        (
          node["shop"](around:{radius_m},{lat},{lon});
          node["amenity"~"cafe|restaurant|fast_food"](around:{radius_m},{lat},{lon});
        );
        out body 30;
        """
        try:
            req = urllib.request.Request(
                overpass_url,
                data=query.encode("utf-8"),
                headers={"User-Agent": "BizMetrics-Intelligence/2.0 (+https://github.com/bizmetrics)"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for elem in data.get("elements", []):
                    tags = elem.get("tags", {})
                    name = tags.get("name")
                    if not name:
                        continue
                    cat = tags.get("shop") or tags.get("amenity") or "Retail"
                    all_raw_pois.append({
                        "osm_id": elem.get("id"),
                        "name": name,
                        "category": cat.capitalize(),
                        "osm_tag": f"{list(tags.keys())[0]}={list(tags.values())[0]}" if tags else "shop=yes",
                        "lat": elem.get("lat"),
                        "lon": elem.get("lon"),
                        "street": tags.get("addr:street") or tags.get("addr:city") or f"Near {city}",
                        "city": city,
                        "type": "competitor",
                        "source": "OpenStreetMap Overpass API (Live)"
                    })
                if all_raw_pois:
                    source_label = "OpenStreetMap Overpass API (Live Query)"
                    is_live = True
        except Exception:
            all_raw_pois = []

    # If live POIs were not fetched (or try_live_api was False), use verified local OSM dataset
    if not all_raw_pois:
        city_businesses = city_info.get("businesses", [])
        for b in city_businesses:
            poi = dict(b)
            poi["source"] = f"OpenStreetMap Node #{b.get('osm_id', 'verified')}"
            all_raw_pois.append(poi)

    # Calculate exact Haversine distance and filter within radius_km
    competitors = []
    opportunities = []

    for item in all_raw_pois:
        p_lat = item.get("lat")
        p_lon = item.get("lon")
        if p_lat is None or p_lon is None:
            continue
        dist = haversine_km(lat, lon, p_lat, p_lon)
        if dist is None or dist > radius_km:
            continue

        item_copy = dict(item)
        item_copy["dist"] = round(dist, 2)

        # Classify as competitor or opportunity
        node_type = item.get("type", "competitor")
        if node_type == "opportunity" or "hub" in str(item.get("category", "")).lower():
            opportunities.append(item_copy)
        else:
            # Check category compatibility
            if category and not _category_matches(item.get("category", ""), category):
                # If category doesn't match, it can represent an adjacent commercial node
                continue
            competitors.append(item_copy)

    competitors.sort(key=lambda x: x["dist"])
    opportunities.sort(key=lambda x: x["dist"])

    return {
        "city": city,
        "center": [lat, lon],
        "radius_km": radius_km,
        "competitors": competitors,
        "opportunities": opportunities,
        "source_label": source_label,
        "attribution": attribution,
        "license": license_name,
        "is_live": is_live,
    }

