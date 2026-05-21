"""
WaterSight — terrain data acquisition.
Downloads real elevation + satellite imagery tiles for Lake Powell region.

Sources (both free, no authentication required):
  Elevation : AWS Terrain Tiles (Terrarium RGB encoding)
              https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
  Satellite : ESRI World Imagery
              https://server.arcgisonline.com/ArcGIS/rest/services/
              World_Imagery/MapServer/tile/{z}/{y}/{x}
"""
import sys
import json
import math
import time
from pathlib import Path
from io import BytesIO

import numpy as np
import requests
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import BBOX_WGS84, TILE_ZOOM, DATA_DIR, ELEVATION_NPY, ELEVATION_META, HEIGHTMAP_PNG, SATELLITE_PNG

TERRAIN_URL  = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SATELLITE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
TILE_PX = 256


def _lon_to_tile_x(lon, zoom):
    return int((lon + 180) / 360 * (2 ** zoom))


def _lat_to_tile_y(lat, zoom):
    lat_r = math.radians(lat)
    return int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * (2 ** zoom))


def _tile_bounds(bbox, zoom):
    lon_w, lat_s, lon_e, lat_n = bbox
    x_min = _lon_to_tile_x(lon_w, zoom)
    x_max = _lon_to_tile_x(lon_e, zoom)
    y_min = _lat_to_tile_y(lat_n, zoom)   # note: y_min for northern lat
    y_max = _lat_to_tile_y(lat_s, zoom)
    return x_min, x_max, y_min, y_max


def _tile_to_lon(x, zoom):
    return x / (2 ** zoom) * 360 - 180


def _tile_to_lat(y, zoom):
    n = math.pi - 2 * math.pi * y / (2 ** zoom)
    return math.degrees(math.atan(math.sinh(n)))


def _download_tile(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 ** attempt)


def _decode_terrarium(img: Image.Image) -> np.ndarray:
    """Decode Terrarium RGB-encoded elevation to metres."""
    arr = np.array(img).astype(np.float32)
    return arr[:, :, 0] * 256 + arr[:, :, 1] + arr[:, :, 2] / 256 - 32768


def fetch_and_stitch(bbox, zoom):
    x_min, x_max, y_min, y_max = _tile_bounds(bbox, zoom)
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    total = rows * cols
    print(f"  Tile grid: {cols}×{rows} = {total} tiles at zoom {zoom}")

    elev_canvas = np.zeros((rows * TILE_PX, cols * TILE_PX), dtype=np.float32)
    sat_canvas  = np.zeros((rows * TILE_PX, cols * TILE_PX, 3), dtype=np.uint8)

    for i, ty in enumerate(range(y_min, y_max + 1)):
        for j, tx in enumerate(range(x_min, x_max + 1)):
            n = i * cols + j + 1
            print(f"  [{n:02d}/{total}] tile ({tx},{ty}) …", end="\r")

            # Elevation
            elev_url = TERRAIN_URL.format(z=zoom, x=tx, y=ty)
            elev_img = _download_tile(elev_url)
            elev_tile = _decode_terrarium(elev_img)

            # Satellite
            sat_url = SATELLITE_URL.format(z=zoom, y=ty, x=tx)
            sat_img = _download_tile(sat_url)
            sat_tile = np.array(sat_img)

            r0, r1 = i * TILE_PX, (i + 1) * TILE_PX
            c0, c1 = j * TILE_PX, (j + 1) * TILE_PX
            elev_canvas[r0:r1, c0:c1] = elev_tile
            sat_canvas[r0:r1, c0:c1]  = sat_tile

            time.sleep(0.05)   # polite rate limit

    print(f"\n  Stitched: {elev_canvas.shape[1]}×{elev_canvas.shape[0]} px")

    # Geographic extent of the stitched raster
    lon_w = _tile_to_lon(x_min, zoom)
    lon_e = _tile_to_lon(x_max + 1, zoom)
    lat_n = _tile_to_lat(y_min, zoom)
    lat_s = _tile_to_lat(y_max + 1, zoom)

    meta = {
        "zoom":     zoom,
        "x_min":    x_min,  "x_max": x_max,
        "y_min":    y_min,  "y_max": y_max,
        "cols_px":  int(elev_canvas.shape[1]),
        "rows_px":  int(elev_canvas.shape[0]),
        "lon_w":    lon_w,  "lon_e": lon_e,
        "lat_s":    lat_s,  "lat_n": lat_n,
        "elev_min": float(elev_canvas.min()),
        "elev_max": float(elev_canvas.max()),
        "elev_mean": float(elev_canvas.mean()),
    }
    print(f"  Elevation: {meta['elev_min']:.0f} – {meta['elev_max']:.0f} m  "
          f"(mean {meta['elev_mean']:.0f} m)")
    return elev_canvas, sat_canvas, meta


def save_outputs(elev, sat, meta):
    DATA_DIR.mkdir(exist_ok=True)

    # Raw elevation array
    np.save(ELEVATION_NPY, elev)

    # Metadata
    with open(ELEVATION_META, "w") as f:
        json.dump(meta, f, indent=2)

    # Normalised heightmap PNG (0–255) for Blender displacement
    norm = (elev - elev.min()) / (elev.max() - elev.min() + 1e-8)
    heightmap = (norm * 255).astype(np.uint8)
    Image.fromarray(heightmap, mode="L").save(HEIGHTMAP_PNG)
    print(f"  Heightmap → {HEIGHTMAP_PNG}")

    # Satellite texture PNG
    Image.fromarray(sat).save(SATELLITE_PNG)
    print(f"  Satellite → {SATELLITE_PNG}")


def fetch_all():
    print("  Fetching terrain + satellite tiles …")
    elev, sat, meta = fetch_and_stitch(BBOX_WGS84, TILE_ZOOM)
    save_outputs(elev, sat, meta)
    return elev, sat, meta


if __name__ == "__main__":
    fetch_all()
