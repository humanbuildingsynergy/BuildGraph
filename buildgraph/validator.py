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

_DATA_DIR = Path(__file__).parent.parent / "data"
_ONTO_DIR = _DATA_DIR / "ontology"

BRICK_NS = "https://brickschema.org/schema/Brick#"
META_NS  = "https://buildgraph.org/meta#"

_BRICK = Namespace(BRICK_NS)
_META  = Namespace(META_NS)

_SERVICE_ZONE_TYPES = frozenset({"mechanical", "storage", "server_room"})

_BRICK_PFX_FULL = (
    "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
    "PREFIX meta:  <https://buildgraph.org/meta#>\n"
)
_BRICK_PFX = "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"


@dataclass
class ValidationResult:
    bldg_id: str
    triple_count: int
    pattern_count: int
    known_patterns: list[str]         = field(default_factory=list)
    unknown_classes: list[str]        = field(default_factory=list)
    structural_issues: list[str]      = field(default_factory=list)
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
            f"[{status}] {self.bldg_id}:",
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

def _load_valid_classes() -> set[str]:
    classes: set[str] = set()
    path = _ONTO_DIR / "Brick.ttl"
    if path.exists():
        g = Graph()
        g.parse(str(path), format="turtle")
        from rdflib.namespace import OWL
        for s in g.subjects(RDF.type, OWL.Class):
            if str(s).startswith(BRICK_NS):
                classes.add(str(s)[len(BRICK_NS):])
    else:
        warnings.warn(
            f"Brick ontology not found at {path}. "
            "Unknown-class validation will be skipped. "
            "Download Brick.ttl from https://github.com/BrickSchema/Brick/releases "
            f"and place it in {_ONTO_DIR}/",
            UserWarning,
            stacklevel=3,
        )
    return classes


def _load_known_patterns() -> set[str]:
    patterns: set[str] = set()
    path = _DATA_DIR / "empirical_patterns.json"
    if path.exists():
        with open(path) as f:
            raw = json.load(f)
        entries = raw.get("patterns", []) if isinstance(raw, dict) else raw
        for e in entries:
            key = f"{e.get('subject_class')}::{e.get('property')}::{e.get('object_class')}"
            patterns.add(key)
    return patterns


# ── Structural completeness checks ────────────────────────────────────────────

def _check_structural(g: Graph) -> list[str]:
    issues: list[str] = []

    if len(g) < 20:
        issues.append(f"Suspiciously low triple count ({len(g)}); expected ≥ 20")

    # ── Zone population ───────────────────────────────────────────────────────
    zones = set(g.subjects(RDF.type, _BRICK.HVAC_Zone))
    if not zones:
        issues.append("No HVAC_Zone nodes found in Brick graph")
        return issues

    occupied: set = set()
    service: set  = set()
    for z in zones:
        zt = g.value(z, _META.zoneType)
        if zt is not None and str(zt) in _SERVICE_ZONE_TYPES:
            service.add(z)
        else:
            occupied.add(z)

    # ── Every floor must contain ≥1 zone ─────────────────────────────────────
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

        disconnected = []
        for ahu in ahus:
            q = _BRICK_PFX_FULL + f"ASK {{ <{ahu}> brick:feeds+ ?z . ?z a brick:HVAC_Zone }}"
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

    # ── Every terminal must feed ≥1 zone ─────────────────────────────────────
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
            issues.append(f"{len(no_feed)} terminal(s) feed no zone: {no_feed[:5]}")

    # ── Every instrumented occupied zone must have a temperature sensor ───────
    missing_temp: list[str] = []
    for z in occupied:
        has_any = (
            bool(list(g.objects(z, _BRICK.hasPoint)))
            or bool(list(g.subjects(_BRICK.isPointOf, z)))
        )
        if not has_any:
            continue
        q = _BRICK_PFX_FULL + f"""ASK {{
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


# ── Query answerability checks ─────────────────────────────────────────────────

_ANSWERABILITY: list[tuple[str, str | None, str]] = [
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


def _check_answerability(g: Graph) -> list[str]:
    failures: list[str] = []
    for desc, scope_ask, select_body in _ANSWERABILITY:
        if scope_ask is not None:
            try:
                if not bool(g.query(_BRICK_PFX + scope_ask)):
                    continue
            except Exception:
                continue
        try:
            rows = list(g.query(_BRICK_PFX + select_body))
            if not rows:
                failures.append(desc)
        except Exception as exc:
            failures.append(f"{desc} [query error: {exc}]")
    return failures


# ── Public entry point ────────────────────────────────────────────────────────

def validate_building(ttl_path: Path) -> ValidationResult:
    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    bldg_id      = ttl_path.stem
    triple_count = len(g)

    type_map: dict[str, str] = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        s_str = str(s)
        o_str = str(o)
        if o_str.startswith(BRICK_NS):
            type_map[s_str] = o_str[len(BRICK_NS):]

    known_patterns = _load_known_patterns()
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

    valid_classes = _load_valid_classes()
    unknown: list[str] = []
    if valid_classes:
        for cls in set(type_map.values()):
            if cls not in valid_classes:
                unknown.append(cls)

    return ValidationResult(
        bldg_id=bldg_id,
        triple_count=triple_count,
        pattern_count=len(set(matched)),
        known_patterns=list(set(matched))[:10],
        unknown_classes=unknown,
        structural_issues=_check_structural(g),
        answerability_failures=_check_answerability(g),
    )


# ── SHACL conformance check ───────────────────────────────────────────────────

def check_shacl_conformance(ttl_path: Path) -> tuple[bool, list[str]]:
    """Run Brick SHACL shapes against a generated TTL file.

    Requires ``brickschema`` (bundled shapes) and ``pyshacl`` (engine).
    Returns (conforms, violation_messages).
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
