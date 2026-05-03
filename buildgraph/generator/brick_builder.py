"""Generates Brick-ontology TTL from a BuildingSpec."""
from __future__ import annotations

from random import Random

import uuid as _uuid_module

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef, XSD
from rdflib.namespace import RDFS

from .schema import AHUSpec, BuildingSpec, TerminalUnitSpec, ZoneSpec
from .naming import NamingStrategy, bldg_namespace
from .patterns import get_brick_points

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF   = Namespace("https://brickschema.org/schema/Brick/ref#")
UNIT  = Namespace("http://qudt.org/vocab/unit/")
META  = Namespace("https://buildgraph.org/meta#")

_DENSITY_SCALE = {"sparse": 0.4, "standard": 1.0, "dense": 1.4}

# Deterministic UUID namespace for BuildGraph timeseries references
_BG_UUID_NS = _uuid_module.UUID("8be9f5e4-6178-4a2e-b231-f9dc27a0f2e3")

# Brick class map for terminal unit types
_TERMINAL_BRICK_CLASS: dict[str, str] = {
    "vav_reheat":      "VAV",
    "vav_no_reheat":   "VAV",
    "fan_powered_vav": "Variable_Air_Volume_Box_With_Reheat",
    "fcu":             "Fan_Coil_Unit",
    "cav":             "VAV",
    "dual_duct":       "VAV",
}

# Empirical pattern lookup key per terminal type
_TERMINAL_PATTERN_CLASS: dict[str, str] = {
    "vav_reheat":      "VAV",
    "vav_no_reheat":   "VAV",
    "fan_powered_vav": "Variable_Air_Volume_Box_With_Reheat",
    "fcu":             "Terminal_Unit",
    "cav":             "VAV",
    "dual_duct":       "VAV",
}


def build(spec: BuildingSpec, bldg_id: str, ns: Namespace, rng: Random) -> Graph:
    g = Graph()
    g.bind("brick", BRICK)
    g.bind("ref", REF)
    g.bind("unit", UNIT)
    g.bind("meta", META)
    g.bind("bldg", ns)

    namer     = NamingStrategy(ns, spec.naming_style)
    density   = _DENSITY_SCALE[spec.sensor_density]
    rel_style = spec.rel_style

    bldg_uri = ns[bldg_id]
    g.add((bldg_uri, RDF.type, BRICK.Building))
    g.add((bldg_uri, META.buildingType,  Literal(spec.building_type)))
    g.add((bldg_uri, META.vintage,       Literal(spec.vintage)))
    g.add((bldg_uri, META.climateZone,   Literal(spec.climate_zone)))
    g.add((bldg_uri, META.namingStyle,   Literal(spec.naming_style)))

    # Build zone_id → (ZoneSpec, URIRef) map
    zone_map = _make_spatial(g, namer, bldg_uri, spec, rel_style, density, rng)

    # AHUs + sub-components
    ahu_uris: dict[str, URIRef] = {}
    for ai, ahu_spec in enumerate(spec.ahus, 1):
        ahu_uri = _make_ahu(g, namer, ahu_spec, ai, density, rng, rel_style)
        ahu_uris[ahu_spec.ahu_id] = ahu_uri

    # Terminal units (VAV / FCU / etc.)
    fcu_uris = _make_terminals(g, namer, spec, zone_map, ahu_uris, density, rng, rel_style)

    # Central plant
    _make_plant(g, namer, spec, list(ahu_uris.values()), fcu_uris, density, rng, rel_style)

    # DOAS (hospital / vav_doas)
    if spec.ahus and any(a.ahu_type == "doas" for a in spec.ahus):
        _make_doas(g, namer, spec, zone_map, density, rng, rel_style)

    # Meters
    if spec.has_electric_meter:
        m = namer.ns["ElectricMeter"]
        g.add((m, RDF.type, BRICK.Electrical_Meter))
        g.add((m, BRICK.isPointOf, bldg_uri))
    if spec.has_lighting_meter:
        m = namer.ns["LightingMeter"]
        g.add((m, RDF.type, BRICK.Lighting_Meter))
        g.add((m, BRICK.isPointOf, bldg_uri))

    return g


