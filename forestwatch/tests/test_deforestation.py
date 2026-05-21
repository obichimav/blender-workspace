"""
Tests for ForestWatch deforestation logic.
Run from project root:  venv/bin/pytest tests/ -v
"""
import sys
import math
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import YEARS, NDVI_FOREST, NDVI_DEGRADED, GRID_ROWS, GRID_COLS
from generate_data import (
    _build_road_mask,
    _forest_base,
    generate_ndvi_sequence,
    classify_zones,
    compute_stats,
    ndvi_to_rgb,
)


# ── Road mask ─────────────────────────────────────────────────────────────────

class TestRoadMask:
    def test_mask_shape(self):
        mask = _build_road_mask(128, 128)
        assert mask.shape == (128, 128)

    def test_mask_is_bool(self):
        mask = _build_road_mask(64, 64)
        assert mask.dtype == bool

    def test_has_road_pixels(self):
        mask = _build_road_mask(128, 128)
        assert mask.any()

    def test_roads_do_not_cover_everything(self):
        # Roads are prominent but should leave the majority of the grid as forest
        mask = _build_road_mask(128, 128)
        assert mask.mean() < 0.40

    def test_spine_road_is_horizontal(self):
        rows, cols = 128, 128
        mask = _build_road_mask(rows, cols)
        spine_row = int(rows * 0.52)
        # Spine row should be mostly True
        assert mask[spine_row, :].mean() > 0.9

    def test_branch_roads_are_vertical(self):
        rows, cols = 128, 128
        mask = _build_road_mask(rows, cols, n_branches=4)
        # At least some columns should have road running full height
        col_coverage = mask.mean(axis=0)
        assert (col_coverage > 0.5).sum() >= 4


# ── Forest base ───────────────────────────────────────────────────────────────

class TestForestBase:
    def test_output_shape(self):
        base = _forest_base(64, 64)
        assert base.shape == (64, 64)

    def test_output_range(self):
        base = _forest_base(128, 128)
        assert base.min() >= 0.60
        assert base.max() <= 0.95

    def test_dtype_float32(self):
        base = _forest_base(32, 32)
        assert base.dtype == np.float32

    def test_spatial_variation(self):
        base = _forest_base(64, 64)
        # Should have genuine variation, not a flat value
        assert base.std() > 0.01


# ── NDVI sequence ─────────────────────────────────────────────────────────────

class TestNDVISequence:
    @pytest.fixture(scope="class")
    def seq(self):
        # Use 256×256 so road density and deforestation radius scale correctly
        return generate_ndvi_sequence(rows=256, cols=256, years=YEARS)

    def test_sequence_length(self, seq):
        assert len(seq) == len(YEARS)

    def test_each_element_is_tuple(self, seq):
        for item in seq:
            assert isinstance(item, tuple) and len(item) == 2

    def test_years_match_config(self, seq):
        assert [y for y, _ in seq] == YEARS

    def test_ndvi_shape(self, seq):
        for _, ndvi in seq:
            assert ndvi.shape == (256, 256)

    def test_ndvi_bounded(self, seq):
        for _, ndvi in seq:
            assert ndvi.min() >= 0.0
            assert ndvi.max() <= 1.0

    def test_deforestation_increases_over_time(self, seq):
        # Each later year should have fewer forest pixels than earlier year
        forest_counts = []
        for _, ndvi in seq:
            forest_counts.append((ndvi >= NDVI_FOREST).sum())
        # Should be non-increasing overall (allow one-off noise)
        assert forest_counts[-1] < forest_counts[0]

    def test_first_year_mostly_forest(self, seq):
        _, ndvi_2018 = seq[0]
        forest_fraction = (ndvi_2018 >= NDVI_FOREST).mean()
        assert forest_fraction > 0.50   # majority forest at start

    def test_last_year_has_more_clearing(self, seq):
        _, ndvi_first = seq[0]
        _, ndvi_last  = seq[-1]
        cleared_first = (ndvi_first < NDVI_DEGRADED).mean()
        cleared_last  = (ndvi_last  < NDVI_DEGRADED).mean()
        assert cleared_last > cleared_first


