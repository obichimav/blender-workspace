"""
WaterSight — water zone computation.
Classifies each terrain pixel by its relationship to the two water levels:
  Zone 0 — below after-level  (currently submerged / deep lake)
  Zone 1 — between levels     (the bathtub ring: exposed since 2022)
  Zone 2 — above before-level (canyon walls / upland terrain)
"""
import sys
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import (
    WATER_LEVEL_BEFORE_M, WATER_LEVEL_AFTER_M,
    ELEVATION_NPY, ELEVATION_META, DATA_DIR, OUTPUT_DIR, DATA_JSON,
)


def classify_zones(elev: np.ndarray) -> np.ndarray:
    zones = np.full(elev.shape, 2, dtype=np.int32)   # default: upland
    zones[elev <= WATER_LEVEL_BEFORE_M] = 1           # was / is underwater
    zones[elev <= WATER_LEVEL_AFTER_M]  = 0           # currently submerged
    return zones


def compute_water_area(zones: np.ndarray, meta: dict) -> dict:
    """Estimate water surface area change in km²."""
    # Pixel ground size in metres (approximate at target latitude)
    import math
    lat_m = math.radians((meta["lat_n"] + meta["lat_s"]) / 2)
    deg_lat_m = 111_320
    deg_lon_m = 111_320 * math.cos(lat_m)
    px_height_m = (meta["lat_n"] - meta["lat_s"]) * deg_lat_m / meta["rows_px"]
    px_width_m  = (meta["lon_e"] - meta["lon_w"]) * deg_lon_m / meta["cols_px"]
    px_area_km2 = px_height_m * px_width_m / 1e6

    n_before = int((zones <= 1).sum())   # zone 0 + 1
    n_after  = int((zones == 0).sum())   # zone 0 only
    n_ring   = int((zones == 1).sum())   # bathtub ring

    return {
        "water_area_before_km2": round(n_before * px_area_km2, 2),
        "water_area_after_km2":  round(n_after  * px_area_km2, 2),
        "exposed_ring_km2":      round(n_ring   * px_area_km2, 2),
        "pct_water_lost":        round((n_ring / max(n_before, 1)) * 100, 1),
        "water_drop_m":          round(WATER_LEVEL_BEFORE_M - WATER_LEVEL_AFTER_M, 1),
        "px_area_km2":           round(px_area_km2, 6),
    }


def build_data_json(elev, zones, meta, stats):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Normalised heightmap values for Blender water plane positioning
    elev_range = meta["elev_max"] - meta["elev_min"]
    water_norm_before = (WATER_LEVEL_BEFORE_M - meta["elev_min"]) / elev_range
    water_norm_after  = (WATER_LEVEL_AFTER_M  - meta["elev_min"]) / elev_range

    data = {
        "schema_version": "0.1.0",
        "location": {
            "name":       "Lake Powell, Utah/Arizona",
            "bbox_wgs84": [-111.5, 37.0, -110.7, 37.6],
        },
        "water_levels": {
            "before_label": "Year 2000 — full pool",
            "before_m":     WATER_LEVEL_BEFORE_M,
            "after_label":  "Year 2022 — record low",
            "after_m":      WATER_LEVEL_AFTER_M,
            "drop_m":       WATER_LEVEL_BEFORE_M - WATER_LEVEL_AFTER_M,
        },
        "terrain": {
            "elev_min_m":   meta["elev_min"],
            "elev_max_m":   meta["elev_max"],
            "rows_px":      meta["rows_px"],
            "cols_px":      meta["cols_px"],
            "water_plane_before_norm": round(water_norm_before, 6),
            "water_plane_after_norm":  round(water_norm_after, 6),
        },
        "stats": stats,
    }
    with open(DATA_JSON, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Data JSON → {DATA_JSON}")
    return data


def process():
    elev = np.load(ELEVATION_NPY)
    with open(ELEVATION_META) as f:
        meta = json.load(f)

    zones = classify_zones(elev)
    stats = compute_water_area(zones, meta)

    print(f"  Water drop: {stats['water_drop_m']:.0f} m")
    print(f"  Before: {stats['water_area_before_km2']:.1f} km²  "
          f"After: {stats['water_area_after_km2']:.1f} km²")
    print(f"  Exposed ring: {stats['exposed_ring_km2']:.1f} km²  "
          f"({stats['pct_water_lost']:.1f}% lost)")

    data = build_data_json(elev, zones, meta, stats)
    return data


if __name__ == "__main__":
    process()
