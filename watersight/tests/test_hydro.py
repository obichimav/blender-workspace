"""
Tests for WaterSight hydrology logic.
Run from project root:  venv/bin/pytest tests/ -v
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from compute_zones import classify_zones, compute_water_area
from fetch_terrain import _lon_to_tile_x, _lat_to_tile_y, _decode_terrarium


# ── Tile coordinate helpers ───────────────────────────────────────────────────

class TestTileCoordinates:
    def test_prime_meridian_lon_zero(self):
        # lon=0 should land at midpoint of tile grid
        x = _lon_to_tile_x(0, zoom=1)
        assert x == 1

    def test_antimeridian_lon_180(self):
        x = _lon_to_tile_x(180, zoom=1)
        assert x == 2   # wraps to right edge

    def test_lon_west_is_smaller_tile(self):
        x_west = _lon_to_tile_x(-111.5, zoom=11)
        x_east = _lon_to_tile_x(-110.7, zoom=11)
        assert x_west < x_east

    def test_lat_north_is_smaller_y(self):
        # In tile systems, y=0 is top (north)
        y_north = _lat_to_tile_y(37.6, zoom=11)
        y_south = _lat_to_tile_y(37.0, zoom=11)
        assert y_north < y_south

    def test_tile_x_within_zoom_range(self):
        x = _lon_to_tile_x(-111.0, zoom=11)
        assert 0 <= x < 2**11

    def test_tile_y_within_zoom_range(self):
        y = _lat_to_tile_y(37.3, zoom=11)
        assert 0 <= y < 2**11


# ── Terrarium elevation decoding ─────────────────────────────────────────────

class TestDecodeTerarium:
    def test_zero_rgb_gives_negative_32768(self):
        from PIL import Image
        img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8), mode="RGB")
        result = _decode_terrarium(img)
        assert result[0, 0] == pytest.approx(-32768.0)

    def test_known_value(self):
        # R=128, G=0, B=0 → 128*256 + 0 + 0 - 32768 = 32768 - 32768 = 0 m
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        arr[0, 0] = [128, 0, 0]
        from PIL import Image
        img = Image.fromarray(arr, mode="RGB")
        result = _decode_terrarium(img)
        assert result[0, 0] == pytest.approx(0.0)

    def test_output_shape_matches_input(self):
        from PIL import Image
        arr = np.zeros((8, 8, 3), dtype=np.uint8)
        arr[:, :] = [128, 50, 0]
        img = Image.fromarray(arr, mode="RGB")
        result = _decode_terrarium(img)
        assert result.shape == (8, 8)


# ── Zone classification ───────────────────────────────────────────────────────

class TestClassifyZones:
    def test_below_after_level_is_zone_0(self):
        elev = np.array([[1000.0, 1050.0]])
        zones = classify_zones(elev)
        assert (zones == 0).all()

    def test_at_after_level_is_zone_0(self):
        # Exactly at WATER_LEVEL_AFTER_M (1074 m) → submerged
        from config import WATER_LEVEL_AFTER_M
        elev = np.array([[WATER_LEVEL_AFTER_M]])
        assert classify_zones(elev)[0, 0] == 0

    def test_between_levels_is_zone_1(self):
        # 1074 < elev <= 1128 → bathtub ring
        elev = np.array([[1100.0, 1120.0]])
        zones = classify_zones(elev)
        assert (zones == 1).all()

    def test_at_before_level_is_zone_1(self):
        # Exactly at WATER_LEVEL_BEFORE_M (1128 m) → in the ring
        from config import WATER_LEVEL_BEFORE_M
        elev = np.array([[WATER_LEVEL_BEFORE_M]])
        assert classify_zones(elev)[0, 0] == 1

    def test_above_before_level_is_zone_2(self):
        elev = np.array([[1200.0, 1500.0]])
        zones = classify_zones(elev)
        assert (zones == 2).all()

    def test_output_shape_preserved(self):
        elev = np.ones((10, 15)) * 1100.0
        assert classify_zones(elev).shape == (10, 15)

    def test_all_three_zones_present(self):
        elev = np.array([[1000.0, 1100.0, 1200.0]])
        zones = classify_zones(elev)
        assert set(zones.flatten()) == {0, 1, 2}


# ── Water area computation ────────────────────────────────────────────────────

class TestComputeWaterArea:
    MOCK_META = {
        "lat_n": 37.6, "lat_s": 37.0,
        "lon_w": -111.5, "lon_e": -110.7,
        "rows_px": 10, "cols_px": 10,
    }

    def test_all_submerged_maximises_before_area(self):
        zones = np.zeros((10, 10), dtype=np.int32)
        stats = compute_water_area(zones, self.MOCK_META)
        assert stats["water_area_before_km2"] >= stats["water_area_after_km2"]

    def test_no_water_gives_zero_areas(self):
        zones = np.full((10, 10), 2, dtype=np.int32)
        stats = compute_water_area(zones, self.MOCK_META)
        assert stats["water_area_before_km2"] == 0.0
        assert stats["water_area_after_km2"]  == 0.0

    def test_drop_m_is_correct(self):
        zones = np.zeros((5, 5), dtype=np.int32)
        stats = compute_water_area(zones, self.MOCK_META)
        from config import WATER_LEVEL_BEFORE_M, WATER_LEVEL_AFTER_M
        assert stats["water_drop_m"] == pytest.approx(
            WATER_LEVEL_BEFORE_M - WATER_LEVEL_AFTER_M
        )

    def test_returns_all_required_keys(self):
        zones = np.zeros((5, 5), dtype=np.int32)
        stats = compute_water_area(zones, self.MOCK_META)
        for key in ("water_area_before_km2", "water_area_after_km2",
                    "exposed_ring_km2", "pct_water_lost", "water_drop_m"):
            assert key in stats
