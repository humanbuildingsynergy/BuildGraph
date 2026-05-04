"""Serializes an rdflib Graph to a Turtle file."""
from pathlib import Path

from rdflib import Graph

_BRICK_NS = "https://brickschema.org/schema/Brick#"
_REF_NS = "https://brickschema.org/schema/Brick/ref#"

_PREFIXES: dict[str, str] = {
    "brick": _BRICK_NS,
    "ref":   _REF_NS,
}


def write_ttl(g: Graph, output_dir: Path, bldg_id: str, ontology_mode: str = "brick") -> Path:
    subdir = output_dir / ontology_mode
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{bldg_id}.ttl"
    g.serialize(destination=str(path), format="turtle")
    return path
