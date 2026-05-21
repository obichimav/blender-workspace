"""
ForestWatch — build_scene.py

Builds a 3D terrain scene in Blender for each year 2018–2023.
- Subdivided plane displaced by NDVI height map (forest canopy illusion)
- NDVI RGB colour texture changes per year
- Sun + HDRI lighting
- Six renders saved to output/render_{year}.png
- GLB exported from the final (2023) state

Headless usage:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py -- /path/to/forestwatch
"""
import sys
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def _root():
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra:
            return Path(extra[0]).resolve()
    return Path(__file__).resolve().parent.parent


ROOT      = _root()
DATA_DIR  = ROOT / "data"
HDRI_PATH = ROOT / "assets" / "hdri" / "rural_landscape_2k.hdr"
OUT_DIR   = ROOT / "output"
YEARS     = [2018, 2019, 2020, 2021, 2022, 2023]

# Scene dimensions (10 km × 10 km study area mapped to 40 Blender units)
SCENE_SIZE  = 40.0
TERRAIN_H   = 1.8     # max displacement height (canopy illusion)
SUBDIVISONS = 256     # terrain mesh resolution


# ── Scene setup ───────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                bpy.data.materials, bpy.data.images, bpy.data.textures):
        for blk in list(col):
            col.remove(blk)


# ── Terrain mesh ──────────────────────────────────────────────────────────────

def build_terrain():
    """
    Creates a subdivided grid plane. Displacement is applied via a Displace
    modifier driven by the NDVI greyscale heightmap — high NDVI (forest) raises
    the surface, giving a canopy-height illusion.
    """
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=SUBDIVISONS,
        y_subdivisions=SUBDIVISONS,
        size=SCENE_SIZE,
        location=(0, 0, 0),
    )
    terrain = bpy.context.active_object
    terrain.name = "Terrain"
    return terrain


def add_displacement(terrain, ndvi_path):
    """Apply a Displace modifier using the NDVI greyscale as height map."""
    # Remove any previous displace modifier
    for mod in list(terrain.modifiers):
        if mod.type == "DISPLACE":
            terrain.modifiers.remove(mod)

    tex = bpy.data.textures.new("NDVIDisplace", type="IMAGE")
    img = bpy.data.images.load(str(ndvi_path))
    img.colorspace_settings.name = "Non-Color"
    tex.image = img

    mod = terrain.modifiers.new("Displace", type="DISPLACE")
    mod.texture        = tex
    mod.texture_coords = "UV"
    mod.strength       = TERRAIN_H
    mod.mid_level      = 0.0
    return mod


# ── NDVI material ─────────────────────────────────────────────────────────────

def _ndvi_colorramp(nt, ndvi_tex_node):
    """
    Wire: NDVITex → ColorRamp (forest palette) → BSDF Base Color
    Returns the ColorRamp node.
    """
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    elems = ramp.color_ramp.elements

    # 0.00 – road / water
    elems[0].position = 0.00
    elems[0].color    = (0.18, 0.14, 0.10, 1.0)
    # 0.15 – bare soil / recent clearing
    e = elems.new(0.15)
    e.color = (0.72, 0.55, 0.30, 1.0)
    # 0.35 – pasture / degraded
    e = elems.new(0.35)
    e.color = (0.62, 0.68, 0.22, 1.0)
    # 0.55 – secondary growth
    e = elems.new(0.55)
    e.color = (0.22, 0.52, 0.18, 1.0)
    # 1.00 – dense primary forest
    elems[1].position = 1.00
    elems[1].color    = (0.04, 0.30, 0.06, 1.0)

    nt.links.new(ndvi_tex_node.outputs["Color"], ramp.inputs["Fac"])
    return ramp


