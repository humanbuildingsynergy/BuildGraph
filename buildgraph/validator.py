"""Validator: checks generated TTLs for pattern coverage, valid class names,
structural/physical plausibility, SPARQL query answerability, and SHACL conformance.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Namespace, RDF
from rdflib.term import URIRef

from .archetypes.base import OntologyMode

_DATA_DIR = Path(__file__).parent.parent / "data"
_ONTO_DIR = _DATA_DIR / "ontology"

BRICK_NS  = "https://brickschema.org/schema/Brick#"
S223_NS   = "http://data.ashrae.org/standard223#"
META_NS   = "https://buildgraph.org/meta#"

_BRICK = Namespace(BRICK_NS)
_S223  = Namespace(S223_NS)
_META  = Namespace(META_NS)

# Zone types that do not require a dedicated HVAC terminal unit.
# Mechanical rooms, storage rooms, and server rooms may be unconditioned
# or served only by corridor diffusers / emergency ventilation.
_SERVICE_ZONE_TYPES = frozenset({"mechanical", "storage", "server_room"})

_BRICK_PFX_FULL = (
    "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
    "PREFIX meta:  <https://buildgraph.org/meta#>\n"
)


@dataclass
class ValidationResult:
    bldg_id: str
    ontology_mode: OntologyMode
    triple_count: int
    pattern_count: int
    known_patterns: list[str]        = field(default_factory=list)
    unknown_classes: list[str]       = field(default_factory=list)
    structural_issues: list[str]     = field(default_factory=list)
    answerability_failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.pattern_count >= 3
            and not self.unknown_classes
            and not self.structural_issues
            and not self.answerability_failures
        )

    def summary(self) -> str:
        status = "OK" if self.ok else "WARN"
        parts = [
            f"[{status}] {self.bldg_id} ({self.ontology_mode}):",
            f"{self.triple_count} triples,",
            f"{self.pattern_count} patterns",
        ]
        if self.unknown_classes:
            parts.append(f"unknown: {self.unknown_classes}")
        if self.structural_issues:
            parts.append(f"issues: {self.structural_issues}")
        if self.answerability_failures:
            parts.append(f"answerability: {self.answerability_failures}")
        return " ".join(parts)


# ── Ontology class loaders ─────────────────────────────────────────────────────

def _load_valid_classes(ontology_mode: OntologyMode) -> set[str]:
    classes: set[str] = set()
    if ontology_mode in ("brick", "mixed"):
        path = _ONTO_DIR / "Brick.ttl"
        if path.exists():
            g = Graph()
            g.parse(str(path), format="turtle")
            from rdflib.namespace import OWL
            for s in g.subjects(RDF.type, OWL.Class):
                if str(s).startswith(BRICK_NS):
                    classes.add(str(s)[len(BRICK_NS):])
        else:
            import warnings
            warnings.warn(
                f"Brick ontology not found at {path}. "
                "Unknown-class validation will be skipped. "
                "Download Brick.ttl from https://github.com/BrickSchema/Brick/releases "
                f"and place it in {_ONTO_DIR}/",
                UserWarning,
                stacklevel=3,
            )
    if ontology_mode in ("s223", "mixed"):
        path = _ONTO_DIR / "s223.ttl"
        if path.exists():
            g = Graph()
            g.parse(str(path), format="turtle")
            from rdflib.namespace import OWL
            for s in g.subjects(RDF.type, OWL.Class):
                if str(s).startswith(S223_NS):
                    classes.add(str(s)[len(S223_NS):])
        else:
            import warnings
            warnings.warn(
                f"ASHRAE 223p ontology not found at {path}. "
                "Unknown-class validation will be skipped. "
                "Download s223.ttl from https://open223.info/ "
                f"and place it in {_ONTO_DIR}/",
                UserWarning,
                stacklevel=3,
            )
    return classes


def _load_known_patterns(ontology_mode: OntologyMode) -> set[str]:
    """Load known (subject_class, property, object_class) tuples as strings."""
    patterns: set[str] = set()
    files = []
    if ontology_mode in ("brick", "mixed"):
        files.append(_DATA_DIR / "empirical_patterns.json")
    if ontology_mode in ("s223", "mixed"):
        files.append(_DATA_DIR / "s223_patterns.json")
    for path in files:
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
            entries = raw.get("patterns", []) if isinstance(raw, dict) else raw
            for e in entries:
                key = f"{e.get('subject_class')}::{e.get('property')}::{e.get('object_class')}"
                patterns.add(key)
    return patterns


# ── Structural completeness checks ────────────────────────────────────────────

def _check_structural(g: Graph, ontology_mode: OntologyMode) -> list[str]:
    """Return a list of structural/plausibility issues (empty = pass)."""
    issues: list[str] = []

    triple_count = len(g)
    if triple_count < 20:
        issues.append(f"Suspiciously low triple count ({triple_count}); expected ≥ 20")

    if ontology_mode in ("brick", "mixed"):
        issues.extend(_check_brick(g))
    if ontology_mode == "s223":
        issues.extend(_check_s223(g))
    elif ontology_mode == "mixed":
        # Mixed mode uses Brick types for spatial/equipment hierarchy;
        # only Connection-level S223 checks apply here.
        issues.extend(_check_s223_connections(g))

    return issues


def _check_brick(g: Graph) -> list[str]:
    issues: list[str] = []

    # ── Zone population ───────────────────────────────────────────────────────
    zones = set(g.subjects(RDF.type, _BRICK.HVAC_Zone))
    if not zones:
        issues.append("No HVAC_Zone nodes found in Brick graph")
        return issues

    # Classify zones by occupancy type.
    # Service zones (mechanical, storage, server_room) do not require a
    # dedicated terminal or zone-level temperature sensor; they may be
    # unconditioned or served only by passive ventilation.
    # Zones without a meta:zoneType are treated as occupied (defensive default).
    occupied: set = set()
    service: set  = set()
    for z in zones:
        zt = g.value(z, _META.zoneType)
        if zt is not None and str(zt) in _SERVICE_ZONE_TYPES:
            service.add(z)
        else:
            occupied.add(z)

    # ── Every floor must contain ≥1 zone (any type) ───────────────────────────
    floors = set(g.subjects(RDF.type, _BRICK.Floor))
    empty_floors = [
        str(f).split("#")[-1]
        for f in floors
        if not list(g.objects(f, _BRICK.hasPart))
    ]
    if empty_floors:
        issues.append(
            f"{len(empty_floors)} floor(s) have no zones (brick:hasPart): "
            f"{empty_floors[:3]}"
        )

    # ── Every occupied zone must be fed by ≥1 terminal ───────────────────────
    unfed = [
        str(z).split("#")[-1]
        for z in occupied
        if not list(g.subjects(_BRICK.feeds, z))
    ]
    if unfed:
        issues.append(
            f"{len(unfed)} occupied zone(s) have no terminal feeding them "
            f"(service zones excluded): {unfed[:5]}"
        )

    # ── Every AHU must feed ≥1 downstream node ───────────────────────────────
    ahus = set(g.subjects(RDF.type, _BRICK.AHU))
    if not ahus:
        issues.append("No AHU nodes found in Brick graph")
    else:
        dangling = [
            str(a).split("#")[-1]
            for a in ahus
            if not list(g.objects(a, _BRICK.feeds))
        ]
        if dangling:
            issues.append(f"{len(dangling)} AHU(s) feed nothing: {dangling[:3]}")

        # Every AHU must reach ≥1 HVAC_Zone via transitive feeds
        pfx = _BRICK_PFX_FULL
        disconnected = []
        for ahu in ahus:
            q = pfx + f"ASK {{ <{ahu}> brick:feeds+ ?z . ?z a brick:HVAC_Zone }}"
            try:
                if not bool(g.query(q)):
                    disconnected.append(str(ahu).split("#")[-1])
            except Exception:
                pass
        if disconnected:
            issues.append(
                f"{len(disconnected)} AHU(s) do not reach any HVAC_Zone via "
                f"brick:feeds+: {disconnected[:3]}"
            )

    # ── Plant consistency ─────────────────────────────────────────────────────
    chillers  = list(g.subjects(RDF.type, _BRICK.Chiller))
    chw_pumps = list(g.subjects(RDF.type, _BRICK.Chilled_Water_Pump))
    if chillers and not chw_pumps:
        issues.append(f"Building has {len(chillers)} chiller(s) but no CHW pumps")

    boilers  = list(g.subjects(RDF.type, _BRICK.Boiler))
    hw_pumps = list(g.subjects(RDF.type, _BRICK.Hot_Water_Pump))
    if boilers and not hw_pumps:
        issues.append(f"Building has {len(boilers)} boiler(s) but no HW pumps")

    # ── Every terminal must feed ≥1 zone (all failures reported) ─────────────
    terminal_classes = {
        _BRICK.VAV,
        _BRICK.Variable_Air_Volume_Box_With_Reheat,
        _BRICK.Fan_Coil_Unit,
        _BRICK.CAV,
    }
    terminals: set = set()
    for cls in terminal_classes:
        terminals.update(g.subjects(RDF.type, cls))

    if occupied and not terminals:
        issues.append("Building has occupied zones but no terminal units (VAV/FCU/CAV)")
    else:
        no_feed = [
            str(t).split("#")[-1]
            for t in terminals
            if not list(g.objects(t, _BRICK.feeds))
        ]
        if no_feed:
            issues.append(
                f"{len(no_feed)} terminal(s) feed no zone: {no_feed[:5]}"
            )

    # ── Every occupied zone with any sensor must have a temperature sensor ────
    # If a zone was assigned sensors (has ≥1 point), it must have a zone air
    # temperature sensor — partial sensor sets indicate a generation bug.
    pfx = _BRICK_PFX_FULL
    missing_temp: list[str] = []
    for z in occupied:
        has_any = (
            bool(list(g.objects(z, _BRICK.hasPoint)))
            or bool(list(g.subjects(_BRICK.isPointOf, z)))
        )
        if not has_any:
            continue  # sparse building: zone not instrumented — acceptable
        q = pfx + f"""ASK {{
            {{ <{z}> brick:hasPoint ?s . ?s a brick:Zone_Air_Temperature_Sensor }}
            UNION
            {{ ?s brick:isPointOf <{z}> . ?s a brick:Zone_Air_Temperature_Sensor }}
        }}"""
        try:
            if not bool(g.query(q)):
                missing_temp.append(str(z).split("#")[-1])
        except Exception:
            pass
    if missing_temp:
        issues.append(
            f"{len(missing_temp)} instrumented occupied zone(s) have sensors "
            f"but no Zone_Air_Temperature_Sensor: {missing_temp[:5]}"
        )

    return issues


def _check_s223(g: Graph) -> list[str]:
    issues: list[str] = []

    # --- every DomainSpace must be served by at least one terminal ------------
    domain_spaces = set(g.subjects(RDF.type, _S223.DomainSpace))
    if not domain_spaces:
        issues.append("No DomainSpace nodes found in S223 graph")
    else:
        # Service zones (mechanical/storage/server_room) do not get dedicated
        # terminals — same exemption as on the Brick side.
        occupied: set = set()
        for ds in domain_spaces:
            zt = g.value(ds, _META.zoneType)
            if zt is not None and str(zt) in _SERVICE_ZONE_TYPES:
                continue
            occupied.add(ds)

        if not occupied:
            issues.append("No occupied DomainSpace nodes found in S223 graph")
        else:
            unserved = [
                ds for ds in occupied
                if not list(g.subjects(_S223.hasDomainSpace, ds))
            ]
            if unserved:
                issues.append(
                    f"{len(unserved)} occupied DomainSpace(s) have no terminal serving them "
                    f"(service zones excluded): "
                    f"{[str(ds).split('#')[-1] for ds in unserved[:3]]}"
                )

    # --- every AirHandlingUnit must have ≥2 connection points -----------------
    ahus = set(g.subjects(RDF.type, _S223.AirHandlingUnit))
    if not ahus:
        issues.append("No AirHandlingUnit nodes found in S223 graph")
    else:
        for ahu in ahus:
            cps = list(g.objects(ahu, _S223.hasConnectionPoint))
            if len(cps) < 2:
                lbl = str(ahu).split("#")[-1]
                issues.append(
                    f"AirHandlingUnit {lbl} has only {len(cps)} connection point(s); "
                    f"expected ≥ 2 (supply out + return in)"
                )
                break

    issues.extend(_check_s223_connections(g))
    return issues


def _check_s223_connections(g: Graph) -> list[str]:
    """Check S223 Connection integrity — used for both pure S223 and mixed mode."""
    issues: list[str] = []

    # --- every Connection must have both endpoints ----------------------------
    connections = set(g.subjects(RDF.type, _S223.Connection))
    bad_conns: list[str] = []
    for conn in connections:
        has_from = bool(list(g.objects(conn, _S223.connectsFrom)))
        has_to   = bool(list(g.objects(conn, _S223.connectsTo)))
        if not has_from or not has_to:
            bad_conns.append(str(conn).split("#")[-1])
    if bad_conns:
        issues.append(
            f"{len(bad_conns)} Connection(s) missing connectsFrom/connectsTo: "
            f"{bad_conns[:3]}"
        )

    # --- plant consistency (S223 side) ----------------------------------------
    chillers = list(g.subjects(RDF.type, _S223.Chiller))
    pumps    = list(g.subjects(RDF.type, _S223.Pump))
    if chillers and not pumps:
        issues.append(f"Building has {len(chillers)} chiller(s) but no pumps")

    boilers = list(g.subjects(RDF.type, _S223.Boiler))
    if boilers and not pumps:
        issues.append(f"Building has {len(boilers)} boiler(s) but no pumps")

    return issues


# ── Query answerability checks ─────────────────────────────────────────────────
#
# Each entry: (description, scope_ask, select_sparql)
#   scope_ask  : None = always run; otherwise an ASK body — skip check if False
#   select_sparql: must return ≥1 row to pass
#
# Prefixes are prepended at runtime.

_BRICK_PFX = "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
_S223_PFX  = "PREFIX s223: <http://data.ashrae.org/standard223#>\n"
# _BRICK_PFX_FULL is defined at module level above (includes meta: prefix)

_ANSWERABILITY_BRICK: list[tuple[str, str | None, str]] = [
    (
        "AHU→zone chain (via terminal, feeds+)",
        None,
        "SELECT ?ahu WHERE { ?ahu a brick:AHU . ?ahu brick:feeds+ ?z . ?z a brick:HVAC_Zone } LIMIT 1",
    ),
    (
        "Zone has at least one sensor (hasPoint or isPointOf)",
        None,
        "SELECT ?z WHERE { ?z a brick:HVAC_Zone . { ?z brick:hasPoint ?s } UNION { ?s brick:isPointOf ?z } } LIMIT 1",
    ),
    (
        "AHU has at least one sensor",
        None,
        "SELECT ?ahu WHERE { ?ahu a brick:AHU . { ?ahu brick:hasPoint ?s } UNION { ?s brick:isPointOf ?ahu } } LIMIT 1",
    ),
    (
        "Floor→zone spatial hierarchy",
        None,
        "SELECT ?f WHERE { ?f a brick:Floor . ?f brick:hasPart ?z . ?z a brick:HVAC_Zone } LIMIT 1",
    ),
    (
        "Terminal unit exists and feeds a zone",
        None,
        "SELECT ?t WHERE { { ?t a brick:VAV } UNION { ?t a brick:Variable_Air_Volume_Box_With_Reheat } UNION { ?t a brick:Fan_Coil_Unit } UNION { ?t a brick:CAV } . ?t brick:feeds ?z . ?z a brick:HVAC_Zone } LIMIT 1",
    ),
    (
        "Chiller→CHWPump→AHU chain (feeds+)",
        "ASK { ?x a brick:Chiller }",
        "SELECT ?c WHERE { ?c a brick:Chiller . ?c brick:feeds+ ?p . ?p a brick:Chilled_Water_Pump . ?p brick:feeds+ ?ahu . ?ahu a brick:AHU } LIMIT 1",
    ),
    (
        "Boiler→HWPump→AHU chain (feeds+)",
        "ASK { ?x a brick:Boiler }",
        "SELECT ?b WHERE { ?b a brick:Boiler . ?b brick:feeds+ ?p . ?p a brick:Hot_Water_Pump . ?p brick:feeds+ ?ahu . ?ahu a brick:AHU } LIMIT 1",
    ),
    (
        "Zone air temperature sensor reachable from zone",
        None,
        "SELECT ?z WHERE { ?z a brick:HVAC_Zone . { ?z brick:hasPoint ?s . ?s a brick:Zone_Air_Temperature_Sensor } UNION { ?s brick:isPointOf ?z . ?s a brick:Zone_Air_Temperature_Sensor } } LIMIT 1",
    ),
]

_ANSWERABILITY_S223: list[tuple[str, str | None, str]] = [
    (
        "AHU has ≥2 connection points",
        None,
        "SELECT ?ahu WHERE { ?ahu a s223:AirHandlingUnit . ?ahu s223:hasConnectionPoint ?cp1 . ?ahu s223:hasConnectionPoint ?cp2 . FILTER(?cp1 != ?cp2) } LIMIT 1",
    ),
    (
        "DomainSpace served by a terminal (hasDomainSpace)",
        None,
        "SELECT ?ds WHERE { ?t s223:hasDomainSpace ?ds . ?ds a s223:DomainSpace } LIMIT 1",
    ),
    (
        "Connection has both endpoints",
        None,
        "SELECT ?c WHERE { ?c a s223:Connection . ?c s223:connectsFrom ?f . ?c s223:connectsTo ?t } LIMIT 1",
    ),
    (
        "DomainSpace has observable property",
        None,
        "SELECT ?ds WHERE { ?ds a s223:DomainSpace . ?ds s223:hasProperty ?p . ?p a s223:QuantifiableObservableProperty } LIMIT 1",
    ),
    (
        "Chiller→Pump connection chain exists",
        "ASK { ?x a s223:Chiller }",
        "SELECT ?c WHERE { ?c a s223:Chiller . ?c s223:hasConnectionPoint ?cp . ?conn s223:connectsFrom ?cp . ?conn s223:connectsTo ?pin . ?p s223:hasConnectionPoint ?pin . ?p a s223:Pump } LIMIT 1",
    ),
]

_ANSWERABILITY_MIXED: list[tuple[str, str | None, str]] = [
    # Brick side
    (
        "AHU→zone chain (Brick feeds+)",
        None,
        "SELECT ?ahu WHERE { ?ahu a brick:AHU . ?ahu brick:feeds+ ?z . ?z a brick:HVAC_Zone } LIMIT 1",
    ),
    (
        "Zone has sensor (Brick hasPoint or isPointOf)",
        None,
        "SELECT ?z WHERE { ?z a brick:HVAC_Zone . { ?z brick:hasPoint ?s } UNION { ?s brick:isPointOf ?z } } LIMIT 1",
    ),
    # S223 side
    (
        "AHU has S223 connection points",
        None,
        "SELECT ?ahu WHERE { ?ahu a brick:AHU . ?ahu s223:hasConnectionPoint ?cp } LIMIT 1",
    ),
    (
        "S223 Connection has both endpoints",
        None,
        "SELECT ?c WHERE { ?c a s223:Connection . ?c s223:connectsFrom ?f . ?c s223:connectsTo ?t } LIMIT 1",
    ),
    (
        "Chiller→CHWPump→AHU chain (Brick feeds+)",
        "ASK { ?x a brick:Chiller }",
        "SELECT ?c WHERE { ?c a brick:Chiller . ?c brick:feeds+ ?p . ?p a brick:Chilled_Water_Pump . ?p brick:feeds+ ?ahu . ?ahu a brick:AHU } LIMIT 1",
    ),
]


def _check_answerability(g: Graph, ontology_mode: OntologyMode) -> list[str]:
    """Run SPARQL spot-checks; return list of failure descriptions (empty = all pass)."""
    if ontology_mode == "brick":
        checks = _ANSWERABILITY_BRICK
        pfx = _BRICK_PFX
    elif ontology_mode == "s223":
        checks = _ANSWERABILITY_S223
        pfx = _S223_PFX
    else:
        checks = _ANSWERABILITY_MIXED
        pfx = _BRICK_PFX + _S223_PFX

    failures: list[str] = []
    for desc, scope_ask, select_body in checks:
        # Evaluate scope condition
        if scope_ask is not None:
            try:
                if not bool(g.query(pfx + scope_ask)):
                    continue  # not applicable to this building
            except Exception:
                continue

        # Run the SELECT check
        try:
            rows = list(g.query(pfx + select_body))
            if not rows:
                failures.append(desc)
        except Exception as exc:
            failures.append(f"{desc} [query error: {exc}]")

    return failures


# ── Public entry point ────────────────────────────────────────────────────────

def validate_building(ttl_path: Path, ontology_mode: OntologyMode) -> ValidationResult:
    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    bldg_id     = ttl_path.stem
    triple_count = len(g)

    # Determine target namespace
    ns_uri = BRICK_NS if ontology_mode == "brick" else S223_NS

    # Extract all typed entities and their types
    type_map: dict[str, str] = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        s_str = str(s)
        o_str = str(o)
        if o_str.startswith(BRICK_NS):
            type_map[s_str] = o_str[len(BRICK_NS):]
        elif o_str.startswith(S223_NS):
            type_map[s_str] = o_str[len(S223_NS):]

    # Extract (subject_class, property, object_class) patterns
    known_patterns = _load_known_patterns(ontology_mode)
    matched: list[str] = []
    for s, p, o in g:
        if not isinstance(o, URIRef):
            continue
        s_cls = type_map.get(str(s))
        o_cls = type_map.get(str(o))
        if s_cls and o_cls:
            prop_local = str(p).split("#")[-1]
            key = f"{s_cls}::{prop_local}::{o_cls}"
            if key in known_patterns:
                matched.append(key)

    # Check for unknown class names (requires bundled ontology)
    valid_classes = _load_valid_classes(ontology_mode)
    unknown: list[str] = []
    if valid_classes:
        for cls in set(type_map.values()):
            if cls not in valid_classes:
                unknown.append(cls)

    # Structural completeness checks
    structural_issues = _check_structural(g, ontology_mode)

    # SPARQL answerability spot-checks
    answerability_failures = _check_answerability(g, ontology_mode)

    return ValidationResult(
        bldg_id=bldg_id,
        ontology_mode=ontology_mode,
        triple_count=triple_count,
        pattern_count=len(set(matched)),
        known_patterns=list(set(matched))[:10],
        unknown_classes=unknown,
        structural_issues=structural_issues,
        answerability_failures=answerability_failures,
    )


# ── SHACL conformance check ───────────────────────────────────────────────────

def check_shacl_conformance(ttl_path: Path) -> tuple[bool, list[str]]:
    """Run Brick SHACL shapes against a generated TTL file.

    Requires ``brickschema`` (bundled shapes) and ``pyshacl`` (engine).
    Returns (conforms, violation_messages). If either package is missing,
    returns (True, []) with a warning — the caller can treat missing-package
    as a skip rather than a failure.
    """
    try:
        import brickschema  # noqa: PLC0415
    except ImportError:
        warnings.warn(
            "brickschema not installed; SHACL validation skipped. "
            "Install with: pip install brickschema pyshacl",
            UserWarning,
            stacklevel=2,
        )
        return True, []

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = brickschema.Graph()
        g.parse(str(ttl_path), format="turtle")
        conforms, _, results_text = g.validate(engine="pyshacl")
    except Exception as exc:
        return False, [f"SHACL engine error: {exc}"]

    violations: list[str] = []
    if not conforms and results_text:
        for line in results_text.splitlines():
            line = line.strip()
            if line.startswith("Constraint Violation"):
                violations.append(line)

    return bool(conforms), violations
