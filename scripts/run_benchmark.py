#!/usr/bin/env python3
"""Run the BuildGraph SPARQL benchmark against a directory of TTL files.

Usage:
    # Run against a single file
    python scripts/run_benchmark.py --input data/output/brick/BG_small_office_pre1980_0000.ttl

    # Run against a full directory
    python scripts/run_benchmark.py --input data/output/brick/ --output results/benchmark.csv

    # Run only brick-mode files, all seeds
    python scripts/run_benchmark.py --input data/output/ --mode brick

    # Run against your own Brick TTL files with class normalization
    # (--inference expands owl:equivalentClass aliases; --no-meta excludes BuildGraph-specific queries)
    python scripts/run_benchmark.py --input path/to/your/buildings/ --inference --no-meta \
        --output results/benchmark_external.csv

    # Verbose: print per-query results for each file
    python scripts/run_benchmark.py --input data/output/brick/ --verbose
"""
import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.query import Result

# ── Class normalization (owl:equivalentClass expansion) ───────────────────────
# Based on owl:equivalentClass declarations in Brick Schema 1.3.
# Applied when --inference is set to make real buildings comparable to BuildGraph.
#
# Format: (alias_class, canonical_class) — instances of alias gain the canonical type.
# Also includes critical subclass chains (e.g., Variable_Air_Volume_Box_With_Reheat
# → Variable_Air_Volume_Box → VAV) since our scope/queries use the canonical names.

_BRICK_NS = "https://brickschema.org/schema/Brick#"

_EQUIV_NORM: list[tuple[str, str]] = [
    # AHU variants (brick:AHU owl:equivalentClass brick:Air_Handling_Unit)
    ("Air_Handling_Unit",  "AHU"),
    ("Air_Handler_Unit",   "AHU"),
    # Floor / Storey (brick:Floor owl:equivalentClass brick:Storey)
    ("Storey",  "Floor"),
    ("Floor",   "Storey"),
    # VAV / Variable_Air_Volume_Box (owl:equivalentClass)
    # Plus subclass chain: Variable_Air_Volume_Box_With_Reheat → Variable_Air_Volume_Box → VAV
    ("Variable_Air_Volume_Box",             "VAV"),
    ("Variable_Air_Volume_Box_With_Reheat", "VAV"),
    ("RVAV",                                "VAV"),
    # FCU (brick:FCU owl:equivalentClass brick:Fan_Coil_Unit)
    ("Fan_Coil_Unit", "FCU"),
    ("FCU",           "Fan_Coil_Unit"),
    # VFD (brick:VFD owl:equivalentClass brick:Variable_Frequency_Drive)
    ("Variable_Frequency_Drive", "VFD"),
    ("VFD",                      "Variable_Frequency_Drive"),
    # Fan (brick:Discharge_Fan owl:equivalentClass brick:Supply_Fan)
    ("Discharge_Fan", "Supply_Fan"),
    ("Supply_Fan",    "Discharge_Fan"),
    # RTU (brick:RTU owl:equivalentClass brick:Rooftop_Unit)
    ("Rooftop_Unit", "RTU"),
    ("RTU",          "Rooftop_Unit"),
]

# Queries that use BuildGraph-specific meta: predicates with scope='all'.
# Q43 and Q61 are already N/A via scope detection (has_lobby / has_server_room),
# but Q58 has scope='all' and must be explicitly excluded for real buildings.
_META_ONLY_QUERY_IDS: frozenset[str] = frozenset({"Q58"})


def _normalize_classes(g: Graph) -> None:
    """Add canonical Brick type assertions based on owl:equivalentClass relationships.

    This implements a targeted subset of OWL RL inference covering the specific
    class aliases most common in real Brick buildings (pre-1.3 names, IFC-derived
    classes, and subclass chains that alias into scope-detection classes).
    """
    new_triples: list[tuple] = []
    for alias, canonical in _EQUIV_NORM:
        alias_uri     = URIRef(f"{_BRICK_NS}{alias}")
        canonical_uri = URIRef(f"{_BRICK_NS}{canonical}")
        for subj in g.subjects(RDF.type, alias_uri):
            t = (subj, RDF.type, canonical_uri)
            if t not in g:
                new_triples.append(t)
    for triple in new_triples:
        g.add(triple)

