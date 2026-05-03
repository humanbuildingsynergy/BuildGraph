from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models — extended (retail / strip mall)"

STRIP_MALL_PRE1980 = BuildingArchetype(
    name="strip_mall_pre1980",
    display_name="Strip Mall / Retail (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(1, 1),
    total_zones_range=(4, 10),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(2, 5),
        zones_per_ahu_range=(1, 3),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
    zone_profile="retail",
)

STRIP_MALL_2004 = BuildingArchetype(
    name="strip_mall_2004",
    display_name="Strip Mall / Retail (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(5, 15),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(3, 6),
        zones_per_ahu_range=(1, 3),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
    zone_profile="retail",
)

STRIP_MALL_2013 = BuildingArchetype(
    name="strip_mall_2013",
    display_name="Strip Mall / Retail (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(1, 2),
    total_zones_range=(5, 18),
    hvac=SystemConfig(
        system_type="psz_ac",
        ahu_range=(3, 8),
        zones_per_ahu_range=(1, 3),
        has_chiller=False, has_boiler=False, has_doas=False,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
    zone_profile="retail",
)

RETAIL_ARCHETYPES = [STRIP_MALL_PRE1980, STRIP_MALL_2004, STRIP_MALL_2013]
