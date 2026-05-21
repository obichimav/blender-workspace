"""
WaterSight — Blender scene builder.
Real terrain displaced by AWS elevation tiles + satellite imagery texture.
Renders TWO states: before (full pool 2000) and after (drought 2022).

Headless usage:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py \
        -- /path/to/watersight
"""
import sys
import json
import math
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


ROOT = _project_root()

DATA_JSON      = ROOT / "output"   / "data.json"
HEIGHTMAP_PNG  = ROOT / "data"     / "heightmap.png"
SATELLITE_PNG  = ROOT / "data"     / "satellite.png"
HDRI_PATH      = ROOT / "assets"   / "hdri"     / "kloofendal_48d_partly_cloudy_2k.hdr"
ROCK_DIFF      = ROOT / "assets"   / "textures" / "rock_ground_02_diff_2k.png"
ROCK_ROUGH     = ROOT / "assets"   / "textures" / "rock_ground_02_rough_2k.png"
CRACKED_DIFF   = ROOT / "assets"   / "textures" / "mud_cracked_dry_03_diff_2k.png"
BLEND_FILE     = ROOT / "output"   / "watersight_scene.blend"
RENDER_BEFORE  = ROOT / "output"   / "render_before.png"
RENDER_AFTER   = ROOT / "output"   / "render_after.png"
GLB_PATH       = ROOT / "output"   / "watersight_scene.glb"

SCENE_SIZE_M   = 120.0    # Blender world units = metres
ELEVATION_EXAG = 3.0      # vertical exaggeration for visual impact


# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                bpy.data.materials, bpy.data.images, bpy.data.textures):
        for blk in list(col):
            col.remove(blk)


# ── 1. Terrain ─────────────────────────────────────────────────────────────────