# ── Spatial hierarchy ─────────────────────────────────────────────────────────

def _make_spatial(
    g: Graph,
    namer: NamingStrategy,
    bldg_uri: URIRef,
    spec: BuildingSpec,
    rel_style: str = "standard",
    density: float = 1.0,
    rng: Random | None = None,
) -> dict[str, tuple[ZoneSpec, URIRef]]:
    """Create Floor and HVAC_Zone nodes; return zone_id → (ZoneSpec, URIRef)."""
    floor_uris: dict[int, URIRef] = {}
    for fi in range(1, spec.num_floors + 1):
        f = namer.floor(fi)
        g.add((f, RDF.type, BRICK.Floor))
        g.add((bldg_uri, BRICK.hasPart, f))
        floor_uris[fi] = f

    zone_map: dict[str, tuple[ZoneSpec, URIRef]] = {}
    zone_counter: dict[int, int] = {}
    for zspec in spec.zones:
        fi = zspec.floor
        zone_counter[fi] = zone_counter.get(fi, 0) + 1
        z_uri = namer.zone(fi, zone_counter[fi])
        g.add((z_uri, RDF.type, BRICK.HVAC_Zone))
        g.add((floor_uris[fi], BRICK.hasPart, z_uri))
        g.add((z_uri, RDFS.label, Literal(zspec.name)))
        g.add((z_uri, META.zoneType, Literal(zspec.zone_type)))
        g.add((z_uri, META.spatialLocation, Literal(zspec.spatial_location)))
        g.add((z_uri, META.floorAreaM2, Literal(zspec.area_m2, datatype=XSD.decimal)))
        zone_map[zspec.zone_id] = (zspec, z_uri)
        if rng is not None:
            _attach_points(g, namer, z_uri, namer.local(z_uri), "HVAC_Zone", density, rng, rel_style)
            _ensure_zone_temp_sensor(g, namer, z_uri, namer.local(z_uri), rel_style, rng)

    return zone_map


# ── AHU + sub-components ──────────────────────────────────────────────────────

def _make_ahu(
    g: Graph,
    namer: NamingStrategy,
    ahu_spec: AHUSpec,
    ai: int,
    density: float,
    rng: Random,
    rel_style: str = "standard",
) -> URIRef:
    a = namer.ahu(ai)
    lbl = namer.ahu_label(ai)

    if ahu_spec.ahu_type == "vrf":
        g.add((a, RDF.type, META.VRFOutdoorUnit))
        _attach_points(g, namer, a, lbl, "AHU", density, rng, rel_style)
        return a

    g.add((a, RDF.type, BRICK.AHU))

    # Supply fan (always)
    if ahu_spec.has_supply_fan:
        sf = namer.supply_fan(lbl)
        g.add((sf, RDF.type, BRICK.Supply_Fan))
        g.add((a, BRICK.hasPart, sf))
        _attach_points(g, namer, sf, namer.local(sf), "Supply_Fan", density, rng, rel_style)
        # VFD on supply fan
        vfd = namer.vfd(namer.local(sf))
        g.add((vfd, RDF.type, BRICK.Variable_Frequency_Drive))
        g.add((vfd, BRICK.controls, sf))

    # Return fan
    if ahu_spec.has_return_fan:
        rf = namer.return_fan(lbl)
        g.add((rf, RDF.type, BRICK.Return_Fan))
        g.add((a, BRICK.hasPart, rf))
        _attach_points(g, namer, rf, namer.local(rf), "Return_Fan", density, rng, rel_style)
        vfd_rf = namer.vfd(namer.local(rf))
        g.add((vfd_rf, RDF.type, BRICK.Variable_Frequency_Drive))
        g.add((vfd_rf, BRICK.controls, rf))

    # Cooling coil (CHW)
    if ahu_spec.has_chw_coil:
        cc = namer.cooling_coil(lbl)
        g.add((cc, RDF.type, BRICK.Cooling_Coil))
        g.add((a, BRICK.hasPart, cc))
        _attach_points(g, namer, cc, namer.local(cc), "Cooling_Coil", density, rng, rel_style)

    # Heating coil (HW)
    if ahu_spec.has_hw_coil:
        hc = namer.heating_coil(lbl)
        g.add((hc, RDF.type, BRICK.Heating_Coil))
        g.add((a, BRICK.hasPart, hc))
        _attach_points(g, namer, hc, namer.local(hc), "Heating_Coil", density, rng, rel_style)

    # Dampers
    if ahu_spec.has_economizer_damper:
        ed = namer.economizer_damper(lbl)
        g.add((ed, RDF.type, BRICK.Economizer_Damper))
        g.add((a, BRICK.hasPart, ed))
        _attach_points(g, namer, ed, namer.local(ed), "Economizer_Damper", density, rng, rel_style)

    if ahu_spec.has_return_damper:
        rd = namer.return_damper(lbl)
        g.add((rd, RDF.type, BRICK.Return_Damper))
        g.add((a, BRICK.hasPart, rd))

    if ahu_spec.has_exhaust_damper:
        exd = namer.exhaust_damper(lbl)
        g.add((exd, RDF.type, BRICK.Exhaust_Damper))
        g.add((a, BRICK.hasPart, exd))

    # Heat recovery wheel (ERV) — ASHRAE 90.1-2013 §6.5.6 DOAS requirement
    if ahu_spec.has_heat_recovery:
        hrw = namer.ns[f"{lbl}_HeatRecoveryWheel"]
        g.add((hrw, RDF.type, BRICK.Heat_Exchanger))
        g.add((a, BRICK.hasPart, hrw))

    _attach_points(g, namer, a, lbl, "AHU", density, rng, rel_style)
    return a


