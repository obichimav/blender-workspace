"""
SprinkleSim Mini — main pipeline.
Computes coverage math, writes output/data.json and output/zone_texture.png.

Usage (from project root):
    python src/run_pipeline.py
"""
import json
import sys
import os
from pathlib import Path

# Allow running from project root or src/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np
import matplotlib
matplotlib.use('Agg')   # headless — no display needed
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from config import (
    FIELD_WIDTH_FT, FIELD_HEIGHT_FT,
    SPRINKLER_THROW_FT, SPACING_FT, SPRINKLER_FLOW_GPM,
    GRID_RESOLUTION_FT, FT_TO_M,
    DATA_JSON_PATH, ZONE_TEXTURE_PATH,
)
from coverage_engine import (
    generate_sprinkler_grid,
    compute_coverage_field,
    compute_application_rate_field,
    compute_distribution_uniformity,
    compute_christiansen_uniformity,
    classify_zones,
)

ROOT = HERE.parent


def save_zone_texture(zones_array, output_path):
    """Render zones array as a borderless color PNG for use as a Blender texture."""
    cmap = ListedColormap([
        '#d64545',   # 0 = under-watered  (red)
        '#4caf50',   # 1 = optimal         (green)
        '#ffc107',   # 2 = over-watered    (yellow)
    ])

    fig, ax = plt.subplots(figsize=(10, 6.667), dpi=150)
    ax.imshow(zones_array, origin='lower', cmap=cmap, vmin=0, vmax=2,
              interpolation='nearest', aspect='auto')
    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0)
    plt.close()
    print(f"  Zone texture → {output_path}")


def main():
    print("=" * 50)
    print("SprinkleSim Mini — Pipeline")
    print("=" * 50)

    # ── Compute ───────────────────────────────────────────────────────────────
    print("\n[1/4] Placing sprinklers …")
    sprinklers = generate_sprinkler_grid(FIELD_WIDTH_FT, FIELD_HEIGHT_FT, SPACING_FT)
    print(f"  {len(sprinklers)} sprinklers at {SPACING_FT:.1f} ft spacing")

    print("[2/4] Computing coverage field …")
    coverage = compute_coverage_field(
        FIELD_WIDTH_FT, FIELD_HEIGHT_FT,
        sprinklers, SPRINKLER_THROW_FT, GRID_RESOLUTION_FT,
    )
    application = compute_application_rate_field(coverage, SPRINKLER_FLOW_GPM)
    zones = classify_zones(coverage)

    print("[3/4] Computing uniformity metrics …")
    du = compute_distribution_uniformity(application)
    cu = compute_christiansen_uniformity(application)

    # ── Print summary ─────────────────────────────────────────────────────────
    area_acres = FIELD_WIDTH_FT * FIELD_HEIGHT_FT / 43560
    total_cells = zones.size
    pct_dry     = float((zones == 0).sum() / total_cells * 100)
    pct_optimal = float((zones == 1).sum() / total_cells * 100)
    pct_over    = float((zones == 2).sum() / total_cells * 100)

    print(f"\n  Field: {FIELD_WIDTH_FT} × {FIELD_HEIGHT_FT} ft ({area_acres:.2f} acres)")
    print(f"  Sprinkler throw: {SPRINKLER_THROW_FT} ft  |  Spacing: {SPACING_FT:.1f} ft")
    print(f"  Distribution Uniformity (DU): {du:.3f}  {'✓' if du >= 0.75 else '⚠'}")
    print(f"  Christiansen Uniformity  (CU): {cu:.3f}  {'✓' if cu >= 0.85 else '⚠'}")
    print(f"  Zone breakdown:")
    print(f"    Under-watered:  {pct_dry:.1f}%")
    print(f"    Optimal:        {pct_optimal:.1f}%")
    print(f"    Over-watered:   {pct_over:.1f}%")

    # ── Save texture ──────────────────────────────────────────────────────────
    print("\n[4/4] Saving outputs …")
    (ROOT / "output").mkdir(exist_ok=True)
    save_zone_texture(zones, ROOT / ZONE_TEXTURE_PATH)

    # ── Write JSON ────────────────────────────────────────────────────────────
    output_data = {
        "schema_version": "0.1.0",
        "field": {
            "width_ft": FIELD_WIDTH_FT,
            "height_ft": FIELD_HEIGHT_FT,
            "width_m": round(FIELD_WIDTH_FT * FT_TO_M, 4),
            "height_m": round(FIELD_HEIGHT_FT * FT_TO_M, 4),
            "area_acres": round(area_acres, 4),
        },
        "sprinkler_specs": {
            "throw_ft": SPRINKLER_THROW_FT,
            "throw_m": round(SPRINKLER_THROW_FT * FT_TO_M, 4),
            "flow_gpm": SPRINKLER_FLOW_GPM,
            "spacing_ft": SPACING_FT,
        },
        "sprinklers_ft": [{"x": s[0], "y": s[1]} for s in sprinklers],
        "sprinklers_m":  [{"x": round(s[0]*FT_TO_M, 4), "y": round(s[1]*FT_TO_M, 4)}
                          for s in sprinklers],
        "grid_resolution_ft": GRID_RESOLUTION_FT,
        "coverage_field": coverage.tolist(),
        "zones_field": zones.tolist(),
        "metrics": {
            "sprinkler_count": len(sprinklers),
            "du": round(du, 4),
            "cu": round(cu, 4),
            "application_rate_min_gpm": float(application.min()),
            "application_rate_max_gpm": float(application.max()),
            "pct_dry":     round(pct_dry, 2),
            "pct_optimal": round(pct_optimal, 2),
            "pct_over":    round(pct_over, 2),
        },
    }

    data_path = ROOT / DATA_JSON_PATH
    with open(data_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"  Data JSON  → {data_path}")

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