def build_material(ndvi_rgb_path):
    """PBR terrain material driven by NDVI RGB image."""
    mat = bpy.data.materials.new("TerrainMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    tex   = nt.nodes.new("ShaderNodeTexImage")

    img = bpy.data.images.load(str(ndvi_rgb_path))
    img.colorspace_settings.name = "sRGB"
    tex.image = img

    nt.links.new(coord.outputs["UV"],       tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"],      bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Metallic"].default_value  = 0.0
    nt.links.new(bsdf.outputs["BSDF"],     out.inputs["Surface"])

    return mat


def swap_material_image(terrain, ndvi_rgb_path):
    """Swap the NDVI RGB texture on the existing terrain material."""
    mat = terrain.data.materials[0]
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE":
            img = bpy.data.images.load(str(ndvi_rgb_path))
            img.colorspace_settings.name = "sRGB"
            node.image = img
            break


# ── Forest particle layer ─────────────────────────────────────────────────────

def add_forest_markers(terrain):
    """
    Lightweight forest canopy markers: a cone template instanced via a
    Particle System on high-NDVI vertices (visual density indicator only,
    not physics). Skipped if no particle support in headless Cycles.
    Uses manual object placement instead for reliability.
    """
    pass   # Reserved for future enhancement


# ── Border frame (annotation) ─────────────────────────────────────────────────

def add_year_plane(year):
    """Thin coloured strip along the near edge to colour-code the year."""
    colours = {
        2018: (0.08, 0.45, 0.12),
        2019: (0.18, 0.52, 0.10),
        2020: (0.55, 0.55, 0.08),
        2021: (0.65, 0.38, 0.06),
        2022: (0.70, 0.22, 0.04),
        2023: (0.72, 0.10, 0.02),
    }
    col = colours.get(year, (0.5, 0.5, 0.5))
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, -(SCENE_SIZE / 2 + 0.4), 0.05),
    )
    strip = bpy.context.active_object
    strip.scale = (SCENE_SIZE / 2, 0.15, 0.05)
    bpy.ops.object.transform_apply(scale=True)
    strip.name = f"YearStrip_{year}"
    mat = bpy.data.materials.new(f"YearCol_{year}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value  = (*col, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 2.0
    strip.data.materials.append(mat)
    return strip


# ── Lighting ──────────────────────────────────────────────────────────────────

def setup_lighting():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 60))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.rotation_euler[0] = math.radians(52)
    sun.rotation_euler[2] = math.radians(-38)
    sun.data.energy = 5.0
    sun.data.color  = (1.0, 0.97, 0.88)
    sun.data.angle  = math.radians(0.6)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg  = nt.nodes.new("ShaderNodeBackground")

    if HDRI_PATH.exists():
        env     = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(HDRI_PATH))
        coord   = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value[2] = math.radians(200)
        nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"],  env.inputs["Vector"])
        nt.links.new(env.outputs["Color"],       bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.6
        print(f"  Lighting: HDRI ({HDRI_PATH.name})")
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "HOSEK_WILKIE"
        sky.turbidity = 4.0
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        print("  Lighting: Hosek-Wilkie")

    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


# ── Camera ────────────────────────────────────────────────────────────────────

def setup_camera():
    bpy.ops.object.camera_add(location=(-18, -32, 28))
    cam = bpy.context.active_object
    cam.name = "Cam_Hero"
    cam.data.lens = 50
    target = Vector((2, 2, 0))
    d = target - Vector(cam.location)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


# ── Render ────────────────────────────────────────────────────────────────────

def configure_render():
    scn = bpy.context.scene
    scn.render.engine        = "CYCLES"
    scn.cycles.device        = "CPU"
    scn.cycles.samples       = 96
    scn.cycles.use_denoising = True
    scn.render.resolution_x  = 1920
    scn.render.resolution_y  = 1080
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = "PNG"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 56)
    print("  ForestWatch — Amazon Deforestation NDVI Time-Lapse")
    print("=" * 56)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    clear_scene()
    terrain = build_terrain()

    # Initial material (2018)
    ndvi_rgb_2018 = DATA_DIR / "ndvi_rgb_2018.png"
    mat = build_material(ndvi_rgb_2018)
    terrain.data.materials.append(mat)

    setup_lighting()
    setup_camera()
    configure_render()

    year_strips = {}

    for i, year in enumerate(YEARS):
        print(f"\n  Year {year} …")

        # Swap NDVI RGB texture
        ndvi_rgb_path = DATA_DIR / f"ndvi_rgb_{year}.png"
        ndvi_gray_path = DATA_DIR / f"ndvi_{year}.png"

        if i == 0:
            pass   # material already built with 2018 texture
        else:
            swap_material_image(terrain, ndvi_rgb_path)

        # Swap displacement map
        add_displacement(terrain, ndvi_gray_path)

        # Year indicator strip (remove previous)
        for strip in year_strips.values():
            bpy.data.objects.remove(strip, do_unlink=True)
        year_strips.clear()
        year_strips[year] = add_year_plane(year)

        render_path = OUT_DIR / f"render_{year}.png"
        bpy.context.scene.render.filepath = str(render_path)
        bpy.ops.render.render(write_still=True)
        print(f"  Rendered → {render_path.name}")

    # Export GLB from final state (2023)
    blend_path = OUT_DIR / "forestwatch_scene.blend"
    glb_path   = OUT_DIR / "forestwatch_scene.glb"

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
        export_normals=True,
        export_texcoords=True,
        export_cameras=True,
        export_lights=False,
    )
    print(f"\n  Saved .blend → {blend_path.name}")
    print(f"  Saved .glb   → {glb_path.name}")
    print("\n  ForestWatch render complete.")


if __name__ == "__main__":
    main()
