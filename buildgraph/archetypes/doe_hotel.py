from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models — extended (hotel/lodging)"

HOTEL_PRE1980 = BuildingArchetype(
    name="hotel_pre1980",
    display_name="Hotel / Motel (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(4, 10),
    total_zones_range=(30, 80),
    hvac=SystemConfig(
        system_type="fcu_system",
        ahu_range=(2, 4),
        zones_per_ahu_range=(10, 25),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
    zone_profile="hotel",
)

HOTEL_2004 = BuildingArchetype(
    name="hotel_2004",
    display_name="Hotel / Motel (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(6, 15),
    total_zones_range=(50, 120),
    hvac=SystemConfig(
        system_type="fcu_system",
        ahu_range=(3, 6),
        zones_per_ahu_range=(12, 25),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
    zone_profile="hotel",
)

HOTEL_2013 = BuildingArchetype(
    name="hotel_2013",
    display_name="Hotel / Motel (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(8, 20),
    total_zones_range=(60, 150),
    hvac=SystemConfig(
        system_type="doas_fcu",
        ahu_range=(4, 8),
        zones_per_ahu_range=(12, 25),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
    zone_profile="hotel",
)

HOTEL_ARCHETYPES = [HOTEL_PRE1980, HOTEL_2004, HOTEL_2013]
