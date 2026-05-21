"""Shared helpers for all CacaoSim Blender scripts."""

import json
import sys
from pathlib import Path


def project_root() -> Path:
    """Return the cacaosim project root passed as the first arg after '--'."""
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            return Path(sys.argv[idx + 1])
    # Fallback: two levels up from this file (src/blender/ → cacaosim/)
    return Path(__file__).resolve().parent.parent.parent


def load_scene_data(root: Path) -> dict:
    path = root / "data" / "intermediate" / "scene_data.json"
    with open(path) as f:
        return json.load(f)


def ensure_collection(name: str):
    """Return (or create) a top-level Blender collection by name."""
    import bpy
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def link_to(obj, collection):
    """Link object to collection, unlinking from scene root first if needed."""
    import bpy
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)
    if obj.name not in collection.objects:
        collection.objects.link(obj)


def make_material(name: str, base_color, roughness=0.8, metallic=0.0,
                  subsurface=0.0, subsurface_color=None):
    """Create (or reuse) a Principled BSDF material."""
    import bpy
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        # Subsurface weight (Blender 4+)
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = subsurface
        elif "Subsurface" in bsdf.inputs:
            bsdf.inputs["Subsurface"].default_value = subsurface
        if subsurface_color and "Subsurface Color" in bsdf.inputs:
            bsdf.inputs["Subsurface Color"].default_value = (*subsurface_color, 1.0)
    return mat