def create_terrain(data):
    elev_min = data["terrain"]["elev_min_m"]
    elev_max = data["terrain"]["elev_max_m"]
    elev_range = elev_max - elev_min
    S = SCENE_SIZE_M

    # Subdivided plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(S / 2, S / 2, 0))
    terrain = bpy.context.active_object
    terrain.name = "Terrain"
    terrain.scale = (S, S, 1)
    bpy.ops.object.transform_apply(scale=True)

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(terrain.data)
    for _ in range(8):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=1, use_grid_fill=True)
    bmesh.update_edit_mesh(terrain.data)
    bpy.ops.object.mode_set(mode="OBJECT")

    # ── Terrain material — satellite imagery base ─────────────────────────────
    mat = bpy.data.materials.new("TerrainMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")

    if SATELLITE_PNG.exists():
        sat_tex = nt.nodes.new("ShaderNodeTexImage")
        sat_tex.image = bpy.data.images.load(str(SATELLITE_PNG))
        sat_tex.image.colorspace_settings.name = "sRGB"
        nt.links.new(coord.outputs["UV"], sat_tex.inputs["Vector"])
        nt.links.new(sat_tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        # Fallback: red sandstone colour
        bsdf.inputs["Base Color"].default_value = (0.65, 0.30, 0.12, 1.0)

    bsdf.inputs["Roughness"].default_value = 0.85
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    terrain.data.materials.append(mat)

    # ── DEM displacement ───────────────────────────────────────────────────────
    dem_img = bpy.data.images.load(str(HEIGHTMAP_PNG))
    dem_img.colorspace_settings.name = "Non-Color"
    dem_tex = bpy.data.textures.new("DEMTex", type="IMAGE")
    dem_tex.image = dem_img

    mod = terrain.modifiers.new("DEM", type="DISPLACE")
    mod.texture         = dem_tex
    mod.strength        = elev_range / SCENE_SIZE_M * SCENE_SIZE_M * ELEVATION_EXAG / 100
    mod.texture_coords  = "UV"
    mod.direction       = "Z"

    # Apply displacement so water planes can intersect correctly
    bpy.ops.object.modifier_apply(modifier="DEM")

    print(f"  Terrain: {int(SCENE_SIZE_M)}m × {int(SCENE_SIZE_M)}m  "
          f"elev {elev_min:.0f}–{elev_max:.0f} m  exag×{ELEVATION_EXAG}")
    return terrain


# ── 2. Water plane ────────────────────────────────────────────────────────────

def _water_z(norm_level, data):
    """Convert normalised water level to Blender Z coordinate."""
    elev_range = data["terrain"]["elev_max_m"] - data["terrain"]["elev_min_m"]
    return norm_level * elev_range / 100 * ELEVATION_EXAG


def make_water_material(name="WaterMat"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out  = nt.nodes.new("ShaderNodeOutputMaterial")
    mix  = nt.nodes.new("ShaderNodeMixShader")

    # Refraction — depth colour
    refr = nt.nodes.new("ShaderNodeBsdfRefraction")
    refr.inputs["Color"].default_value = (0.03, 0.18, 0.38, 1.0)
    refr.inputs["IOR"].default_value   = 1.333
    refr.inputs["Roughness"].default_value = 0.02

    # Glossy — surface reflections
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Color"].default_value    = (0.85, 0.92, 1.00, 1.0)
    gloss.inputs["Roughness"].default_value = 0.03

    # Fresnel mixing
    fresnel = nt.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.333

    nt.links.new(fresnel.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(refr.outputs["BSDF"],   mix.inputs[1])
    nt.links.new(gloss.outputs["BSDF"],  mix.inputs[2])
    nt.links.new(mix.outputs["Shader"],  out.inputs["Surface"])

    mat.blend_method = "BLEND"
    return mat


def create_water_plane(z_pos, name="WaterPlane"):
    S = SCENE_SIZE_M
    bpy.ops.mesh.primitive_plane_add(size=S, location=(S / 2, S / 2, z_pos))
    plane = bpy.context.active_object
    plane.name = name
    plane.data.materials.append(make_water_material(f"{name}Mat"))
    return plane


# ── 3. Exposed lake bed (bathtub ring) ────────────────────────────────────────

def make_exposed_bed_material():
    """White mineral deposits + cracked mud — the 'bathtub ring' look."""
    mat = bpy.data.materials.new("ExposedBedMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (8, 8, 8)   # tile the texture

    if CRACKED_DIFF.exists():
        crack_tex = nt.nodes.new("ShaderNodeTexImage")
        crack_tex.image = bpy.data.images.load(str(CRACKED_DIFF))
        crack_tex.image.colorspace_settings.name = "sRGB"
        nt.links.new(coord.outputs["UV"],        mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"],  crack_tex.inputs["Vector"])
        nt.links.new(crack_tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.82, 0.78, 0.68, 1.0)

    bsdf.inputs["Roughness"].default_value = 0.9
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ── 4. Cameras ────────────────────────────────────────────────────────────────

def setup_cameras():
    S = SCENE_SIZE_M
    cx, cy = S / 2, S / 2

    def add_cam(name, loc, target, lens):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = name
        cam.data.lens = lens
        d = Vector(target) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return cam

    hero = add_cam("Cam_Hero",   (-15, -12, 28),  (cx, cy * 0.7, 0), 35)
    add_cam("Cam_Aerial",        (cx, cy, 120),   (cx, cy, 0),       28)
    add_cam("Cam_Canyon",        (cx * 0.3, cy * 0.2, 8), (cx, cy, 0), 50)
    bpy.context.scene.camera = hero
    print("  Cameras: Hero 35mm, Aerial 28mm, Canyon 50mm")


# ── 5. Lighting ────────────────────────────────────────────────────────────────

def setup_lighting():
    # Harsh midday Utah desert sun
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 100))
    sun = bpy.context.active_object
    sun.name = "Sun"
    el = math.radians(68)
    az = math.radians(200)
    sun.rotation_euler[0] = math.pi / 2 - el
    sun.rotation_euler[2] = -az
    sun.data.energy = 5.0
    sun.data.color  = (1.0, 0.96, 0.88)   # warm desert sun
    sun.data.angle  = math.radians(0.5)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
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
        mapping.inputs["Rotation"].default_value[2] = math.radians(45)
        nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"],  env.inputs["Vector"])
        nt.links.new(env.outputs["Color"],       bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.3
        print(f"  Lighting: desert sun + HDRI ({HDRI_PATH.name})")
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "HOSEK_WILKIE"
        sky.sun_direction = (
            math.cos(el) * math.sin(az),
            math.cos(el) * math.cos(az),
            math.sin(el),
        )
        sky.turbidity = 2.0
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.0
        print("  Lighting: desert sun + Hosek-Wilkie (HDRI not found)")

    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


# ── 6. Render ─────────────────────────────────────────────────────────────────

def configure_render():
    scn = bpy.context.scene
    scn.render.engine          = "CYCLES"
    scn.cycles.device          = "CPU"
    scn.cycles.samples         = 128
    scn.cycles.use_denoising   = True
    scn.render.resolution_x    = 1920
    scn.render.resolution_y    = 1080
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = "PNG"
    try:
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "NONE"
    except Exception:
        pass


def render_state(filepath):
    bpy.context.scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered → {filepath}")


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
    print(f"  Saved GLB → {GLB_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  WaterSight — Blender Scene")
    print("=" * 52)

    with open(DATA_JSON) as f:
        data = json.load(f)

    s = data["stats"]
    print(f"  Location : {data['location']['name']}")
    print(f"  Water drop: {s['water_drop_m']:.0f} m  "
          f"({s['pct_water_lost']:.0f}% surface lost)")

    clear_scene()
    terrain = create_terrain(data)
    setup_cameras()
    setup_lighting()
    configure_render()

    # ── Compute water plane Z positions ───────────────────────────────────────
    elev_min = data["terrain"]["elev_min_m"]
    elev_max = data["terrain"]["elev_max_m"]
    elev_range = elev_max - elev_min

    def elev_to_z(level_m):
        """Map real elevation to Blender Z using same formula as displacement."""
        return (level_m - elev_min) / elev_range * elev_range / 100 * ELEVATION_EXAG

    z_before = elev_to_z(data["water_levels"]["before_m"])
    z_after  = elev_to_z(data["water_levels"]["after_m"])
    print(f"  Water planes: before Z={z_before:.2f}  after Z={z_after:.2f}")

    # ── BEFORE render — full pool ─────────────────────────────────────────────
    water_before = create_water_plane(z_before, "WaterBefore")
    print(f"\n  Rendering BEFORE (full pool {data['water_levels']['before_m']:.0f} m) …")
    render_state(RENDER_BEFORE)

    # ── AFTER render — drought ────────────────────────────────────────────────
    # Lower the water plane
    water_before.location.z = z_after
    water_before.name = "WaterAfter"

    # Add exposed lake bed ring mesh (a flat plane between the two water levels)
    # Placed just above terrain, between z_after and z_before
    ring_z = (z_before + z_after) / 2
    bpy.ops.mesh.primitive_plane_add(
        size=SCENE_SIZE_M, location=(SCENE_SIZE_M / 2, SCENE_SIZE_M / 2, ring_z)
    )
    ring = bpy.context.active_object
    ring.name = "BathtubRing"
    ring.data.materials.append(make_exposed_bed_material())

    print(f"\n  Rendering AFTER  (drought {data['water_levels']['after_m']:.0f} m) …")
    render_state(RENDER_AFTER)

    # ── Save ──────────────────────────────────────────────────────────────────
    BLEND_FILE.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"\n  Saved .blend → {BLEND_FILE}")

    export_glb()
    print("  Scene complete.")


if __name__ == "__main__":
    main()
