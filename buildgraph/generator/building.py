"""Top-level generator: builds Brick TTL from a BuildingArchetype."""
from random import Random

from rdflib import Graph, Namespace

from ..archetypes.base import BuildingArchetype
from .naming import building_id, bldg_namespace
from .spec_builder import archetype_to_spec
from . import brick_builder


class BuildingGenerator:
    """Generates a synthetic Brick building TTL from an archetype."""

    def generate(self, archetype: BuildingArchetype, seed: int = 0) -> tuple[Graph, str]:
        """Return (graph, bldg_id) from an archetype.

        Converts the archetype to a BuildingSpec with Random(seed),
        then builds the graph with Random(seed + 1) to keep the two
        random streams independent.
        """
        spec = archetype_to_spec(archetype, Random(seed), seed)
        bldg_id = building_id(archetype.name, seed)
        ns = bldg_namespace(bldg_id)
        rng = Random(seed + 1)
        return brick_builder.build(spec, bldg_id, ns, rng), bldg_id
