"""
SprinkleSim Mini — Blender Scene Builder
Full 3D scene: grass field, 3D pipe network, sprinkler heads,
spray coverage discs, perspective hero camera, Hosek-Wilkie sky.

Runs headlessly:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py \
        -- /path/to/sprinklesim
"""
import sys
import json
import math
from pathlib import Path
from collections import defaultdict

import bpy
from mathutils import Vector, Matrix


def _project_root():
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra:
            return Path(extra[0]).resolve()
    return Path(__file__).resolve().parent.parent


ROOT       = _project_root()
DATA_JSON  = ROOT / "output" / "data.json"
TEXTURE    = ROOT / "output" / "zone_texture.png"
RAW_RENDER = ROOT / "output" / "raw_render.png"
BLEND_FILE = ROOT / "output" / "sprinklesim_scene.blend"


# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for d in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
              bpy.data.materials, bpy.data.curves):
        for blk in list(d):
            d.remove(blk)


def get_col(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def move_to(obj, col_name):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    get_col(col_name).objects.link(obj)


def make_mat(name, base, metallic=0.0, roughness=0.6,
             emission=None, alpha=1.0, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value  = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value    = metallic
    bsdf.inputs["Roughness"].default_value   = roughness
    if emission:
        try:
            bsdf.inputs["Emission Color"].default_value    = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 2.0
        except KeyError:
            pass
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = 'BLEND'
        try:
            mat.shadow_method = 'NONE'
        except AttributeError:
            pass
    return mat


# ── 1. Field plane (zone-texture + grass surroundings) ────────────────────────

def create_field(data):
    w = data['field']['width_m']
    h = data['field']['height_m']

    # Zone-textured field
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(w / 2, h / 2, 0))
    field = bpy.context.active_object
    field.name = "Field"
    field.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True)

    mat = bpy.data.materials.new("FieldZones")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.95

    tex     = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(TEXTURE))
    tex.interpolation = 'Linear'
    coord   = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(coord.outputs['UV'],       mapping.inputs['Vector'])
    nt.links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'],      bsdf.inputs['Base Color'])

    field.data.materials.append(mat)
    bpy.context.view_layer.objects.active = field
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.reset()
    bpy.ops.object.mode_set(mode='OBJECT')
    move_to(field, "Field")

    # Grass apron around the field (so it doesn't float in white void)
    margin = 12.0
    bpy.ops.mesh.primitive_plane_add(
        size=1.0,
        location=(w / 2, h / 2, -0.01)
    )
    apron = bpy.context.active_object
    apron.name = "Apron"
    apron.scale = (w + margin * 2, h + margin * 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    grass_mat = make_mat("Grass", (0.18, 0.38, 0.12), roughness=0.95)
    apron.data.materials.append(grass_mat)
    move_to(apron, "Field")

    return field


# ── 2. Pipe network ───────────────────────────────────────────────────────────

def _cylinder_along(x0, y0, x1, y1, z, radius, mat, col_name):
    """Create a cylinder from (x0,y0) to (x1,y1) at height z."""
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 0.01:
        return None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=length,
        location=(cx, cy, z), vertices=12,
    )
    obj = bpy.context.active_object
    obj.rotation_euler = (math.pi / 2, 0, math.atan2(y1 - y0, x1 - x0))
    obj.data.materials.append(mat)
    move_to(obj, col_name)
    return obj


def add_pipe_network(data):
    sprinklers = data['sprinklers_m']
    spacing_m  = data['sprinkler_specs']['spacing_ft'] * 0.3048

    mat_lat  = make_mat("PipeLateral", (0.08, 0.08, 0.08), roughness=0.65)
    mat_main = make_mat("PipeMain",    (0.04, 0.04, 0.04), roughness=0.55)
    mat_joint = make_mat("PipeJoint", (0.15, 0.15, 0.15), metallic=0.4, roughness=0.4)

    PIPE_Z   = 0.12     # pipes sit slightly above ground
    LAT_R    = 0.14     # lateral 2" nominal (visible at field scale)
    MAIN_R   = 0.22     # supply main 4" nominal
    JOINT_R  = LAT_R * 1.6

    # Group by row
    rows = defaultdict(list)
    for s in sprinklers:
        rows[round(s['y'], 1)].append(s)

    y_vals = sorted(rows.keys())
    x_main = min(s['x'] for s in sprinklers) - spacing_m * 0.5

    # Laterals
    for y in y_vals:
        row = sorted(rows[y], key=lambda s: s['x'])
        _cylinder_along(x_main, y, row[-1]['x'], y,
                        PIPE_Z, LAT_R, mat_lat, "Pipes")
        # T-joints at each sprinkler
        for s in row:
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=JOINT_R, location=(s['x'], s['y'], PIPE_Z), segments=8, ring_count=6)
            jt = bpy.context.active_object
            jt.data.materials.append(mat_joint)
            move_to(jt, "Pipes")

    # Supply main (vertical header)
    _cylinder_along(x_main, y_vals[0] - LAT_R, x_main, y_vals[-1] + LAT_R,
                    PIPE_Z, MAIN_R, mat_main, "Pipes")

    # Main-to-lateral stubs
    for y in y_vals:
        _cylinder_along(x_main, y, rows[y][0]['x'], y,
                        PIPE_Z, MAIN_R, mat_main, "Pipes")
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=MAIN_R * 1.5, location=(x_main, y, PIPE_Z), segments=8, ring_count=6)
        jm = bpy.context.active_object
        jm.data.materials.append(mat_joint)
        move_to(jm, "Pipes")

    print(f"  Pipes: {len(y_vals)} laterals + supply main + joints")


