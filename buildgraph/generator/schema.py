"""Pydantic v2 schema for BuildingSpec — the normalized intermediate representation
consumed by the Brick builder and produced by the archetype path.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo

# ── Type aliases ──────────────────────────────────────────────────────────────

NamingStyle = Literal["numeric", "hyphenated", "descriptive", "legacy"]
RelStyle    = Literal["standard", "inverse", "mixed"]

TerminalType = Literal[
    "vav_reheat", "vav_no_reheat", "fan_powered_vav", "fcu", "cav", "dual_duct",
    "vrf_indoor",
]

AHUType = Literal["single_duct", "dual_duct", "doas", "rtu", "vrf"]

ZoneType = Literal[
    "office", "lab", "corridor", "classroom", "patient_room",
    "mechanical", "lobby", "storage", "gymnasium", "cafeteria",
    "guestroom", "retail", "exam_room", "procedure_room", "meeting_room", "waiting",
    "server_room",
]

SpatialLocation = Literal[
    "core", "perimeter_N", "perimeter_S", "perimeter_E", "perimeter_W", "roof"
]

ChillerConfig = Literal["standalone", "lead_lag", "parallel"]
BoilerConfig  = Literal["standalone", "lead_lag", "parallel"]


# ── Sub-models ────────────────────────────────────────────────────────────────

class ZoneSpec(BaseModel):
    zone_id:          str             # opaque key, e.g. "Z001"
    name:             str             # display name, e.g. "Conference Room 301"
    zone_type:        ZoneType        = "office"
    floor:            int             = Field(ge=1)
    spatial_location: SpatialLocation = "core"
    area_m2:          float           = Field(default=50.0, gt=0)  # conditioned floor area


class AHUSpec(BaseModel):
    ahu_id:               str     # opaque key, e.g. "A01"
    ahu_type:             AHUType = "single_duct"
    zone_ids:             list[str]

    has_supply_fan:       bool = True   # always True for real AHUs
    has_return_fan:       bool = False
    has_economizer_damper: bool = False
    has_return_damper:    bool = False
    has_exhaust_damper:   bool = False
    has_chw_coil:         bool = False
    has_hw_coil:          bool = False
    has_heat_recovery:    bool = False

    @field_validator("zone_ids")
    @classmethod
    def zones_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("AHU must serve at least one zone")
        return v

    @model_validator(mode="after")
    def supply_fan_required_for_non_vrf(self) -> "AHUSpec":
        if not self.has_supply_fan and self.ahu_type != "vrf":
            raise ValueError(
                f"AHU type '{self.ahu_type}' must have has_supply_fan=True"
            )
        return self

    @model_validator(mode="after")
    def heat_recovery_requires_doas(self) -> "AHUSpec":
        if self.has_heat_recovery and self.ahu_type not in ("doas", "vrf"):
            raise ValueError(
                "has_heat_recovery=True is only valid for DOAS or VRF AHU types"
            )
        return self


class TerminalUnitSpec(BaseModel):
    terminal_id:   str
    terminal_type: TerminalType = "vav_reheat"
    zone_id:       str          # foreign key → ZoneSpec.zone_id


class PlantSpec(BaseModel):
    num_chillers:              int = Field(default=0, ge=0, le=6)
    chiller_config:            ChillerConfig = "standalone"
    num_cooling_towers:        int = Field(default=0, ge=0, le=4)
    num_chw_pumps:             int = Field(default=0, ge=0, le=4)
    num_condenser_water_pumps: int = Field(default=0, ge=0, le=4)

    num_boilers:    int = Field(default=0, ge=0, le=4)
    boiler_config:  BoilerConfig = "standalone"
    num_hw_pumps:   int = Field(default=0, ge=0, le=4)

    @model_validator(mode="after")
    def cooling_tower_needs_chiller(self) -> PlantSpec:
        if self.num_cooling_towers > 0 and self.num_chillers == 0:
            raise ValueError("num_cooling_towers requires num_chillers >= 1")
        return self

    @model_validator(mode="after")
    def condenser_pumps_need_cooling_tower(self) -> PlantSpec:
        if self.num_condenser_water_pumps > 0 and self.num_cooling_towers == 0:
            raise ValueError("num_condenser_water_pumps requires num_cooling_towers >= 1")
        return self

    @model_validator(mode="after")
    def chw_pumps_need_chiller(self) -> PlantSpec:
        if self.num_chw_pumps > 0 and self.num_chillers == 0:
            raise ValueError("num_chw_pumps requires num_chillers >= 1")
        return self

    @model_validator(mode="after")
    def hw_pumps_need_boiler(self) -> PlantSpec:
        if self.num_hw_pumps > 0 and self.num_boilers == 0:
            raise ValueError("num_hw_pumps requires num_boilers >= 1")
        return self

    @model_validator(mode="after")
    def pump_counts_match_equipment(self) -> "PlantSpec":
        if self.num_chillers > 1 and self.num_chw_pumps < self.num_chillers:
            raise ValueError(
                f"num_chw_pumps ({self.num_chw_pumps}) must be >= "
                f"num_chillers ({self.num_chillers}) for multi-chiller plants"
            )
        if self.num_boilers > 1 and self.num_hw_pumps < self.num_boilers:
            raise ValueError(
                f"num_hw_pumps ({self.num_hw_pumps}) must be >= "
                f"num_boilers ({self.num_boilers}) for multi-boiler plants"
            )
        return self


class BuildingSpec(BaseModel):
    # Metadata
    building_type: str
    vintage:       Literal["pre1980", "ashrae2004", "ashrae2013"]
    ontology_mode: Literal["brick"] = "brick"
    naming_style:  NamingStyle = "numeric"
    seed:          int         = 0
    climate_zone:  str         = "4A"  # ASHRAE climate zone, e.g. "2A", "4C", "6B"

    # Spatial
    num_floors: int = Field(ge=1, le=20)
    zones:      list[ZoneSpec]
    ahus:       list[AHUSpec]
    terminals:  list[TerminalUnitSpec]
    plant:      PlantSpec

    # Sensor density and relationship style
    sensor_density: Literal["sparse", "standard", "dense"] = "standard"
    rel_style:      RelStyle = "standard"

    # Optional metering
    has_electric_meter: bool = False
    has_lighting_meter: bool = False

    @model_validator(mode="after")
    def ahu_zone_refs_valid(self) -> BuildingSpec:
        zone_ids = {z.zone_id for z in self.zones}
        for ahu in self.ahus:
            for zid in ahu.zone_ids:
                if zid not in zone_ids:
                    raise ValueError(
                        f"AHU {ahu.ahu_id} references unknown zone '{zid}'"
                    )
        return self

    @model_validator(mode="after")
    def terminal_zone_refs_valid(self) -> BuildingSpec:
        zone_ids = {z.zone_id for z in self.zones}
        for t in self.terminals:
            if t.zone_id not in zone_ids:
                raise ValueError(
                    f"Terminal {t.terminal_id} references unknown zone '{t.zone_id}'"
                )
        return self

    @model_validator(mode="after")
    def floors_consistent(self) -> BuildingSpec:
        if self.zones:
            max_floor = max(z.floor for z in self.zones)
            if max_floor > self.num_floors:
                raise ValueError(
                    f"Zone on floor {max_floor} exceeds num_floors={self.num_floors}"
                )
        return self

    @model_validator(mode="after")
    def ahus_not_empty(self) -> BuildingSpec:
        if not self.ahus:
            raise ValueError("BuildingSpec must have at least one AHU")
        return self
