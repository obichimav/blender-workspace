"""
SprinkleSim Mini — Blender Scene Builder
Runs headlessly:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py \
        -- /path/to/sprinklesim
"""
import sys
import json
import math
from pathlib import Path

import bpy


def _project_root():
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra:
            return Path(extra[0]).resolve()
    # Fallback: two levels up from this file
    return Path(__file__).resolve().parent.parent


ROOT = _project_root()
DATA_JSON  = ROOT / "output" / "data.json"
TEXTURE    = ROOT / "output" / "zone_texture.png"
RAW_RENDER = ROOT / "output" / "raw_render.png"


# ── Scene helpers ─────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes) + list(bpy.data.cameras) + list(bpy.data.lights):
        block.user_clear()
        bpy.data.batch_remove(ids=[block])


def create_field_plane(data):
    w = data['field']['width_m']
    h = data['field']['height_m']

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(w / 2, h / 2, 0))
    plane = bpy.context.active_object
    plane.name = "Field"
    plane.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True)

    mat = bpy.data.materials.new("ZoneMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    tex  = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(TEXTURE))

    # Map the texture to the plane 0→1 over the full surface
    coord  = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(coord.outputs['UV'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
    links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 1.0

    plane.data.materials.append(mat)

    # Add UV map so the texture fills the plane correctly
    bpy.context.view_layer.objects.active = plane
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.reset()
    bpy.ops.object.mode_set(mode='OBJECT')

    return plane


def add_sprinkler_markers(data):
    sprinklers = data['sprinklers_m']
    throw_m = data['sprinkler_specs']['throw_m']

    col = bpy.data.collections.new("Sprinklers")
    bpy.context.scene.collection.children.link(col)

    mat = bpy.data.materials.new("SprinklerMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value  = (0.05, 0.05, 0.05, 1)
    bsdf.inputs["Metallic"].default_value    = 0.8
    bsdf.inputs["Roughness"].default_value   = 0.2

    # Use instancing: create one cylinder, then duplicate
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=1.2, location=(0, 0, 0.6))
    template = bpy.context.active_object
    template.name = "Sprinkler_template"
    template.data.materials.append(mat)

    for idx, s in enumerate(sprinklers):
        inst = template.copy()
        inst.data = template.data
        inst.name = f"Sprinkler_{idx:04d}"
        inst.location = (s['x'], s['y'], 0.6)
        col.objects.link(inst)

    # Hide template from render
    template.hide_render = True
    template.hide_viewport = True

    print(f"  Placed {len(sprinklers)} sprinkler markers")


def setup_camera(data):
    w = data['field']['width_m']
    h = data['field']['height_m']

    bpy.ops.object.camera_add(location=(w / 2, h / 2, 200))
    cam = bpy.context.active_object
    cam.name = "TopDownCamera"
    cam.rotation_euler = (0, 0, 0)   # -Z points down = orthographic top-down view
    cam.data.type = 'ORTHO'

    # Fit both field dimensions inside 16:9 frame
    render_aspect = 16 / 9
    field_aspect  = w / h
    if field_aspect > render_aspect:
        cam.data.ortho_scale = w * 1.08
    else:
        cam.data.ortho_scale = h * render_aspect * 1.08

    bpy.context.scene.camera = cam
    return cam


def setup_lighting(data):
    w = data['field']['width_m']
    h = data['field']['height_m']

    # Bright even overhead area light
    bpy.ops.object.light_add(type='AREA', location=(w / 2, h / 2, 80))
    light = bpy.context.active_object
    light.name = "OverheadLight"
    light.rotation_euler = (0, 0, 0)
    light.data.energy = 30000
    light.data.size   = max(w, h) * 1.5
    light.data.use_shadow = False

    # White world background (engineering diagram look)
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background") or \
         world.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value    = (1, 1, 1, 1)
    bg.inputs['Strength'].default_value = 1.0


def configure_render():
    scn = bpy.context.scene
    scn.render.engine             = 'CYCLES'
    scn.cycles.device             = 'CPU'
    scn.cycles.samples            = 32
    scn.cycles.use_denoising      = False
    scn.render.resolution_x       = 1920
    scn.render.resolution_y       = 1080
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = 'PNG'
    scn.render.filepath           = str(RAW_RENDER)

    try:
        bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'
    except Exception:
        pass


def main():
    print("\n" + "=" * 50)
    print("  SprinkleSim Mini — Building Blender scene")
    print("=" * 50)

    with open(DATA_JSON) as f:
        data = json.load(f)

    print(f"  Field : {data['field']['width_ft']} × {data['field']['height_ft']} ft")
    print(f"  Sprinklers: {data['metrics']['sprinkler_count']}")

    clear_scene()
    create_field_plane(data)
    add_sprinkler_markers(data)
    setup_camera(data)
    setup_lighting(data)
    configure_render()

    print("\nRendering …")
    bpy.ops.render.render(write_still=True)
    print(f"Saved → {RAW_RENDER}")


if __name__ == "__main__":
    main()
