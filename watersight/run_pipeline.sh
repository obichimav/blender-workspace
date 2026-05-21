#!/usr/bin/env bash
# WaterSight — full pipeline end-to-end.
# Usage: ./run_pipeline.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

echo "=== Step 1: Fetch terrain + compute water zones ==="
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/src/run_pipeline.py"

echo ""
echo "=== Step 2: Blender scene + dual render ==="
"$BLENDER" --background \
  --python "$SCRIPT_DIR/src/build_scene.py" \
  -- "$SCRIPT_DIR" 2>&1 | grep -v "DeprecationWarning\|expected to be removed" | grep -v "00:[0-9][0-9]\."

echo ""
echo "=== Step 3: Annotate side-by-side ==="
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/src/annotate.py"

echo ""
echo "Done. Output: $SCRIPT_DIR/output/showcase.png"