_BENCHMARK = _ROOT / "benchmarks" / "sparql_queries.json"
_DEFAULT_OUT = _ROOT / "results" / "benchmark.csv"

# ── Tier assignment ────────────────────────────────────────────────────────────
# Filenames use the pattern: BG_{building_type}_{vintage}_{seed:04d}
#   building_type: full name, e.g. hospital, medium_office, hotel_vrf
#   vintage      : pre1980 | 2004 | 2013
#
# T4 Smart    : hospital/hotel/outpatient 2013 — DOAS+ERV, dense sensors
# T3 Advanced : large_office (any vintage), hospital/outpatient pre1980 & 2004
# T2 Standard : medium_office (any), hotel non-VRF (any), hotel_vrf — central plant
# T1 Simple   : small_office, primary_school, strip_mall, small_office_vrf — PSZ-AC/VRF

_TIER_RULES: list[tuple[list[str], str]] = [
    # T4: 2013-vintage complex systems with ERV
    (["hospital_2013"],     "T4"),
    (["hotel_2013"],        "T4"),
    (["outpatient_2013"],   "T4"),
    # T3: large/complex non-2013
    (["large_office"],      "T3"),
    (["hospital"],          "T3"),   # pre1980 and 2004 after T4 matched above
    (["outpatient"],        "T3"),
    # T2: central plant, standard density (hotel_vrf must precede hotel)
    (["hotel_vrf"],         "T2"),
    (["medium_office"],     "T2"),
    (["hotel"],             "T2"),
    # T1: packaged-unit or VRF (small_office_vrf must precede small_office)
    (["small_office_vrf"],  "T1"),
    (["small_office"],      "T1"),
    (["primary_school"],    "T1"),
    (["strip_mall"],        "T1"),
]

def _infer_tier(path: Path) -> str:
    name = path.stem.lower()
    for substrings, tier in _TIER_RULES:
        if all(s in name for s in substrings):
            return tier
    return "T2"  # fallback: medium_office, hotel pre1980/2004


# ── Scope detection ────────────────────────────────────────────────────────────

def _detect_scopes(g: Graph, scope_checks: dict[str, str], prefixes: str) -> set[str]:
    """Run ASK queries to determine which scope features this graph has."""
    active = {"all"}
    for feature, ask_body in scope_checks.items():
        sparql = f"{prefixes}\n{ask_body}"
        try:
            result = g.query(sparql)
            if bool(result):
                active.add(feature)
        except Exception:
            pass
    return active


# ── Query execution ────────────────────────────────────────────────────────────

def _run_query(g: Graph, sparql_body: str, prefixes: str) -> tuple[str, int]:
    """Execute one query. Returns (status, row_count).

    status: "pass" | "fail" | "na" | "error"
    """
    full_sparql = f"{prefixes}\n{sparql_body}"
    try:
        result: Result = g.query(full_sparql)
        rows = list(result)
        count = len(rows)
        return ("pass" if count > 0 else "fail", count)
    except Exception as exc:
        return ("error", 0)


# ── Per-file benchmark ─────────────────────────────────────────────────────────

