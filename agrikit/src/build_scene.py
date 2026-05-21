"""
AgriKit — Modular Agricultural Asset Pack
Procedurally builds 6 farm assets in a single Blender scene:
  1. Grain silo    (corrugated steel + cone roof + ladder)
  2. Red barn      (gambrel roof + wood plank walls)
  3. Water tower   (elevated tank + lattice legs)
  4. Greenhouse    (glass + metal frame)
  5. Center pivot  (irrigation arm on wheels)
  6. Hay bales     (round bales + straw texture)

All assets use Polyhaven PBR textures, assembled into a hero farm scene.

Headless usage:
    /Applications/Blender.app/Contents/MacOS/Blender \
        --background --python src/build_scene.py \
        -- /path/to/agrikit
"""
import sys
import math
import random
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

def _root():
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra:
            return Path(extra[0]).resolve()
    return Path(__file__).resolve().parent.parent

ROOT     = _root()
TEX_DIR  = ROOT / "assets" / "textures"
HDRI_PATH = ROOT / "assets" / "hdri" / "rural_landscape_2k.hdr"
BLEND_OUT = ROOT / "output" / "agrikit_scene.blend"
GLB_OUT   = ROOT / "output" / "agrikit_scene.glb"
RENDER_HERO    = ROOT / "output" / "render_hero.png"
RENDER_AERIAL  = ROOT / "output" / "render_aerial.png"
RENDER_ASSETS  = ROOT / "output" / "render_assets.png"


# ── Material helpers ───────────────────────────────────────────────────────────

def _load_tex(slug, map_type, colorspace="Non-Color"):
    path = TEX_DIR / f"{slug}_{map_type}_2k.png"
    if not path.exists():
        return None
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "sRGB" if map_type == "diff" else "Non-Color"
    return img


