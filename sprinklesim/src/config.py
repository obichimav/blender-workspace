# Field dimensions (feet)
FIELD_WIDTH_FT = 300
FIELD_HEIGHT_FT = 200

# Sprinkler specs
SPRINKLER_THROW_FT = 40       # radius of coverage
SPRINKLER_FLOW_GPM = 5.0      # gallons per minute per sprinkler
OVERLAP_FACTOR = 0.625        # 0.5–0.65 typical; spacing = throw × factor × 2

# Derived spacing
SPACING_FT = SPRINKLER_THROW_FT * OVERLAP_FACTOR * 2   # = 50.0 ft

# Coverage grid resolution
GRID_RESOLUTION_FT = 2.0      # 2-foot cells

# Output paths (relative to project root)
DATA_JSON_PATH = "output/data.json"
ZONE_TEXTURE_PATH = "output/zone_texture.png"
RAW_RENDER_PATH = "output/raw_render.png"
FINAL_OUTPUT_PATH = "output/sprinklesim_coverage_demo.png"

# Unit conversion
FT_TO_M = 0.3048
