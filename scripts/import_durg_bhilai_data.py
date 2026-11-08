"""
BizMetrics - Import Durg-Bhilai Local Datasets into Database
Imports census demographics, OpenStreetMap business directory,
geographic nodes, and economic indicators into SQLite database tables.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from utils.database import (
    DB_PATH,
    AUTH_DB_PATH,
    import_durg_bhilai_datasets,
    get_local_businesses_df,
    get_local_demographics_df,
    get_local_economic_indicators_df,
    get_local_geographic_nodes_df,
    get_dataset_sources_df,
)


def run_import():
    print("=" * 65)
    print("  IMPORTING DURG-BHILAI LOCAL DATASETS INTO BIZMETRICS DATABASE")
    print("=" * 65)

    for target_db in [DB_PATH, AUTH_DB_PATH]:
        print(f"Target Database: {target_db.name}")
        stats = import_durg_bhilai_datasets(target_db)
        print(f"  • Demographics records imported:       {stats['demographics']}")
        print(f"  • Geographic locality nodes imported:  {stats['localities']}")
        print(f"  • OSM Business POIs imported:          {stats['businesses']}")
        print(f"  • Economic indicators imported:        {stats['economic']}")
        print(f"  • Dataset source citations imported:   {stats['sources']}")
        print("  ✓ Import complete with duplicate prevention.")

    print("-" * 65)
    print("Verification Query Results:")
    biz_df = get_local_businesses_df()
    demo_df = get_local_demographics_df()
    econ_df = get_local_economic_indicators_df()
    geo_df = get_local_geographic_nodes_df()
    src_df = get_dataset_sources_df()

    print(f"  • Total Mapped Businesses in Database:   {len(biz_df)}")
    print(f"  • Cities Covered:                        {', '.join(biz_df['city'].unique())}")
    print(f"  • Business Categories:                   {', '.join(biz_df['category'].unique())}")
    print(f"  • Total Demographics Records:            {len(demo_df)}")
    print(f"  • Total Regional Economic Indicators:    {len(econ_df)}")
    print(f"  • Geographic Locality Centroids:         {len(geo_df)}")
    print(f"  • Certified Source Provenances:          {len(src_df)}")
    print("=" * 65)


if __name__ == "__main__":
    run_import()

