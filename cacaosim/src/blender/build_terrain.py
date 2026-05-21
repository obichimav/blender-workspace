"""
Builds the terrain mesh from the pre-computed heightmap PNG.

The plane is centred at (0, 0, 0) in Blender world space, which corresponds
to the plot centroid at mean elevation. Vertex Z values encode elevation
relative to that mean so plant z-coordinates in scene_data.json match.
"""

import bpy
import bmesh
import struct
from pathlib import Path
from mathutils import Vector


def _read_png_16bit(path: str):
    """Read a 16-bit greyscale PNG without PIL (Blender has no PIL).
    Returns (pixel_array_uint16, width, height).
    Pixel order: row 0 = top of image.
    """
    import zlib

    data = Path(path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', "Not a PNG file"

    chunks = []
    i = 8
    while i < len(data):
        length = struct.unpack('>I', data[i:i+4])[0]
        chunk_type = data[i+4:i+8]
        chunk_data = data[i+8:i+8+length]
        chunks.append((chunk_type, chunk_data))
        i += 12 + length

    # Parse IHDR
    ihdr = next(d for t, d in chunks if t == b'IHDR')
    width  = struct.unpack('>I', ihdr[0:4])[0]
    height = struct.unpack('>I', ihdr[4:8])[0]
    bit_depth   = ihdr[8]
    color_type  = ihdr[9]

    assert bit_depth == 16 and color_type == 0, \
        f"Expected 16-bit greyscale, got bit_depth={bit_depth} color_type={color_type}"

    # Combine IDAT chunks
    raw_deflate = b''.join(d for t, d in chunks if t == b'IDAT')
    raw = zlib.decompress(raw_deflate)

    # Reconstruct filtered scanlines
    stride = width * 2 + 1   # 2 bytes per pixel + 1 filter byte
    pixels = []
    prev_row = [0] * (width * 2)

    for row in range(height):
        filter_byte = raw[row * stride]
        line = list(raw[row * stride + 1: row * stride + 1 + width * 2])

        if filter_byte == 0:   # None
            pass
        elif filter_byte == 1: # Sub
            for j in range(2, len(line)):
                line[j] = (line[j] + line[j-2]) & 0xFF
        elif filter_byte == 2: # Up
            line = [(line[j] + prev_row[j]) & 0xFF for j in range(len(line))]
        elif filter_byte == 3: # Average
            for j in range(len(line)):
                a = line[j-2] if j >= 2 else 0
                b = prev_row[j]
                line[j] = (line[j] + (a + b) // 2) & 0xFF
        elif filter_byte == 4: # Paeth
            def paeth(a, b, c):
                p = a + b - c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                return a if pa<=pb and pa<=pc else (b if pb<=pc else c)
            for j in range(len(line)):
                a = line[j-2] if j >= 2 else 0
                b = prev_row[j]
                c = prev_row[j-2] if j >= 2 else 0
                line[j] = (line[j] + paeth(a, b, c)) & 0xFF

        prev_row = line
        for j in range(0, len(line), 2):
            pixels.append((line[j] << 8) | line[j+1])

    return pixels, width, height


def build_terrain(scene_data: dict, root) -> bpy.types.Object:
    ti = scene_data["terrain"]
    elev_min  = ti["elevation_min_m"]
    elev_range = ti["elevation_range_m"]
    elev_mean  = ti["elevation_mean_m"]
    dem_w = ti["dem_width_px"]
    dem_h = ti["dem_height_px"]
    dem_ex = ti["dem_extent_x_m"]
    dem_ey = ti["dem_extent_y_m"]
    vert_exag = ti.get("vertical_exaggeration", 1.0)

    heightmap_path = str(root / ti["heightmap_png"])

    print(f"  Loading heightmap: {heightmap_path}")
    pixels, img_w, img_h = _read_png_16bit(heightmap_path)
    assert img_w == dem_w and img_h == dem_h, \
        f"Heightmap size mismatch: {img_w}×{img_h} vs {dem_w}×{dem_h}"

    # Build a grid mesh matching DEM resolution
    # Vertex (col, row) in DEM → Blender (x, y, z)
    print(f"  Building terrain mesh ({dem_w}×{dem_h} vertices)...")

    mesh = bpy.data.meshes.new("TerrainMesh")
    bm = bmesh.new()

    # Pre-create all vertices
    verts = []
    for row in range(dem_h):
        for col in range(dem_w):
            # PNG row 0 = North (top), row dem_h-1 = South (bottom)
            # Blender Y+ = North, so flip Y
            x = (col / (dem_w - 1) - 0.5) * dem_ex
            y = ((dem_h - 1 - row) / (dem_h - 1) - 0.5) * dem_ey

            pix_val = pixels[row * dem_w + col]
            elevation = elev_min + (pix_val / 65535.0) * elev_range
            z = (elevation - elev_mean) * vert_exag

            verts.append(bm.verts.new((x, y, z)))

    bm.verts.ensure_lookup_table()

    # Create quad faces
    for row in range(dem_h - 1):
        for col in range(dem_w - 1):
            i00 = row * dem_w + col
            i10 = row * dem_w + col + 1
            i01 = (row + 1) * dem_w + col
            i11 = (row + 1) * dem_w + col + 1
            bm.faces.new([verts[i00], verts[i01], verts[i11], verts[i10]])

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    # Smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True

    terrain = bpy.data.objects.new("Terrain", mesh)
    bpy.context.scene.collection.objects.link(terrain)
    terrain.location = (0, 0, 0)

    # Soil material
    from utils import make_material
    mat = make_material(
        "soil_laterite",
        base_color=(0.42, 0.22, 0.10),
        roughness=0.92,
    )
    mesh.materials.append(mat)

    print(f"  Terrain built: {dem_w * dem_h:,} vertices")
    return terrain
