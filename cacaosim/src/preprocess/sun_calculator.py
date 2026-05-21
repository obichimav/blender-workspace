"""
Solar position calculator using standard geometric equations.
Accurate to within ~1° for most practical purposes.
"""

import math
from datetime import datetime


def solar_position(
    date_str: str,
    time_str: str,
    lat: float,
    lon: float,
) -> dict:
    """Return sun elevation and azimuth for the given date/time/location.

    Args:
        date_str: "YYYY-MM-DD"
        time_str: "HH:MM"  (local clock time, not UTC)
        lat: latitude in decimal degrees
        lon: longitude in decimal degrees (negative = West)

    Returns dict with elevation_deg, azimuth_deg, and diagnostics.
    """
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    doy = dt.timetuple().tm_yday

    # Solar declination (degrees)
    declination = -23.45 * math.cos(math.radians(360 / 365 * (doy + 10)))

    # Equation of time (minutes)
    b = math.radians(360 / 365 * (doy - 81))
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    # Time correction factor (minutes): distance from the standard time meridian
    lstm = 15 * round(lon / 15)
    tc = 4 * (lon - lstm) + eot

    # Local solar time (hours)
    clock_h = dt.hour + dt.minute / 60.0
    lst = clock_h + tc / 60.0

    # Hour angle (degrees; negative before solar noon)
    hour_angle = 15.0 * (lst - 12.0)

    lat_r = math.radians(lat)
    dec_r = math.radians(declination)
    ha_r = math.radians(hour_angle)

    # Solar altitude (elevation)
    sin_alt = (
        math.sin(lat_r) * math.sin(dec_r)
        + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    )
    sin_alt = max(-1.0, min(1.0, sin_alt))
    elevation = math.degrees(math.asin(sin_alt))

    # Solar azimuth (0° = North, clockwise)
    cos_alt = math.cos(math.asin(sin_alt))
    if cos_alt < 1e-9:
        azimuth = 180.0
    else:
        cos_az = (math.sin(dec_r) - math.sin(lat_r) * sin_alt) / (math.cos(lat_r) * cos_alt)
        cos_az = max(-1.0, min(1.0, cos_az))
        azimuth = math.degrees(math.acos(cos_az))
        if hour_angle > 0:
            azimuth = 360.0 - azimuth

    return {
        "elevation_deg": round(elevation, 2),
        "azimuth_deg": round(azimuth, 2),
        "declination_deg": round(declination, 2),
        "hour_angle_deg": round(hour_angle, 2),
        "local_solar_time": round(lst, 3),
    }
