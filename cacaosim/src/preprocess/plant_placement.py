import math
from typing import Any

import numpy as np
import geopandas as gpd
from rasterio.transform import rowcol
from shapely.geometry import Point


def generate_grid_points(
    boundary_utm: gpd.GeoDataFrame,
    row_spacing: float,
    plant_spacing: float,
    row_orientation_deg: float,
    edge_buffer: float,
    jitter_m: float,
    missing_rate: float,
    seed: int = 42,
) -> list[dict]:
    """Return plant positions as absolute UTM coordinates.

    row_orientation_deg: bearing of the rows themselves (0 = N-S rows).
    """
    rng = np.random.default_rng(seed)
    geom = boundary_utm.geometry.union_all().buffer(-edge_buffer)
    if geom.is_empty:
        return []

    cx, cy = geom.centroid.x, geom.centroid.y
    extent = max(geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]) * 0.75

    theta = math.radians(row_orientation_deg)
    sin_t, cos_t = math.sin(theta), math.cos(theta)

    # Along-row unit vector: (sin θ, cos θ)
    # Across-row unit vector: (cos θ, -sin θ)
    n = int(extent / min(row_spacing, plant_spacing)) + 4

    points = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = cx + j * plant_spacing * sin_t + i * row_spacing * cos_t
            y = cy + j * plant_spacing * cos_t - i * row_spacing * sin_t

            if not geom.contains(Point(x, y)):
                continue
            if rng.random() < missing_rate:
                continue

            jx = rng.uniform(-jitter_m, jitter_m)
            jy = rng.uniform(-jitter_m, jitter_m)
            points.append({"x_utm": x + jx, "y_utm": y + jy, "row": i, "col": j})

    return points


def sample_elevation(
    points: list[dict],
    elevation: np.ndarray,
    transform_utm,
    origin_x: float,
    origin_y: float,
    fallback_elev: float | None = None,
) -> list[dict]:
    """Add local (x, y, z) to each point dict; origin at plot centroid."""
    h, w = elevation.shape
    _fallback = fallback_elev if fallback_elev is not None else float(np.nanmean(elevation))
    result = []
    for pt in points:
        try:
            rows, cols = rowcol(transform_utm, pt["x_utm"], pt["y_utm"])
            r, c = int(rows), int(cols)
            if 0 <= r < h and 0 <= c < w:
                elev = float(elevation[r, c])
                if np.isnan(elev):
                    elev = _fallback
            else:
                elev = _fallback
        except Exception:
            elev = _fallback

        result.append({
            **pt,
            "x": pt["x_utm"] - origin_x,
            "y": pt["y_utm"] - origin_y,
            "z": elev,
            "rotation_z": 0.0,
            "scale": 1.0,
        })
    return result


def assign_shade_species(
    points: list[dict],
    species_mix: list[dict[str, Any]],
    seed: int = 0,
) -> list[dict]:
    """Randomly assign a species to each shade-tree point by weight."""
    rng = np.random.default_rng(seed)
    names = [s["species"] for s in species_mix]
    weights = np.array([s["weight"] for s in species_mix], dtype=float)
    weights /= weights.sum()

    for pt in points:
        pt["species"] = rng.choice(names, p=weights)
    return points
