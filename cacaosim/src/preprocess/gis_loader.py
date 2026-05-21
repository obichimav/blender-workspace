import numpy as np
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rio_mask
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling

UTM_30N = "EPSG:32630"
WGS84 = "EPSG:4326"


def load_boundary(boundary_file: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(boundary_file)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf


def reproject_to_utm(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(UTM_30N)


def compute_local_origin(gdf_utm: gpd.GeoDataFrame) -> tuple[float, float]:
    centroid = gdf_utm.geometry.union_all().centroid
    return centroid.x, centroid.y


def boundary_area_ha(gdf_utm: gpd.GeoDataFrame) -> float:
    return gdf_utm.geometry.union_all().area / 10_000


def load_and_clip_dem_utm(
    dem_file: str,
    boundary_utm: gpd.GeoDataFrame,
    output_path: str = "data/intermediate/terrain_utm.tif",
) -> tuple[np.ndarray, rasterio.transform.Affine]:
    """Clip DEM to boundary and reproject to UTM 30N.

    Returns (elevation_array, transform) both in UTM metres.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    dst_crs = CRS.from_epsg(32630)

    with rasterio.open(dem_file) as src:
        dem_crs = src.crs
        nodata_val = src.nodata if src.nodata is not None else -9999.0

        # Clip in native DEM CRS
        boundary_dem_crs = boundary_utm.to_crs(dem_crs)
        shapes = [g.__geo_interface__ for g in boundary_dem_crs.geometry]

        clipped, clip_tf = rio_mask(
            src, shapes,
            crop=True, nodata=nodata_val,
            pad=True, pad_width=10,
        )
        clip_h, clip_w = clipped.shape[1], clipped.shape[2]
        clip_bounds = array_bounds(clip_h, clip_w, clip_tf)

        # Calculate UTM output transform
        utm_tf, utm_w, utm_h = calculate_default_transform(
            dem_crs, dst_crs, clip_w, clip_h, *clip_bounds
        )

        utm_data = np.full((1, utm_h, utm_w), nodata_val, dtype=np.float32)
        reproject(
            source=clipped.astype(np.float32),
            destination=utm_data,
            src_transform=clip_tf,
            src_crs=dem_crs,
            dst_transform=utm_tf,
            dst_crs=dst_crs,
            src_nodata=nodata_val,
            dst_nodata=nodata_val,
            resampling=Resampling.bilinear,
        )

        utm_meta = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": utm_w,
            "height": utm_h,
            "count": 1,
            "crs": dst_crs,
            "transform": utm_tf,
            "nodata": nodata_val,
        }
        with rasterio.open(output_path, "w", **utm_meta) as dst:
            dst.write(utm_data)

    elevation = utm_data[0]
    elevation[elevation == nodata_val] = np.nan
    return elevation, utm_tf
