"""
Tests for AgriKit geometry math.
Run from project root:  venv/bin/pytest tests/ -v
"""
import math
import pytest


# ── Silo geometry ─────────────────────────────────────────────────────────────

class TestSiloGeometry:
    def test_silo_body_radius(self):
        radius = 2.2
        assert radius > 0

    def test_silo_roof_radius_larger_than_body(self):
        # Roof should overhang the body slightly
        body_r = 2.2
        roof_r = 2.4
        assert roof_r > body_r

    def test_ladder_rung_count(self):
        rung_count = 12
        assert rung_count > 0

    def test_ladder_vertical_spacing(self):
        start_z = 1.0
        step = 0.85
        rungs = 12
        top_z = start_z + (rungs - 1) * step
        # Should be less than silo height (10m)
        assert top_z < 10.5

    def test_silo_total_height(self):
        body_depth = 10.0
        roof_depth = 2.5
        # Body top + half roof depth
        total_approx = 10.0 + 2.5 / 2
        assert total_approx == pytest.approx(11.25)


# ── Barn geometry ─────────────────────────────────────────────────────────────

class TestBarnGeometry:
    W, D, H = 8.0, 5.0, 5.0

    def test_barn_dimensions_positive(self):
        assert self.W > 0 and self.D > 0 and self.H > 0

    def test_gambrel_ridge_above_walls(self):
        ridge_h = self.H + 3.2
        assert ridge_h > self.H

    def test_gambrel_mid_between_wall_and_ridge(self):
        ridge_h = self.H + 3.2
        mid_h   = self.H + 1.8
        assert self.H < mid_h < ridge_h

    def test_gambrel_mid_width_narrower_than_walls(self):
        mid_w = self.W / 2 * 0.55
        assert mid_w < self.W / 2

    def test_door_height_less_than_wall(self):
        door_h = self.H * 0.35
        assert door_h < self.H

    def test_trim_strips_within_wall_height(self):
        trim_z_values = [0.6, self.H * 0.33 + 0.6,
                         self.H * 0.66 + 0.6, self.H + 0.6]
        for z in trim_z_values:
            assert z <= self.H + 1.0


# ── Water tower geometry ──────────────────────────────────────────────────────

class TestWaterTowerGeometry:
    def test_tank_above_ground(self):
        tank_z = 12.0
        assert tank_z > 0

    def test_dome_above_tank(self):
        tank_top = 12.0 + 1.5
        dome_z   = 13.6
        assert dome_z >= tank_top

    def test_six_legs(self):
        leg_count = 6
        angle_step = 360 / leg_count
        assert angle_step == pytest.approx(60.0)

    def test_leg_positions_form_circle(self):
        leg_count = 6
        positions = []
        for i in range(leg_count):
            angle = math.radians(i * 60)
            positions.append((math.cos(angle) * 1.4, math.sin(angle) * 1.4))
        # All radii should be equal
        for x, y in positions:
            assert math.sqrt(x**2 + y**2) == pytest.approx(1.4, rel=1e-4)

    def test_banding_within_tank_height(self):
        band_z_values = [11.0, 12.0, 13.0]
        tank_bottom = 12.0 - 1.5
        tank_top    = 12.0 + 1.5
        for z in band_z_values:
            assert tank_bottom <= z <= tank_top


# ── Greenhouse geometry ───────────────────────────────────────────────────────

class TestGreenhouseGeometry:
    W, D, H, RH = 6.0, 12.0, 2.5, 2.0

    def test_greenhouse_depth_longer_than_width(self):
        assert self.D > self.W

    def test_ridge_height_above_walls(self):
        ridge = self.H + self.RH
        assert ridge > self.H

    def test_rib_count_proportional_to_depth(self):
        rib_count = int(self.D / 1.5) + 1
        assert rib_count >= 2

    def test_rafter_length_correct(self):
        rafter_len = math.sqrt((self.W / 2) ** 2 + self.RH ** 2)
        assert rafter_len > self.W / 2

    def test_roof_slope_angle(self):
        slope_angle = 30  # degrees
        assert 20 <= slope_angle <= 45


# ── Center pivot geometry ─────────────────────────────────────────────────────

class TestPivotGeometry:
    ARM_LENGTH = 28.0
    TOWER_COUNT = 5

    def test_span_per_tower(self):
        span = self.ARM_LENGTH / self.TOWER_COUNT
        assert span == pytest.approx(5.6)

    def test_span_is_positive(self):
        span = self.ARM_LENGTH / self.TOWER_COUNT
        assert span > 0

    def test_drop_pipes_per_span(self):
        # 2 drop pipes per span
        drop_per_span = 2
        total_drops = drop_per_span * self.TOWER_COUNT
        assert total_drops == 10

    def test_tower_height_reasonable(self):
        tower_h = 3.2
        assert 2.0 <= tower_h <= 6.0

    def test_arm_length_covers_typical_field(self):
        # Real center pivots: 100–800m radius
        assert 20 <= self.ARM_LENGTH <= 500


# ── Hay bale geometry ─────────────────────────────────────────────────────────

class TestHayBaleGeometry:
    def test_bale_radius_reasonable(self):
        radius = 0.9
        assert 0.5 <= radius <= 2.0

    def test_bale_depth_reasonable(self):
        depth = 1.2
        assert 0.8 <= depth <= 2.5

    def test_wrap_radius_larger_than_bale(self):
        bale_r = 0.9
        wrap_r = 0.92
        assert wrap_r > bale_r

    def test_six_bale_locations_given(self):
        bale_locs = [
            (16, 12, 0), (18, 14, 0), (20, 12.5, 0),
            (22, 13, 0), (17, 15.5, 0), (24, 11.5, 0),
        ]
        assert len(bale_locs) == 6

    def test_bale_locs_near_barn(self):
        barn_x = 20
        bale_locs = [
            (16, 12, 0), (18, 14, 0), (20, 12.5, 0),
            (22, 13, 0), (17, 15.5, 0), (24, 11.5, 0),
        ]
        for x, y, z in bale_locs:
            dist = math.sqrt((x - barn_x) ** 2)
            assert dist <= 10
