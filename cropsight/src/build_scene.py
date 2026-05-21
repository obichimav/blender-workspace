"""
CropSight — Blender 3D scene builder.
Terrain displaced by DEM heightmap + NDVI zone texture + procedural crop rows.

Headless usage:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py \
        -- /path/to/cropsight
"""
import sys
import json
import math
import random
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def _project_root():
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra:
            return Path(extra[0]).resolve()
    return Path(__file__).resolve().parent.parent


ROOT       = _project_root()
DATA_JSON  = ROOT / "output"  / "data.json"
ZONE_TEX   = ROOT / "output"  / "zone_texture.png"
DEM_PNG    = ROOT / "data"    / "dem_heightmap.png"
HDRI_PATH  = ROOT / "assets"  / "hdri" / "rural_landscape_2k.hdr"
BLEND_FILE = ROOT / "output"  / "cropsight_scene.blend"
RAW_RENDER = ROOT / "output"  / "raw_render.png"
GLB_PATH   = ROOT / "output"  / "cropsight_scene.glb"


# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blk_list in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                     bpy.data.materials, bpy.data.images, bpy.data.curves):
        for blk in list(blk_list):
            blk_list.remove(blk)


def make_mat(name, color, roughness=0.8, metallic=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value  = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value   = roughness
    bsdf.inputs["Metallic"].default_value    = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value    = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.3
    return mat


# ── 1. Terrain ─────────────────────────────────────────────────────────────────

def create_terrain(data):
    W = data["scene"]["width_m"]
    H = data["scene"]["height_m"]
    subdivs = 200   # enough resolution for smooth displacement

    # Base plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(W / 2, H / 2, 0))
    terrain = bpy.context.active_object
    terrain.name = "Terrain"
    terrain.scale = (W, H, 1)
    bpy.ops.object.transform_apply(scale=True)

    # Subdivide
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(terrain.data)
    for _ in range(7):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=1, use_grid_fill=True)
    bmesh.update_edit_mesh(terrain.data)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Zone colour texture
    mat = bpy.data.materials.new("TerrainMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex   = nt.nodes.new("ShaderNodeTexImage")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    bsdf.inputs["Roughness"].default_value = 0.9
    tex.image = bpy.data.images.load(str(ZONE_TEX))
    tex.image.colorspace_settings.name = "sRGB"
    nt.links.new(coord.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    terrain.data.materials.append(mat)

    # DEM displacement modifier
    if DEM_PNG.exists():
        dem_img = bpy.data.images.load(str(DEM_PNG))
        dem_img.colorspace_settings.name = "Non-Color"
        tex_disp = bpy.data.textures.new("DEMTex", type="IMAGE")
        tex_disp.image = dem_img
        mod = terrain.modifiers.new("DEM", type="DISPLACE")
        mod.texture      = tex_disp
        mod.strength     = 0.3    # very subtle — Kansas is nearly flat, crops must stay visible
        mod.texture_coords = "UV"
        mod.direction    = "Z"

    print("  Terrain: zone texture + DEM displacement")
    return terrain


# ── 2. Crop rows ──────────────────────────────────────────────────────────────

# Height and colour per zone
CROP_SPECS = {
    0: {"height": 0.6,  "color": (0.55, 0.35, 0.15), "name": "StressedCrop"},   # brown stubble
    1: {"height": 1.4,  "color": (0.60, 0.72, 0.25), "name": "ModerateCrop"},   # yellow-green
    2: {"height": 2.2,  "color": (0.15, 0.55, 0.12), "name": "HealthyCrop"},    # deep green
}


def _make_wheat_stalk(zone: int):
    """Simple wheat stalk: cylinder body + ellipsoid grain head."""
    spec   = CROP_SPECS[zone]
    h      = spec["height"]
    mat    = make_mat(spec["name"], spec["color"], roughness=0.9)

    # Stalk — thick enough to be visible at distance
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.06, depth=h, location=(0, 0, h / 2)
    )
    stalk = bpy.context.active_object
    stalk.name = f"Stalk_z{zone}"
    stalk.data.materials.append(mat)

    # Grain head (flattened sphere on top)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.14, location=(0, 0, h + 0.12)
    )
    head = bpy.context.active_object
    head.name = f"Head_z{zone}"
    head.scale.z = 1.8
    bpy.ops.object.transform_apply(scale=True)
    head.data.materials.append(mat)

    # Join into single mesh
    bpy.ops.object.select_all(action="DESELECT")
    stalk.select_set(True)
    head.select_set(True)
    bpy.context.view_layer.objects.active = stalk
    bpy.ops.object.join()
    template = bpy.context.active_object
    template.name = f"WheatTemplate_z{zone}"
    return template


