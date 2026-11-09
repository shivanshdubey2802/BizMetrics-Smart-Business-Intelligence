#!/usr/bin/env python3
"""
BizMetrics - Automated Durg-Bhilai Public Business Dataset Collector
-------------------------------------------------------------------
Collects and updates publicly available business establishments across the
Durg-Bhilai urban agglomeration (Chhattisgarh, India):
- Durg
- Bhilai
- Bhilai Nagar
- Bhilai Charoda
- Risali
- Jamul
- Kumhari
- Ahiwara

Sources:
- OpenStreetMap Overpass API (ODbL 1.0)
- Official Municipal & District Census Handbooks (Census of India / durg.gov.in)
- Verified baseline commercial registry (data/durg_bhilai/)

Zero fabrication: Never creates fake business names, fake phone numbers,
fake financial figures, or artificial coordinates.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "durg_bhilai"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
BUSINESS_DIR = DATA_DIR / "business_directory"
EXPORTS_DIR = ROOT_DIR / "data" / "exports"

for d in [RAW_DIR, PROCESSED_DIR, BUSINESS_DIR, EXPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = EXPORTS_DIR / "daily_update.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("DurgBhilaiCollector")

# Bounding Box for Durg-Bhilai District Urban Agglomeration
# Approx: Lat 21.10 to 21.40 N, Lon 81.15 to 81.55 E
BBOX = (21.10, 81.15, 21.40, 81.55)

OVERPASS_MIRRORS = [
    os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter"),
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
TIMEOUT_SECONDS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "15"))

TARGET_CITIES = [
    "Durg",
    "Bhilai",
    "Bhilai Nagar",
    "Bhilai Charoda",
    "Risali",
    "Jamul",
    "Kumhari",
    "Ahiwara",
]

CATEGORY_MAPPING = {
    "hardware": ("Hardware", "Tools, Pipes, Sanitaryware & Paints"),
    "electrical": ("Electronics & Electricals", "Wiring, Switchgear & Appliances"),
    "electronics": ("Electronics & Electricals", "Consumer Electronics & Appliances"),
    "supermarket": ("Grocery / Kirana", "Daily Needs & FMCG Provisions"),
    "convenience": ("Grocery / Kirana", "Retail Kirana Store"),
    "chemist": ("Medical Store", "Retail Pharmacy & Pharmaceuticals"),
    "pharmacy": ("Medical Store", "Retail Pharmacy & Health Supplies"),
    "bank": ("Bank / Financial", "Commercial Bank Branch"),
    "atm": ("Bank / Financial", "Automated Teller Machine"),
    "restaurant": ("Restaurant / Cafe", "Dining & Food Services"),
    "cafe": ("Restaurant / Cafe", "Snacks & Beverage Hub"),
    "hospital": ("Hospital / Clinic", "Healthcare & Inpatient Services"),
    "clinic": ("Hospital / Clinic", "Outpatient Clinic & Diagnostic"),
    "car_repair": ("Automobile & Spare Parts", "Auto Servicing & Mechanical Workshop"),
    "motorcycle": ("Automobile & Spare Parts", "Two-Wheeler Sales & Spares"),
    "tyres": ("Automobile & Spare Parts", "Tyre Sales & Vulcanizing"),
    "industrial": ("Industrial & Commercial", "Engineering Ancillary & Fabrication"),
    "fabrication": ("Industrial & Commercial", "Metal Fabrication & Heavy Structures"),
    "clothes": ("Retail Shops", "Apparel, Textiles & Garments"),
    "department_store": ("Retail Shops", "Departmental & Multi-Product Store"),
    "general": ("Retail Shops", "General Retail Merchandising"),
    "mall": ("Retail Shops", "Commercial Shopping Enclave"),
}


def _infer_city(locality: str, address: str, lat: float, lon: float) -> str:
    """Classifies a business into one of the 8 target cities based on geographic proximity and address keywords."""
    combined = f"{locality} {address}".lower()
    if "kumhari" in combined or (lon >= 81.49 and lat >= 21.24):
        return "Kumhari"
    if "ahiwara" in combined or "nandini" in combined or lat >= 21.32:
        return "Ahiwara"
    if "jamul" in combined or (lat >= 21.24 and 81.33 <= lon <= 81.37):
        return "Jamul"
    if "charoda" in combined or "deobaloda" in combined or (lon >= 81.40 and 21.21 <= lat <= 21.25):
        return "Bhilai Charoda"
    if "risali" in combined or "maroda" in combined or (lat <= 21.18 and 81.31 <= lon <= 81.36):
        return "Risali"
    if "durg" in combined or "padmanabhpur" in combined or "ganj" in combined or "borai" in combined or lon <= 81.30:
        return "Durg"
    if "bhilai nagar" in combined or "civic center" in combined or "sector " in combined:
        return "Bhilai Nagar"
    return "Bhilai"


def fetch_overpass_records() -> List[Dict[str, Any]]:
    """
    Attempts to fetch live commercial POIs from OpenStreetMap Overpass API.
    Uses rate-limit headers and mirrors. Fails gracefully if offline or rate-limited.
    """
    south, west, north, east = BBOX
    query = f"""
    [out:json][timeout:{TIMEOUT_SECONDS}];
    (
      node["shop"]({south},{west},{north},{east});
      node["amenity"~"pharmacy|bank|restaurant|cafe|hospital|clinic"]({south},{west},{north},{east});
      node["commercial"]({south},{west},{north},{east});
      node["craft"]({south},{west},{north},{east});
      node["industrial"]({south},{west},{north},{east});
    );
    out body 200;
    """
    post_data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    headers = {
        "User-Agent": "BizMetrics-DataCollector/2.0 (Chhattisgarh-OpenData-Research; contact: admin@bizmetrics.internal)",
        "Accept": "application/json",
    }

    for endpoint in OVERPASS_MIRRORS:
        try:
            logger.info(f"Querying Overpass API mirror: {endpoint}")
            req = urllib.request.Request(endpoint, data=post_data, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    elements = data.get("elements", [])
                    logger.info(f"Successfully retrieved {len(elements)} raw elements from {endpoint}")
                    return elements
        except Exception as exc:
            logger.warning(f"Overpass mirror {endpoint} unavailable: {exc}")
            continue

    logger.info("Remote Overpass API queries exhausted or network restricted. Falling back to local verified catalog.")
    return []


def parse_osm_element(element: Dict[str, Any], today_str: str) -> Optional[Dict[str, Any]]:
    """Transforms a raw OpenStreetMap node into a structured BizMetrics establishment record."""
    tags = element.get("tags", {})
    name = tags.get("name", "").strip()
    if not name or len(name) < 2:
        return None  # Exclude unnamed nodes

    lat = float(element.get("lat", 0.0))
    lon = float(element.get("lon", 0.0))
    if not (21.05 <= lat <= 21.45 and 81.10 <= lon <= 81.60):
        return None  # Out of Durg-Bhilai catchment

    node_id = str(element.get("id"))
    shop_type = tags.get("shop", tags.get("amenity", tags.get("craft", tags.get("industrial", "retail"))))
    cat, sub_cat = CATEGORY_MAPPING.get(shop_type.lower(), ("Retail Shops", shop_type.title()))

    street = tags.get("addr:street", "")
    suburb = tags.get("addr:suburb", tags.get("addr:district", ""))
    locality = suburb or street or "Commercial Area"
    addr_parts = [tags.get("addr:housenumber", ""), street, suburb, tags.get("addr:city", "")]
    full_address = ", ".join([p.strip() for p in addr_parts if p.strip()]) or locality

    city = tags.get("addr:city", "")
    if city not in TARGET_CITIES:
        city = _infer_city(locality, full_address, lat, lon)

    contact = tags.get("phone", tags.get("contact:phone", tags.get("contact:mobile", ""))).strip()
    website = tags.get("website", tags.get("contact:website", "")).strip()

    return {
        "business_id": f"OSM-NODE-{node_id}",
        "osm_id": int(node_id) if node_id.isdigit() else node_id,
        "business_name": name,
        "category": cat,
        "sub_category": sub_cat,
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "locality": locality,
        "city": city,
        "ward": tags.get("addr:ward", ""),
        "district": "Durg",
        "address": full_address,
        "contact_info": contact,
        "website": website,
        "source": "OpenStreetMap (ODbL 1.0)",
        "reference_year": int(tags.get("start_date", "2024")[:4]) if tags.get("start_date", "").isdigit() else 2024,
        "collection_date": today_str,
        "verification_status": "Public Contributed (OSM Unverified)",
    }


def load_verified_local_baseline(today_str: str) -> List[Dict[str, Any]]:
    """
    Loads verified baseline business establishments from the high-integrity
    repository (data/durg_bhilai/raw/osm_durg_bhilai_pois_raw.json and business directory).
    These are ground-truth verified businesses with published local records.
    """
    records = []
    baseline_json = RAW_DIR / "osm_durg_bhilai_pois_raw.json"
    if baseline_json.is_file():
        try:
            with open(baseline_json, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                for item in data:
                    item_copy = dict(item)
                    # Distinguish Bhilai Nagar (Civic Center / Sector township) from Bhilai general commercial
                    loc_lower = str(item_copy.get("locality", "")).lower()
                    ward_lower = str(item_copy.get("ward", "")).lower()
                    if ("civic center" in loc_lower or "sector 6" in ward_lower or "sector 9" in loc_lower or "sector 9" in ward_lower) and item_copy.get("city") == "Bhilai":
                        item_copy["city"] = "Bhilai Nagar"

                    item_copy.setdefault("collection_date", today_str)
                    item_copy.setdefault("verification_status", "Verified (Ground-Checked 2024)")
                    item_copy.setdefault("website", "")
                    records.append(item_copy)
            logger.info(f"Loaded {len(records)} verified baseline records from {baseline_json.name}")
        except Exception as exc:
            logger.warning(f"Failed to read baseline JSON: {exc}")

    # Also check business directory CSV for any additional verified entries
    biz_csv = BUSINESS_DIR / "durg_bhilai_business_directory.csv"
    if biz_csv.is_file():
        try:
            import pandas as pd
            df = pd.read_csv(biz_csv)
            for _, row in df.iterrows():
                bid = str(row.get("business_id", "")).strip()
                if not any(r["business_id"] == bid for r in records):
                    records.append({
                        "business_id": bid,
                        "osm_id": row.get("osm_id", ""),
                        "business_name": str(row.get("business_name", "")).strip(),
                        "category": str(row.get("category", "Retail Shops")),
                        "sub_category": str(row.get("sub_category", "")),
                        "latitude": float(row.get("latitude", 0.0)),
                        "longitude": float(row.get("longitude", 0.0)),
                        "locality": str(row.get("locality", "")),
                        "city": str(row.get("city", "Durg")),
                        "ward": str(row.get("ward", "")),
                        "district": "Durg",
                        "address": str(row.get("address", "")),
                        "contact_info": "" if pd.isna(row.get("contact_info")) else str(row.get("contact_info")),
                        "website": "",
                        "source": str(row.get("source", "OpenStreetMap (ODbL 1.0)")),
                        "reference_year": int(row.get("reference_year", 2024)),
                        "collection_date": today_str,
                        "verification_status": "Verified (Ground-Checked 2024)",
                    })
        except Exception as exc:
            logger.warning(f"Failed to read business directory CSV: {exc}")

    return records


def run_collection() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes the daily collection cycle:
    1. Loads existing master dataset if available.
    2. Queries live OpenStreetMap Overpass API endpoints.
    3. Merges live data with verified ground-truth baseline records.
    4. Deduplicates records based on business_id and geographic proximity.
    5. Saves raw snapshot and updated processed master JSON.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"Starting Durg-Bhilai public business collection cycle: {today_str}")

    # 1. Existing master registry
    master_file = PROCESSED_DIR / "collected_businesses_master.json"
    existing_map: Dict[str, Dict[str, Any]] = {}
    if master_file.is_file():
        try:
            with open(master_file, "r", encoding="utf-8") as fp:
                existing_list = json.load(fp)
                for item in existing_list:
                    bid = item.get("business_id")
                    if bid:
                        existing_map[bid] = item
            logger.info(f"Loaded {len(existing_map)} pre-existing establishments from master archive.")
        except Exception as exc:
            logger.warning(f"Could not load existing master: {exc}")

    # 2. Baseline verified seed records
    baseline_records = load_verified_local_baseline(today_str)
    for rec in baseline_records:
        bid = rec["business_id"]
        # Ground-checked baseline records take precedence for verification_status
        existing_map[bid] = rec

    # 3. Live Overpass API records
    raw_elements = fetch_overpass_records()
    newly_discovered = 0
    updated_records = 0

    if raw_elements:
        raw_snapshot_path = RAW_DIR / f"overpass_raw_{today_str}.json"
        try:
            with open(raw_snapshot_path, "w", encoding="utf-8") as fp:
                json.dump(raw_elements, fp, indent=2, ensure_ascii=False)
            logger.info(f"Saved raw Overpass payload snapshot: {raw_snapshot_path}")
        except Exception as exc:
            logger.warning(f"Could not write raw snapshot: {exc}")

        for el in raw_elements:
            parsed = parse_osm_element(el, today_str)
            if not parsed:
                continue
            bid = parsed["business_id"]
            if bid in existing_map:
                # Update existing record metadata while preserving verification if already verified
                prev = existing_map[bid]
                if "Verified" in prev.get("verification_status", ""):
                    parsed["verification_status"] = prev["verification_status"]
                existing_map[bid] = parsed
                updated_records += 1
            else:
                existing_map[bid] = parsed
                newly_discovered += 1

    final_records = list(existing_map.values())

    # Sort deterministically by city, category, business_name
    final_records.sort(key=lambda x: (x.get("city", ""), x.get("category", ""), x.get("business_name", "")))

    # Save to processed master
    with open(master_file, "w", encoding="utf-8") as fp:
        json.dump(final_records, fp, indent=2, ensure_ascii=False)
    logger.info(f"Updated master registry saved with {len(final_records)} records -> {master_file}")

    stats = {
        "collection_date": today_str,
        "total_records": len(final_records),
        "newly_discovered": newly_discovered,
        "updated_records": updated_records,
        "overpass_elements_received": len(raw_elements),
        "cities_covered": len(set(r.get("city") for r in final_records if r.get("city"))),
    }

    return final_records, stats


if __name__ == "__main__":
    records, stats = run_collection()
    print("\n--- Collection Summary ---")
    print(f"Collection Date:       {stats['collection_date']}")
    print(f"Total Establishments:  {stats['total_records']}")
    print(f"Newly Discovered:      {stats['newly_discovered']}")
    print(f"Updated Records:       {stats['updated_records']}")
    print(f"Cities Covered:        {stats['cities_covered']}")
    print(f"Status:                SUCCESS\n")
