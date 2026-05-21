"""
CacaoSim — main Blender scene builder.

Run from cacaosim/ root:
  /Applications/Blender.app/Contents/MacOS/Blender \
      --background --python src/blender/load_scene.py \
      -- /full/path/to/cacaosim [--preview N]

Args after '--':
  path/to/cacaosim   (required) absolute path to the cacaosim project root
  --preview N        (optional) only place N plants per category (fast test)
"""

import sys
import time
from pathlib import Path


def _setup_path():
    """Add src/blender/ to sys.path so sibling modules can be imported."""
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


_setup_path()

import bpy
from utils import project_root, load_scene_data


def parse_args():
    preview = 0
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if "--preview" in extra:
            idx = extra.index("--preview")
            if idx + 1 < len(extra):
                preview = int(extra[idx + 1])
    return preview


def clear_scene():
    """Remove all default objects (cube, light, camera)."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light)


def configure_render(scene_data: dict):
    render = scene_data["render"]
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.render.resolution_x, scn.render.resolution_y = render["resolution"]
    scn.cycles.samples = render.get("samples", 128)
    scn.cycles.use_denoising = True
    # Use GPU if available
    prefs = bpy.context.preferences.addons.get('cycles')
    if prefs:
        try:
            bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'METAL'
        except Exception:
            pass
    scn.render.filepath = "//data/outputs/render_####"


def main():
    t0 = time.time()
    preview = parse_args()
    root = project_root()

    print(f"\n{'='*55}")
    print(f"  CacaoSim Scene Builder")
    print(f"  Project root : {root}")
    if preview:
        print(f"  Preview mode : {preview} plants/category")
    print(f"{'='*55}\n")

    # ── Load data ─────────────────────────────────────────────────────────────
    print("[1/6] Loading scene_data.json …")
    scene_data = load_scene_data(root)
    analytics = scene_data.get("analytics", {})
    counts = analytics.get("plant_counts", {})
    print(f"  cacao:  {counts.get('cacao', '?')}")
    print(f"  shade:  {counts.get('shade_upper', '?')}")
    print(f"  banana: {counts.get('banana', '?')}")

    # ── Clear default scene ───────────────────────────────────────────────────
    print("\n[2/6] Clearing default scene …")
    clear_scene()

    # ── Terrain ───────────────────────────────────────────────────────────────
    print("\n[3/6] Building terrain …")
    from build_terrain import build_terrain
    terrain = build_terrain(scene_data, root)

    # ── Assets ────────────────────────────────────────────────────────────────
    print("\n[4/6] Creating plant assets …")
    from create_assets import build_all_assets
    assets = build_all_assets()
    print(f"  Assets created: {list(assets.keys())}")

    # Mark Assets collection as "Indirect Only" so templates don't appear
    # directly in renders but are still accessible by GN Object Info nodes
    def _set_indirect_only(name):
        def _find(lc, n):
            if lc.collection.name == n:
                return lc
            for child in lc.children:
                r = _find(child, n)
                if r:
                    return r
        lc = _find(bpy.context.view_layer.layer_collection, name)
        if lc:
            lc.indirect_only = True

    _set_indirect_only("Assets")

    # ── Place plants ──────────────────────────────────────────────────────────
    print("\n[5/6] Placing plants …")
    from place_plants import place_all_plants
    plant_objs = place_all_plants(scene_data, assets, preview_n=preview)

    # ── Lighting + cameras ────────────────────────────────────────────────────
    print("\n[6/6] Lighting and cameras …")
    from setup_lighting import setup_lighting
    from setup_cameras import setup_cameras
    setup_lighting(scene_data)
    cameras = setup_cameras(scene_data)

    # ── Render settings ───────────────────────────────────────────────────────
    configure_render(scene_data)

    # ── Save .blend ───────────────────────────────────────────────────────────
    blend_path = str(root / "data" / "outputs" / "cacaosim_scene.blend")
    Path(blend_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"  Scene built in {elapsed:.1f}s")
    print(f"  Saved → {blend_path}")
    print(f"  Open in Blender to render (F12)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
