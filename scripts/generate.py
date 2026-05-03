#!/usr/bin/env python3
"""Generate synthetic Brick building TTL files.

The released dataset (data/output/brick/) contains 120 buildings: 24 archetypes
(8 building types × 3 vintages) × 5 seeds. This script can reproduce or extend
that dataset.

Usage:
    # One building (defaults: Brick mode, 1 seed)
    python scripts/generate.py --archetype medium_office_2004 --seeds 1

    # Reproduce the full released dataset (defaults match exactly)
    python scripts/generate.py --all --output data/output/

    # Generate additional seeds beyond the released 5
    python scripts/generate.py --all --seeds 10 --output data/output/
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from buildgraph.archetypes.registry import list_base_names, iter_archetypes

_DEFAULT_OUTPUT = _ROOT / "data" / "output"


def _init_worker(root: str) -> None:
    """Add project root to sys.path in each worker process."""
    if root not in sys.path:
        sys.path.insert(0, root)


def _generate_one(
    archetype_name: str,
    seed: int,
    output_dir: Path,
) -> tuple[str, int, str, str | None]:
    """Generate one building and write to disk.

    Returns (bldg_id, triple_count, filename, error).
    """
    from buildgraph.archetypes.registry import ARCHETYPES
    from buildgraph.generator.building import BuildingGenerator
    from buildgraph.writer.ttl import write_ttl
    try:
        archetype = ARCHETYPES[archetype_name]
        gen = BuildingGenerator()
        g, bldg_id = gen.generate(archetype, seed=seed)
        path = write_ttl(g, output_dir, bldg_id, "brick")
        return (bldg_id, len(g), path.name, None)
    except Exception as e:
        return (archetype_name, 0, "", str(e))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic building TTLs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--archetype", help="Base archetype name (e.g. 'medium_office_2004')")
    group.add_argument("--all", action="store_true", help="Generate all base archetypes")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds per config (default: 5, matching the released dataset)")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument(
        "--workers", type=int, default=min(os.cpu_count() or 1, 8),
        help="Parallel worker processes (default: min(cpu_count, 8))",
    )
    args = parser.parse_args()

    if args.all:
        base_names = list_base_names()
    else:
        valid_bases = set(list_base_names())
        if args.archetype not in valid_bases:
            print(f"ERROR: unknown archetype '{args.archetype}'")
            print("Valid archetypes:\n  " + "\n  ".join(sorted(valid_bases)))
            sys.exit(1)
        base_names = [args.archetype]

    work = [
        (archetype.name, seed, args.output)
        for archetype in iter_archetypes(base_names=base_names, modes=["brick"])
        for seed in range(args.seeds)
    ]

    if not work:
        print("No work to do — check --archetype argument.")
        sys.exit(1)

    total_jobs = len(work)
    print(f"Generating {total_jobs} buildings with {args.workers} worker(s)...\n")
    done = total = errors = 0

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_init_worker,
        initargs=(str(_ROOT),),
    ) as pool:
        futures = {pool.submit(_generate_one, *item): item for item in work}
        for future in as_completed(futures):
            done += 1
            bldg_id, triples, filename, err = future.result()
            if err:
                print(f"  [{done}/{total_jobs}] ERROR {bldg_id}: {err}")
                errors += 1
            else:
                print(f"  [{done}/{total_jobs}] {bldg_id}: {triples} triples → {filename}")
                total += 1

    print(f"\nDone. {total} buildings generated, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
