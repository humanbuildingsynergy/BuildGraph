"""Converts a BuildingArchetype into a BuildingSpec using deterministic RNG.

This is the non-LLM path: archetype bounds drive the sampling, producing
a fully-specified BuildingSpec that the extended builders consume.
"""
from __future__ import annotations

from random import Random

from ..archetypes.base import BuildingArchetype
from .schema import (
    AHUSpec, AHUType, BuildingSpec, PlantSpec, RelStyle, TerminalType,
    TerminalUnitSpec, ZoneSpec,
)

# ── Mapping tables ─────────────────────────────────────────────────────────────

_SYSTEM_TO_AHU_TYPE: dict[str, AHUType] = {
    "psz_ac":       "rtu",
    "pvav_reheat":  "single_duct",
    "vav_reheat":   "single_duct",
    "vav_doas":     "doas",
    "fcu_system":   "single_duct",  # fresh air handler feeding FCU terminals
    "doas_fcu":     "doas",         # dedicated OA system + FCU terminals
    "vrf_system":   "vrf",          # VRF outdoor condensing unit
}

# Zone type lists by building profile (weighted toward dominant space type)
_ZONE_TYPE_PROFILES: dict[str, list[str]] = {
    "office":     ["office", "office", "office", "corridor", "lobby", "storage", "server_room"],
    "school":     ["classroom", "classroom", "corridor", "lab", "office", "cafeteria", "gymnasium"],
    "hotel":      ["guestroom", "guestroom", "guestroom", "corridor", "lobby", "meeting_room"],
    "retail":     ["retail", "retail", "retail", "storage", "office", "corridor"],
    "healthcare": ["exam_room", "exam_room", "office", "corridor", "procedure_room", "waiting", "lab"],
    "hospital":   ["patient_room", "patient_room", "office", "corridor", "lab", "mechanical"],
}

_SPATIAL_LOCS = [
    "core", "perimeter_N", "perimeter_S", "perimeter_E", "perimeter_W"
]

_NAMING_STYLES = ["numeric", "hyphenated", "descriptive", "legacy"]
_NAMING_WEIGHTS = [40, 25, 25, 10]

_REL_STYLES: list[RelStyle] = ["standard", "inverse", "mixed"]
_REL_WEIGHTS = [50, 25, 25]

# ASHRAE climate zones — weighted by US commercial floor area share
_CLIMATE_ZONES = ["1A", "2A", "2B", "3A", "3B", "3C", "4A", "4B", "4C", "5A", "5B", "6A", "6B", "7"]
_CLIMATE_WEIGHTS = [4, 8, 3, 14, 10, 3, 16, 4, 3, 18, 6, 8, 3, 2]  # proportional to EIA CBECS floor area

# Zone conditioned area ranges (m²) by zone type
_ZONE_AREA_M2: dict[str, tuple[float, float]] = {
    "office":        (30.0, 120.0),
    "lab":           (50.0, 200.0),
    "corridor":      (20.0,  80.0),
    "classroom":     (60.0, 120.0),
    "patient_room":  (20.0,  40.0),
    "mechanical":    (30.0, 100.0),
    "lobby":         (80.0, 400.0),
    "storage":       (15.0,  60.0),
    "gymnasium":    (200.0, 800.0),
    "cafeteria":    (150.0, 400.0),
    "guestroom":     (25.0,  45.0),
    "retail":        (80.0, 400.0),
    "exam_room":     (20.0,  35.0),
    "procedure_room":(30.0,  60.0),
    "meeting_room":  (25.0,  80.0),
    "waiting":       (30.0, 100.0),
    "server_room":   (20.0,  80.0),
}

