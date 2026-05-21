"""
Visualise the coverage field with matplotlib — run this BEFORE Blender
to verify the math is correct.

Usage (from project root):
    python src/sanity_check.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from config import (
    FIELD_WIDTH_FT, FIELD_HEIGHT_FT,
    SPRINKLER_THROW_FT, SPACING_FT, SPRINKLER_FLOW_GPM,
    GRID_RESOLUTION_FT,
)
from coverage_engine import (
    generate_sprinkler_grid,
    compute_coverage_field,
    classify_zones,
)

ROOT = HERE.parent


def main():
    sprinklers = generate_sprinkler_grid(FIELD_WIDTH_FT, FIELD_HEIGHT_FT, SPACING_FT)
    coverage = compute_coverage_field(
        FIELD_WIDTH_FT, FIELD_HEIGHT_FT,
        sprinklers, SPRINKLER_THROW_FT, GRID_RESOLUTION_FT,
    )
    zones = classify_zones(coverage)

    print(f"Coverage shape : {coverage.shape}")
    print(f"Coverage range : {coverage.min()} – {coverage.max()}")
    print(f"Mean coverage  : {coverage.mean():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Left: raw coverage count
    im0 = axes[0].imshow(
        coverage, origin='lower',
        extent=[0, FIELD_WIDTH_FT, 0, FIELD_HEIGHT_FT],
        cmap='viridis', aspect='equal',
    )
    sx = [s[0] for s in sprinklers]
    sy = [s[1] for s in sprinklers]
    axes[0].scatter(sx, sy, color='red', s=25, marker='+', label='Sprinklers')
    plt.colorbar(im0, ax=axes[0], label='Sprinkler count')
    axes[0].set_title('Coverage count')
    axes[0].set_xlabel('X (ft)'); axes[0].set_ylabel('Y (ft)')
    axes[0].legend()

    # Right: zone classification
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    cmap = ListedColormap(['#d64545', '#4caf50', '#ffc107'])
    axes[1].imshow(
        zones, origin='lower',
        extent=[0, FIELD_WIDTH_FT, 0, FIELD_HEIGHT_FT],
        cmap=cmap, vmin=0, vmax=2, aspect='equal',
    )
    axes[1].scatter(sx, sy, color='black', s=25, marker='+', label='Sprinklers')
    legend_handles = [
        Patch(color='#d64545', label='Under-watered (0–1)'),
        Patch(color='#4caf50', label='Optimal (2)'),
        Patch(color='#ffc107', label='Over-watered (3+)'),
    ]
    axes[1].legend(handles=legend_handles, loc='upper right', fontsize=8)
    axes[1].set_title('Zone classification')
    axes[1].set_xlabel('X (ft)'); axes[1].set_ylabel('Y (ft)')

    plt.suptitle(
        f'SprinkleSim Mini — Sanity Check  |  '
        f'{len(sprinklers)} sprinklers  |  '
        f'throw={SPRINKLER_THROW_FT} ft  spacing={SPACING_FT:.0f} ft',
        fontsize=12,
    )
    plt.tight_layout()

    out = ROOT / "output" / "sanity_check.png"
    out.parent.mkdir(exist_ok=True)
    plt.savefig(out, dpi=120, bbox_inches='tight')
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
