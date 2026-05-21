"""
WaterSight — Python pipeline.
Downloads terrain + satellite tiles, computes water zones, writes data.json.

Usage (from project root):
    python src/run_pipeline.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fetch_terrain import fetch_all
from compute_zones  import process


def main():
    print("=" * 52)
    print("  WaterSight — Pipeline")
    print("=" * 52)

    print("\n[1/2] Fetching terrain + satellite tiles …")
    elev, sat, meta = fetch_all()

    print("\n[2/2] Computing water zones …")
    data = process()

    s = data["stats"]
    print(f"\n  Location : {data['location']['name']}")
    print(f"  Water drop: {s['water_drop_m']:.0f} m over 22 years")
    print(f"  Surface lost: {s['exposed_ring_km2']:.1f} km²  ({s['pct_water_lost']:.1f}%)")
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
