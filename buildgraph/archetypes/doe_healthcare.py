from .base import BuildingArchetype, SystemConfig

_DOE_REF = "DOE Commercial Prototype Building Models — extended (outpatient healthcare)"

OUTPATIENT_PRE1980 = BuildingArchetype(
    name="outpatient_pre1980",
    display_name="Outpatient Healthcare (pre-1980)",
    doe_reference=_DOE_REF,
    floors_range=(1, 3),
    total_zones_range=(8, 20),
    hvac=SystemConfig(
        system_type="fcu_system",
        ahu_range=(1, 3),
        zones_per_ahu_range=(4, 10),
        has_chiller=True, has_boiler=True, has_doas=False,
        sensor_density="sparse",
    ),
    has_lighting_meter=False,
    has_electric_meter=False,
    vintage="pre1980",
    zone_profile="healthcare",
)

OUTPATIENT_2004 = BuildingArchetype(
    name="outpatient_2004",
    display_name="Outpatient Healthcare (ASHRAE 90.1-2004)",
    doe_reference=_DOE_REF,
    floors_range=(2, 4),
    total_zones_range=(12, 30),
    hvac=SystemConfig(
        system_type="doas_fcu",
        ahu_range=(2, 4),
        zones_per_ahu_range=(5, 10),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="standard",
    ),
    has_lighting_meter=False,
    has_electric_meter=True,
    vintage="ashrae2004",
    zone_profile="healthcare",
)

OUTPATIENT_2013 = BuildingArchetype(
    name="outpatient_2013",
    display_name="Outpatient Healthcare (ASHRAE 90.1-2013)",
    doe_reference=_DOE_REF,
    floors_range=(2, 5),
    total_zones_range=(15, 40),
    hvac=SystemConfig(
        system_type="doas_fcu",
        ahu_range=(2, 6),
        zones_per_ahu_range=(5, 10),
        has_chiller=True, has_boiler=True, has_doas=True,
        sensor_density="dense",
    ),
    has_lighting_meter=True,
    has_electric_meter=True,
    vintage="ashrae2013",
    zone_profile="healthcare",
)

HEALTHCARE_ARCHETYPES = [OUTPATIENT_PRE1980, OUTPATIENT_2004, OUTPATIENT_2013]
