# BuildGraph

**Synthetic building knowledge graph generator grounded in DOE prototype archetypes.**

BuildGraph generates realistic `.ttl` files representing commercial buildings in the [Brick Schema](https://brickschema.org/) ontology. Building configurations are derived from U.S. DOE Commercial Prototype Building Models; sensor placement probabilities are calibrated against patterns mined from 65 real buildings on the [Mortar](https://mortardata.org/) platform.

---

## Dataset

The released dataset contains **120 Brick Schema buildings** (24 archetypes × 5 seeds), deposited at Zenodo:

> **DOI:** [https://doi.org/10.5281/zenodo.20015123](https://doi.org/10.5281/zenodo.20015123)

Each building is a self-contained RDF Turtle (`.ttl`) file. Filenames follow the convention `BG_{type}_{vintage}_{seed:04d}.ttl` — for example, `BG_hospital_2013_0002.ttl`.

**Coverage:** 8 commercial building types × 3 ASHRAE energy code vintages:

| Building Type | HVAC System | Terminal | Central Plant |
|---|---|---|---|
| Small Office | PSZ-AC (RTU) | CAV | No |
| Medium Office | PVAV + Reheat | VAV mix | Yes |
| Large Office | VAV + Reheat | VAV mix | Yes |
| Primary School | PSZ-AC | CAV | No |
| Hospital | VAV + DOAS | VAV reheat | Yes |
| Hotel | FCU / DOAS+FCU (2013) | FCU | Yes |
| Strip Mall | PSZ-AC (RTU) | CAV | No |
| Outpatient Healthcare | FCU / DOAS+FCU | FCU | Yes |

**Vintages:** `pre1980` (sparse sensors, 40% density), `2004` (standard, 100%), `2013` (dense, 140%; adds ERV on DOAS AHUs and electric metering).

Dataset scale ranges from ~100 triples (sparse pre-1980 strip mall) to ~11,000 triples (dense 2013 hotel), with a mean of 1,865 triples and 470 typed entities per building.

---

## Installation

```bash
git clone https://github.com/humanbuildingsynergy/BuildGraph.git
cd BuildGraph
pip install -r requirements.txt
```

Python 3.10+ required. No external services needed for the deterministic archetype path.

---

## Quick Start

### Generate a building

```bash
# One building (Brick mode is the default; --seeds 1 for a quick test)
python scripts/generate.py --archetype medium_office_2004 --seeds 1

# Reproduce the full released dataset — defaults match exactly (Brick, 5 seeds)
python scripts/generate.py --all --output data/output/
```

Output files are written to `data/output/brick/BG_{type}_{vintage}_{seed:04d}.ttl`.

### Run the SPARQL benchmark

```bash
# Run all 75 queries against a directory of TTL files
python scripts/run_benchmark.py \
    --input data/output/brick/ \
    --output results/benchmark.csv

# Verbose: per-query results for a single file
python scripts/run_benchmark.py \
    --input data/output/brick/BG_hospital_2013_0000.ttl \
    --verbose
```

---

## Ontology and Heterogeneity

All buildings use the [Brick Schema](https://brickschema.org/) ontology (v1.3): equipment-centric, with `brick:hasPoint` / `brick:isPointOf` for sensor attachment and `brick:feeds` for topology.

Each building independently samples one of three sensor-attachment styles (50% `hasPoint`-only / 25% `isPointOf`-only / 25% both), and one of four URI naming styles (`numeric`, `hyphenated`, `descriptive`, `legacy`), mirroring heterogeneity found in real deployed Brick buildings.

---

## SPARQL Benchmark

**File:** `benchmarks/sparql_queries.json` — 75 queries across 5 categories with automatic scope detection.

| Category | Description | BuildGraph QAR |
|---|---|---|
| 1 | Equipment Discovery | 96.9% |
| 2 | Sensor/Point Relations | 82.6% |
| 3 | Topological Traversal | 92.5% |
| 4 | Aggregation | 98.7% |
| 5 | Multi-hop / Complex | 89.1% |
| **Overall** | | **91.5%** |

Results stratified by building complexity tier (120 buildings, Brick mode):

| Tier | Building types | QAR |
|---|---|---|
| T1 Simple | small_office, primary_school, strip_mall | 87.5% |
| T2 Standard | medium_office, hotel (pre1980/2004) | 91.7% |
| T3 Advanced | large_office, hospital/outpatient (pre1980/2004) | 92.9% |
| T4 Smart | hospital/hotel/outpatient 2013 | 96.5% |

For comparison, 59 publicly available real-world Brick building files (44 from the Mortar platform, 4 from the BuildingQA benchmark, and 11 additional community files) achieve an aggregate QAR of 35.8% on the same benchmark.

**QAR (Query Answerability Rate):** fraction of applicable queries returning ≥1 result row. Queries out of scope for a building (e.g., chiller queries on packaged-unit buildings) are excluded from the denominator.

---

## Text-to-SPARQL Baselines

`prompts/` contains the prompt templates and full protocol documentation for the
text-to-SPARQL pilot evaluation reported in the paper. Using Gemma 4 (27B) on 12
held-out buildings:

| Condition | Exec. Accuracy | Row-Matching F1 |
|---|---|---|
| Zero-shot | 21.2% | 9.8% |
| Few-shot (3 cross-building examples) | 54.6% | 27.3% |

See [`prompts/README.md`](prompts/README.md) for the full prompt structure, evaluation
protocol, metric definitions, and instructions for running your own evaluation with any
model.

---

## Repo Structure

```
BuildGraph/
├── buildgraph/
│   ├── archetypes/          ← DOE prototype parameters as Python dataclasses
│   ├── generator/           ← Brick builder, spec converter, naming strategy
│   └── writer/              ← TTL serializer
├── benchmarks/
│   └── sparql_queries.json  ← 75 SPARQL queries, scope checks, tier rules
├── prompts/
│   ├── system.txt           ← System message for text-to-SPARQL prompting
│   ├── building_summary.md  ← Annotated building context template
│   └── README.md            ← Full prompt protocol and baseline results
├── scripts/
│   ├── generate.py          ← CLI: --archetype/--all, --seeds
│   ├── run_benchmark.py     ← Execute benchmark → CSV
│   └── report_benchmark.py  ← QAR tables from CSV
├── data/
│   ├── output/brick/            ← 120 released TTL files
│   └── empirical_patterns.json  ← 1,421 Brick patterns from 65 Mortar buildings
├── pyproject.toml
└── requirements.txt
```

---

## Extending the Dataset

The generator is fully reproducible. To extend to more seeds or additional archetypes:

```bash
# Generate 10 seeds instead of 5 (seeds 0–9; first 5 match the released dataset)
python scripts/generate.py --all --seeds 10 --output data/output/

# Generate a single archetype for quick testing
python scripts/generate.py --archetype hospital_2013 --seeds 1
```

---

## Citation

If you use BuildGraph or the released dataset, please cite:

```bibtex
@article{jung2026buildgraph,
  title   = {BuildGraph: A Synthetic Multi-Archetype Building Knowledge Graph Dataset},
  author  = {Jung, Wooyoung},
  journal = {Journal of Computing in Civil Engineering},
  year    = {2026},
  note    = {Under review}
}
```

---

## License

Code: [CC BY-NC 4.0](LICENSE). Dataset (Zenodo deposit): CC BY-NC 4.0.
