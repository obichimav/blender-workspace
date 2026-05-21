"""
CropSight — data acquisition.
Downloads Sentinel-2 L2A B04 (Red) + B08 (NIR) bands from Microsoft
Planetary Computer (free, no API key required for public data).
Falls back to synthetic NDVI if no scene is found or network is unavailable.
"""
import sys
import json
import math
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import (
    BBOX_WGS84, DATE_RANGE, CLOUD_MAX,
    DATA_DIR, SCENE_WIDTH_M, SCENE_HEIGHT_M,
)

# Suppress noisy GDAL/rasterio warnings
warnings.filterwarnings("ignore", category=UserWarning)


def _fetch_sentinel2_bands():
    """
    Search Planetary Computer for a low-cloud Sentinel-2 L2A scene and
    download clipped B04 + B08 arrays.
    Returns (red_arr, nir_arr, meta_dict) or raises on failure.
    """
    import pystac_client
    import planetary_computer
    import rasterio
    from rasterio.mask import mask as rio_mask
    from shapely.geometry import box, mapping

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX_WGS84,
        datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": CLOUD_MAX}},
        sortby="eo:cloud_cover",
    )
    items = list(search.items())
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found for the given bbox/date/cloud filter.")

    item = items[0]
    aoi_geom = mapping(box(*BBOX_WGS84))
    print(f"  Scene: {item.id}  cloud={item.properties['eo:cloud_cover']:.1f}%")

    bands = {}
    for band_key in ("B04", "B08"):
        href = item.assets[band_key].href
        with rasterio.open(href) as src:
            # Reproject AOI to the scene CRS before masking
            from rasterio.warp import transform_geom
            aoi_native = transform_geom("EPSG:4326", src.crs.to_epsg(), aoi_geom)
            arr, transform = rio_mask(src, [aoi_native], crop=True)
            bands[band_key] = {
                "data":      arr[0].astype(np.float32),
                "transform": transform,
                "crs":       str(src.crs),
                "nodata":    src.nodata,
            }
        print(f"  Downloaded {band_key}: {bands[band_key]['data'].shape}")

    return bands["B04"], bands["B08"]


def _make_synthetic_ndvi(rows, cols, seed=42):
    """
    Generate a realistic synthetic NDVI field using layered noise.
    Mimics an agricultural mosaic: field parcels with varying crop health.
    Used when real satellite data is unavailable.
    """
    rng = np.random.default_rng(seed)

    # Base layer: large-scale field parcels
    parcel_size = max(rows, cols) // 6
    base = np.kron(
        rng.uniform(0.1, 0.9, size=(rows // parcel_size + 1, cols // parcel_size + 1)),
        np.ones((parcel_size, parcel_size)),
    )[:rows, :cols]

    # Medium-scale variation within parcels
    mid = np.kron(
        rng.uniform(-0.15, 0.15, size=(rows // 20 + 1, cols // 20 + 1)),
        np.ones((20, 20)),
    )[:rows, :cols]

    # Fine-scale noise (soil variation, individual plant variation)
    fine = rng.uniform(-0.05, 0.05, size=(rows, cols))

    ndvi = np.clip(base + mid + fine, 0.0, 1.0).astype(np.float32)

    # Carve out a dry creek/road pattern (low NDVI strip)
    ndvi[rows // 3 : rows // 3 + 4, :] *= 0.3
    ndvi[:, cols // 2 : cols // 2 + 3] *= 0.3

    return ndvi


def fetch_and_save():
    DATA_DIR.mkdir(exist_ok=True)
    rows = int(SCENE_HEIGHT_M / 10)   # 10 m/pixel target
    cols = int(SCENE_WIDTH_M  / 10)

    meta = {
        "source": None,
        "rows": rows,
        "cols": cols,
        "bbox_wgs84": list(BBOX_WGS84),
        "date_range": DATE_RANGE,
        "pixel_size_m": 10,
    }

    ndvi_path = DATA_DIR / "ndvi_raw.npy"

    try:
        print("  Connecting to Planetary Computer …")
        red_band, nir_band = _fetch_sentinel2_bands()

        red = red_band["data"].astype(np.float32)
        nir = nir_band["data"].astype(np.float32)

        # Resize to target resolution if needed
        if red.shape != (rows, cols):
            from skimage.transform import resize
            red = resize(red, (rows, cols), anti_aliasing=True).astype(np.float32)
            nir = resize(nir, (rows, cols), anti_aliasing=True).astype(np.float32)

        # Sentinel-2 L2A values are surface reflectance scaled by 10000
        red = red / 10000.0
        nir = nir / 10000.0

        ndvi = (nir - red) / (nir + red + 1e-8)
        ndvi = np.clip(ndvi, -1.0, 1.0).astype(np.float32)

        meta["source"] = "Sentinel-2 L2A via Planetary Computer"
        print(f"  Real NDVI: min={ndvi.min():.3f}  max={ndvi.max():.3f}  mean={ndvi.mean():.3f}")

    except Exception as exc:
        print(f"  Planetary Computer unavailable ({exc})")
        print("  Falling back to synthetic NDVI …")
        ndvi = _make_synthetic_ndvi(rows, cols)
        meta["source"] = "synthetic (Planetary Computer unavailable)"
        print(f"  Synthetic NDVI: min={ndvi.min():.3f}  max={ndvi.max():.3f}  mean={ndvi.mean():.3f}")

    np.save(ndvi_path, ndvi)
    with open(DATA_DIR / "fetch_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Saved raw NDVI → {ndvi_path}")
    return ndvi, meta


if __name__ == "__main__":
    fetch_and_save()
