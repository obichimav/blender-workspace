"""
Tests for CropSight NDVI processing logic.
Run from project root:  venv/bin/pytest tests/ -v
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from compute_ndvi import classify_ndvi, compute_metrics, generate_dem


# ── classify_ndvi ─────────────────────────────────────────────────────────────

class TestClassifyNdvi:
    def test_below_stressed_threshold(self):
        ndvi = np.array([[0.0, 0.10, 0.29]])
        zones = classify_ndvi(ndvi)
        assert (zones == 0).all()

    def test_at_stressed_threshold_is_moderate(self):
        # NDVI_STRESSED = 0.30 → >= 0.30 is moderate
        ndvi = np.array([[0.30]])
        assert classify_ndvi(ndvi)[0, 0] == 1

    def test_moderate_band(self):
        ndvi = np.array([[0.35, 0.50, 0.59]])
        zones = classify_ndvi(ndvi)
        assert (zones == 1).all()

    def test_at_healthy_threshold_is_healthy(self):
        ndvi = np.array([[0.60]])
        assert classify_ndvi(ndvi)[0, 0] == 2

    def test_healthy_band(self):
        ndvi = np.array([[0.65, 0.80, 1.00]])
        zones = classify_ndvi(ndvi)
        assert (zones == 2).all()

    def test_all_three_zones_present(self):
        ndvi = np.array([[0.10, 0.45, 0.75]])
        zones = classify_ndvi(ndvi)
        assert set(zones.flatten()) == {0, 1, 2}

    def test_output_shape_matches_input(self):
        ndvi = np.random.default_rng(0).uniform(0, 1, (15, 20)).astype(np.float32)
        zones = classify_ndvi(ndvi)
        assert zones.shape == ndvi.shape

    def test_output_dtype_is_int32(self):
        ndvi = np.array([[0.2, 0.5, 0.8]], dtype=np.float32)
        zones = classify_ndvi(ndvi)
        assert zones.dtype == np.int32


# ── compute_metrics ───────────────────────────────────────────────────────────

class TestComputeMetrics:
    def test_uniform_healthy_field(self):
        ndvi  = np.full((10, 10), 0.75, dtype=np.float32)
        zones = classify_ndvi(ndvi)
        m = compute_metrics(ndvi, zones)
        assert m["pct_healthy"]  == pytest.approx(100.0)
        assert m["pct_moderate"] == pytest.approx(0.0)
        assert m["pct_stressed"] == pytest.approx(0.0)

    def test_uniform_stressed_field(self):
        ndvi  = np.full((10, 10), 0.10, dtype=np.float32)
        zones = classify_ndvi(ndvi)
        m = compute_metrics(ndvi, zones)
        assert m["pct_stressed"] == pytest.approx(100.0)
        assert m["pct_healthy"]  == pytest.approx(0.0)

    def test_percentages_sum_to_100(self):
        rng   = np.random.default_rng(1)
        ndvi  = rng.uniform(0, 1, (20, 20)).astype(np.float32)
        zones = classify_ndvi(ndvi)
        m     = compute_metrics(ndvi, zones)
        total = m["pct_stressed"] + m["pct_moderate"] + m["pct_healthy"]
        assert total == pytest.approx(100.0, abs=0.01)

    def test_ndvi_stats_match_input(self):
        ndvi  = np.array([[0.2, 0.5], [0.7, 0.9]], dtype=np.float32)
        zones = classify_ndvi(ndvi)
        m     = compute_metrics(ndvi, zones)
        assert m["ndvi_min"]  == pytest.approx(float(ndvi.min()),  abs=1e-4)
        assert m["ndvi_max"]  == pytest.approx(float(ndvi.max()),  abs=1e-4)
        assert m["ndvi_mean"] == pytest.approx(float(ndvi.mean()), abs=1e-4)

    def test_returns_all_required_keys(self):
        ndvi  = np.ones((5, 5), dtype=np.float32) * 0.5
        zones = classify_ndvi(ndvi)
        m     = compute_metrics(ndvi, zones)
        for key in ("ndvi_min", "ndvi_max", "ndvi_mean", "ndvi_std",
                    "pct_stressed", "pct_moderate", "pct_healthy"):
            assert key in m


# ── generate_dem ──────────────────────────────────────────────────────────────

class TestGenerateDem:
    def test_output_shape(self):
        dem = generate_dem(50, 80)
        assert dem.shape == (50, 80)

    def test_values_in_0_1(self):
        dem = generate_dem(40, 40)
        assert dem.min() >= 0.0
        assert dem.max() <= 1.0

    def test_dtype_float32(self):
        dem = generate_dem(20, 20)
        assert dem.dtype == np.float32

    def test_not_flat(self):
        # DEM should have meaningful variation, not constant
        dem = generate_dem(50, 50)
        assert dem.std() > 0.01

    def test_deterministic_with_same_seed(self):
        dem_a = generate_dem(30, 30, seed=99)
        dem_b = generate_dem(30, 30, seed=99)
        np.testing.assert_array_equal(dem_a, dem_b)

    def test_different_seeds_differ(self):
        dem_a = generate_dem(30, 30, seed=1)
        dem_b = generate_dem(30, 30, seed=2)
        assert not np.array_equal(dem_a, dem_b)