def add_crop_rows(data):
    """
    Place wheat stalk instances from the pre-sampled crop_positions list.
    Uses Blender instancing (linked duplicates) for memory efficiency.
    """
    positions = data["crop_positions"]
    rng = random.Random(42)

    # Build one template per zone
    templates = {z: _make_wheat_stalk(z) for z in (0, 1, 2)}
    for t in templates.values():
        t.hide_render = True
        t.hide_viewport = True

    counts = {0: 0, 1: 0, 2: 0}
    for p in positions:
        zone = p["zone"]
        tmpl = templates[zone]
        spec = CROP_SPECS[zone]

        # Instance (linked duplicate — shares mesh data)
        inst = tmpl.copy()
        inst.data = tmpl.data        # shared mesh
        inst.hide_render   = False   # copy() inherits hide flags — must reset
        inst.hide_viewport = False
        bpy.context.collection.objects.link(inst)

        jitter = 0.4
        inst.location = (
            p["x"] + rng.uniform(-jitter, jitter),
            p["y"] + rng.uniform(-jitter, jitter),
            0.0,
        )
        inst.rotation_euler[2] = rng.uniform(0, 2 * math.pi)

        # Slight height randomness
        scale = 1.0 + rng.uniform(-0.15, 0.15)
        inst.scale = (scale, scale, scale)
        counts[zone] += 1

    total = sum(counts.values())
    print(f"  Crops: {total} instances  "
          f"(stressed={counts[0]}  moderate={counts[1]}  healthy={counts[2]})")


# ── 3. Field border ───────────────────────────────────────────────────────────

def add_field_border(data):
    """Low dirt berm around the perimeter — gives the field a grounded look."""
    W, H = data["scene"]["width_m"], data["scene"]["height_m"]
    margin = 15
    bpy.ops.mesh.primitive_plane_add(size=1, location=(W / 2, H / 2, -0.1))
    apron = bpy.context.active_object
    apron.name = "FieldApron"
    apron.scale = (W + margin * 2, H + margin * 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    apron.data.materials.append(
        make_mat("DirtMat", (0.55, 0.42, 0.28), roughness=0.95)
    )


# ── 4. Cameras ────────────────────────────────────────────────────────────────

def _add_camera(name, location, target, lens_mm):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = lens_mm
    direction = Vector(target) - Vector(location)
    rot = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()
    return cam


def setup_cameras(data):
    W = data["scene"]["width_m"]
    H = data["scene"]["height_m"]
    cx, cy = W / 2, H / 2

    hero = _add_camera(
        "Cam_Hero",
        location=(-30, -20, 35),
        target=(cx, cy * 0.6, 0),
        lens_mm=35,
    )
    _add_camera(
        "Cam_Aerial",
        location=(cx, cy, 160),
        target=(cx, cy, 0),
        lens_mm=28,
    )
    _add_camera(
        "Cam_Detail",
        location=(cx * 0.3, cy * 0.2, 12),
        target=(cx * 0.5, cy * 0.4, 0),
        lens_mm=50,
    )

    bpy.context.scene.camera = hero
    print("  Cameras: Hero 35mm, Aerial 28mm, Detail 50mm")


# ── 5. Lighting ────────────────────────────────────────────────────────────────

def setup_lighting():
    # Midday summer sun over Kansas
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 100))
    sun = bpy.context.active_object
    sun.name = "Sun"
    el = math.radians(62)
    az = math.radians(180)
    sun.rotation_euler[0] = math.pi / 2 - el
    sun.rotation_euler[2] = -az
    sun.data.energy = 4.0
    sun.data.color  = (1.0, 0.98, 0.92)
    sun.data.angle  = math.radians(0.5)

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg  = nt.nodes.new("ShaderNodeBackground")

    if HDRI_PATH.exists():
        env   = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(HDRI_PATH))
        coord = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value[2] = math.radians(90)
        nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"],  env.inputs["Vector"])
        nt.links.new(env.outputs["Color"],       bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.2
        print(f"  Lighting: sun + HDRI ({HDRI_PATH.name})")
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "HOSEK_WILKIE"
        sky.sun_direction = (
            math.cos(el) * math.sin(az),
            math.cos(el) * math.cos(az),
            math.sin(el),
        )
        sky.turbidity = 3.0
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.0
        print("  Lighting: sun + Hosek-Wilkie (HDRI not found)")

    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


# ── 6. Render settings ────────────────────────────────────────────────────────

def configure_render():
    scn = bpy.context.scene
    scn.render.engine              = "CYCLES"
    scn.cycles.device              = "CPU"
    scn.cycles.samples             = 128
    scn.cycles.use_denoising       = True
    scn.render.resolution_x        = 1920
    scn.render.resolution_y        = 1080
    scn.render.resolution_percentage = 100
    scn.render.filepath            = str(RAW_RENDER)
    scn.render.image_settings.file_format = "PNG"
    try:
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "NONE"
    except Exception:
        pass


# ── 7. GLB export ─────────────────────────────────────────────────────────────

def export_glb():
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
        export_normals=True,
        export_texcoords=True,
        export_cameras=True,
        export_lights=False,
    )
    print(f"  Saved GLB  → {GLB_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  CropSight — 3D Blender Scene")
    print("=" * 52)

    with open(DATA_JSON) as f:
        data = json.load(f)

    m = data["metrics"]
    print(f"  Region : {data['region']['name']}")
    print(f"  Source : {data['source']}")
    print(f"  Scene  : {data['scene']['width_m']} × {data['scene']['height_m']} m")
    print(f"  Crops  : {len(data['crop_positions'])} instances")

    clear_scene()
    create_terrain(data)
    add_field_border(data)
    add_crop_rows(data)
    setup_cameras(data)
    setup_lighting()
    configure_render()

    # Save .blend
    BLEND_FILE.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"\n  Saved .blend → {BLEND_FILE}")

    # Export GLB
    export_glb()

    # Render
    print("  Rendering hero shot …")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved render → {RAW_RENDER}")


if __name__ == "__main__":
    main()
