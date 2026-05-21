#!/usr/bin/env bash
# Run a CacaoSim Blender script in background mode.
#
# Usage (from cacaosim/ root):
#   ./run_blender.sh                      # full scene build
#   ./run_blender.sh --preview 500        # preview: 500 plants per category
#
# The resulting .blend file is saved to data/outputs/cacaosim_scene.blend
# Open it in your Blender app to inspect and render.

set -euo pipefail
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$ROOT/src/blender/load_scene.py"

echo "Starting Blender scene build …"
"$BLENDER" --background --python "$SCRIPT" -- "$ROOT" "$@"
