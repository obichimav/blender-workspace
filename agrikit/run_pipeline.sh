#!/usr/bin/env bash
# AgriKit — full pipeline: Blender scene build + annotate.
# Usage: ./run_pipeline.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

echo "=== Step 1: Build Blender scene + render ==="
"$BLENDER" --background \
  --python "$SCRIPT_DIR/src/build_scene.py" \
  -- "$SCRIPT_DIR" 2>&1 | grep -v "DeprecationWarning\|expected to be removed" | grep -v "00:[0-9][0-9]\."

echo ""
echo "=== Step 2: Annotate showcase composite ==="
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/src/annotate.py"

echo ""
echo "Done. Output: $SCRIPT_DIR/output/showcase.png"
