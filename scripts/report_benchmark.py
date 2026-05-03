#!/usr/bin/env python3
"""Generate QAR tables and per-query analysis from a benchmark results CSV.

Usage:
    python scripts/report_benchmark.py --input results/benchmark.csv
    python scripts/report_benchmark.py --input results/benchmark.csv --by-query
    python scripts/report_benchmark.py --input results/benchmark.csv --ablation
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def _load(csv_path: Path) -> list[dict]:
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def _qar(pass_n: int, total: int) -> str:
    if total == 0:
        return "  N/A"
    return f"{100 * pass_n / total:5.1f}%"


# ── Table 1: QAR by tier × category ──────────────────────────────────────────

def table_tier_category(rows: list[dict]) -> None:
    tiers = ["T1", "T2", "T3", "T4"]
    cats  = [1, 2, 3, 4, 5]
    cat_labels = {
        1: "Equip. Discovery",
        2: "Sensor/Point",
        3: "Topol. Traversal",
        4: "Aggregation",
        5: "Multi-hop/Complex",
    }
    tier_labels = {"T1": "Simple", "T2": "Standard", "T3": "Advanced", "T4": "Smart"}

    # Build stats[tier][cat] = {pass, total}
    stats: dict = defaultdict(lambda: defaultdict(lambda: {"pass": 0, "total": 0}))
    for r in rows:
        if r["status"] == "na":
            continue
        tier = r["tier"]
        cat  = int(r["category"])
        stats[tier][cat]["total"] += 1
        if r["status"] == "pass":
            stats[tier][cat]["pass"]  += 1

    # Header
    col_w = 18
    print("\nTable 1 — QAR by Building Tier and Query Category")
    print("=" * (col_w + 10 * len(tiers)))
    header = f"{'Category':<{col_w}}" + "".join(f"  {tier_labels.get(t, t):>8}" for t in tiers) + f"  {'Overall':>8}"
    print(header)
    print("-" * len(header))

    overall_pass  = defaultdict(int)
    overall_total = defaultdict(int)

    for cat in cats:
        row_pass  = []
        row_total = []
        for t in tiers:
            d = stats[t][cat]
            row_pass.append(d["pass"])
            row_total.append(d["total"])
            overall_pass[t]  += d["pass"]
            overall_total[t] += d["total"]

        all_pass  = sum(row_pass)
        all_total = sum(row_total)
        cells = "".join(f"  {_qar(p, n):>8}" for p, n in zip(row_pass, row_total))
        print(f"  {cat}. {cat_labels[cat]:<{col_w-4}}{cells}  {_qar(all_pass, all_total):>8}")

    # Overall row
    print("-" * len(header))
    overall_cells = "".join(f"  {_qar(overall_pass[t], overall_total[t]):>8}" for t in tiers)
    grand_p = sum(overall_pass.values())
    grand_n = sum(overall_total.values())
    print(f"  {'Overall QAR':<{col_w}}{overall_cells}  {_qar(grand_p, grand_n):>8}")
    print()


# ── Table 2: Per-query pass rate across all buildings ─────────────────────────

def table_per_query(rows: list[dict]) -> None:
    query_stats: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "na": 0, "error": 0})
    query_meta:  dict[str, dict] = {}

    for r in rows:
        qid = r["query_id"]
        query_stats[qid][r["status"]] += 1
        if qid not in query_meta:
            query_meta[qid] = {"cat": int(r["category"]), "diff": r["difficulty"]}

    print("\nTable 2 — Per-Query Pass Rate Across All Buildings")
    print("=" * 72)
    print(f"  {'ID':>4}  {'Cat':>4}  {'Diff':>6}  {'QAR':>8}  {'Pass/App':>10}  N/A")
    print("-" * 72)

    for qid in sorted(query_stats, key=lambda x: int(x[1:])):
        d    = query_stats[qid]
        meta = query_meta.get(qid, {})
        app  = d["pass"] + d["fail"] + d.get("error", 0)
        print(f"  {qid:>4}  {meta.get('cat',''):>4}  {meta.get('diff',''):>6}  "
              f"{_qar(d['pass'], app):>8}  {d['pass']:>4}/{app:<4}  {d['na']}")
    print()


# ── Table 3: Ablation — QAR by variant (populated manually or from tagged CSVs) ──

def table_ablation(rows: list[dict]) -> None:
    """Print ablation table if the CSV has a 'variant' column (from multi-run results)."""
    if not rows or "variant" not in rows[0]:
        print("\n[Ablation] CSV does not have a 'variant' column.")
        print("  Run the benchmark separately for each generator variant and merge the CSVs,")
        print("  adding a 'variant' column to identify each run.")
        return

    variant_stats: dict[str, dict] = defaultdict(lambda: {"pass": 0, "total": 0})
    for r in rows:
        if r["status"] == "na":
            continue
        v = r["variant"]
        variant_stats[v]["total"] += 1
        if r["status"] == "pass":
            variant_stats[v]["pass"]  += 1

    print("\nTable 3 — Ablation: QAR by Generator Variant")
    print("=" * 52)
    print(f"  {'Variant':<30}  {'QAR':>8}  {'Pass/App':>10}")
    print("-" * 52)
    for variant, d in variant_stats.items():
        print(f"  {variant:<30}  {_qar(d['pass'], d['total']):>8}  {d['pass']}/{d['total']}")
    print()


# ── QAR by difficulty × tier ──────────────────────────────────────────────────

def table_difficulty_tier(rows: list[dict]) -> None:
    tiers = ["T1", "T2", "T3", "T4"]
    diffs = ["easy", "medium", "hard"]
    stats: dict = defaultdict(lambda: defaultdict(lambda: {"pass": 0, "total": 0}))

    for r in rows:
        if r["status"] == "na":
            continue
        stats[r["difficulty"]][r["tier"]]["total"] += 1
        if r["status"] == "pass":
            stats[r["difficulty"]][r["tier"]]["pass"] += 1

    print("\nTable 4 — QAR by Difficulty and Tier")
    print("=" * 52)
    header = f"  {'Difficulty':<12}" + "".join(f"  {t:>8}" for t in tiers)
    print(header)
    print("-" * len(header))
    for diff in diffs:
        cells = "".join(f"  {_qar(stats[diff][t]['pass'], stats[diff][t]['total']):>8}" for t in tiers)
        print(f"  {diff:<12}{cells}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Report BuildGraph benchmark results")
    parser.add_argument("--input",    type=Path, required=True, help="benchmark CSV from run_benchmark.py")
    parser.add_argument("--by-query", action="store_true", help="Print per-query pass rate table")
    parser.add_argument("--ablation", action="store_true", help="Print ablation table (needs 'variant' column)")
    args = parser.parse_args()

    rows = _load(args.input)
    if not rows:
        print(f"No data in {args.input}", file=sys.stderr)
        sys.exit(1)

    n_files   = len({r["file"] for r in rows})
    n_queries = len({r["query_id"] for r in rows})
    print(f"\nBuildGraph Benchmark Report")
    print(f"  Source  : {args.input}")
    print(f"  Files   : {n_files}")
    print(f"  Queries : {n_queries}")
    print(f"  Rows    : {len(rows)}")

    table_tier_category(rows)
    table_difficulty_tier(rows)

    if args.by_query:
        table_per_query(rows)

    if args.ablation:
        table_ablation(rows)


if __name__ == "__main__":
    main()
