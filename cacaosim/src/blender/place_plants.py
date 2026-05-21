"""
Places all plants in the scene using Geometry Nodes (Instance on Points).

For each plant category a point-cloud mesh is created at the plant positions,
then a GN modifier instances the corresponding asset mesh at every point.
This is memory-efficient: Blender stores one mesh + N lightweight instances.
"""

import bpy
import bmesh
from mathutils import Vector


def _make_point_cloud(name: str, points: list[dict], elev_mean: float) -> bpy.types.Object:
    """Create a mesh whose vertices are the plant positions."""
    mesh = bpy.data.meshes.new(name + "_pts")
    coords = []
    for pt in points:
        x = pt["x"]
        y = pt["y"]
        z = pt["z"] - elev_mean          # local elevation
        coords.append((x, y, z))

    mesh.vertices.add(len(coords))
    flat = [v for xyz in coords for v in xyz]
    mesh.vertices.foreach_set("co", flat)
    mesh.update()

    obj = bpy.data.objects.new(name + "_cloud", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _make_gn_instance_modifier(cloud_obj, asset_obj, mod_name="GN_Instances"):
    """Add a Geometry Nodes modifier that instances asset_obj at every point."""
    ng_name = mod_name + "_ng"
    if ng_name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[ng_name])

    ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')

    # Interface (Blender 4.2+ style)
    ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    nodes = ng.nodes
    links = ng.links

    n_in  = nodes.new('NodeGroupInput');  n_in.location  = (-500, 0)
    n_out = nodes.new('NodeGroupOutput'); n_out.location = ( 500, 0)

    n_obj = nodes.new('GeometryNodeObjectInfo'); n_obj.location = (-200, -150)
    n_obj.inputs['Object'].default_value = asset_obj
    n_obj.inputs['As Instance'].default_value = True

    n_inst = nodes.new('GeometryNodeInstanceOnPoints'); n_inst.location = (100, 0)

    links.new(n_in.outputs[0],           n_inst.inputs['Points'])
    links.new(n_obj.outputs['Geometry'], n_inst.inputs['Instance'])
    links.new(n_inst.outputs['Instances'], n_out.inputs[0])

    mod = cloud_obj.modifiers.new(mod_name, 'NODES')
    mod.node_group = ng
    return mod


def place_all_plants(scene_data: dict, assets: dict,
                     preview_n: int = 0) -> list:
    """
    Create instanced plant objects for all categories.

    Args:
        preview_n: if > 0 only place this many plants per category (for fast testing).
    """
    from utils import ensure_collection, make_material

    elev_mean = scene_data["terrain"]["elevation_mean_m"]
    plant_data = scene_data["plants"]
    plant_objs = []

    category_to_asset = {
        "cacao":       "cacao",
        "banana":      "banana",
    }

    for category, points in plant_data.items():
        if preview_n > 0:
            points = points[:preview_n]
        if not points:
            continue

        col = ensure_collection(f"Plants_{category}")

        if category == "shade_upper":
            # Mixed species — create one cloud per species
            species_map: dict[str, list] = {}
            for pt in points:
                sp = pt.get("species", "inga_edulis")
                species_map.setdefault(sp, []).append(pt)

            for species, sp_pts in species_map.items():
                asset_name = species
                if asset_name not in assets:
                    asset_name = "inga_edulis"   # fallback
                cloud = _make_point_cloud(f"shade_{species}", sp_pts, elev_mean)
                col.objects.link(cloud)
                if cloud.name in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.unlink(cloud)
                _make_gn_instance_modifier(cloud, assets[asset_name],
                                           f"GN_{species}")
                plant_objs.append(cloud)
                print(f"    {species}: {len(sp_pts)} instances")
        else:
            asset_key = category_to_asset.get(category, "cacao")
            if asset_key not in assets:
                print(f"  [WARN] No asset for '{category}', skipping")
                continue

            cloud = _make_point_cloud(category, points, elev_mean)
            col.objects.link(cloud)
            if cloud.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(cloud)
            _make_gn_instance_modifier(cloud, assets[asset_key],
                                       f"GN_{category}")
            plant_objs.append(cloud)
            print(f"    {category}: {len(points)} instances")

    return plant_objs
