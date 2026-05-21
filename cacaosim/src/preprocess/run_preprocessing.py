#!/usr/bin/env python3
"""
Preprocessing orchestrator — converts GIS data + config into scene_data.json
ready for the Blender scene-building script.

Usage (run from cacaosim/ project root):
    python src/preprocess/run_preprocessing.py configs/sefwi_demo.json
"""

import sys
from pathlib import Path

# Ensure sibling modules are importable when run as a script
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np

from config_loader import load_config
from gis_loader import (
    load_boundary,
    reproject_to_utm,
    compute_local_origin,
    boundary_area_ha,
    load_and_clip_dem_utm,
)
from terrain_analysis import (
    compute_slope_aspect,
    dominant_slope_direction,
    row_orientation_from_aspect,
)
from plant_placement import generate_grid_points, sample_elevation, assign_shade_species
from sun_calculator import solar_position
from analytics import compute_analytics
from scene_writer import write_scene_data


def main(config_path: str) -> None:
    print(f"\n{'='*55}")
    print(f"  CacaoSim Preprocessor")
    print(f"{'='*55}")

    # ── 1. Config ────────────────────────────────────────────
    print(f"\n[1/8] Config: {config_path}")
    config = load_config(config_path)
    site = config["site"]
    planting = config["planting"]
    seed = config.get("reproducibility", {}).get("random_seed", 42)
    print(f"      project: {config['project_name']}")

    # ── 2. Boundary ──────────────────────────────────────────
    print(f"\n[2/8] Boundary: {site['boundary_file']}")
    boundary_wgs84 = load_boundary(site["boundary_file"])
    boundary_utm = reproject_to_utm(boundary_wgs84)
    origin_x, origin_y = compute_local_origin(boundary_utm)
    area_ha = boundary_area_ha(boundary_utm)
    print(f"      origin  : ({origin_x:.1f}, {origin_y:.1f}) UTM 30N")
    print(f"      area    : {area_ha:.1f} ha")

    # ── 3. DEM ───────────────────────────────────────────────
    print(f"\n[3/8] DEM: {site['terrain_file']}")
    elevation_utm, transform_utm = load_and_clip_dem_utm(
        site["terrain_file"], boundary_utm,
        output_path="data/intermediate/terrain_utm.tif",
    )
    res_m = abs(transform_utm.a)
    valid = elevation_utm[~np.isnan(elevation_utm)]
    print(f"      pixel res: {res_m:.1f} m")
    print(f"      elevation: {valid.min():.1f} – {valid.max():.1f} m  (mean {valid.mean():.1f} m)")

    # ── 4. Terrain analysis ──────────────────────────────────
    print(f"\n[4/8] Terrain analysis")
    slope, aspect = compute_slope_aspect(elevation_utm, res_m)
    dom_aspect = dominant_slope_direction(slope, aspect)

    cacao_cfg = planting["cacao"]
    if cacao_cfg.get("row_orientation") == "auto_slope_aware":
        row_orient = row_orientation_from_aspect(dom_aspect)
        print(f"      dominant slope direction : {dom_aspect:.1f}°")
        print(f"      row orientation (contour): {row_orient:.1f}°")
    else:
        row_orient = float(cacao_cfg.get("row_orientation", 0))
        print(f"      row orientation (fixed)  : {row_orient:.1f}°")

    # ── 5. Plant placement ───────────────────────────────────
    print(f"\n[5/8] Plant placement")
    plants: dict[str, list] = {}

    # Cacao
    cacao_pts = generate_grid_points(
        boundary_utm=boundary_utm,
        row_spacing=cacao_cfg["row_spacing_m"],
        plant_spacing=cacao_cfg["plant_spacing_m"],
        row_orientation_deg=row_orient,
        edge_buffer=cacao_cfg["edge_buffer_m"],
        jitter_m=cacao_cfg["position_jitter_m"],
        missing_rate=cacao_cfg["missing_rate"],
        seed=seed,
    )
    cacao_pts = sample_elevation(cacao_pts, elevation_utm, transform_utm, origin_x, origin_y)
    plants["cacao"] = cacao_pts
    print(f"      cacao       : {len(cacao_pts):>5} plants")

    # Shade upper canopy
    shade_cfg = planting["shade_upper"]
    if shade_cfg["enabled"]:
        shade_pts = generate_grid_points(
            boundary_utm=boundary_utm,
            row_spacing=shade_cfg["spacing_m"],
            plant_spacing=shade_cfg["spacing_m"],
            row_orientation_deg=row_orient,
            edge_buffer=cacao_cfg["edge_buffer_m"],
            jitter_m=shade_cfg["position_jitter_m"],
            missing_rate=0.0,
            seed=seed + 1,
        )
        shade_pts = sample_elevation(shade_pts, elevation_utm, transform_utm, origin_x, origin_y)
        shade_pts = assign_shade_species(shade_pts, shade_cfg["species_mix"], seed=seed + 2)
        plants["shade_upper"] = shade_pts
        print(f"      shade upper : {len(shade_pts):>5} trees")

    # Banana (middle canopy)
    banana_cfg = planting["shade_middle"]
    if banana_cfg["enabled"]:
        banana_pts = generate_grid_points(
            boundary_utm=boundary_utm,
            row_spacing=banana_cfg["spacing_m"],
            plant_spacing=banana_cfg["spacing_m"],
            row_orientation_deg=row_orient,
            edge_buffer=cacao_cfg["edge_buffer_m"],
            jitter_m=banana_cfg["position_jitter_m"],
            missing_rate=0.0,
            seed=seed + 3,
        )
        banana_pts = sample_elevation(banana_pts, elevation_utm, transform_utm, origin_x, origin_y)
        plants["banana"] = banana_pts
        print(f"      banana      : {len(banana_pts):>5} plants")

    # ── 6. Sun ───────────────────────────────────────────────
    print(f"\n[6/8] Sun position")
    sun = solar_position(
        config["environment"]["date"],
        config["environment"]["time_of_day"],
        site["lat"],
        site["lon"],
    )
    print(f"      elevation : {sun['elevation_deg']}°")
    print(f"      azimuth   : {sun['azimuth_deg']}°")

    # ── 7. Analytics ─────────────────────────────────────────
    print(f"\n[7/8] Analytics")
    analytics = compute_analytics(plants, area_ha, planting.get("growth_stage", "productive"))
    print(f"      canopy cover : {analytics['estimated_canopy_cover_pct']}%")
    print(f"      biomass      : {analytics['estimated_biomass_tonnes']} t")
    print(f"      carbon       : {analytics['estimated_carbon_tonnes']} t CO₂e")

    # ── 8. Write outputs ─────────────────────────────────────
    print(f"\n[8/8] Writing outputs")

    # Boundary extent (for Blender terrain plane sizing)
    bounds = boundary_utm.geometry.union_all().bounds
    extent_x = bounds[2] - bounds[0]
    extent_y = bounds[3] - bounds[1]

    # DEM extent (slightly larger due to padding)
    dem_h, dem_w = elevation_utm.shape
    dem_extent_x = float(abs(transform_utm.a) * dem_w)
    dem_extent_y = float(abs(transform_utm.e) * dem_h)

    elev_min = float(np.nanmin(elevation_utm))
    elev_max = float(np.nanmax(elevation_utm))
    elev_mean = float(np.nanmean(elevation_utm))
    elev_range = elev_max - elev_min

    terrain_info = {
        "origin_utm": {"x": origin_x, "y": origin_y},
        "area_ha": area_ha,
        "boundary_extent_x_m": extent_x,
        "boundary_extent_y_m": extent_y,
        "dem_extent_x_m": dem_extent_x,
        "dem_extent_y_m": dem_extent_y,
        "dem_width_px": dem_w,
        "dem_height_px": dem_h,
        "elevation_min_m": elev_min,
        "elevation_max_m": elev_max,
        "elevation_mean_m": elev_mean,
        "elevation_range_m": elev_range,
        "dominant_slope_deg": float(dom_aspect),
        "row_orientation_deg": float(row_orient),
        "pixel_resolution_m": float(res_m),
        "vertical_exaggeration": config["terrain"]["vertical_exaggeration"],
        "mesh_resolution_m": config["terrain"]["mesh_resolution_m"],
        "terrain_file_utm": "data/intermediate/terrain_utm.tif",
        "heightmap_png": "data/intermediate/terrain_heightmap.png",
    }

    out_path = write_scene_data(
        output_path="data/intermediate/scene_data.json",
        config=config,
        plants=plants,
        terrain_info=terrain_info,
        sun_info=sun,
        analytics=analytics,
        origin=(origin_x, origin_y),
    )
    print(f"      scene_data.json → {out_path}")

    # Export 16-bit greyscale heightmap for Blender displacement
    _export_heightmap(elevation_utm, elev_min, elev_range,
                      "data/intermediate/terrain_heightmap.png")

    total_plants = sum(len(v) for v in plants.values())
    print(f"\n{'='*55}")
    print(f"  Done → {out_path}")
    print(f"  Total plants : {total_plants}")
    print(f"  Terrain      : {dem_w}×{dem_h} px  ({dem_extent_x:.0f}×{dem_extent_y:.0f} m)")
    print(f"{'='*55}\n")


def _export_heightmap(elevation: np.ndarray, elev_min: float, elev_range: float,
                      output_path: str) -> None:
    from pathlib import Path
    from PIL import Image

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Replace NaN with elev_min (edges)
    clean = np.where(np.isnan(elevation), elev_min, elevation)

    # Normalise to 0-65535 (16-bit)
    norm = (clean - elev_min) / (elev_range if elev_range > 0 else 1.0)
    uint16 = (norm * 65535).clip(0, 65535).astype(np.uint16)

    # PIL expects row 0 at top; flip Y so North is up
    img = Image.fromarray(np.flipud(uint16), mode='I;16')
    img.save(output_path)
    print(f"      heightmap PNG  → {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/preprocess/run_preprocessing.py <config.json>")
        sys.exit(1)
    main(sys.argv[1])
