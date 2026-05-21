#!/usr/bin/env bash
# Wrapper that ensures PROJ/GDAL use the data bundled in the venv,
# not a conflicting system or conda installation.
#
# Usage (from cacaosim/ root):
#   ./run.sh src/preprocess/run_preprocessing.py configs/sefwi_demo.json
#   ./run.sh src/preprocess/generate_test_data.py

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SP="$SCRIPT_DIR/venv/lib/python3.12/site-packages"

export PROJ_LIB="$SP/rasterio/proj_data"
export PROJ_DATA="$SP/rasterio/proj_data"
export GDAL_DATA="$SP/rasterio/gdal_data"

exec "$SCRIPT_DIR/venv/bin/python" "$@"
