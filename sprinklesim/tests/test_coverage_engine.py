"""
Tests for SprinkleSim coverage_engine.py
Run from project root:  venv/bin/pytest tests/ -v
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from coverage_engine import (
    generate_sprinkler_grid,
    count_coverage_at_point,
    compute_coverage_field,
    compute_application_rate_field,
    compute_distribution_uniformity,
    compute_christiansen_uniformity,
    classify_zones,
)


# ── generate_sprinkler_grid ────────────────────────────────────────────────────

class TestGenerateSprinklerGrid:
    def test_2x2_grid(self):
        # 100×100 field, 50 ft spacing → 2 cols × 2 rows = 4 sprinklers
        sprinklers = generate_sprinkler_grid(100, 100, 50)
        assert len(sprinklers) == 4

    def test_positions_centered_in_cells(self):
        # With 50 ft spacing, first head lands at (25, 25)
        sprinklers = generate_sprinkler_grid(100, 100, 50)
        xs = sorted(set(s[0] for s in sprinklers))
        ys = sorted(set(s[1] for s in sprinklers))
        assert xs == [25.0, 75.0]
        assert ys == [25.0, 75.0]

    def test_all_heads_inside_field(self):
        sprinklers = generate_sprinkler_grid(300, 200, 50)
        for x, y in sprinklers:
            assert 0 < x < 300
            assert 0 < y < 200

    def test_single_sprinkler_when_spacing_just_fits(self):
        # spacing=90 on 100×100: half=45, one column/row fits → 1 sprinkler at (45, 45)
        sprinklers = generate_sprinkler_grid(100, 100, 90)
        assert len(sprinklers) == 1
        assert sprinklers[0] == (45.0, 45.0)

    def test_no_sprinklers_when_spacing_exceeds_field(self):
        # spacing=200 on 100×100: half-buffer (100) equals field size → nothing fits
        sprinklers = generate_sprinkler_grid(100, 100, 200)
        assert len(sprinklers) == 0

    def test_count_matches_known_config(self):
        # 300×200 ft, 50 ft spacing → 6 cols × 4 rows = 24 sprinklers
        sprinklers = generate_sprinkler_grid(300, 200, 50)
        assert len(sprinklers) == 24


# ── count_coverage_at_point ───────────────────────────────────────────────────

class TestCountCoverageAtPoint:
    def test_point_at_sprinkler_is_covered(self):
        sprinklers = [(0.0, 0.0)]
        assert count_coverage_at_point((0.0, 0.0), sprinklers, throw_radius=10) == 1

    def test_point_exactly_at_radius_is_covered(self):
        # Boundary: distance == radius, should be included (<=)
        sprinklers = [(0.0, 0.0)]
        assert count_coverage_at_point((10.0, 0.0), sprinklers, throw_radius=10) == 1

    def test_point_beyond_radius_not_covered(self):
        sprinklers = [(0.0, 0.0)]
        assert count_coverage_at_point((10.1, 0.0), sprinklers, throw_radius=10) == 0

    def test_two_sprinklers_overlap(self):
        sprinklers = [(0.0, 0.0), (5.0, 0.0)]
        # Point at (2.5, 0) is within 10 ft of both
        assert count_coverage_at_point((2.5, 0.0), sprinklers, throw_radius=10) == 2

    def test_no_sprinklers_returns_zero(self):
        assert count_coverage_at_point((5.0, 5.0), [], throw_radius=10) == 0


# ── compute_coverage_field ────────────────────────────────────────────────────

class TestComputeCoverageField:
    def test_output_shape(self):
        sprinklers = [(50.0, 50.0)]
        field = compute_coverage_field(100, 100, sprinklers, throw_radius=20, resolution=2)
        assert field.shape == (50, 50)   # 100/2 rows, 100/2 cols

    def test_center_cell_covered_by_center_sprinkler(self):
        # Single sprinkler at exact center, large throw — center cell must be covered
        sprinklers = [(50.0, 50.0)]
        field = compute_coverage_field(100, 100, sprinklers, throw_radius=40, resolution=10)
        row, col = 5, 5   # cell centre at (55, 55) — within 40 ft
        assert field[row, col] >= 1

    def test_all_values_non_negative(self):
        sprinklers = generate_sprinkler_grid(100, 100, 50)
        field = compute_coverage_field(100, 100, sprinklers, throw_radius=30, resolution=5)
        assert (field >= 0).all()

    def test_zero_sprinklers_gives_zero_field(self):
        field = compute_coverage_field(100, 100, [], throw_radius=20, resolution=10)
        assert field.sum() == 0


# ── compute_application_rate_field ───────────────────────────────────────────

class TestComputeApplicationRateField:
    def test_scales_by_flow_rate(self):
        coverage = np.array([[0, 1], [2, 3]], dtype=np.int32)
        result = compute_application_rate_field(coverage, per_sprinkler_rate=5.0)
        np.testing.assert_array_equal(result, [[0.0, 5.0], [10.0, 15.0]])

    def test_zero_coverage_gives_zero_rate(self):
        coverage = np.zeros((3, 3), dtype=np.int32)
        result = compute_application_rate_field(coverage, per_sprinkler_rate=5.0)
        assert result.sum() == 0.0

    def test_output_shape_preserved(self):
        coverage = np.ones((4, 6), dtype=np.int32)
        result = compute_application_rate_field(coverage, per_sprinkler_rate=3.0)
        assert result.shape == (4, 6)


# ── compute_distribution_uniformity ──────────────────────────────────────────

class TestComputeDistributionUniformity:
    def test_uniform_field_gives_du_1(self):
        # Every cell has the same value → lower quartile mean == overall mean
        field = np.full((10, 10), 5.0)
        assert compute_distribution_uniformity(field) == pytest.approx(1.0)

    def test_empty_field_gives_zero(self):
        field = np.zeros((5, 5))
        assert compute_distribution_uniformity(field) == 0.0

    def test_du_less_than_one_for_uneven_field(self):
        # Mix of high and low values → DU < 1
        field = np.array([[1.0, 10.0], [10.0, 10.0]])
        du = compute_distribution_uniformity(field)
        assert 0.0 < du < 1.0

    def test_du_within_valid_range(self):
        rng = np.random.default_rng(42)
        field = rng.uniform(1, 10, size=(20, 20))
        du = compute_distribution_uniformity(field)
        assert 0.0 <= du <= 1.0


# ── compute_christiansen_uniformity ──────────────────────────────────────────

class TestComputeChristiansenUniformity:
    def test_uniform_field_gives_cu_1(self):
        field = np.full((10, 10), 7.0)
        assert compute_christiansen_uniformity(field) == pytest.approx(1.0)

    def test_empty_field_gives_zero(self):
        field = np.zeros((5, 5))
        assert compute_christiansen_uniformity(field) == 0.0

    def test_cu_less_than_one_for_uneven_field(self):
        field = np.array([[1.0, 10.0], [10.0, 10.0]])
        cu = compute_christiansen_uniformity(field)
        assert 0.0 < cu < 1.0

    def test_cu_within_valid_range(self):
        rng = np.random.default_rng(7)
        field = rng.uniform(1, 10, size=(20, 20))
        cu = compute_christiansen_uniformity(field)
        assert 0.0 <= cu <= 1.0

    def test_known_formula_result(self):
        # [4, 6] → mean=5, deviations=[1,1], CU = 1 - 2/(2*5) = 0.8
        field = np.array([[4.0, 6.0]])
        assert compute_christiansen_uniformity(field) == pytest.approx(0.8)


# ── classify_zones ────────────────────────────────────────────────────────────

class TestClassifyZones:
    def test_zero_coverage_is_underwatered(self):
        field = np.array([[0]])
        assert classify_zones(field)[0, 0] == 0

    def test_one_coverage_is_underwatered(self):
        field = np.array([[1]])
        assert classify_zones(field)[0, 0] == 0

    def test_two_coverage_is_optimal(self):
        field = np.array([[2]])
        assert classify_zones(field)[0, 0] == 1

    def test_three_coverage_is_overwatered(self):
        field = np.array([[3]])
        assert classify_zones(field)[0, 0] == 2

    def test_high_coverage_is_overwatered(self):
        field = np.array([[6]])
        assert classify_zones(field)[0, 0] == 2

    def test_output_shape_matches_input(self):
        field = np.array([[0, 1, 2], [3, 2, 1]])
        zones = classify_zones(field)
        assert zones.shape == field.shape

    def test_all_zone_codes_present(self):
        field = np.array([[0, 2, 3]])
        zones = classify_zones(field)
        assert set(zones.flatten()) == {0, 1, 2}
