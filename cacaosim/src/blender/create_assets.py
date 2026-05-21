"""
Procedurally generates all plant/tree 3D assets using bmesh.
Creates one mesh per species; all instances share the same mesh data.

No external assets needed — everything is built from geometry.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _frustum(bm, z0, z1, r0, r1, segs=8, transform=None):
    """Add a tapered cylinder (frustum) to bm. Returns (bot_verts, top_verts)."""
    angles = [2 * math.pi * i / segs for i in range(segs)]
    bot, top = [], []
    for a in angles:
        vb = Vector((math.cos(a) * r0, math.sin(a) * r0, z0))
        vt = Vector((math.cos(a) * r1, math.sin(a) * r1, z1))
        if transform:
            vb = transform @ vb
            vt = transform @ vt
        bot.append(bm.verts.new(vb))
        top.append(bm.verts.new(vt))
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new([bot[i], bot[j], top[j], top[i]])
    return bot, top


def _sphere_approx(bm, center, radius, rings=5, segs=8):
    """Add a low-poly sphere approximation to bm."""
    cx, cy, cz = center
    verts_by_ring = []
    for ri in range(rings + 1):
        phi = math.pi * ri / rings  # 0 (top) to π (bottom)
        r = radius * math.sin(phi)
        z = cz + radius * math.cos(phi)
        ring = []
        for si in range(segs):
            theta = 2 * math.pi * si / segs
            ring.append(bm.verts.new(
                (cx + r * math.cos(theta), cy + r * math.sin(theta), z)
            ))
        verts_by_ring.append(ring)
    # Caps and bands
    top_v = bm.verts.new((cx, cy, cz + radius))
    bot_v = bm.verts.new((cx, cy, cz - radius))
    for si in range(segs):
        j = (si + 1) % segs
        bm.faces.new([top_v, verts_by_ring[0][j], verts_by_ring[0][si]])
        bm.faces.new([bot_v, verts_by_ring[-1][si], verts_by_ring[-1][j]])
    for ri in range(rings):
        for si in range(segs):
            j = (si + 1) % segs
            bm.faces.new([
                verts_by_ring[ri][si], verts_by_ring[ri][j],
                verts_by_ring[ri + 1][j], verts_by_ring[ri + 1][si],
            ])


def _branch_transform(origin: Vector, azimuth_deg: float, tilt_deg: float) -> Matrix:
    """Return a transform that places a Z-aligned cylinder as a branch."""
    az = math.radians(azimuth_deg)
    tilt = math.radians(tilt_deg)   # angle from vertical (0 = straight up)
    # Direction vector of branch
    dx = math.sin(tilt) * math.cos(az)
    dy = math.sin(tilt) * math.sin(az)
    dz = math.cos(tilt)
    direction = Vector((dx, dy, dz))
    z_axis = Vector((0, 0, 1))
    cross = z_axis.cross(direction)
    if cross.length < 1e-6:
        rot = Matrix.Identity(4)
    else:
        angle = math.acos(max(-1.0, min(1.0, z_axis.dot(direction))))
        rot = Matrix.Rotation(angle, 4, cross.normalized())
    return Matrix.Translation(origin) @ rot


def _new_obj(name, bm, collection=None):
    """Finalise a bmesh → mesh → object and link it."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    col = collection or bpy.context.scene.collection
    col.objects.link(obj)
    return obj


# ── Tree builders ─────────────────────────────────────────────────────────────

def create_cacao(collection, name="cacao_productive"):
    bm = bmesh.new()

    # Trunk
    _frustum(bm, 0.0, 1.8, 0.08, 0.04, segs=8)

    # 5 main branches at z=1.6, splaying outward 45°
    n_branches = 5
    for i in range(n_branches):
        az = 360 * i / n_branches
        tf = _branch_transform(Vector((0, 0, 1.6)), az, 45)
        _frustum(bm, 0.0, 1.2, 0.025, 0.01, segs=6, transform=tf)

        # 3 sub-branches per main branch
        branch_tip = tf @ Vector((0, 0, 1.2))
        for j in range(3):
            sub_az = az + (j - 1) * 40
            sub_tf = _branch_transform(branch_tip, sub_az, 35)
            _frustum(bm, 0.0, 0.5, 0.012, 0.005, segs=5, transform=sub_tf)
            # Leaf cluster at sub-branch tip
            leaf_tip = sub_tf @ Vector((0, 0, 0.5))
            _sphere_approx(bm, leaf_tip, 0.28, rings=3, segs=6)

        # Leaf cluster at main branch tip
        tip = tf @ Vector((0, 0, 1.2))
        _sphere_approx(bm, tip, 0.38, rings=3, segs=6)

    # Central top canopy
    _sphere_approx(bm, (0, 0, 2.6), 0.5, rings=3, segs=8)

    # Cacao pods on trunk (key credibility detail — cauliflory!)
    import random
    rng = random.Random(42)
    for _ in range(12):
        z_pod = rng.uniform(0.3, 1.4)
        az_pod = rng.uniform(0, 360)
        ar = math.radians(az_pod)
        px = math.cos(ar) * 0.09
        py = math.sin(ar) * 0.09
        # Pod = scaled sphere (ellipsoid: 0.05 × 0.05 × 0.12 m)
        bm_pod = bmesh.new()
        _sphere_approx(bm_pod, (0, 0, 0), 1.0, rings=4, segs=6)
        scale = Matrix.Diagonal(Vector((0.05, 0.05, 0.12, 1.0)))
        trans = Matrix.Translation(Vector((px, py, z_pod)))
        mat = trans @ scale
        bmesh.ops.transform(bm_pod, verts=bm_pod.verts, matrix=mat)
        # Merge pod into main bm
        temp_mesh = bpy.data.meshes.new("_pod_tmp")
        bm_pod.to_mesh(temp_mesh)
        bm_pod.free()
        bm.from_mesh(temp_mesh)
        bpy.data.meshes.remove(temp_mesh)

    obj = _new_obj(name, bm, collection)
    return obj


