"""
ForestWatch — generate_data.py

Produces a realistic synthetic NDVI time-series that replicates the
fishbone deforestation pattern observed in Rondônia, Brazil.

Real Amazon deforestation spreads outward from road corridors — each new
road segment triggers lateral clearing by smallholders within 5–20 km.
The synthetic model captures:
  • Spine highway + branch roads (fishbone geometry)
  • Deforestation buffer that widens ~2 km/yr from each road
  • Stochastic small-farm patches scattered in cleared zones
  • Base forest NDVI variation from layered Perlin-like noise
"""
import json
import numpy as np
from pathlib import Path
from PIL import Image

from config import (
    ROOT, YEARS, GRID_ROWS, GRID_COLS,
    NDVI_FOREST, NDVI_DEGRADED, DATA_DIR, OUTPUT_DIR,
)


# ── Road network geometry ─────────────────────────────────────────────────────

def _build_road_mask(rows, cols, n_branches=5, seed=7):
    """Returns bool mask: True where a road exists.

    5 branch roads gives ~100 px spacing at 512px — realistic for Rondônia
    where the highway grid is ~10 km apart.
    """
    mask = np.zeros((rows, cols), dtype=bool)

    # Road widths scale with grid size
    sw = max(1, int(3 * rows / GRID_ROWS))      # spine half-width
    bw = max(1, int(2 * cols / GRID_COLS))      # branch half-width
    nb = max(2, int(n_branches * cols / GRID_COLS))

    spine_r = int(rows * 0.52)
    mask[spine_r - sw: spine_r + sw, :] = True

    for k in range(nb):
        col = int(cols * (k + 0.5) / nb)
        mask[:, max(0, col - bw): col + bw] = True

    sec_r = int(rows * 0.27)
    sw2 = max(1, int(2 * rows / GRID_ROWS))
    mask[sec_r - sw2: sec_r + sw2, cols // 3:] = True

    return mask


# ── Forest NDVI base layer ─────────────────────────────────────────────────────

def _forest_base(rows, cols, seed=42):
    """Dense-forest NDVI with spatial autocorrelation (pseudo-Perlin)."""
    rng = np.random.RandomState(seed)
    base = np.zeros((rows, cols), dtype=np.float32)
    for scale in [8, 16, 32, 64]:
        noise = rng.uniform(0, 1, (rows // scale + 2, cols // scale + 2)).astype(np.float32)
        from PIL import Image as _Image
        upsampled = np.array(
            _Image.fromarray(noise).resize((cols, rows), _Image.BILINEAR)
        )
        base += upsampled / scale
    base = (base - base.min()) / (base.max() - base.min())
    # Scale to [0.68, 0.90] — realistic undisturbed Amazon dry-season NDVI
    return (base * 0.22 + 0.68).astype(np.float32)


# ── Deforestation spread ──────────────────────────────────────────────────────

def _deforested_mask(dist_from_road, year_idx, rows, cols, rng):
    """
    Returns bool mask of cleared pixels for a given year.
    Road buffer grows ~2 km/yr. All parameters scale with grid size so the
    function behaves consistently at any resolution.
    """
    scale  = min(rows, cols) / GRID_ROWS
    # base=4px, growing 5px/yr → year 5 = 29px at 512px grid
    # With 5 branches at ~100px spacing, max interior dist ~50px
    # → 2018: ~20% cleared, 2023: ~55% cleared (realistic hotspot loss)
    radius = max(1, int((4 + year_idx * 5) * scale))
    mask   = dist_from_road < radius

    # Stochastic farm patches — count and size both scale with area
    n_farms  = 2 + year_idx * 4
    farm_max = max(2, int(14 * scale))
    farm_min = max(1, int(3  * scale))
    for _ in range(n_farms):
        cr = rng.randint(0, rows)
        cc = rng.randint(0, cols)
        r  = rng.randint(farm_min, farm_max + 1)
        mask[max(0, cr - r): min(rows, cr + r),
             max(0, cc - r): min(cols, cc + r)] = True

    return mask


# ── Public API ────────────────────────────────────────────────────────────────

def generate_ndvi_sequence(rows=GRID_ROWS, cols=GRID_COLS, years=YEARS):
    """
    Returns list of (year, ndvi_array) tuples, one per year in YEARS.
    ndvi_array is float32 in [0, 1].
    """
    from scipy.ndimage import distance_transform_edt

    rng = np.random.RandomState(99)
    road_mask   = _build_road_mask(rows, cols)
    forest_base = _forest_base(rows, cols)
    dist_from_road = distance_transform_edt(~road_mask).astype(np.float32)

    sequence = []
    for year_idx, year in enumerate(years):
        ndvi = forest_base.copy()

        cleared = _deforested_mask(dist_from_road, year_idx, rows, cols, rng)

        # Cleared pixels: bare soil / pasture NDVI (0.05–0.30)
        n_cleared = int(cleared.sum())
        ndvi[cleared] = rng.uniform(0.05, 0.28, n_cleared).astype(np.float32)

        # Road pixels: near-zero (asphalt / bare laterite)
        ndvi[road_mask] = rng.uniform(0.02, 0.08, road_mask.sum()).astype(np.float32)

        # Small rivers / water bodies (near-zero or negative in real NDVI → clip to ~0)
        river_row = int(rows * 0.72)
        ndvi[river_row - 2: river_row + 2, :] = rng.uniform(0.0, 0.05, cols)

        sequence.append((year, ndvi.clip(0.0, 1.0)))

    return sequence


def classify_zones(ndvi):
    """
    Returns int8 array:  0=deforested  1=degraded  2=forest
    """
    zones = np.full(ndvi.shape, 2, dtype=np.int8)
    zones[ndvi < NDVI_FOREST]   = 1
    zones[ndvi < NDVI_DEGRADED] = 0
    return zones


def compute_stats(sequence):
    """
    Returns list of dicts with forest coverage stats per year.
    Pixel area assumed ~2.5 km² total → area_px * (10/512)² km² per pixel
    (roughly 20 m/px for a 10 km × 10 km scene at 512 px).
    """
    km2_per_px = (10_000 / GRID_COLS * 10_000 / GRID_ROWS) / 1e6   # m² → km²
    stats = []
    for year, ndvi in sequence:
        zones = classify_zones(ndvi)
        forest_km2    = float((zones == 2).sum() * km2_per_px)
        degraded_km2  = float((zones == 1).sum() * km2_per_px)
        cleared_km2   = float((zones == 0).sum() * km2_per_px)
        total_km2     = forest_km2 + degraded_km2 + cleared_km2
        stats.append({
            "year":            year,
            "forest_km2":      round(forest_km2, 1),
            "degraded_km2":    round(degraded_km2, 1),
            "cleared_km2":     round(cleared_km2, 1),
            "forest_pct":      round(100 * forest_km2 / total_km2, 1),
            "cleared_pct":     round(100 * cleared_km2 / total_km2, 1),
        })
    return stats


def save_ndvi_png(ndvi, path):
    """Save float32 NDVI [0,1] as 8-bit greyscale PNG."""
    arr = (ndvi * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(arr, mode="L").save(path)


def ndvi_to_rgb(ndvi):
    """Map NDVI [0,1] → RGB colour matching forest/degraded/cleared palette."""
    r = np.zeros_like(ndvi)
    g = np.zeros_like(ndvi)
    b = np.zeros_like(ndvi)

    # Cleared: tan → brown  (NDVI < 0.35)
    m = ndvi < NDVI_DEGRADED
    r[m] = 0.72 + ndvi[m] * 0.3
    g[m] = 0.52 + ndvi[m] * 0.2
    b[m] = 0.28

    # Degraded: yellow-green  (0.35 ≤ NDVI < 0.60)
    m = (ndvi >= NDVI_DEGRADED) & (ndvi < NDVI_FOREST)
    t = (ndvi[m] - NDVI_DEGRADED) / (NDVI_FOREST - NDVI_DEGRADED)
    r[m] = 0.55 - t * 0.35
    g[m] = 0.60 + t * 0.15
    b[m] = 0.10

    # Forest: green → deep green  (NDVI ≥ 0.60)
    m = ndvi >= NDVI_FOREST
    t = (ndvi[m] - NDVI_FOREST) / (1.0 - NDVI_FOREST)
    r[m] = 0.06 + (1 - t) * 0.12
    g[m] = 0.42 + t * 0.18
    b[m] = 0.08 + (1 - t) * 0.06

    rgb = np.stack([r, g, b], axis=-1)
    return (rgb.clip(0, 1) * 255).astype(np.uint8)


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating NDVI sequence …")
    seq = generate_ndvi_sequence()

    for year, ndvi in seq:
        save_ndvi_png(ndvi, DATA_DIR / f"ndvi_{year}.png")
        rgb = ndvi_to_rgb(ndvi)
        Image.fromarray(rgb, mode="RGB").save(DATA_DIR / f"ndvi_rgb_{year}.png")
        print(f"  {year}: forest={classify_zones(ndvi)[classify_zones(ndvi)==2].size} px")

    stats = compute_stats(seq)
    (DATA_DIR / "stats.json").write_text(json.dumps(stats, indent=2))
    print("Stats saved →", DATA_DIR / "stats.json")
