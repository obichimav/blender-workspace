import numpy as np


def compute_slope_aspect(
    elevation: np.ndarray, res_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (slope_deg, aspect_deg) arrays from an elevation raster."""
    # np.gradient returns (dy_array, dx_array) for a 2-D input
    dy, dx = np.gradient(elevation, res_m, res_m)

    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    # Aspect: 0° = North, clockwise
    aspect = np.degrees(np.arctan2(-dx, dy)) % 360

    return slope, aspect


def dominant_slope_direction(
    slope: np.ndarray, aspect: np.ndarray
) -> float:
    """Circular mean of aspect values, weighted by slope magnitude."""
    w = slope.flatten()
    a = aspect.flatten()

    valid = ~(np.isnan(w) | np.isnan(a))
    w, a = w[valid], a[valid]

    rad = np.radians(a)
    x = np.average(np.cos(rad), weights=w)
    y = np.average(np.sin(rad), weights=w)

    return float(np.degrees(np.arctan2(y, x)) % 360)


def row_orientation_from_aspect(dominant_aspect_deg: float) -> float:
    """Rows run perpendicular to the downhill direction (along contours)."""
    return (dominant_aspect_deg + 90) % 180