# ── 3. Sprinkler heads ────────────────────────────────────────────────────────

def add_sprinkler_heads(data):
    """
    Each sprinkler:
      - Ground stake / riser pipe
      - Rotating head body (disc + dome)
      - Spray coverage disc showing throw radius
    """
    sprinklers = data['sprinklers_m']
    throw_m    = data['sprinkler_specs']['throw_m']

    mat_riser   = make_mat("Riser",    (0.20, 0.20, 0.20), metallic=0.5, roughness=0.5)
    mat_head    = make_mat("HeadBody", (0.85, 0.87, 0.90), metallic=0.85, roughness=0.15,
                           emission=(0.9, 0.95, 1.0))
    mat_spray   = make_mat("Spray",    (0.25, 0.65, 0.95), roughness=0.2, alpha=0.30)

    RISER_R  = 0.07
    RISER_H  = 0.50
    HEAD_R   = 0.18
    DOME_R   = 0.14
    SPRAY_THICK = 0.40   # torus minor radius (ring thickness)

    for idx, s in enumerate(sprinklers):
        x, y = s['x'], s['y']

        # Riser pipe
        bpy.ops.mesh.primitive_cylinder_add(
            radius=RISER_R, depth=RISER_H,
            location=(x, y, RISER_H / 2), vertices=10,
        )
        riser = bpy.context.active_object
        riser.name = f"Riser_{idx:03d}"
        riser.data.materials.append(mat_riser)
        move_to(riser, "Sprinklers")

        # Head disc (flat flange)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=HEAD_R, depth=0.06,
            location=(x, y, RISER_H + 0.03), vertices=16,
        )
        disc = bpy.context.active_object
        disc.name = f"Disc_{idx:03d}"
        disc.data.materials.append(mat_head)
        move_to(disc, "Sprinklers")

        # Dome nozzle on top
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=DOME_R, location=(x, y, RISER_H + 0.12),
            segments=12, ring_count=8,
        )
        dome = bpy.context.active_object
        dome.name = f"Dome_{idx:03d}"
        # Flatten slightly — looks like a rotary nozzle cap
        dome.scale.z = 0.55
        bpy.ops.object.transform_apply(scale=True)
        dome.data.materials.append(mat_head)
        move_to(dome, "Sprinklers")

        # Spray ring at throw radius (shows coverage area)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=throw_m,
            minor_radius=SPRAY_THICK,
            major_segments=64,
            minor_segments=6,
            location=(x, y, 0.04),
        )
        ring = bpy.context.active_object
        ring.name = f"SprayRing_{idx:03d}"
        ring.data.materials.append(mat_spray)
        move_to(ring, "Sprinklers")

    print(f"  Sprinkler heads: {len(sprinklers)}")


# ── 4. Cameras ────────────────────────────────────────────────────────────────

def setup_cameras(data):
    w = data['field']['width_m']
    h = data['field']['height_m']

    def _cam(name, loc, target, focal_mm):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = name
        cam.data.type  = 'PERSP'
        cam.data.lens  = focal_mm
        cam.data.clip_start = 0.1
        cam.data.clip_end   = 1000.0
        direction = Vector(target) - Vector(loc)
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        return cam

    cx, cy = w / 2, h / 2

    # Hero — diagonal view from one corner, low angle
    hero = _cam("Cam_Hero",
                loc=(-22, -14, 22),
                target=(cx, cy * 0.6, 1.5),
                focal_mm=35)
    bpy.context.scene.camera = hero

    # Aerial — higher, wider view
    _cam("Cam_Aerial",
         loc=(cx * 0.4, -25, 55),
         target=(cx, cy, 0),
         focal_mm=28)

    # Close-up — eye level, shows one row of sprinklers
    _cam("Cam_CloseUp",
         loc=(-10, h * 0.25, 3.5),
         target=(w * 0.4, h * 0.25, 0.8),
         focal_mm=50)

    print("  Cameras: Hero, Aerial, CloseUp")