# ── Terminal units ────────────────────────────────────────────────────────────

def _make_terminals(
    g: Graph,
    namer: NamingStrategy,
    spec: BuildingSpec,
    zone_map: dict[str, tuple[ZoneSpec, URIRef]],
    ahu_uris: dict[str, URIRef],
    density: float,
    rng: Random,
    rel_style: str = "standard",
) -> list[URIRef]:
    """Return URIs of all FCU terminals created (used by plant builder for A3)."""
    zone_to_ahu: dict[str, str] = {}
    for ahu_spec in spec.ahus:
        for zid in ahu_spec.zone_ids:
            zone_to_ahu[zid] = ahu_spec.ahu_id

    zone_counter: dict[int, int] = {}
    fcu_uris: list[URIRef] = []

    for t in spec.terminals:
        if t.zone_id not in zone_map:
            continue
        zspec, z_uri = zone_map[t.zone_id]
        fi = zspec.floor
        zone_counter[fi] = zone_counter.get(fi, 0) + 1
        zi = zone_counter[fi]

        ahu_id  = zone_to_ahu.get(t.zone_id)
        ahu_uri = ahu_uris.get(ahu_id) if ahu_id else next(iter(ahu_uris.values()))

        if t.terminal_type == "vrf_indoor":
            v = namer.vrf_indoor_unit(fi, zi)
            g.add((v, RDF.type, META.VRFIndoorUnit))
            g.add((ahu_uri, BRICK.feeds, v))
            g.add((v, BRICK.feeds, z_uri))
            _attach_points(g, namer, v, namer.local(v), "Terminal_Unit", density, rng, rel_style)
            continue

        brick_class   = _TERMINAL_BRICK_CLASS.get(t.terminal_type, "VAV")
        pattern_class = _TERMINAL_PATTERN_CLASS.get(t.terminal_type, "VAV")

        if t.terminal_type == "fcu":
            v = namer.fcu(fi, zi)
            fcu_uris.append(v)
        else:
            v = namer.vav(fi, zi)

        g.add((v, RDF.type, BRICK[brick_class]))
        g.add((ahu_uri, BRICK.feeds, v))
        g.add((v, BRICK.feeds, z_uri))
        _attach_points(g, namer, v, namer.local(v), pattern_class, density, rng, rel_style)

    # AHUs that only serve service zones (mechanical/storage/server_room) have no
    # terminals and therefore no brick:feeds. Add direct AHU→zone feeds so those
    # AHUs still have at least one reachable HVAC_Zone.
    terminal_zone_ids = {t.zone_id for t in spec.terminals}
    for ahu_spec in spec.ahus:
        ahu_uri = ahu_uris.get(ahu_spec.ahu_id)
        if ahu_uri is None:
            continue
        for zid in ahu_spec.zone_ids:
            if zid not in terminal_zone_ids and zid in zone_map:
                _, z_uri = zone_map[zid]
                g.add((ahu_uri, BRICK.feeds, z_uri))

    return fcu_uris