def create_banana(collection, name="banana_mature"):
    bm = bmesh.new()

    # Pseudostem
    _frustum(bm, 0.0, 2.4, 0.14, 0.07, segs=7)

    # 8 large leaves radiating from top, slightly drooping
    n_leaves = 8
    for i in range(n_leaves):
        az = 360 * i / n_leaves
        az_r = math.radians(az)

        # Each leaf: flat elongated shape, 1.5m long × 0.3m wide
        # Built as a thin frustum (wedge) then we use a flat quad plane
        lx = math.cos(az_r)
        ly = math.sin(az_r)

        # 4 points of the leaf quad
        width = 0.3
        length = 1.5
        droop = -0.3  # droop at tip

        origin = Vector((lx * 0.07, ly * 0.07, 2.4))
        perp = Vector((-ly, lx, 0)).normalized()

        p0 = origin + perp * width / 2
        p1 = origin - perp * width / 2
        p2 = origin + Vector((lx * length, ly * length, droop)) - perp * width / 4
        p3 = origin + Vector((lx * length, ly * length, droop)) + perp * width / 4

        bm.faces.new([bm.verts.new(p0), bm.verts.new(p1),
                      bm.verts.new(p2), bm.verts.new(p3)])

    obj = _new_obj(name, bm, collection)
    return obj


def create_shade_tree(collection, name, trunk_h, trunk_r_bot, trunk_r_top,
                      crown_centers, crown_radii):
    """Generic shade tree: trunk + cluster of leaf spheres at crown_centers."""
    bm = bmesh.new()
    _frustum(bm, 0.0, trunk_h, trunk_r_bot, trunk_r_top, segs=8)
    for center, radius in zip(crown_centers, crown_radii):
        _sphere_approx(bm, center, radius, rings=4, segs=7)
    obj = _new_obj(name, bm, collection)
    return obj


# ── Material assignment ────────────────────────────────────────────────────────

def apply_materials(assets):
    """Apply simple Principled BSDF materials to each asset object."""
    from utils import make_material

    mat_bark   = make_material("bark",         (0.25, 0.14, 0.06), roughness=0.92)
    mat_leaf   = make_material("leaves_green", (0.12, 0.38, 0.08), roughness=0.75,
                               subsurface=0.05, subsurface_color=(0.4, 0.7, 0.2))
    mat_pod    = make_material("cacao_pod",    (0.85, 0.45, 0.05), roughness=0.5)
    mat_banana = make_material("banana_stem",  (0.55, 0.52, 0.12), roughness=0.8)
    mat_leaf_b = make_material("banana_leaf",  (0.15, 0.52, 0.10), roughness=0.65)

    for obj in assets.values():
        mesh = obj.data
        if "cacao" in obj.name:
            mesh.materials.clear()
            mesh.materials.append(mat_bark)
            mesh.materials.append(mat_leaf)
            mesh.materials.append(mat_pod)
        elif "banana" in obj.name:
            mesh.materials.clear()
            mesh.materials.append(mat_banana)
            mesh.materials.append(mat_leaf_b)
        else:
            mesh.materials.clear()
            mesh.materials.append(mat_bark)
            mesh.materials.append(mat_leaf)


# ── Main entry point ──────────────────────────────────────────────────────────

def build_all_assets():
    """Create all plant assets and return dict of name → object."""
    from utils import ensure_collection

    assets_col = ensure_collection("Assets")

    assets = {}

    # Cacao
    assets["cacao"] = create_cacao(assets_col)

    # Banana
    assets["banana"] = create_banana(assets_col)

    # Shade trees
    # Terminalia superba — tall, umbrella crown
    assets["terminalia_superba"] = create_shade_tree(
        assets_col, "terminalia_superba",
        trunk_h=12.0, trunk_r_bot=0.28, trunk_r_top=0.12,
        crown_centers=[
            (0, 0, 13.5), (4.0, 0, 12.5), (-4.0, 0, 12.5),
            (0, 4.0, 12.5), (0, -4.0, 12.5),
            (2.8, 2.8, 12.0), (-2.8, 2.8, 12.0),
        ],
        crown_radii=[2.5, 2.0, 2.0, 2.0, 2.0, 1.8, 1.8],
    )

    # Inga edulis — medium, spreading feathery crown
    assets["inga_edulis"] = create_shade_tree(
        assets_col, "inga_edulis",
        trunk_h=5.0, trunk_r_bot=0.14, trunk_r_top=0.07,
        crown_centers=[
            (0, 0, 7.0), (2.5, 0, 6.0), (-2.5, 0, 6.0),
            (0, 2.5, 6.0), (0, -2.5, 6.0),
            (1.8, 1.8, 5.5), (-1.8, 1.8, 5.5), (1.8, -1.8, 5.5),
        ],
        crown_radii=[1.8, 1.5, 1.5, 1.5, 1.5, 1.2, 1.2, 1.2],
    )

    # Gliricidia sepium — small, round crown
    assets["gliricidia_sepium"] = create_shade_tree(
        assets_col, "gliricidia_sepium",
        trunk_h=3.5, trunk_r_bot=0.09, trunk_r_top=0.05,
        crown_centers=[
            (0, 0, 5.5), (1.5, 0, 5.0), (-1.5, 0, 5.0),
            (0, 1.5, 5.0), (0, -1.5, 5.0),
        ],
        crown_radii=[1.5, 1.2, 1.2, 1.2, 1.2],
    )

    apply_materials(assets)

    return assets