# ── 5. Lighting ───────────────────────────────────────────────────────────────

HDRI_PATH = ROOT / "assets" / "hdri" / "rural_landscape_2k.hdr"


def setup_lighting():
    # Sun lamp — mid-morning tropical sun
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 50))
    sun = bpy.context.active_object
    sun.name = "Sun"
    el = math.radians(38)   # 38° elevation
    az = math.radians(125)  # SE direction
    sun.rotation_euler[0] = math.pi / 2 - el
    sun.rotation_euler[2] = -az
    sun.data.energy = 3.0   # softer with HDRI fill light
    sun.data.angle  = math.radians(0.5)
    sun.data.color  = (1.0, 0.97, 0.90)

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out  = nt.nodes.new('ShaderNodeOutputWorld')
    bg   = nt.nodes.new('ShaderNodeBackground')

    if HDRI_PATH.exists():
        # Polyhaven HDRI environment — real photographed rural landscape
        env  = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(str(HDRI_PATH))
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.inputs['Rotation'].default_value[2] = math.radians(120)  # rotate to match sun
        nt.links.new(coord.outputs['Generated'], mapping.inputs['Vector'])
        nt.links.new(mapping.outputs['Vector'],  env.inputs['Vector'])
        nt.links.new(env.outputs['Color'],       bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 1.2
        print(f"  Lighting: sun + HDRI ({HDRI_PATH.name})")
    else:
        # Fallback: Hosek-Wilkie procedural sky
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'HOSEK_WILKIE'
        sky.sun_direction = (
            math.cos(el) * math.sin(az),
            math.cos(el) * math.cos(az),
            math.sin(el),
        )
        sky.turbidity = 3.5
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 1.0
        print("  Lighting: sun + Hosek-Wilkie sky (HDRI not found, using fallback)")

    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])


# ── 6. Render settings ────────────────────────────────────────────────────────

def configure_render():
    scn = bpy.context.scene
    scn.render.engine             = 'CYCLES'
    scn.cycles.device             = 'CPU'
    scn.cycles.samples            = 128
    scn.cycles.use_denoising      = True
    try:
        bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'
    except Exception:
        pass
    scn.render.resolution_x   = 1920
    scn.render.resolution_y   = 1080
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = 'PNG'
    scn.render.filepath       = str(RAW_RENDER)


# ── 7. GLB export ────────────────────────────────────────────────────────────

def export_glb(filepath):
    """
    Export scene as GLB (binary glTF 2.0).
    Includes all meshes, materials, and the zone texture image.
    Opens in browsers, Sketchfab, Unity, Unreal, AR Quick Look.
    """
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format='GLB',
        export_apply=True,          # apply modifiers
        export_materials='EXPORT',  # include all materials + textures
        export_normals=True,
        export_texcoords=True,
        export_cameras=True,
        export_lights=False,        # lights not needed for viewing
    )
    print(f"  Saved GLB  → {filepath}")


# ── 8. PLY export ────────────────────────────────────────────────────────────

def export_ply(filepath):
    bpy.ops.wm.ply_export(
        filepath=str(filepath),
        ascii_format=False,
        export_normals=True,
        export_uv=True,
        export_colors='NONE',
    )
    print(f"  Saved PLY  → {filepath}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  SprinkleSim Mini — 3D Blender Scene")
    print("=" * 52)

    with open(DATA_JSON) as f:
        data = json.load(f)

    print(f"  Field : {data['field']['width_ft']} × {data['field']['height_ft']} ft")
    print(f"  Sprinklers: {data['metrics']['sprinkler_count']}"
          f"  |  Throw: {data['sprinkler_specs']['throw_ft']} ft")

    clear_scene()
    create_field(data)
    add_pipe_network(data)
    add_sprinkler_heads(data)
    setup_cameras(data)
    setup_lighting()
    configure_render()

    # Save navigable .blend
    BLEND_FILE.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"\nSaved .blend → {BLEND_FILE}")

    # Export GLB
    glb_path = ROOT / "output" / "sprinklesim_scene.glb"
    export_glb(glb_path)

    # Export PLY
    ply_path = ROOT / "output" / "sprinklesim_scene.ply"
    export_ply(ply_path)

    print("Rendering hero shot …")
    bpy.ops.render.render(write_still=True)
    print(f"Saved render → {RAW_RENDER}")


if __name__ == "__main__":
    main()
