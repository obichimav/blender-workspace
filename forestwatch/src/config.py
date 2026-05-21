"""ForestWatch configuration — Rondônia, Brazil deforestation hotspot."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Study area: Rondônia state, Brazil — classic fishbone deforestation corridor
BBOX_WGS84 = (-62.5, -11.5, -61.5, -10.5)   # lon_w, lat_s, lon_e, lat_n

# Six dry-season composites (July–Sep minimises cloud cover over Amazon)
YEARS = [2018, 2019, 2020, 2021, 2022, 2023]

# NDVI thresholds for zone classification
NDVI_FOREST   = 0.60   # dense canopy
NDVI_DEGRADED = 0.35   # degraded / secondary growth
# below NDVI_DEGRADED → deforested / bare soil / pasture

# Spatial resolution of output NDVI grids
GRID_ROWS = 512
GRID_COLS = 512

# Blender displacement scale for canopy height illusion (metres equivalent)
CANOPY_DISPLACEMENT = 0.6

# Paths
DATA_DIR   = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
