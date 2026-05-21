"""
SprinkleSim Mini — Coverage Engine
Pure-math irrigation coverage module. No Blender dependency.
"""
import numpy as np


def generate_sprinkler_grid(field_w, field_h, spacing):
    """
    Place sprinklers in a square grid inside the field.
    First sprinkler at (spacing/2, spacing/2) so edges have a half-spacing buffer.
    Returns list of (x, y) tuples in feet.
    """
    sprinklers = []
    half = spacing / 2.0
    x = half
    while x <= field_w - half + 0.01:
        y = half
        while y <= field_h - half + 0.01:
            sprinklers.append((x, y))
            y += spacing
        x += spacing
    return sprinklers


def count_coverage_at_point(point, sprinklers, throw_radius):
    """
    Count how many sprinklers reach the given point.
    Returns integer count.
    """
    px, py = point
    r_sq = throw_radius ** 2
    return sum(
        1 for sx, sy in sprinklers
        if (px - sx) ** 2 + (py - sy) ** 2 <= r_sq
    )


def compute_coverage_field(field_w, field_h, sprinklers, throw_radius, resolution):
    """
    Compute a 2D numpy array where each cell holds the sprinkler count
    covering that cell's centre point.
    Returns: ndarray shape (rows, cols), dtype int32.
    """
    cols = int(np.ceil(field_w / resolution))
    rows = int(np.ceil(field_h / resolution))
    coverage = np.zeros((rows, cols), dtype=np.int32)

    # Vectorised distance check for speed
    sx = np.array([s[0] for s in sprinklers])
    sy = np.array([s[1] for s in sprinklers])
    r_sq = throw_radius ** 2

    for j in range(rows):
        py = (j + 0.5) * resolution
        for i in range(cols):
            px = (i + 0.5) * resolution
            coverage[j, i] = int(np.sum((px - sx) ** 2 + (py - sy) ** 2 <= r_sq))

    return coverage


def compute_application_rate_field(coverage_field, per_sprinkler_rate):
    """Multiply coverage count by per-sprinkler flow rate."""
    return coverage_field.astype(np.float64) * per_sprinkler_rate


def compute_distribution_uniformity(application_rate_field):
    """
    DU = lower-quartile mean / overall mean.
    Standard irrigation target: DU ≥ 0.75.
    """
    flat = application_rate_field.flatten()
    flat = flat[flat > 0]
    if len(flat) == 0:
        return 0.0
    sorted_vals = np.sort(flat)
    lower_q = sorted_vals[: max(1, len(sorted_vals) // 4)]
    avg_total = sorted_vals.mean()
    if avg_total == 0:
        return 0.0
    return float(lower_q.mean() / avg_total)


def compute_christiansen_uniformity(application_rate_field):
    """
    CU = 1 − Σ|xi − mean| / (n × mean).
    Returned as a fraction (0–1). Target: CU ≥ 0.85.
    """
    flat = application_rate_field.flatten()
    flat = flat[flat > 0]
    if len(flat) == 0:
        return 0.0
    mean = flat.mean()
    if mean == 0:
        return 0.0
    cu = 1.0 - np.abs(flat - mean).sum() / (len(flat) * mean)
    return float(max(0.0, cu))


def classify_zones(coverage_field):
    """
    Zone codes:
      0 = under-watered  (0–1 sprinklers)
      1 = optimal        (2 sprinklers)
      2 = over-watered   (3+ sprinklers)
    """
    zones = np.zeros_like(coverage_field, dtype=np.int32)
    zones[coverage_field <= 1] = 0
    zones[coverage_field == 2] = 1
    zones[coverage_field >= 3] = 2
    return zones


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from config import FIELD_WIDTH_FT, FIELD_HEIGHT_FT, SPRINKLER_THROW_FT, SPACING_FT

    sprinklers = generate_sprinkler_grid(FIELD_WIDTH_FT, FIELD_HEIGHT_FT, SPACING_FT)
    print(f"Sprinklers: {len(sprinklers)}")
    print(f"First few: {sprinklers[:3]}")
    center = (FIELD_WIDTH_FT / 2, FIELD_HEIGHT_FT / 2)
    cov = count_coverage_at_point(center, sprinklers, SPRINKLER_THROW_FT)
    print(f"Coverage at centre: {cov} sprinklers")