def benchmark_file(
    ttl_path: Path,
    queries: list[dict],
    prefixes: str,
    scope_checks: dict[str, str],
    mode: str | None,
    verbose: bool,
    use_inference: bool = False,
    no_meta: bool = False,
) -> list[dict]:
    """Run all applicable queries against one TTL file. Returns list of result rows."""
    # Infer mode from path if not forced
    file_mode = mode
    if file_mode is None:
        for part in ttl_path.parts:
            if part in ("brick", "s223", "mixed"):
                file_mode = part
                break
        if file_mode is None:
            file_mode = "brick"  # fallback

    tier = _infer_tier(ttl_path)

    g = Graph()
    try:
        g.parse(str(ttl_path), format="turtle")
    except Exception as exc:
        print(f"  [PARSE ERROR] {ttl_path.name}: {exc}", file=sys.stderr)
        return []

    if use_inference:
        _normalize_classes(g)

    scopes = _detect_scopes(g, scope_checks, prefixes)

    rows = []
    for q in queries:
        # Skip queries not applicable to this mode
        if file_mode not in q.get("modes", ["brick", "mixed"]):
            status, count = "na", 0
        # Exclude BuildGraph-specific meta: queries from real-building denominator
        elif no_meta and q["id"] in _META_ONLY_QUERY_IDS:
            status, count = "na", 0
        else:
            # Check scope: all required scope features must be active
            required = set(q.get("scope", ["all"]))
            if not required.issubset(scopes):
                status, count = "na", 0
            else:
                status, count = _run_query(g, q["sparql"], prefixes)

        rows.append({
            "file":       ttl_path.name,
            "tier":       tier,
            "mode":       file_mode,
            "query_id":   q["id"],
            "category":   q["category"],
            "difficulty": q["difficulty"],
            "status":     status,   # pass | fail | na | error
            "row_count":  count,
        })

        if verbose:
            icon = {"pass": "✓", "fail": "✗", "na": "–", "error": "!"}.get(status, "?")
            print(f"    {icon} {q['id']:4s} ({q['difficulty']:6s})  {status:5s}  {q['nl'][:60]}")

    return rows


# ── Worker shim for parallel execution ────────────────────────────────────────

def _benchmark_worker(
    ttl_path_str: str,
    queries: list[dict],
    prefixes: str,
    scope_checks: dict[str, str],
    mode: str | None,
    verbose: bool,
    use_inference: bool,
    no_meta: bool,
) -> list[dict]:
    return benchmark_file(
        Path(ttl_path_str), queries, prefixes, scope_checks, mode, verbose,
        use_inference=use_inference, no_meta=no_meta,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run BuildGraph SPARQL benchmark")
    parser.add_argument("--input",   type=Path, required=True,  help="TTL file or directory of TTL files")
    parser.add_argument("--output",  type=Path, default=_DEFAULT_OUT, help="Output CSV path")
    parser.add_argument("--mode",    choices=["brick", "s223", "mixed"], help="Force ontology mode")
    parser.add_argument("--verbose", action="store_true", help="Print per-query results")
    parser.add_argument("--inference", action="store_true",
        help="Apply Brick 1.3 equivalentClass normalization before querying "
             "(fixes Air_Handling_Unit→AHU, Storey→Floor, Variable_Air_Volume_Box→VAV, etc.)")
    parser.add_argument("--no-meta", action="store_true",
        help="Exclude BuildGraph-specific meta: queries (Q58) from QAR denominator "
             "(appropriate when benchmarking real buildings)")
    parser.add_argument(
        "--workers", type=int, default=min(os.cpu_count() or 1, 8),
        help="Parallel worker processes (default: min(cpu_count, 8))",
    )
    args = parser.parse_args()

    # Load benchmark
    with open(_BENCHMARK) as f:
        bench = json.load(f)
    prefixes     = bench["prefixes"]
    queries      = bench["queries"]
    scope_checks = bench["scope_checks"]

    # Collect TTL files
    input_path = args.input
    if input_path.is_file():
        ttl_files = [input_path]
    else:
        ttl_files = sorted(input_path.rglob("*.ttl"))

    if not ttl_files:
        print(f"No TTL files found under {input_path}", file=sys.stderr)
        sys.exit(1)

    use_inference = args.inference
    no_meta       = args.no_meta

    print(f"BuildGraph SPARQL Benchmark")
    print(f"  Queries   : {len(queries)}")
    print(f"  Files     : {len(ttl_files)}")
    print(f"  Workers   : {args.workers}")
    print(f"  Inference : {use_inference} (equivalentClass normalization)")
    print(f"  No-meta   : {no_meta} (exclude Q58 from denominator)")
    print(f"  Output    : {args.output}")
    print()

    # Run benchmark (parallel)
    all_rows: list[dict] = []
    t0 = time.time()
    done = 0
    total_files = len(ttl_files)

    if args.workers == 1 or args.verbose:
        for i, ttl in enumerate(ttl_files, 1):
            if args.verbose:
                print(f"[{i}/{total_files}] {ttl.name}")
            else:
                print(f"\r  Progress: {i}/{total_files}", end="", flush=True)
            rows = benchmark_file(ttl, queries, prefixes, scope_checks, args.mode, args.verbose,
                                  use_inference=use_inference, no_meta=no_meta)
            all_rows.extend(rows)
    else:
        work = [(str(ttl), queries, prefixes, scope_checks, args.mode, False, use_inference, no_meta)
                for ttl in ttl_files]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_benchmark_worker, *item): item for item in work}
            for future in as_completed(futures):
                done += 1
                print(f"\r  Progress: {done}/{total_files}", end="", flush=True)
                rows = future.result()
                all_rows.extend(rows)

    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.1f}s")

    # Write CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["file", "tier", "mode", "query_id", "category", "difficulty", "status", "row_count"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Print summary
    _print_summary(all_rows, queries)


