#!/usr/bin/env bash
# ForestWatch — full pipeline: generate NDVI data + Blender renders + annotate.
# Usage: ./run_pipeline.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

echo "=== Step 1: Generate NDVI time-series ==="
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/src/run_pipeline.py"

echo ""
echo "=== Step 2: Blender — 6 renders (one per year) + GLB ==="
"$BLENDER" --background \
  --python "$SCRIPT_DIR/src/build_scene.py" \
  -- "$SCRIPT_DIR" 2>&1 | grep -v "DeprecationWarning\|expected to be removed" | grep -v "00:[0-9][0-9]\."

echo ""
echo "=== Step 3: Annotate showcase + animated GIF ==="
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/src/annotate.py"

echo ""
echo "Done."
echo "  Showcase  → $SCRIPT_DIR/output/showcase.png"
echo "  Timelapse → $SCRIPT_DIR/output/deforestation_timelapse.gif"
