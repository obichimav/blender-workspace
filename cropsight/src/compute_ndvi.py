"""
CropSight — NDVI processing and texture generation.
Loads raw NDVI array, classifies health zones, generates:
  - output/zone_texture.png    (RGB colour map for Blender UV)
  - data/dem_heightmap.png     (normalised greyscale for displacement)
  - output/data.json           (metrics + arrays for build_scene.py)
"""
import sys
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import (
    NDVI_STRESSED, NDVI_HEALTHY,
    DATA_DIR, OUTPUT_DIR,
    ZONE_TEXTURE_PATH, DATA_JSON_PATH, DEM_PNG,
    SCENE_WIDTH_M, SCENE_HEIGHT_M, CROP_SPACING_M,
)


# Zone colours — matches SprinkleSim palette for portfolio consistency
ZONE_COLORS = {
    0: "#c0392b",   # stressed  → deep red
    1: "#f39c12",   # moderate  → amber
    2: "#27ae60",   # healthy   → rich green
}

ZONE_LABELS = {0: "Stressed / Bare", 1: "Moderate", 2: "Healthy"}


def classify_ndvi(ndvi: np.ndarray) -> np.ndarray:
    zones = np.zeros_like(ndvi, dtype=np.int32)
    zones[ndvi >= NDVI_STRESSED] = 1
    zones[ndvi >= NDVI_HEALTHY]  = 2
    return zones


def save_zone_texture(zones: np.ndarray, path: Path):
    cmap = ListedColormap([ZONE_COLORS[0], ZONE_COLORS[1], ZONE_COLORS[2]])
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
    ax.imshow(zones, origin="lower", cmap=cmap, vmin=0, vmax=2,
              interpolation="bicubic", aspect="auto")
    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()
    print(f"  Zone texture → {path}")


def generate_dem(rows: int, cols: int, seed: int = 7) -> np.ndarray:
    """
    Procedural DEM for gently rolling Kansas farmland.
    Returns a (rows, cols) float32 array, values in [0, 1].
    Real elevation variation ~10 m over 2 km = very subtle.
    """
    rng = np.random.default_rng(seed)
    # Large gentle rolls
    coarse = np.kron(
        rng.uniform(0.3, 0.7, size=(rows // 30 + 2, cols // 30 + 2)),
        np.ones((30, 30)),
    )[:rows, :cols]
    # Medium undulation
    mid = np.kron(
        rng.uniform(-0.1, 0.1, size=(rows // 8 + 2, cols // 8 + 2)),
        np.ones((8, 8)),
    )[:rows, :cols]
    dem = np.clip(coarse + mid, 0.0, 1.0).astype(np.float32)

    # Smooth with a simple box filter
    from scipy.ndimage import uniform_filter
    dem = uniform_filter(dem, size=15).astype(np.float32)
    dem = (dem - dem.min()) / (dem.max() - dem.min() + 1e-8)
    return dem


def save_dem_heightmap(dem: np.ndarray, path: Path):
    img_arr = (dem * 255).astype(np.uint8)
    Image.fromarray(img_arr, mode="L").save(path)
    print(f"  DEM heightmap → {path}")


def compute_metrics(ndvi: np.ndarray, zones: np.ndarray):
    total = zones.size
    pct = {z: float((zones == z).sum() / total * 100) for z in (0, 1, 2)}
    return {
        "ndvi_min":       round(float(ndvi.min()), 4),
        "ndvi_max":       round(float(ndvi.max()), 4),
        "ndvi_mean":      round(float(ndvi.mean()), 4),
        "ndvi_std":       round(float(ndvi.std()), 4),
        "pct_stressed":   round(pct[0], 2),
        "pct_moderate":   round(pct[1], 2),
        "pct_healthy":    round(pct[2], 2),
    }


def process_and_save():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load raw NDVI
    ndvi_path = DATA_DIR / "ndvi_raw.npy"
    ndvi = np.load(ndvi_path).astype(np.float32)
    rows, cols = ndvi.shape
    print(f"  NDVI array: {rows} × {cols}  ({rows*10}m × {cols*10}m)")

    # Load fetch metadata
    with open(DATA_DIR / "fetch_meta.json") as f:
        fetch_meta = json.load(f)

    # Classify zones
    zones = classify_ndvi(ndvi)
    save_zone_texture(zones, ZONE_TEXTURE_PATH)

    # DEM
    dem = generate_dem(rows, cols)
    save_dem_heightmap(dem, DEM_PNG)

    # Metrics
    metrics = compute_metrics(ndvi, zones)
    print(f"  NDVI mean={metrics['ndvi_mean']:.3f}  "
          f"stressed={metrics['pct_stressed']:.1f}%  "
          f"moderate={metrics['pct_moderate']:.1f}%  "
          f"healthy={metrics['pct_healthy']:.1f}%")

    # Crop positions: upsample zones to CROP_SPACING_M density
    # (NDVI pixel_size_m may be coarser than desired crop spacing)
    from scipy.ndimage import zoom as ndimage_zoom
    zoom_factor = fetch_meta["pixel_size_m"] / CROP_SPACING_M
    zones_dense = ndimage_zoom(zones, zoom_factor, order=0).astype(np.int32)
    ndvi_dense  = ndimage_zoom(ndvi,  zoom_factor, order=1).astype(np.float32)
    dr, dc = zones_dense.shape

    crop_positions = []
    for r in range(dr):
        for c in range(dc):
            x_m = c * CROP_SPACING_M
            y_m = r * CROP_SPACING_M
            if x_m >= SCENE_WIDTH_M or y_m >= SCENE_HEIGHT_M:
                continue
            crop_positions.append({
                "x":    round(x_m, 1),
                "y":    round(y_m, 1),
                "zone": int(zones_dense[r, c]),
                "ndvi": round(float(ndvi_dense[r, c]), 3),
            })

    # Write data.json
    output = {
        "schema_version": "0.1.0",
        "source": fetch_meta["source"],
        "region": {
            "name": "Dodge City, KS — wheat belt",
            "bbox_wgs84": fetch_meta["bbox_wgs84"],
            "date_range": fetch_meta["date_range"],
        },
        "scene": {
            "width_m":  SCENE_WIDTH_M,
            "height_m": SCENE_HEIGHT_M,
            "rows":     rows,
            "cols":     cols,
            "pixel_size_m": fetch_meta["pixel_size_m"],
        },
        "thresholds": {
            "stressed_below":  NDVI_STRESSED,
            "healthy_above":   NDVI_HEALTHY,
        },
        "metrics": metrics,
        "zones_field":    zones.tolist(),
        "dem_field":      dem.tolist(),
        "crop_positions": crop_positions,
    }
    with open(DATA_JSON_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Data JSON  → {DATA_JSON_PATH}")

    return output


if __name__ == "__main__":
    process_and_save()