# Terminal type weights per HVAC system type
_TERMINAL_WEIGHTS: dict[str, tuple[list[TerminalType], list[int]]] = {
    "psz_ac":      (["cav"],                                                [100]),
    "pvav_reheat": (["vav_reheat", "fan_powered_vav", "vav_no_reheat", "dual_duct"], [75, 15, 5, 5]),
    "vav_reheat":  (["vav_reheat", "fan_powered_vav", "vav_no_reheat", "dual_duct"], [75, 15, 5, 5]),
    "vav_doas":    (["vav_reheat"],                                          [100]),
    "fcu_system":  (["fcu"],                                                [100]),
    "doas_fcu":    (["fcu"],                                                [100]),
    "vrf_system":  (["vrf_indoor"],                                         [100]),
}

# System types where AHU has a return fan
_HAS_RETURN_FAN = {"vav_reheat", "pvav_reheat", "vav_doas"}

# Zone types that do NOT receive dedicated HVAC terminal units
_NO_TERMINAL = frozenset({"mechanical", "storage", "server_room"})


# ── Public API ─────────────────────────────────────────────────────────────────

def archetype_to_spec(
    archetype: BuildingArchetype,
    rng: Random,
    seed: int = 0,
) -> BuildingSpec:
    """Return a fully-specified BuildingSpec from an archetype + seeded RNG.

    Uses rng for all sampling so the caller controls reproducibility.
    The builders use a *separate* RNG (Random(seed + 1)) to avoid
    coupling spec-sampling and graph-building random state.
    """
    n_floors = rng.randint(*archetype.floors_range)
    n_ahus   = rng.randint(*archetype.hvac.ahu_range)
    n_zones  = rng.randint(*archetype.total_zones_range)

    system_type  = archetype.hvac.system_type

    # PSZ-AC and VRF: each AHU/outdoor-unit serves at least one zone.
    # Cap n_ahus so every AHU gets its own zone (round-robin saturates otherwise).
    if system_type in ("psz_ac", "vrf_system"):
        n_ahus = min(n_ahus, n_zones)
    else:
        # Central systems (VAV, DOAS, FCU): floor-band assignment needs at least
        # one zone per AHU, otherwise the safety code produces structurally hollow AHUs.
        n_ahus = min(n_ahus, n_zones)
    ahu_type     = _SYSTEM_TO_AHU_TYPE.get(system_type, "single_duct")
    has_chiller  = archetype.hvac.has_chiller
    has_boiler   = archetype.hvac.has_boiler
    naming_style = rng.choices(_NAMING_STYLES, weights=_NAMING_WEIGHTS)[0]
    rel_style    = rng.choices(_REL_STYLES,   weights=_REL_WEIGHTS)[0]
    climate_zone = rng.choices(_CLIMATE_ZONES, weights=_CLIMATE_WEIGHTS)[0]
    zone_types   = _ZONE_TYPE_PROFILES.get(archetype.zone_profile, _ZONE_TYPE_PROFILES["office"])

    # ── Zones ──────────────────────────────────────────────────────────────────
    zones: list[ZoneSpec] = []
    per_floor = max(1, n_zones // n_floors)
    zi = 1
    lobby_placed = False
    for fi in range(1, n_floors + 1):
        remaining = n_zones - len(zones)
        count = per_floor if fi < n_floors else remaining
        for _ in range(max(0, count)):
            if len(zones) >= n_zones:
                break
            ztype = _pick_zone_type(zone_types, fi, n_floors, rng, lobby_placed)
            if ztype == "lobby":
                lobby_placed = True
            lo, hi = _ZONE_AREA_M2.get(ztype, (30.0, 120.0))
            zones.append(ZoneSpec(
                zone_id=f"Z{zi:03d}",
                name=f"Zone_F{fi}_Z{zi:03d}",
                zone_type=ztype,
                floor=fi,
                spatial_location=rng.choice(_SPATIAL_LOCS),
                area_m2=round(rng.uniform(lo, hi), 1),
            ))
            zi += 1

    # ── AHUs: spatially coherent zone assignment ───────────────────────────────
    buckets = _assign_zones_to_ahus(zones, n_ahus, system_type)

    is_vrf = (system_type == "vrf_system")
    has_return_fan  = system_type in _HAS_RETURN_FAN
    has_heat_recovery = (
        system_type in ("doas_fcu", "vav_doas")
        and archetype.vintage == "ashrae2013"
    )

    ahus: list[AHUSpec] = []
    for ai in range(1, n_ahus + 1):
        ahus.append(AHUSpec(
            ahu_id=f"A{ai:02d}",
            ahu_type=ahu_type,
            zone_ids=buckets[ai - 1] or [zones[0].zone_id],  # safety: never empty
            has_supply_fan=not is_vrf,
            has_return_fan=has_return_fan and not is_vrf,
            # 60% probability: ASHRAE 90.1 requires economizers in most U.S. climate zones;
            # the 40% without reflect buildings pre-dating the requirement or warm-humid
            # climates (1A, 2A) where economizers are not cost-effective.
            has_economizer_damper=(not is_vrf) and rng.random() < 0.6,
            has_return_damper=has_return_fan and not is_vrf,
            # 40% probability: exhaust dampers are common but not universal; many smaller
            # AHUs use gravity relief or transfer air instead of a powered exhaust damper.
            has_exhaust_damper=(not is_vrf) and rng.random() < 0.4,
            has_chw_coil=has_chiller and not is_vrf,
            has_hw_coil=has_boiler and not is_vrf,
            has_heat_recovery=has_heat_recovery and not is_vrf,
        ))

    # ── Terminal units: one per conditioned zone ───────────────────────────────
    # Mechanical rooms, storage rooms, and server rooms do not have dedicated
    # HVAC terminal units in real buildings. They are spatially present but
    # unconditioned or served only by corridor diffusers / emergency ventilation.
    terminals: list[TerminalUnitSpec] = []
    ti = 1
    for zone in zones:
        if zone.zone_type in _NO_TERMINAL:
            continue
        terminals.append(TerminalUnitSpec(
            terminal_id=f"T{ti:03d}",
            terminal_type=_pick_terminal_type(system_type, rng),
            zone_id=zone.zone_id,
        ))
        ti += 1

    # ── Plant ──────────────────────────────────────────────────────────────────
    if has_chiller:
        # Buildings with ≥4 AHUs represent large/hospital-scale plants where
        # N+1 redundancy (two chillers in lead-lag) is standard practice per
        # ASHRAE Handbook — HVAC Applications, Chapter 43 (central plants).
        n_chillers = rng.randint(1, 2) if n_ahus >= 4 else 1
        n_ct       = n_chillers   # one cooling tower per chiller (standard pairing)
        n_chwp     = n_chillers   # one dedicated CHW pump per chiller
        n_cwp      = n_chillers   # one condenser water pump per chiller
        ch_cfg     = "lead_lag" if n_chillers > 1 else "standalone"
    else:
        n_chillers = n_ct = n_chwp = n_cwp = 0
        ch_cfg = "standalone"

    if has_boiler:
        # Dual boilers only for very large plants (≥6 AHUs); smaller buildings
        # typically rely on a single boiler with a domestic HW backup.
        n_boilers = rng.randint(1, 2) if n_ahus >= 6 else 1
        n_hwp     = n_boilers   # one dedicated HW pump per boiler
        b_cfg     = "lead_lag" if n_boilers > 1 else "standalone"
    else:
        n_boilers = n_hwp = 0
        b_cfg = "standalone"

    plant = PlantSpec(
        num_chillers=n_chillers,
        chiller_config=ch_cfg,
        num_cooling_towers=n_ct,
        num_chw_pumps=n_chwp,
        num_condenser_water_pumps=n_cwp,
        num_boilers=n_boilers,
        boiler_config=b_cfg,
        num_hw_pumps=n_hwp,
    )

    _name_parts = archetype.name.split("_")
    if _name_parts[-1] in {"brick"}:
        _name_parts = _name_parts[:-1]
    _vi = next(
        (i for i, p in enumerate(_name_parts) if p in {"pre1980", "2004", "2013"}),
        len(_name_parts),
    )
    _building_type = "_".join(_name_parts[:_vi])

    return BuildingSpec(
        building_type=_building_type,
        vintage=archetype.vintage,
        ontology_mode=archetype.ontology_mode,
        naming_style=naming_style,
        seed=seed,
        climate_zone=climate_zone,
        num_floors=n_floors,
        zones=zones,
        ahus=ahus,
        terminals=terminals,
        plant=plant,
        sensor_density=archetype.hvac.sensor_density,
        rel_style=rel_style,
        has_electric_meter=archetype.has_electric_meter,
        has_lighting_meter=archetype.has_lighting_meter,
    )


def _pick_zone_type(
    zone_types: list[str],
    fi: int,
    n_floors: int,
    rng: Random,
    lobby_placed: bool,
) -> str:
    """Pick a zone type that respects floor placement constraints.

    lobby:      ground floor (fi==1) only, at most once per building.
    mechanical: ground floor (fi==1) or top floor (fi==n_floors) only.
    """
    allowed = [
        zt for zt in zone_types
        if not (zt == "lobby" and (fi != 1 or lobby_placed))
        and not (zt == "mechanical" and fi not in (1, n_floors))
    ]
    return rng.choice(allowed or zone_types)


def _pick_terminal_type(system_type: str, rng: Random) -> TerminalType:
    types, weights = _TERMINAL_WEIGHTS.get(system_type, (["vav_reheat"], [100]))
    return rng.choices(types, weights=weights)[0]


def _assign_zones_to_ahus(
    zones: list[ZoneSpec],
    n_ahus: int,
    system_type: str,
) -> list[list[str]]:
    """Assign zone_ids to AHU buckets.

    PSZ-AC (packaged units): round-robin — each RTU serves 1–3 nearby zones
    with no concept of floor band.

    Central systems (VAV, FCU, DOAS): floor-band assignment — each AHU serves
    a contiguous range of floors. When n_ahus > n_floors, the extra AHUs split
    a floor by wing (zones distributed round-robin within that floor's AHUs).
    """
    buckets: list[list[str]] = [[] for _ in range(n_ahus)]

    if system_type in ("psz_ac", "vrf_system"):
        for i, z in enumerate(zones):
            buckets[i % n_ahus].append(z.zone_id)
        return buckets

    # Group zone_ids by floor number
    by_floor: dict[int, list[str]] = {}
    for z in zones:
        by_floor.setdefault(z.floor, []).append(z.zone_id)

    sorted_floors = sorted(by_floor)
    n_floors = len(sorted_floors)

    if n_ahus <= n_floors:
        # One or more floors per AHU — assign floor bands
        for fi, floor_num in enumerate(sorted_floors):
            ai = min(int(fi * n_ahus / n_floors), n_ahus - 1)
            buckets[ai].extend(by_floor[floor_num])
    else:
        # More AHUs than floors — split floors into wings
        ahus_per_floor_base = n_ahus // n_floors
        extra = n_ahus % n_floors  # first `extra` floors get one additional AHU
        ahu_idx = 0
        for fi, floor_num in enumerate(sorted_floors):
            n_this = ahus_per_floor_base + (1 if fi < extra else 0)
            n_this = max(1, min(n_this, n_ahus - ahu_idx))
            for j, zid in enumerate(by_floor[floor_num]):
                buckets[ahu_idx + (j % n_this)].append(zid)
            ahu_idx += n_this

    # Safety: ensure no AHU bucket is completely empty
    for bi in range(n_ahus):
        if not buckets[bi]:
            src = max(range(n_ahus), key=lambda x: len(buckets[x]))
            if len(buckets[src]) > 1:
                buckets[bi].append(buckets[src].pop())
            elif zones:
                buckets[bi].append(zones[0].zone_id)

    return buckets
