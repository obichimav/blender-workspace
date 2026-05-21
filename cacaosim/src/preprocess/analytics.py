import math

# Canopy radius (m) per species / growth stage
CANOPY_RADIUS = {
    "cacao":              {"young": 0.8, "productive": 2.0, "mature": 2.5},
    "banana":             {"default": 1.5},
    "terminalia_superba": {"default": 5.0},
    "inga_edulis":        {"default": 3.5},
    "gliricidia_sepium":  {"default": 2.5},
    "shade_upper":        {"default": 4.0},   # fallback for mixed canopy
}

# Biomass (dry tonnes per tree) per species / growth stage
BIOMASS_T = {
    "cacao":              {"young": 0.05, "productive": 0.15, "mature": 0.25},
    "banana":             {"default": 0.04},
    "terminalia_superba": {"default": 2.5},
    "inga_edulis":        {"default": 1.2},
    "gliricidia_sepium":  {"default": 0.8},
    "shade_upper":        {"default": 1.5},
}


def _radius(category: str, species: str | None, stage: str) -> float:
    lookup = CANOPY_RADIUS.get(species or category, CANOPY_RADIUS.get(category, {"default": 2.0}))
    return lookup.get(stage, lookup.get("default", 2.0))


def _biomass(category: str, species: str | None, stage: str) -> float:
    lookup = BIOMASS_T.get(species or category, BIOMASS_T.get(category, {"default": 0.5}))
    return lookup.get(stage, lookup.get("default", 0.5))


def compute_analytics(
    plants: dict[str, list[dict]],
    boundary_area_ha: float,
    growth_stage: str,
) -> dict:
    counts = {k: len(v) for k, v in plants.items()}
    area_m2 = boundary_area_ha * 10_000

    total_canopy_m2 = 0.0
    total_biomass_t = 0.0

    for category, pts in plants.items():
        for pt in pts:
            species = pt.get("species")
            r = _radius(category, species, growth_stage)
            total_canopy_m2 += math.pi * r**2
            total_biomass_t += _biomass(category, species, growth_stage)

    canopy_pct = min(100.0, (total_canopy_m2 / area_m2) * 100)
    carbon_t = total_biomass_t * 0.5   # ~50 % carbon by dry weight

    return {
        "plant_counts": counts,
        "boundary_area_ha": round(boundary_area_ha, 2),
        "estimated_canopy_cover_pct": round(canopy_pct, 1),
        "estimated_biomass_tonnes": round(total_biomass_t, 1),
        "estimated_carbon_tonnes": round(carbon_t, 1),
    }
