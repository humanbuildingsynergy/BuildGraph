from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models (https://www.energy.gov/eere/buildings/commercial-reference-buildings)"

HOSPITAL_PRE1980 = BuildingArchetype(
    name="hospital_pre1980",
    display_name="Hospital (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(3, 6),
    total_zones_range=(20, 50),
    hvac=SystemConfig(
        system_type="vav_doas",
        ahu_range=(4, 8),
        zones_per_ahu_range=(5, 10),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
    zone_profile="hospital",
)

HOSPITAL_2004 = BuildingArchetype(
    name="hospital_2004",
    display_name="Hospital (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(4, 8),
    total_zones_range=(30, 70),
    hvac=SystemConfig(
        system_type="vav_doas",
        ahu_range=(6, 12),
        zones_per_ahu_range=(5, 10),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
    zone_profile="hospital",
)

HOSPITAL_2013 = BuildingArchetype(
    name="hospital_2013",
    display_name="Hospital (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(4, 8),
    total_zones_range=(30, 80),
    hvac=SystemConfig(
        system_type="vav_doas",
        ahu_range=(6, 12),
        zones_per_ahu_range=(5, 10),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
    zone_profile="hospital",
)

HOSPITAL_ARCHETYPES = [
    HOSPITAL_PRE1980, HOSPITAL_2004, HOSPITAL_2013,
]
