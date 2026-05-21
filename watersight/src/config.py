"""
WaterSight — Lake Powell Drought Visualizer.
Before (2000): full pool 1,128 m ASL  — blue canyon lake
After  (2022): record low 1,074 m ASL — 54 m bathtub ring exposed
"""
from pathlib import Path

# ── Target region — Lake Powell, Utah / Arizona ───────────────────────────────
BBOX_WGS84 = (-111.5, 37.0, -110.7, 37.6)   # lon_min, lat_min, lon_max, lat_max
TILE_ZOOM   = 11                              # ~15 km tiles; ~60 m/px after stitching

# ── Water levels (metres above sea level) ────────────────────────────────────
WATER_LEVEL_BEFORE_M = 1128.0    # year 2000 full pool
WATER_LEVEL_AFTER_M  = 1074.0    # year 2022 record low (54 m drop)

# Blender elevation exaggeration — canyons are subtle at terrain scale
ELEVATION_EXAGGERATION = 3.0

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR    = ROOT / "data"
OUTPUT_DIR  = ROOT / "output"
ASSETS_DIR  = ROOT / "assets"

ELEVATION_NPY     = DATA_DIR / "elevation.npy"
ELEVATION_META    = DATA_DIR / "elevation_meta.json"
HEIGHTMAP_PNG     = DATA_DIR / "heightmap.png"
SATELLITE_PNG     = DATA_DIR / "satellite.png"

DATA_JSON         = OUTPUT_DIR / "data.json"
RENDER_BEFORE     = OUTPUT_DIR / "render_before.png"
RENDER_AFTER      = OUTPUT_DIR / "render_after.png"
SHOWCASE_PATH     = OUTPUT_DIR / "showcase.png"
BLEND_FILE        = OUTPUT_DIR / "watersight_scene.blend"
GLB_PATH          = OUTPUT_DIR / "watersight_scene.glb"

HDRI_PATH         = ASSETS_DIR / "hdri"  / "kloofendal_48d_partly_cloudy_2k.hdr"
ROCK_TEX_DIFF     = ASSETS_DIR / "textures" / "rock_ground_02_diff_2k.png"
ROCK_TEX_ROUGH    = ASSETS_DIR / "textures" / "rock_ground_02_rough_2k.png"
CRACKED_TEX_DIFF  = ASSETS_DIR / "textures" / "mud_cracked_dry_03_diff_2k.png"
