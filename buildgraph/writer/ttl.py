"""Serializes an rdflib Graph to a Turtle file, using mode-appropriate namespace bindings."""
from pathlib import Path

from rdflib import Graph

from ..archetypes.base import OntologyMode

_BRICK_NS = "https://brickschema.org/schema/Brick#"
_REF_NS = "https://brickschema.org/schema/Brick/ref#"
_S223_NS = "http://data.ashrae.org/standard223#"
_QUDT_NS = "http://qudt.org/schema/qudt/"
_QUDTQK_NS = "http://qudt.org/vocab/quantitykind/"
_QUDTUNIT_NS = "http://qudt.org/vocab/unit/"

_PREFIX_MAP: dict[OntologyMode, dict[str, str]] = {
    "brick": {
        "brick": _BRICK_NS,
        "ref": _REF_NS,
    },
    "s223": {
        "s223": _S223_NS,
        "qudt": _QUDT_NS,
        "qudtqk": _QUDTQK_NS,
        "qudtunit": _QUDTUNIT_NS,
    },
    "mixed": {
        "brick": _BRICK_NS,
        "ref": _REF_NS,
        "s223": _S223_NS,
        "qudt": _QUDT_NS,
    },
}


def write_ttl(g: Graph, output_dir: Path, bldg_id: str, ontology_mode: OntologyMode) -> Path:
    subdir = output_dir / ontology_mode
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{bldg_id}.ttl"
    g.serialize(destination=str(path), format="turtle")
    return path
