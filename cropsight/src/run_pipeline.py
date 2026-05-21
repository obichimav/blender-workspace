"""
CropSight — Python pipeline (steps 1 + 2).
Fetches satellite data, computes NDVI, writes textures + data.json.

Usage (from project root):
    python src/run_pipeline.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fetch_data    import fetch_and_save
from compute_ndvi  import process_and_save


def main():
    print("=" * 52)
    print("  CropSight — Pipeline")
    print("=" * 52)

    print("\n[1/2] Fetching satellite data …")
    ndvi, meta = fetch_and_save()
    print(f"  Source: {meta['source']}")

    print("\n[2/2] Computing NDVI zones + textures …")
    data = process_and_save()

    m = data["metrics"]
    print(f"\n  Region : {data['region']['name']}")
    print(f"  Scene  : {data['scene']['width_m']} × {data['scene']['height_m']} m")
    print(f"  NDVI   : mean={m['ndvi_mean']:.3f}  std={m['ndvi_std']:.3f}")
    print(f"  Zones  : stressed={m['pct_stressed']:.1f}%  "
          f"moderate={m['pct_moderate']:.1f}%  "
          f"healthy={m['pct_healthy']:.1f}%")
    print(f"  Crops  : {len(data['crop_positions'])} instances")
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
