from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models (https://www.energy.gov/eere/buildings/commercial-reference-buildings)"

PRIMARY_SCHOOL_PRE1980 = BuildingArchetype(
    name="primary_school_pre1980",
    display_name="Primary School (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(8, 18),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(2, 5),
        zones_per_ahu_range=(3, 6),
        has_chiller=False, has_boiler=True, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
    zone_profile="school",
)

PRIMARY_SCHOOL_2004 = BuildingArchetype(
    name="primary_school_2004",
    display_name="Primary School (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(10, 25),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(3, 6),
        zones_per_ahu_range=(3, 6),
        has_chiller=False, has_boiler=True, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
    zone_profile="school",
)

PRIMARY_SCHOOL_2013 = BuildingArchetype(
    name="primary_school_2013",
    display_name="Primary School (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(10, 30),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(3, 6),
        zones_per_ahu_range=(3, 6),
        has_chiller=False, has_boiler=True, has_doas=False,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
    zone_profile="school",
)

SCHOOL_ARCHETYPES = [
    PRIMARY_SCHOOL_PRE1980, PRIMARY_SCHOOL_2004, PRIMARY_SCHOOL_2013,
]