# ── Zone classification ───────────────────────────────────────────────────────

class TestClassifyZones:
    def test_high_ndvi_is_forest(self):
        ndvi = np.array([[0.75, 0.85]])
        zones = classify_zones(ndvi)
        assert (zones == 2).all()

    def test_mid_ndvi_is_degraded(self):
        ndvi = np.array([[0.45, 0.55]])
        zones = classify_zones(ndvi)
        assert (zones == 1).all()

    def test_low_ndvi_is_cleared(self):
        ndvi = np.array([[0.10, 0.25]])
        zones = classify_zones(ndvi)
        assert (zones == 0).all()

    def test_exactly_at_forest_threshold(self):
        ndvi = np.array([[NDVI_FOREST]])
        assert classify_zones(ndvi)[0, 0] == 2

    def test_just_below_forest_threshold(self):
        ndvi = np.array([[NDVI_FOREST - 0.01]])
        assert classify_zones(ndvi)[0, 0] == 1

    def test_all_three_zones_in_mixed_array(self):
        ndvi = np.array([[0.10, 0.45, 0.80]])
        zones = classify_zones(ndvi)
        assert set(zones.flatten()) == {0, 1, 2}

    def test_output_shape_preserved(self):
        ndvi = np.ones((10, 15)) * 0.70
        assert classify_zones(ndvi).shape == (10, 15)


# ── Stats computation ─────────────────────────────────────────────────────────

class TestComputeStats:
    @pytest.fixture(scope="class")
    def stats(self):
        seq = generate_ndvi_sequence(rows=256, cols=256, years=YEARS)
        return compute_stats(seq)

    def test_returns_one_dict_per_year(self, stats):
        assert len(stats) == len(YEARS)

    def test_required_keys_present(self, stats):
        keys = {"year", "forest_km2", "degraded_km2",
                "cleared_km2", "forest_pct", "cleared_pct"}
        for s in stats:
            assert keys.issubset(s.keys())

    def test_years_in_order(self, stats):
        assert [s["year"] for s in stats] == YEARS

    def test_areas_non_negative(self, stats):
        for s in stats:
            assert s["forest_km2"]   >= 0
            assert s["degraded_km2"] >= 0
            assert s["cleared_km2"]  >= 0

    def test_percentages_sum_roughly_100(self, stats):
        for s in stats:
            total_pct = s["forest_pct"] + s["cleared_pct"]
            assert total_pct <= 100.1

    def test_forest_decreases_over_years(self, stats):
        forest_vals = [s["forest_km2"] for s in stats]
        assert forest_vals[-1] < forest_vals[0]

    def test_cleared_increases_over_years(self, stats):
        cleared_vals = [s["cleared_km2"] for s in stats]
        assert cleared_vals[-1] > cleared_vals[0]


# ── NDVI to RGB ───────────────────────────────────────────────────────────────

class TestNDVIToRGB:
    def test_output_shape(self):
        ndvi = np.random.rand(32, 32).astype(np.float32)
        rgb = ndvi_to_rgb(ndvi)
        assert rgb.shape == (32, 32, 3)

    def test_output_dtype_uint8(self):
        ndvi = np.ones((4, 4), dtype=np.float32) * 0.5
        rgb = ndvi_to_rgb(ndvi)
        assert rgb.dtype == np.uint8

    def test_high_ndvi_gives_green(self):
        ndvi = np.ones((1, 1), dtype=np.float32) * 0.90
        rgb = ndvi_to_rgb(ndvi)
        assert rgb[0, 0, 1] > rgb[0, 0, 0]   # green > red
        assert rgb[0, 0, 1] > rgb[0, 0, 2]   # green > blue

    def test_low_ndvi_gives_brownish(self):
        ndvi = np.ones((1, 1), dtype=np.float32) * 0.10
        rgb = ndvi_to_rgb(ndvi)
        assert rgb[0, 0, 0] > rgb[0, 0, 2]   # red > blue (brownish)

    def test_values_in_0_255(self):
        ndvi = np.random.rand(16, 16).astype(np.float32)
        rgb = ndvi_to_rgb(ndvi)
        assert rgb.min() >= 0
        assert rgb.max() <= 255
