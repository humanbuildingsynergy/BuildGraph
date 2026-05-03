from dataclasses import replace
from typing import Iterator

from .base import BuildingArchetype, OntologyMode
from .doe_office import OFFICE_ARCHETYPES
from .doe_school import SCHOOL_ARCHETYPES
from .doe_hospital import HOSPITAL_ARCHETYPES
from .doe_hotel import HOTEL_ARCHETYPES
from .doe_retail import RETAIL_ARCHETYPES
from .doe_healthcare import HEALTHCARE_ARCHETYPES

_BASE_ARCHETYPES: list[BuildingArchetype] = (
    OFFICE_ARCHETYPES + SCHOOL_ARCHETYPES + HOSPITAL_ARCHETYPES
    + HOTEL_ARCHETYPES + RETAIL_ARCHETYPES + HEALTHCARE_ARCHETYPES
)

_MODES: tuple[OntologyMode, ...] = ("brick", "s223", "mixed")


def _expand(base: BuildingArchetype) -> list[BuildingArchetype]:
    return [
        replace(base, ontology_mode=m, name=f"{base.name}_{m}")
        for m in _MODES
    ]


ARCHETYPES: dict[str, BuildingArchetype] = {
    a.name: a
    for base in _BASE_ARCHETYPES
    for a in _expand(base)
}


def get_archetype(name: str) -> BuildingArchetype:
    """Get archetype by full name (e.g. 'medium_office_2004_brick')."""
    if name not in ARCHETYPES:
        raise KeyError(f"Unknown archetype '{name}'. Available: {list(ARCHETYPES)[:5]} ...")
    return ARCHETYPES[name]


def list_base_names() -> list[str]:
    """Return unique base archetype names without ontology mode suffix."""
    return sorted({a.name.rsplit("_", 1)[0] for a in ARCHETYPES.values()})


def iter_archetypes(
    base_names: list[str] | None = None,
    modes: list[OntologyMode] | None = None,
) -> Iterator[BuildingArchetype]:
    for archetype in ARCHETYPES.values():
        base = archetype.name.rsplit("_", 1)[0]
        if base_names and base not in base_names:
            continue
        if modes and archetype.ontology_mode not in modes:
            continue
        yield archetype
