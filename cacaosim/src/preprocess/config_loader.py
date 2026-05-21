import json
from pathlib import Path


REQUIRED_TOP = ["schema_version", "project_name", "site", "planting", "terrain", "environment", "render"]
REQUIRED_SITE = ["lat", "lon", "boundary_file", "terrain_file"]


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path) as f:
        config = json.load(f)
    _validate(config)
    return config


def _validate(config: dict) -> None:
    for key in REQUIRED_TOP:
        if key not in config:
            raise ValueError(f"Config missing required key: '{key}'")
    for key in REQUIRED_SITE:
        if key not in config["site"]:
            raise ValueError(f"site config missing: '{key}'")