# ── Central plant ─────────────────────────────────────────────────────────────

def _make_plant(
    g: Graph,
    namer: NamingStrategy,
    spec: BuildingSpec,
    ahu_uris: list[URIRef],
    fcu_uris: list[URIRef],
    density: float,
    rng: Random,
    rel_style: str = "standard",
) -> None:
    plant = spec.plant

    # Build CHW pump URIs first so chillers can reference them
    chw_pump_uris: list[URIRef] = []
    for i in range(1, plant.num_chw_pumps + 1):
        p = namer.chw_pump(i)
        g.add((p, RDF.type, BRICK.Chilled_Water_Pump))
        for ahu in ahu_uris:
            g.add((p, BRICK.feeds, ahu))
        for fcu in fcu_uris:
            g.add((p, BRICK.feeds, fcu))
        vfd = namer.vfd(namer.local(p))
        g.add((vfd, RDF.type, BRICK.Variable_Frequency_Drive))
        g.add((vfd, BRICK.controls, p))
        chw_pump_uris.append(p)

    # Chillers → CHW pumps (correct chain: Chiller → Pump → AHU)
    # If no pumps present, fall back to direct Chiller → AHU connection
    chiller_uris: list[URIRef] = []
    for i in range(1, plant.num_chillers + 1):
        c = namer.chiller(i)
        g.add((c, RDF.type, BRICK.Chiller))
        if chw_pump_uris:
            for p in chw_pump_uris:
                g.add((c, BRICK.feeds, p))
        else:
            for ahu in ahu_uris:
                g.add((c, BRICK.feeds, ahu))
            for fcu in fcu_uris:
                g.add((c, BRICK.feeds, fcu))
        _attach_points(g, namer, c, namer.local(c), "Chiller", density, rng, rel_style)
        chiller_uris.append(c)

    # Cooling towers → feed condenser water side of chillers
    for i in range(1, plant.num_cooling_towers + 1):
        ct = namer.cooling_tower(i)
        g.add((ct, RDF.type, BRICK.Cooling_Tower))
        for c in chiller_uris:
            g.add((ct, BRICK.feeds, c))
        _attach_points(g, namer, ct, namer.local(ct), "Cooling_Tower", density, rng, rel_style)

    # Condenser water pumps
    for i in range(1, plant.num_condenser_water_pumps + 1):
        cp = namer.condenser_pump(i)
        g.add((cp, RDF.type, BRICK.Condenser_Water_Pump))
        for j in range(1, plant.num_cooling_towers + 1):
            g.add((cp, BRICK.feeds, namer.cooling_tower(j)))

    # Build HW pump URIs first so boilers can reference them
    hw_pump_uris: list[URIRef] = []
    for i in range(1, plant.num_hw_pumps + 1):
        hp = namer.hw_pump(i)
        g.add((hp, RDF.type, BRICK.Hot_Water_Pump))
        for ahu in ahu_uris:
            g.add((hp, BRICK.feeds, ahu))
        for fcu in fcu_uris:
            g.add((hp, BRICK.feeds, fcu))
        vfd_hw = namer.vfd(namer.local(hp))
        g.add((vfd_hw, RDF.type, BRICK.Variable_Frequency_Drive))
        g.add((vfd_hw, BRICK.controls, hp))
        hw_pump_uris.append(hp)

    # Boilers → HW pumps (correct chain: Boiler → Pump → AHU)
    # If no pumps present, fall back to direct Boiler → AHU connection
    for i in range(1, plant.num_boilers + 1):
        b = namer.boiler(i)
        g.add((b, RDF.type, BRICK.Boiler))
        if hw_pump_uris:
            for hp in hw_pump_uris:
                g.add((b, BRICK.feeds, hp))
        else:
            for ahu in ahu_uris:
                g.add((b, BRICK.feeds, ahu))
            for fcu in fcu_uris:
                g.add((b, BRICK.feeds, fcu))
        _attach_points(g, namer, b, namer.local(b), "Boiler", density, rng, rel_style)


