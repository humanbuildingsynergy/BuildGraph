from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models (https://www.energy.gov/eere/buildings/commercial-reference-buildings)"

SMALL_OFFICE_PRE1980 = BuildingArchetype(
    name="small_office_pre1980",
    display_name="Small Office (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(3, 6),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(1, 2),
        zones_per_ahu_range=(2, 4),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
)

SMALL_OFFICE_2004 = BuildingArchetype(
    name="small_office_2004",
    display_name="Small Office (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(1, 3),
    total_zones_range=(4, 8),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(1, 2),
        zones_per_ahu_range=(2, 5),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
)

SMALL_OFFICE_2013 = BuildingArchetype(
    name="small_office_2013",
    display_name="Small Office (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(1, 3),
    total_zones_range=(4, 8),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(1, 2),
        zones_per_ahu_range=(2, 5),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
)

MEDIUM_OFFICE_PRE1980 = BuildingArchetype(
    name="medium_office_pre1980",
    display_name="Medium Office (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(2, 4),
    total_zones_range=(6, 15),
    hvac=SystemConfig(
        system_type="pvav_reheat",
        ahu_range=(1, 3),
        zones_per_ahu_range=(3, 7),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
)

MEDIUM_OFFICE_2004 = BuildingArchetype(
    name="medium_office_2004",
    display_name="Medium Office (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(3, 5),
    total_zones_range=(8, 20),
    hvac=SystemConfig(
        system_type="pvav_reheat",
        ahu_range=(2, 4),
        zones_per_ahu_range=(3, 6),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
)

MEDIUM_OFFICE_2013 = BuildingArchetype(
    name="medium_office_2013",
    display_name="Medium Office (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(3, 5),
    total_zones_range=(8, 20),
    hvac=SystemConfig(
        system_type="pvav_reheat",
        ahu_range=(2, 4),
        zones_per_ahu_range=(3, 6),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
)

LARGE_OFFICE_PRE1980 = BuildingArchetype(
    name="large_office_pre1980",
    display_name="Large Office (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(4, 8),
    total_zones_range=(15, 35),
    hvac=SystemConfig(
        system_type="vav_reheat",
        ahu_range=(3, 6),
        zones_per_ahu_range=(4, 8),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
)

LARGE_OFFICE_2004 = BuildingArchetype(
    name="large_office_2004",
    display_name="Large Office (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(5, 10),
    total_zones_range=(20, 50),
    hvac=SystemConfig(
        system_type="vav_reheat",
        ahu_range=(4, 8),
        zones_per_ahu_range=(4, 8),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
)

LARGE_OFFICE_2013 = BuildingArchetype(
    name="large_office_2013",
    display_name="Large Office (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(5, 10),
    total_zones_range=(20, 50),
    hvac=SystemConfig(
        system_type="vav_reheat",
        ahu_range=(4, 8),
        zones_per_ahu_range=(4, 8),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
)

OFFICE_ARCHETYPES = [
    SMALL_OFFICE_PRE1980, SMALL_OFFICE_2004, SMALL_OFFICE_2013,
    MEDIUM_OFFICE_PRE1980, MEDIUM_OFFICE_2004, MEDIUM_OFFICE_2013,
    LARGE_OFFICE_PRE1980, LARGE_OFFICE_2004, LARGE_OFFICE_2013,
]
