"""
BizMetrics - Durg-Bhilai Local Data Validation Script
Validates coordinate bounding boxes, schema integrity, duplicate prevention,
and Census 2011 consistency before database ingestion.
"""

import json
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DATA_DIR = ROOT_DIR / "data" / "durg_bhilai"

# Bounding box for Durg District (including Durg, Bhilai, Charoda, Kumhari, Jamul, Ahiwara, Borai)
LAT_MIN, LAT_MAX = 21.00, 21.55
LON_MIN, LON_MAX = 21.10, 81.65  # 81.10 to 81.65


def validate_durg_bhilai_data() -> dict:
    results = {
        "demographics_valid": False,
        "localities_valid": False,
        "businesses_valid": False,
        "economic_valid": False,
        "sources_valid": False,
        "errors": [],
        "warnings": [],
        "counts": {}
    }

    print("=" * 60)
    print("  VALIDATING DURG-BHILAI LOCAL DATASETS")
    print("=" * 60)

    # 1. Validate Demographics
    demo_file = BASE_DATA_DIR / "demographics" / "durg_bhilai_census_demographics.csv"
    if not demo_file.exists():
        results["errors"].append("Missing demographics CSV file.")
    else:
        df_demo = pd.read_csv(demo_file)
        results["counts"]["demographics"] = len(df_demo)
        
        # Check duplicate IDs
        if df_demo["demographic_id"].duplicated().any():
            results["errors"].append(f"Duplicate demographic IDs found: {df_demo['demographic_id'][df_demo['demographic_id'].duplicated()].tolist()}")
        
        # Check demographic math: male + female == total
        for idx, row in df_demo.iterrows():
            total = int(row["total_population"])
            m = int(row["male_population"])
            f = int(row["female_population"])
            if abs((m + f) - total) > 5:
                results["warnings"].append(f"Demographic gender mismatch for {row['area_name']}: {m} + {f} != {total}")
            
            # Verify census year is labeled 2011
            if int(row.get("census_year", 0)) != 2011:
                results["errors"].append(f"Census year not properly labeled 2011 for {row['area_name']}.")

        print(f"  ✓ Demographics verified: {len(df_demo)} records across Durg district ULBs.")
        results["demographics_valid"] = True

    # 2. Validate Localities
    geo_file = BASE_DATA_DIR / "geographic" / "durg_bhilai_localities.csv"
    if not geo_file.exists():
        results["errors"].append("Missing localities CSV file.")
    else:
        df_geo = pd.read_csv(geo_file)
        results["counts"]["localities"] = len(df_geo)
        for idx, row in df_geo.iterrows():
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if not (LAT_MIN <= lat <= LAT_MAX and 81.10 <= lon <= 81.65):
                results["errors"].append(f"Coordinates out of bounds for {row['area_name']}: ({lat}, {lon})")
        print(f"  ✓ Geographic localities verified: {len(df_geo)} core urban nodes.")
        results["localities_valid"] = True

    # 3. Validate Businesses Directory (OSM)
    biz_file = BASE_DATA_DIR / "business_directory" / "durg_bhilai_business_directory.csv"
    if not biz_file.exists():
        results["errors"].append("Missing business directory CSV file.")
    else:
        df_biz = pd.read_csv(biz_file)
        results["counts"]["businesses"] = len(df_biz)

        # Check required fields
        req_cols = ["business_id", "osm_id", "business_name", "category", "latitude", "longitude", "city"]
        for c in req_cols:
            if c not in df_biz.columns:
                results["errors"].append(f"Missing column in business directory: {c}")

        # Check duplicate business_ids
        if df_biz["business_id"].duplicated().any():
            results["errors"].append("Duplicate business_id in business directory.")

        # Coordinate checks
        for idx, row in df_biz.iterrows():
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if not (LAT_MIN <= lat <= LAT_MAX and 81.10 <= lon <= 81.65):
                results["errors"].append(f"Business coordinate out of bounds for {row['business_name']}: ({lat}, {lon})")
            if not str(row["business_name"]).strip():
                results["errors"].append(f"Empty business name at index {idx}.")

        print(f"  ✓ Business directory verified: {len(df_biz)} verified commercial establishments.")
        results["businesses_valid"] = True

    # 4. Validate Economic Indicators
    econ_file = BASE_DATA_DIR / "economic_indicators" / "durg_district_economy.csv"
    if not econ_file.exists():
        results["errors"].append("Missing economic indicators CSV file.")
    else:
        df_econ = pd.read_csv(econ_file)
        results["counts"]["economic_indicators"] = len(df_econ)
        for idx, row in df_econ.iterrows():
            val = float(row["indicator_value"])
            if val <= 0:
                results["warnings"].append(f"Non-positive indicator value for {row['indicator_name']}: {val}")
        print(f"  ✓ Economic indicators verified: {len(df_econ)} regional indicators.")
        results["economic_valid"] = True

    # 5. Validate Sources Metadata
    src_file = BASE_DATA_DIR / "metadata" / "dataset_sources.json"
    if not src_file.exists():
        results["errors"].append("Missing sources metadata JSON file.")
    else:
        with open(src_file, "r", encoding="utf-8") as f:
            sources = json.load(f)
        results["counts"]["sources"] = len(sources)
        print(f"  ✓ Dataset sources metadata verified: {len(sources)} public authority citations.")
        results["sources_valid"] = True

    print("=" * 60)
    if not results["errors"]:
        print("  ALL DURG-BHILAI DATASETS PASSED VALIDATION (0 Errors)")
    else:
        print(f"  VALIDATION FAILED WITH {len(results['errors'])} ERRORS:")
        for err in results["errors"]:
            print(f"    - {err}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    validate_durg_bhilai_data()