# ── DOAS ──────────────────────────────────────────────────────────────────────

def _make_doas(
    g: Graph,
    namer: NamingStrategy,
    spec: BuildingSpec,
    zone_map: dict[str, tuple[ZoneSpec, URIRef]],
    density: float,
    rng: Random,
    rel_style: str = "standard",
) -> None:
    doas = namer.ns["DOAS01"]
    g.add((doas, RDF.type, BRICK.AHU))
    for _, z_uri in zone_map.values():
        g.add((doas, BRICK.feeds, z_uri))
    _attach_points(g, namer, doas, "DOAS01", "AHU", density, rng, rel_style)


# ── Sensor / point attachment ──────────────────────────────────────────────────

def _ensure_zone_temp_sensor(
    g: Graph,
    namer: NamingStrategy,
    z_uri: URIRef,
    lbl: str,
    rel_style: str,
    rng: Random,
) -> None:
    """Guarantee Zone_Air_Temperature_Sensor if the zone has any instrumentation.

    A zone that received occupancy sensors, setpoints, or CO2 sensors but no
    temperature sensor is physically inconsistent — conditioned spaces always
    have a thermostat/temperature sensor as the baseline measurement point.
    """
    has_any = (
        any(True for _ in g.objects(z_uri, BRICK.hasPoint))
        or any(True for _ in g.subjects(BRICK.isPointOf, z_uri))
    )
    if not has_any:
        return

    temp_class = BRICK.Zone_Air_Temperature_Sensor
    already = any(
        (pt, RDF.type, temp_class) in g
        for pt in (
            list(g.objects(z_uri, BRICK.hasPoint))
            + list(g.subjects(BRICK.isPointOf, z_uri))
        )
    )
    if already:
        return

    p = namer.point(lbl, "Zone_Air_Temperature_Sensor")
    g.add((p, RDF.type, temp_class))
    if rel_style == "inverse":
        g.add((p, BRICK.isPointOf, z_uri))
    elif rel_style == "mixed":
        g.add((z_uri, BRICK.hasPoint, p))
        g.add((p, BRICK.isPointOf, z_uri))
    else:
        g.add((z_uri, BRICK.hasPoint, p))
    _add_timeseries_ref(g, p)  # always present — no RNG to preserve existing sequence


def _attach_points(
    g: Graph,
    namer: NamingStrategy,
    equip: URIRef,
    equip_lbl: str,
    equip_class: str,
    density: float,
    rng: Random,
    rel_style: str = "standard",
) -> None:
    for entry in get_brick_points(equip_class):
        if rng.random() < min(entry.probability * density, 0.95):
            p = namer.point(equip_lbl, entry.object_class)
            g.add((p, RDF.type, BRICK[entry.object_class]))
            if rel_style == "inverse":
                g.add((p, BRICK.isPointOf, equip))
            elif rel_style == "mixed":
                g.add((equip, BRICK.hasPoint, p))
                g.add((p, BRICK.isPointOf, equip))
            else:
                g.add((equip, BRICK.hasPoint, p))
            # Timeseries reference (deterministic UUID from point URI)
            if rng.random() < 0.85:
                _add_timeseries_ref(g, p)


def _add_timeseries_ref(g: Graph, point_uri: URIRef) -> None:
    ts_id = str(_uuid_module.uuid5(_BG_UUID_NS, str(point_uri)))
    # Use a deterministic URN so the reference node is stable across runs and
    # survives TTL round-trips without BNode renaming.
    ref = URIRef(f"urn:buildgraph:tsref:{ts_id}")
    g.add((point_uri, REF.hasExternalReference, ref))
    g.add((ref, RDF.type, REF.TimeseriesReference))
    g.add((ref, REF.hasTimeseriesId, Literal(ts_id)))