def pbr_mat(name, slug, scale=4.0, roughness_fac=1.0, metallic=0.0, tint=None):
    """Full PBR material: diffuse + normal + roughness from Polyhaven textures."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(coord.outputs["UV"], mapping.inputs["Vector"])

    bsdf.inputs["Metallic"].default_value = metallic

    diff_img = _load_tex(slug, "diff")
    if diff_img:
        diff = nt.nodes.new("ShaderNodeTexImage")
        diff.image = diff_img
        diff.image.colorspace_settings.name = "sRGB"
        nt.links.new(mapping.outputs["Vector"], diff.inputs["Vector"])
        if tint:
            mix = nt.nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs["Fac"].default_value = 0.6
            mix.inputs[2].default_value = (*tint, 1.0)
            nt.links.new(diff.outputs["Color"], mix.inputs[1])
            nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            nt.links.new(diff.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)

    nor_img = _load_tex(slug, "nor_gl")
    if nor_img:
        nor = nt.nodes.new("ShaderNodeTexImage")
        nor.image = nor_img
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(mapping.outputs["Vector"], nor.inputs["Vector"])
        nt.links.new(nor.outputs["Color"],      nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"],    bsdf.inputs["Normal"])

    rough_img = _load_tex(slug, "rough")
    if rough_img:
        rough = nt.nodes.new("ShaderNodeTexImage")
        rough.image = rough_img
        if roughness_fac != 1.0:
            fac_node = nt.nodes.new("ShaderNodeMath")
            fac_node.operation = "MULTIPLY"
            fac_node.inputs[1].default_value = roughness_fac
            nt.links.new(mapping.outputs["Vector"], rough.inputs["Vector"])
            nt.links.new(rough.outputs["Color"], fac_node.inputs[0])
            nt.links.new(fac_node.outputs["Value"], bsdf.inputs["Roughness"])
        else:
            nt.links.new(mapping.outputs["Vector"], rough.inputs["Vector"])
            nt.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.7

    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def glass_mat(name, color=(0.7, 0.9, 0.85)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    mix   = nt.nodes.new("ShaderNodeMixShader")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    trans.inputs["Color"].default_value = (*color, 1.0)
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.05
    fresnel = nt.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.45
    nt.links.new(fresnel.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
    nt.links.new(gloss.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.blend_method = "BLEND"
    return mat


def solid_mat(name, color, roughness=0.5, metallic=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value  = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value   = roughness
    bsdf.inputs["Metallic"].default_value    = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value    = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.5
    return mat


# ── Geometry helpers ───────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                bpy.data.materials, bpy.data.images, bpy.data.textures, bpy.data.curves):
        for blk in list(col):
            col.remove(blk)


def _apply(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def _set_smooth(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(60))


def _add_subsurf(obj, levels=2):
    mod = obj.modifiers.new("Subsurf", type="SUBSURF")
    mod.levels = levels
    mod.render_levels = levels


def join_objects(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    bpy.context.active_object.name = name
    return bpy.context.active_object


# ── 1. GRAIN SILO ─────────────────────────────────────────────────────────────

def build_silo(location=(0, 0, 0)):
    parts = []
    mat_body  = pbr_mat("SiloBody",   "corrugated_iron", scale=8.0, metallic=0.3)
    mat_roof  = pbr_mat("SiloRoof",   "metal_plate",     scale=4.0, metallic=0.6,
                        roughness_fac=0.5)
    mat_rust  = pbr_mat("SiloRust",   "rusty_metal_02",  scale=6.0, metallic=0.5)

    # Main cylindrical body
    bpy.ops.mesh.primitive_cylinder_add(
        radius=2.2, depth=10.0, vertices=32, location=(0, 0, 5.0))
    body = bpy.context.active_object
    body.name = "SiloBody"
    body.data.materials.append(mat_body)
    _set_smooth(body)
    parts.append(body)

    # Conical roof
    bpy.ops.mesh.primitive_cone_add(
        radius1=2.4, radius2=0.15, depth=2.5, vertices=32, location=(0, 0, 11.25))
    roof = bpy.context.active_object
    roof.name = "SiloRoof"
    roof.data.materials.append(mat_roof)
    _set_smooth(roof)
    parts.append(roof)

    # Hopper bottom cone
    bpy.ops.mesh.primitive_cone_add(
        radius1=1.4, radius2=2.2, depth=2.0, vertices=32, location=(0, 0, -0.5))
    hopper = bpy.context.active_object
    hopper.name = "SiloHopper"
    hopper.data.materials.append(mat_rust)
    _set_smooth(hopper)
    parts.append(hopper)

    # Base ring
    bpy.ops.mesh.primitive_torus_add(
        major_radius=2.3, minor_radius=0.12, location=(0, 0, 0.1))
    ring = bpy.context.active_object
    ring.name = "SiloRing"
    ring.data.materials.append(mat_rust)
    parts.append(ring)

    # Ladder rungs
    rng = random.Random(1)
    for i in range(12):
        z = 1.0 + i * 0.85
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.04, depth=0.5, location=(2.25, 0, z))
        rung = bpy.context.active_object
        rung.rotation_euler[1] = math.pi / 2
        bpy.ops.object.transform_apply(rotation=True)
        rung.data.materials.append(mat_rust)
        parts.append(rung)

    # Ladder rails
    for dx in (-0.22, 0.22):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.03, depth=11.0, location=(2.25 + dx * 0.5, 0, 5.5))
        rail = bpy.context.active_object
        rail.data.materials.append(mat_rust)
        parts.append(rail)

    # Move entire silo to location
    for p in parts:
        p.location.x += location[0]
        p.location.y += location[1]
        p.location.z += location[2]

    print("  ✓ Grain silo")
    return parts


# ── 2. RED BARN ───────────────────────────────────────────────────────────────

def build_barn(location=(0, 0, 0)):
    parts = []
    mat_wall  = pbr_mat("BarnWall",   "old_planks_02",  scale=3.0,
                        tint=(0.72, 0.15, 0.08))       # classic red barn
    mat_trim  = solid_mat("BarnTrim",  (0.95, 0.94, 0.88), roughness=0.8)
    mat_roof  = pbr_mat("BarnRoof",   "corrugated_iron", scale=5.0, metallic=0.2,
                        tint=(0.25, 0.22, 0.20))
    mat_door  = pbr_mat("BarnDoor",   "old_planks_02",  scale=2.0,
                        tint=(0.50, 0.10, 0.06))
    mat_found = pbr_mat("BarnFound",  "concrete_wall_005", scale=2.0)

    W, D, H = 8.0, 5.0, 5.0   # width, depth, wall height

    # Concrete foundation
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.3))
    found = bpy.context.active_object
    found.scale = (W / 2 + 0.2, D / 2 + 0.2, 0.3)
    bpy.ops.object.transform_apply(scale=True)
    found.data.materials.append(mat_found)
    parts.append(found)

    # Main walls (box body)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H / 2 + 0.6))
    walls = bpy.context.active_object
    walls.scale = (W / 2, D / 2, H / 2)
    bpy.ops.object.transform_apply(scale=True)
    walls.data.materials.append(mat_wall)
    parts.append(walls)

    # Gambrel roof — two slopes per side via mesh
    bm = bmesh.new()
    ridge_h = H + 3.2
    mid_h   = H + 1.8
    mid_w   = W / 2 * 0.55

    verts = [
        bm.verts.new((-W/2,  D/2, H + 0.6)),
        bm.verts.new(( W/2,  D/2, H + 0.6)),
        bm.verts.new(( W/2, -D/2, H + 0.6)),
        bm.verts.new((-W/2, -D/2, H + 0.6)),
        bm.verts.new((-mid_w,  D/2, mid_h + 0.6)),
        bm.verts.new(( mid_w,  D/2, mid_h + 0.6)),
        bm.verts.new(( mid_w, -D/2, mid_h + 0.6)),
        bm.verts.new((-mid_w, -D/2, mid_h + 0.6)),
        bm.verts.new((0,  D/2, ridge_h + 0.6)),
        bm.verts.new((0, -D/2, ridge_h + 0.6)),
    ]
    faces = [
        [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7],  # lower slopes
        [4,5,8],   [5,6,9,8], [6,7,9],   [7,4,8,9],  # upper slopes
        [8,9,6,5], [0,1,2,3],                          # ridge + floor
    ]
    bm.verts.ensure_lookup_table()
    for f in faces:
        try:
            bm.faces.new([verts[i] for i in f])
        except Exception:
            pass
    me = bpy.data.meshes.new("BarnRoofMesh")
    bm.to_mesh(me)
    bm.free()
    roof_obj = bpy.data.objects.new("BarnRoof", me)
    bpy.context.collection.objects.link(roof_obj)
    roof_obj.data.materials.append(mat_roof)
    parts.append(roof_obj)

    # White trim strips (horizontal boards)
    for z in [0.6, H * 0.33 + 0.6, H * 0.66 + 0.6, H + 0.6]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
        trim = bpy.context.active_object
        trim.scale = (W / 2 + 0.05, D / 2 + 0.05, 0.08)
        bpy.ops.object.transform_apply(scale=True)
        trim.data.materials.append(mat_trim)
        parts.append(trim)

    # Barn doors (front face)
    for dx in (-1.5, 1.5):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(dx, -D / 2 - 0.05, H * 0.35 + 0.6))
        door = bpy.context.active_object
        door.scale = (1.35, 0.05, H * 0.35)
        bpy.ops.object.transform_apply(scale=True)
        door.data.materials.append(mat_door)
        parts.append(door)

    for p in parts:
        p.location.x += location[0]
        p.location.y += location[1]
        p.location.z += location[2]

    print("  ✓ Red barn")
    return parts


# ── 3. WATER TOWER ────────────────────────────────────────────────────────────

def build_water_tower(location=(0, 0, 0)):
    parts = []
    mat_tank = pbr_mat("TankMetal", "metal_plate",    scale=5.0, metallic=0.7,
                       roughness_fac=0.6)
    mat_leg  = pbr_mat("TankLeg",   "rusty_metal_02", scale=4.0, metallic=0.5)
    mat_band = solid_mat("TankBand", (0.15, 0.15, 0.15), metallic=0.8, roughness=0.3)

    # Tank body (cylinder)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=1.8, depth=3.0, vertices=32, location=(0, 0, 12.0))
    tank = bpy.context.active_object
    tank.name = "WaterTank"
    tank.data.materials.append(mat_tank)
    _set_smooth(tank)
    parts.append(tank)

    # Domed top
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=1.82, location=(0, 0, 13.6))
    dome = bpy.context.active_object
    dome.scale.z = 0.55
    bpy.ops.object.transform_apply(scale=True)
    dome.data.materials.append(mat_tank)
    _set_smooth(dome)
    parts.append(dome)

    # Steel bands around tank
    for z in [11.0, 12.0, 13.0]:
        bpy.ops.mesh.primitive_torus_add(
            major_radius=1.85, minor_radius=0.06, location=(0, 0, z))
        band = bpy.context.active_object
        band.data.materials.append(mat_band)
        parts.append(band)

    # 6 angled support legs
    for i in range(6):
        angle = math.radians(i * 60)
        bx = math.cos(angle) * 1.4
        by = math.sin(angle) * 1.4
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.09, depth=12.5, location=(bx * 0.5, by * 0.5, 6.0))
        leg = bpy.context.active_object
        # Angle leg outward
        dx = bx * 0.08
        dy = by * 0.08
        leg.rotation_euler[0] = math.atan2(by * 0.08, 12.5)
        leg.rotation_euler[1] = -math.atan2(bx * 0.08, 12.5)
        leg.data.materials.append(mat_leg)
        parts.append(leg)

    # Cross bracing rings
    for z in [3.5, 7.5]:
        bpy.ops.mesh.primitive_torus_add(
            major_radius=1.5, minor_radius=0.05, location=(0, 0, z))
        brace = bpy.context.active_object
        brace.data.materials.append(mat_leg)
        parts.append(brace)

    # Outlet pipe
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.12, depth=4.0, location=(0, 1.85, 10.0))
    pipe = bpy.context.active_object
    pipe.rotation_euler[0] = math.pi / 2
    bpy.ops.object.transform_apply(rotation=True)
    pipe.data.materials.append(mat_leg)
    parts.append(pipe)

    for p in parts:
        p.location.x += location[0]
        p.location.y += location[1]
        p.location.z += location[2]

    print("  ✓ Water tower")
    return parts


# ── 4. GREENHOUSE ─────────────────────────────────────────────────────────────

def build_greenhouse(location=(0, 0, 0)):
    parts = []
    mat_frame = pbr_mat("GHFrame", "metal_plate",    scale=3.0, metallic=0.8,
                        roughness_fac=0.4)
    mat_glass = glass_mat("GHGlass", color=(0.72, 0.88, 0.80))
    mat_found = pbr_mat("GHFound", "concrete_wall_005", scale=2.0)

    W, D, H, RH = 6.0, 12.0, 2.5, 2.0   # width, depth, wall h, ridge add-h

    # Concrete base strip
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(side * (W / 2), 0, 0.2))
        base = bpy.context.active_object
        base.scale = (0.15, D / 2, 0.2)
        bpy.ops.object.transform_apply(scale=True)
        base.data.materials.append(mat_found)
        parts.append(base)

    # Glass side panels
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(side * (W / 2), 0, H / 2))
        panel = bpy.context.active_object
        panel.scale = (0.03, D / 2, H / 2)
        bpy.ops.object.transform_apply(scale=True)
        panel.data.materials.append(mat_glass)
        parts.append(panel)

    # Ridge roof panels (two slopes)
    for side, angle in ((-1, 30), (1, -30)):
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(side * W / 4, 0, H + RH / 2))
        slope = bpy.context.active_object
        slope.scale = (W / 4 / math.cos(math.radians(30)), D / 2, 0.02)
        slope.rotation_euler[1] = math.radians(angle)
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        slope.data.materials.append(mat_glass)
        parts.append(slope)

    # Metal frame ribs (arches along length)
    rib_count = int(D / 1.5) + 1
    for i in range(rib_count):
        y = -D / 2 + i * D / (rib_count - 1)
        for side in (-1, 1):
            # Vertical wall post
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.04, depth=H, location=(side * W / 2, y, H / 2))
            post = bpy.context.active_object
            post.data.materials.append(mat_frame)
            parts.append(post)
            # Roof rafter
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.04,
                depth=math.sqrt((W / 2) ** 2 + RH ** 2),
                location=(side * W / 4, y, H + RH / 2))
            rafter = bpy.context.active_object
            rafter.rotation_euler[1] = math.radians(-30 * side)
            bpy.ops.object.transform_apply(rotation=True)
            rafter.data.materials.append(mat_frame)
            parts.append(rafter)

    for p in parts:
        p.location.x += location[0]
        p.location.y += location[1]
        p.location.z += location[2]

    print("  ✓ Greenhouse")
    return parts


# ── 5. CENTER PIVOT IRRIGATOR ─────────────────────────────────────────────────

def build_pivot(location=(0, 0, 0), arm_length=28.0):
    parts = []
    mat_truss  = pbr_mat("PivotTruss", "metal_plate",    scale=4.0, metallic=0.7,
                         roughness_fac=0.5)
    mat_wheel  = solid_mat("PivotWheel", (0.12, 0.12, 0.12), roughness=0.9)
    mat_pipe   = pbr_mat("PivotPipe",  "rusty_metal_02", scale=5.0, metallic=0.4)

    tower_count = 5
    span = arm_length / tower_count

    # Central pivot column
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.3, depth=4.0, location=(0, 0, 2.0))
    center = bpy.context.active_object
    center.name = "PivotCenter"
    center.data.materials.append(mat_truss)
    parts.append(center)

    # Arm towers + truss spans
    for i in range(tower_count):
        x = (i + 0.5) * span
        tower_h = 3.2

        # A-frame tower
        for dx in (-0.6, 0.6):
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.06, depth=tower_h + 0.5, location=(x + dx * 0.3, 0, tower_h / 2))
            leg = bpy.context.active_object
            leg.rotation_euler[1] = math.atan2(dx * 0.3, tower_h + 0.5) * 0.5
            bpy.ops.object.transform_apply(rotation=True)
            leg.data.materials.append(mat_truss)
            parts.append(leg)

        # Horizontal truss pipe
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.08, depth=span, location=(x + span / 2, 0, tower_h))
        pipe_h = bpy.context.active_object
        pipe_h.rotation_euler[1] = math.pi / 2
        bpy.ops.object.transform_apply(rotation=True)
        pipe_h.data.materials.append(mat_pipe)
        parts.append(pipe_h)

        # Wheel assembly
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.55, minor_radius=0.08, location=(x, 0, 0.6))
        wheel = bpy.context.active_object
        wheel.data.materials.append(mat_wheel)
        parts.append(wheel)

        # Drop pipes (sprinklers)
        for ddx in [span * 0.25, span * 0.75]:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.02, depth=1.2,
                location=(x - span / 2 + ddx, 0, tower_h - 0.6))
            drop = bpy.context.active_object
            drop.data.materials.append(mat_pipe)
            parts.append(drop)

    for p in parts:
        p.location.x += location[0]
        p.location.y += location[1]
        p.location.z += location[2]

    print("  ✓ Center pivot irrigator")
    return parts


# ── 6. HAY BALES ──────────────────────────────────────────────────────────────

def build_hay_bales(locations):
    parts = []
    mat_straw = solid_mat("HayStraw", (0.78, 0.62, 0.22), roughness=0.95)
    mat_wrap  = solid_mat("HayWrap",  (0.20, 0.40, 0.25), roughness=0.7)

    rng = random.Random(42)
    for loc in locations:
        # Round bale — cylinder on its side
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.9, depth=1.2, vertices=24,
            location=(loc[0], loc[1], 0.9))
        bale = bpy.context.active_object
        bale.rotation_euler[0] = math.pi / 2
        bale.rotation_euler[2] = rng.uniform(0, math.pi)
        bpy.ops.object.transform_apply(rotation=True)
        bale.data.materials.append(mat_straw)
        _set_smooth(bale)
        parts.append(bale)

        # Plastic wrap band
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.92, minor_radius=0.06, location=(loc[0], loc[1], 0.9))
        wrap = bpy.context.active_object
        wrap.rotation_euler[0] = math.pi / 2
        bpy.ops.object.transform_apply(rotation=True)
        wrap.data.materials.append(mat_wrap)
        parts.append(wrap)

    print(f"  ✓ {len(locations)} hay bales")
    return parts


# ── 7. GROUND PLANE ───────────────────────────────────────────────────────────

def build_ground(size=120):
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value     = 4.0
    noise.inputs["Detail"].default_value    = 8.0
    noise.inputs["Roughness"].default_value = 0.6

    colorramp = nt.nodes.new("ShaderNodeValToRGB")
    colorramp.color_ramp.elements[0].color = (0.42, 0.35, 0.18, 1.0)   # dry soil
    colorramp.color_ramp.elements[1].color = (0.55, 0.52, 0.28, 1.0)   # dry grass
    colorramp.color_ramp.elements[0].position = 0.3
    colorramp.color_ramp.elements[1].position = 0.7

    nt.links.new(coord.outputs["Generated"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"],       colorramp.inputs["Fac"])
    nt.links.new(colorramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    bpy.ops.mesh.primitive_plane_add(size=size, location=(size * 0.3, size * 0.1, -0.02))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(mat)
    return ground


# ── 8. LIGHTING ───────────────────────────────────────────────────────────────

def setup_lighting():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 60))
    sun = bpy.context.active_object
    sun.name = "Sun"
    el = math.radians(42)
    az = math.radians(155)
    sun.rotation_euler[0] = math.pi / 2 - el
    sun.rotation_euler[2] = -az
    sun.data.energy = 4.5
    sun.data.color  = (1.0, 0.97, 0.90)
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
        coord   = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value[2] = math.radians(80)
        nt.links.new(coord.outputs["Generated"],  mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"],   env.inputs["Vector"])
        nt.links.new(env.outputs["Color"],        bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.1
        print(f"  Lighting: sun + HDRI ({HDRI_PATH.name})")
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "HOSEK_WILKIE"
        sky.turbidity = 3.0
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        print("  Lighting: sun + Hosek-Wilkie")

    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


# ── 9. CAMERAS ────────────────────────────────────────────────────────────────

def setup_cameras():
    def add_cam(name, loc, target, lens):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = name
        cam.data.lens = lens
        d = Vector(target) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return cam

    hero   = add_cam("Cam_Hero",    (-8, -18, 14),   (18, 10, 3),   35)
    aerial = add_cam("Cam_Aerial",  (18, 10, 80),    (18, 10, 0),   28)
    assets = add_cam("Cam_Assets",  (-5, -35, 22),   (18, 8, 4),    28)
    bpy.context.scene.camera = hero
    return hero, aerial, assets


# ── 10. RENDER ────────────────────────────────────────────────────────────────

def configure_render():
    scn = bpy.context.scene
    scn.render.engine        = "CYCLES"
    scn.cycles.device        = "CPU"
    scn.cycles.samples       = 128
    scn.cycles.use_denoising = True
    scn.render.resolution_x  = 1920
    scn.render.resolution_y  = 1080
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = "PNG"


def render_cam(cam_obj, filepath):
    bpy.context.scene.camera = cam_obj
    bpy.context.scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered {cam_obj.name} → {filepath.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  AgriKit — Modular Agricultural Asset Pack")
    print("=" * 52)

    clear_scene()

    # ── Place assets ──────────────────────────────────────────────────────────
    print("\n  Building assets …")

    # Silo cluster (two silos side by side)
    build_silo(location=(0, 0, 0))
    build_silo(location=(6, 0, 0))

    # Barn
    build_barn(location=(20, 4, 0))

    # Water tower
    build_water_tower(location=(36, 2, 0))

    # Greenhouse
    build_greenhouse(location=(14, -16, 0))

    # Center pivot (running diagonally across the field)
    build_pivot(location=(28, -20, 0), arm_length=26.0)

    # Hay bales scattered near barn
    bale_locs = [
        (16, 12, 0), (18, 14, 0), (20, 12.5, 0),
        (22, 13, 0), (17, 15.5, 0), (24, 11.5, 0),
    ]
    build_hay_bales(bale_locs)

    # Ground
    build_ground(size=140)
    setup_lighting()

    hero_cam, aerial_cam, assets_cam = setup_cameras()
    configure_render()

    # ── Save ──────────────────────────────────────────────────────────────────
    OUTPUT_DIR = ROOT / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"\n  Saved .blend → {BLEND_OUT}")

    bpy.ops.export_scene.gltf(
        filepath=str(GLB_OUT),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
        export_normals=True,
        export_texcoords=True,
        export_cameras=True,
        export_lights=False,
    )
    print(f"  Saved GLB   → {GLB_OUT}")

    # ── Renders ───────────────────────────────────────────────────────────────
    print("\n  Rendering …")
    render_cam(hero_cam,   RENDER_HERO)
    render_cam(aerial_cam, RENDER_AERIAL)
    render_cam(assets_cam, RENDER_ASSETS)

    print("\n  AgriKit complete.")


if __name__ == "__main__":
    main()
