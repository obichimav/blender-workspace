"""ForestWatch — Step 1: generate NDVI frames + stats."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, OUTPUT_DIR
from generate_data import (
    generate_ndvi_sequence, compute_stats,
    save_ndvi_png, ndvi_to_rgb,
)
import json
import numpy as np
from PIL import Image


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("ForestWatch — generating NDVI time-series (Rondônia, Brazil 2018–2023)")
    seq = generate_ndvi_sequence()

    for year, ndvi in seq:
        save_ndvi_png(ndvi, DATA_DIR / f"ndvi_{year}.png")
        rgb = ndvi_to_rgb(ndvi)
        Image.fromarray(rgb, mode="RGB").save(DATA_DIR / f"ndvi_rgb_{year}.png")

    stats = compute_stats(seq)
    (DATA_DIR / "stats.json").write_text(json.dumps(stats, indent=2))

    print("\n  Year   Forest(km²)  Cleared(km²)  Forest%")
    print("  " + "-" * 44)
    for s in stats:
        print(f"  {s['year']}   {s['forest_km2']:>10.1f}   {s['cleared_km2']:>10.1f}   {s['forest_pct']:>6.1f}%")

    first_forest = stats[0]["forest_km2"]
    last_forest  = stats[-1]["forest_km2"]
    lost_km2 = first_forest - last_forest
    lost_pct = 100 * lost_km2 / first_forest
    print(f"\n  Net forest loss 2018→2023: {lost_km2:.1f} km² ({lost_pct:.1f}%)")
    print(f"  Data saved → {DATA_DIR}")


if __name__ == "__main__":
    main()
