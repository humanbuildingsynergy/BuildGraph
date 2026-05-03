from dataclasses import dataclass, field
from typing import Literal

OntologyMode = Literal["brick", "s223", "mixed"]


@dataclass
class SystemConfig:
    system_type: str          # "psz_ac" | "pvav_reheat" | "vav_reheat" | "vav_doas"
    ahu_range: tuple[int, int]
    zones_per_ahu_range: tuple[int, int]
    has_chiller: bool
    has_boiler: bool
    has_doas: bool
    sensor_density: str       # "sparse" | "standard" | "dense"


@dataclass
class BuildingArchetype:
    name: str
    display_name: str
    doe_reference: str
    floors_range: tuple[int, int]
    total_zones_range: tuple[int, int]
    hvac: SystemConfig
    has_lighting_meter: bool
    has_electric_meter: bool
    vintage: str              # "pre1980" | "ashrae2004" | "ashrae2013"
    ontology_mode: OntologyMode = "brick"
    zone_profile: str = "office"  # selects zone_type distribution in spec_builder
