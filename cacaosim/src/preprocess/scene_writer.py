import json
from pathlib import Path

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def write_scene_data(
    output_path: str,
    config: dict,
    plants: dict,
    terrain_info: dict,
    sun_info: dict,
    analytics: dict,
    origin: tuple[float, float],
) -> str:
    scene = {
        "schema_version": "1.0.0",
        "project_name": config["project_name"],
        "origin": {
            "utm_easting": origin[0],
            "utm_northing": origin[1],
            "crs": "EPSG:32630",
        },
        "plants": plants,
        "terrain": terrain_info,
        "sun": sun_info,
        "analytics": analytics,
        "render": config["render"],
        "environment": config["environment"],
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(scene, f, indent=2, cls=_NumpyEncoder)

    return output_path