def _print_summary(rows: list[dict], queries: list[dict]) -> None:
    """Print QAR summary tables to stdout."""
    from collections import defaultdict

    # Applicable QAR per tier (exclude na)
    tier_stats: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "na": 0, "error": 0})
    cat_stats:  dict[int, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "na": 0, "error": 0})
    diff_stats: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "na": 0, "error": 0})

    for r in rows:
        tier_stats[r["tier"]][r["status"]] += 1
        cat_stats[r["category"]][r["status"]] += 1
        diff_stats[r["difficulty"]][r["status"]] += 1

    def qar(d: dict) -> str:
        total = d["pass"] + d["fail"] + d.get("error", 0)
        if total == 0:
            return "  N/A"
        return f"{100*d['pass']/total:5.1f}%"

    def applicable(d: dict) -> str:
        total = d["pass"] + d["fail"] + d.get("error", 0)
        return f"{d['pass']}/{total}"

    print()
    print("─" * 56)
    print("  QAR by Building Tier (applicable queries only)")
    print("─" * 56)
    print(f"  {'Tier':<8}  {'QAR':>8}  {'Pass/App':>12}  Label")
    print(f"  {'────':<8}  {'───':>8}  {'────────':>12}  ─────")
    labels = {"T1": "Simple/Legacy", "T2": "Standard", "T3": "Advanced", "T4": "Smart"}
    for tier in sorted(tier_stats):
        d = tier_stats[tier]
        print(f"  {tier:<8}  {qar(d):>8}  {applicable(d):>12}  {labels.get(tier,'')}")

    print()
    print("─" * 56)
    print("  QAR by Query Category")
    print("─" * 56)
    cat_labels = {
        1: "Equipment Discovery",
        2: "Sensor/Point Relationships",
        3: "Topological Traversal",
        4: "Aggregation",
        5: "Multi-hop / Complex",
    }
    print(f"  {'Cat':>4}  {'QAR':>8}  {'Pass/App':>12}  Label")
    print(f"  {'───':>4}  {'───':>8}  {'────────':>12}  ─────")
    for cat in sorted(cat_stats):
        d = cat_stats[cat]
        print(f"  {cat:>4}  {qar(d):>8}  {applicable(d):>12}  {cat_labels.get(cat,'')}")

    print()
    print("─" * 56)
    print("  QAR by Difficulty")
    print("─" * 56)
    print(f"  {'Difficulty':<10}  {'QAR':>8}  {'Pass/App':>12}")
    print(f"  {'──────────':<10}  {'───':>8}  {'────────':>12}")
    for diff in ["easy", "medium", "hard"]:
        d = diff_stats.get(diff, {"pass": 0, "fail": 0})
        print(f"  {diff:<10}  {qar(d):>8}  {applicable(d):>12}")

    total_pass = sum(d["pass"] for d in tier_stats.values())
    total_app  = sum(d["pass"] + d["fail"] + d.get("error", 0) for d in tier_stats.values())
    total_na   = sum(d["na"] for d in tier_stats.values())
    print()
    print(f"  Overall applicable QAR : {100*total_pass/total_app:.1f}%  ({total_pass}/{total_app})")
    print(f"  N/A (out-of-scope)      : {total_na} query-file pairs skipped")
    print()


if __name__ == "__main__":
    main()
