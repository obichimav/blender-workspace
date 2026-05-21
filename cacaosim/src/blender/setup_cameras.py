"""
Creates 4 camera presets for the final render shots.

Camera 1 – Hero Aerial   : 80 m above plot, 35° down, 35 mm  (money shot)
Camera 2 – Eye Level     : 1.8 m, inside the rows, 50 mm
Camera 3 – Top Down      : 200 m, straight down, 24 mm  (pattern reveal)
Camera 4 – Low Angle     : 3 m, at canopy edge looking across, 50 mm
"""

import math
import bpy
from mathutils import Vector


def _look_at(obj, target: tuple):
    """Rotate obj so its -Z axis (camera forward) points at target."""
    direction = (Vector(target) - Vector(obj.location)).normalized()
    quat = direction.to_track_quat('-Z', 'Y')
    obj.rotation_euler = quat.to_euler()


def _add_camera(name, location, target, focal_mm=35):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = focal_mm
    cam_data.clip_start = 0.5
    cam_data.clip_end = 10000.0
    obj = bpy.data.objects.new(name, cam_data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    _look_at(obj, target)
    return obj


def setup_cameras(scene_data: dict) -> list:
    ex = scene_data["terrain"]["boundary_extent_x_m"]
    ey = scene_data["terrain"]["boundary_extent_y_m"]

    # All cameras look at the plot centre (Blender origin = UTM centroid)
    centre = (0.0, 0.0, 0.0)
    cameras = []

    # 1. Hero aerial — classic portfolio money shot
    cameras.append(_add_camera(
        "Cam_HeroAerial",
        location=(-ex * 0.25, -ey * 0.55, 90),
        target=centre,
        focal_mm=35,
    ))

    # 2. Eye level — inside the rows, looking along the planting
    cameras.append(_add_camera(
        "Cam_EyeLevel",
        location=(-ex * 0.1, -ey * 0.38, 1.8),
        target=(ex * 0.15, ey * 0.1, 2.5),
        focal_mm=50,
    ))

    # 3. Top down — reveals the row pattern
    cameras.append(_add_camera(
        "Cam_TopDown",
        location=(0, 0, 220),
        target=centre,
        focal_mm=24,
    ))

    # 4. Low dramatic angle — at boundary edge, looking across canopy
    cameras.append(_add_camera(
        "Cam_LowAngle",
        location=(-ex * 0.48, 0, 4.0),
        target=(ex * 0.1, 0, 3.5),
        focal_mm=50,
    ))

    bpy.context.scene.camera = cameras[0]   # Hero is the render camera

    for cam in cameras:
        print(f"  Camera: {cam.name}  loc={tuple(round(v,1) for v in cam.location)}")
    return cameras
