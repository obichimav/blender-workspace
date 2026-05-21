"""
CropSight — configuration.
Target: a 5 km × 5 km wheat-belt block near Dodge City, Kansas.
Sentinel-2 L2A scene via Microsoft Planetary Computer (free, no API key).
"""
from pathlib import Path

# ── Target region ─────────────────────────────────────────────────────────────
# Dodge City, KS wheat belt  (lon_min, lat_min, lon_max, lat_max)
BBOX_WGS84 = (-100.05, 37.70, -99.95, 37.80)
DATE_RANGE  = "2023-06-01/2023-06-30"   # peak Kansas wheat season
CLOUD_MAX   = 20                        # % cloud cover threshold

# ── Processing ────────────────────────────────────────────────────────────────
NDVI_STRESSED  = 0.30   # below → stressed / bare soil
NDVI_HEALTHY   = 0.60   # above → healthy crop
# Zone codes: 0 = stressed, 1 = moderate, 2 = healthy

# ── Scene dims (metres) ───────────────────────────────────────────────────────
SCENE_WIDTH_M  = 200
SCENE_HEIGHT_M = 200
CROP_SPACING_M = 2.0    # distance between crop stalk instances

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR          = ROOT / "data"
OUTPUT_DIR        = ROOT / "output"
HDRI_PATH         = ROOT / "assets" / "hdri" / "rural_landscape_2k.hdr"

NDVI_TIFF         = DATA_DIR  / "ndvi.tif"
DEM_PNG           = DATA_DIR  / "dem_heightmap.png"
ZONE_TEXTURE_PATH = OUTPUT_DIR / "zone_texture.png"
DATA_JSON_PATH    = OUTPUT_DIR / "data.json"
RAW_RENDER_PATH   = OUTPUT_DIR / "raw_render.png"
BLEND_FILE_PATH   = OUTPUT_DIR / "cropsight_scene.blend"
GLB_PATH          = OUTPUT_DIR / "cropsight_scene.glb"
FINAL_OUTPUT_PATH = OUTPUT_DIR / "cropsight_showcase.png"
