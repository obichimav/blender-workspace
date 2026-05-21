"""
Sets up scene lighting from scene_data sun values.
Uses a Sun lamp + Blender's Sky Texture for a photorealistic tropical sky.
"""

import math
import bpy


def setup_lighting(scene_data: dict) -> None:
    sun_data = scene_data["sun"]
    env_data = scene_data["environment"]

    elev_deg = sun_data["elevation_deg"]
    azim_deg = sun_data["azimuth_deg"]
    haze     = env_data.get("atmospheric_haze", 0.3)

    # ── Sun lamp ──────────────────────────────────────────────────────────────
    # Remove any existing lights
    for obj in list(bpy.data.objects):
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)

    sun_light = bpy.data.lights.new("Sun", 'SUN')
    sun_light.energy   = 4.5
    sun_light.angle    = math.radians(0.5)   # sharp tropical sun shadow
    sun_light.color    = (1.0, 0.97, 0.90)   # slight warm tint

    sun_obj = bpy.data.objects.new("Sun", sun_light)
    bpy.context.scene.collection.objects.link(sun_obj)

    # Convert azimuth + elevation to Euler rotation
    # Blender sun: points in -Z direction, so we rotate X then Z
    # elevation: 0° = horizon, 90° = zenith
    # azimuth: 0° = North (+Y in Blender), 90° = East (+X)
    az_r  = math.radians(azim_deg)
    el_r  = math.radians(elev_deg)

    # Rotation to aim sun in correct direction
    # Start pointing down (-Z), rotate up by elevation, then rotate by azimuth
    sun_obj.rotation_euler[0] = math.pi / 2 - el_r   # tilt from vertical
    sun_obj.rotation_euler[2] = -az_r                 # compass rotation

    # ── World: Sky Texture ────────────────────────────────────────────────────
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()

    out_node = tree.nodes.new('ShaderNodeOutputWorld')
    out_node.location = (400, 0)

    bg_node = tree.nodes.new('ShaderNodeBackground')
    bg_node.location = (200, 0)
    bg_node.inputs['Strength'].default_value = 1.0

    # Sky Texture — HOSEK_WILKIE works reliably in background/headless mode
    sky_node = tree.nodes.new('ShaderNodeTexSky')
    sky_node.location = (-200, 0)
    sky_node.sky_type = 'HOSEK_WILKIE'
    # sun_direction is a unit vector pointing toward the sun
    sky_node.sun_direction = (
        math.cos(el_r) * math.sin(az_r),
        math.cos(el_r) * math.cos(az_r),
        math.sin(el_r),
    )
    sky_node.turbidity = 2.0 + haze * 6.0   # 2 (clear) – 8 (hazy)

    tree.links.new(sky_node.outputs['Color'], bg_node.inputs['Color'])
    tree.links.new(bg_node.outputs['Background'], out_node.inputs['Surface'])

    # World volume scatter is intentionally omitted — it breaks background renders.
    # Hosek-Wilkie turbidity already encodes haze in the sky colour.

    print(f"  Lighting: sun at {elev_deg}° elevation, {azim_deg}° azimuth")
    print(f"  Haze: {haze}")
