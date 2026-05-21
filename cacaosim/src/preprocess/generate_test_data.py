"""
Creates synthetic boundary GeoJSON and DEM GeoTIFF for testing the pipeline
before real QGIS data is available.

Run from cacaosim/ project root:
    python src/preprocess/generate_test_data.py
"""

import json
import numpy as np
from pathlib import Path
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from shapely.geometry import mapping, Polygon

CENTER_LAT = 6.2034
CENTER_LON = -2.4912

# ~350m half-side → ~50 ha plot
HALF_LAT = 0.00318
HALF_LON = 0.00320


def generate_boundary():
    # Slightly irregular polygon — real plots are never perfect rectangles
    corners = [
        (CENTER_LON - HALF_LON * 1.02, CENTER_LAT - HALF_LAT * 0.95),
        (CENTER_LON + HALF_LON * 0.97, CENTER_LAT - HALF_LAT * 1.03),
        (CENTER_LON + HALF_LON * 1.04, CENTER_LAT + HALF_LAT * 0.98),
        (CENTER_LON - HALF_LON * 0.96, CENTER_LAT + HALF_LAT * 1.02),
    ]
    polygon = Polygon(corners)
    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Sefwi Demo Plot"},
            "geometry": mapping(polygon),
        }],
    }
    out = Path("data/inputs/boundary.geojson")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  boundary → {out}")
    return out


def generate_dem():
    # Covers a slightly larger area than the boundary
    west  = CENTER_LON - HALF_LON * 2.5
    east  = CENTER_LON + HALF_LON * 2.5
    south = CENTER_LAT - HALF_LAT * 2.5
    north = CENTER_LAT + HALF_LAT * 2.5

    width, height = 256, 256

    rng = np.random.default_rng(42)
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)

    # Gentle NW-to-SE slope (~12 m total), typical for this area
    base = 268.0 + 12.0 * (1.0 - xx) + 5.0 * yy

    # Smooth undulation + minor noise
    noise = (
        2.5 * np.sin(xx * 5 * np.pi) * np.cos(yy * 4 * np.pi) +
        1.2 * np.cos(xx * 9 * np.pi + 0.7) * np.sin(yy * 7 * np.pi) +
        0.6 * rng.standard_normal((height, width))
    )

    elevation = (base + noise).astype(np.float32)
    transform = from_bounds(west, south, east, north, width, height)
    crs = CRS.from_epsg(4326)

    out = Path("data/inputs/srtm_sefwi_wiawso.tif")
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out, "w",
        driver="GTiff",
        height=height, width=width,
        count=1,
        dtype=np.float32,
        crs=crs,
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(elevation, 1)

    print(f"  DEM      → {out}  ({width}×{height} px, ~{elevation.mean():.1f} m)")
    return out


if __name__ == "__main__":
    print("Generating synthetic test data …")
    generate_boundary()
    generate_dem()
    print("Done.")
