# Text-to-SPARQL Prompts

This directory documents the prompt protocol used in the BuildGraph text-to-SPARQL
pilot evaluation and provides the baseline templates for researchers who want to
replicate, extend, or compare against these results.

The evaluation is described in detail in the companion paper:

> Jung, W. (2026). *BuildGraph: A Synthetic Multi-Archetype Building Knowledge Graph
> Dataset.* Journal of Computing in Civil Engineering. (Under review.)

---

## Directory Contents

| File | Description |
|---|---|
| `system.txt` | Exact system message passed to the model in all conditions |
| `building_summary.md` | Annotated template for the ~500-token building context |
| `README.md` | This file — full protocol documentation |

---

## Overview

The evaluation measures how well an LLM can translate natural language questions into
executable SPARQL queries against BuildGraph buildings. Two conditions are compared:

- **Zero-shot**: model receives only the building summary and the NL question
- **Few-shot**: model receives 3 complete NL→SPARQL examples from other buildings
  before the target question

The NL questions and gold SPARQL are taken from `benchmarks/sparql_queries.json`.
The building summaries are extracted at runtime from each TTL file.

---

## Prompt Structure

### Zero-shot

```
[SYSTEM]
You are a SPARQL expert for building knowledge graphs using Brick Schema 1.3.
Given a building knowledge graph summary and a natural language question,
return ONLY a valid SPARQL SELECT query using the PREFIX declarations shown.
No explanation, no markdown fences, no comments — just the raw SPARQL query.

[USER]
BUILDING: BG_hospital_2004_0001
Type: hospital | Vintage: ashrae2004 | Climate: 5A | Style: numeric

EQUIPMENT:
  AHU (8): AHU01, AHU02, AHU03, AHU04, AHU05 … AHU08 (8 total)
  VAV (52): VAV_F1_Z01, VAV_F1_Z02, … (52 total)
  Chiller (2): Chiller01, Chiller02
  ...

PLANT TOPOLOGY:
  Chiller01 --feeds--> CHWPump01, CHWPump02
  ...

AHU→ZONE SERVICE (via feeds chain):
  AHU01 --feeds+--> Zone_F1_Z01, Zone_F1_Z02, Zone_F1_Z03, Zone_F1_Z04 … (7 zones)
  ...

SENSOR POINTS (sample):
  AHU01: Mixed_Air_Temperature_Sensor, Supply_Air_Flow_Sensor, Supply_Air_Temperature_Sensor
  ...

SPARQL PREFIXES (use exactly these):
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/BG_hospital_2004_0001/>
PREFIX meta: <https://buildgraph.org/meta#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

Question: How many AHUs does this building have?
SPARQL:
```

### Few-shot

The few-shot condition prepends **3 complete (building summary, NL question, gold SPARQL)
triples** as alternating user/assistant turns before the target question. Examples are
drawn from pool buildings (seeds 0000–0002 and 0004) of the **same complexity tier**
as the test building, spanning three query categories (1 = Equipment Discovery,
3 = Topological Traversal, 5 = Multi-hop / Complex) to provide diverse context.

```
[SYSTEM]
(same as zero-shot)

[USER]   ← Example 1 (Category 1, different building, same tier)
BUILDING: BG_hospital_2013_0001
...
Question: List all chillers in this building.
SPARQL:

[ASSISTANT]
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/BG_hospital_2013_0001/>
SELECT ?chiller WHERE {
    ?chiller a brick:Chiller .
}

[USER]   ← Example 2 (Category 3, different building, same tier)
BUILDING: BG_outpatient_2013_0002
...
Question: Which zones does AHU02 serve?
SPARQL:

[ASSISTANT]
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/BG_outpatient_2013_0002/>
SELECT ?zone WHERE {
    bldg:AHU02 brick:feeds+ ?zone .
    ?zone a brick:HVAC_Zone .
}

[USER]   ← Example 3 (Category 5, different building, same tier)
BUILDING: BG_hotel_2013_0000
...
Question: Which AHUs serve zones that have a CO2 sensor?
SPARQL:

[ASSISTANT]
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/BG_hotel_2013_0000/>
SELECT DISTINCT ?ahu WHERE {
    ?ahu a brick:AHU .
    ?ahu brick:feeds+ ?zone .
    ?zone a brick:HVAC_Zone .
    { ?zone brick:hasPoint ?pt } UNION { ?pt brick:isPointOf ?zone }
    ?pt a brick:CO2_Sensor .
}

[USER]   ← Test question (target building)
BUILDING: BG_hospital_2004_0003
...
Question: How many AHUs does this building have?
SPARQL:
```

---

## The Benchmark Queries

`benchmarks/sparql_queries.json` contains 75 NL→SPARQL pairs across 5 categories:

| Category | Description | # Queries | Typical difficulty |
|---|---|---|---|
| 1 | Equipment Discovery | 17 | Easy — count or list equipment of a class |
| 2 | Sensor/Point Relations | 16 | Medium — find points attached to equipment |
| 3 | Topological Traversal | 14 | Medium — follow `feeds` chains |
| 4 | Aggregation | 10 | Medium — `GROUP BY`, `COUNT`, `ORDER BY` |
| 5 | Multi-hop / Complex | 18 | Hard — join across equipment + zones + points |

Each query entry includes:
- `id` — unique identifier (e.g., `q001`)
- `nl` — the natural language question
- `sparql` — the gold SPARQL body (without PREFIX declarations)
- `category` — integer 1–5
- `difficulty` — `easy`, `medium`, or `hard`
- `scope` — list of features required (e.g., `["chiller"]`); queries are skipped for
  buildings that do not have the relevant equipment

The `prefixes` key at the top of the file contains the standard PREFIX block to prepend
to all gold SPARQL bodies.

---

## Test / Pool Split

The pilot evaluation uses a fixed split to prevent data leakage:

**Test buildings** (12 total, seed 0003 only — held out):

| Tier | Buildings |
|---|---|
| T1 Simple | `BG_small_office_2004_0003`, `BG_primary_school_2004_0003`, `BG_strip_mall_2013_0003` |
| T2 Standard | `BG_medium_office_2004_0003`, `BG_hotel_2004_0003`, `BG_medium_office_2013_0003` |
| T3 Advanced | `BG_large_office_2004_0003`, `BG_hospital_2004_0003`, `BG_outpatient_2004_0003` |
| T4 Smart | `BG_hospital_2013_0003`, `BG_hotel_2013_0003`, `BG_outpatient_2013_0003` |

**Pool buildings** (108 total, seeds 0000–0002 and 0004): used only for few-shot example
selection. Gold SPARQL from pool buildings is passed directly to the model as demonstration
examples.

---

## Evaluation Metrics

Results are scored using four metrics from the BuildingQA benchmark
(INFERLab/BuildingQA), computed by comparing the predicted SPARQL result set against
the gold result set:

| Metric | Description |
|---|---|
| **Row-Matching F1** | Primary metric. Best column alignment found by exhaustive permutation search, then one-to-one row matching F1. Penalizes wrong entities even if the right count is returned. |
| **Entity Set F1** | Column-wise value overlap under the best column alignment. Partial credit for returning some correct entities. |
| **Arity F1** | Dice coefficient on column count. Measures whether the query selects the right number of variables. |
| **Exact-Match F1** | Strictest. Positional column mapping (no search); requires correct column order. |

All metrics are computed only over applicable queries where the gold SPARQL returns at
least one result row on the test building (`gold_status == "pass"`). This ensures that
scope mismatches (e.g., a chiller query on a packaged-unit building) do not deflate scores.

**Baseline results** from the paper (Gemma 4 27B, 12 test buildings):

| Category | Zero-shot rmF1 | Few-shot rmF1 | QAR ceiling |
|---|---|---|---|
| 1. Equipment Discovery | 29.0% | 63.0% | 100.0% |
| 2. Sensor/Point Relations | 7.1% | 4.1% | 95.1% |
| 3. Topological Traversal | 4.7% | 20.3% | 99.0% |
| 4. Aggregation | 10.8% | 48.6% | 100.0% |
| 5. Multi-hop / Complex | 0.0% | 10.1% | 91.8% |
| **Overall** | **9.8%** | **27.3%** | **97.1%** |

The gap between few-shot rmF1 and the QAR ceiling represents the remaining headroom
for improvement through fine-tuning, better prompting, or retrieval-augmented generation.

---

## Running Your Own Evaluation

### Prerequisites

```bash
pip install rdflib pydantic  # core (already in requirements.txt)
```

For Gemma 4 via Ollama (replicating the paper):
```bash
pip install ollama
# Install Ollama: https://ollama.com
ollama pull gemma4:27b
```

For OpenAI-compatible APIs, replace the `ollama.chat()` call with your preferred client.

### Minimal zero-shot loop (any model)

```python
import json
from pathlib import Path
from rdflib import Graph

# Load benchmark
bench = json.loads(Path("benchmarks/sparql_queries.json").read_text())
prefixes = bench["prefixes"]
queries = bench["queries"]
system_prompt = Path("prompts/system.txt").read_text().strip()

# Load one building
g = Graph()
g.parse("data/output/brick/BG_medium_office_2004_0000.ttl", format="turtle")

# Build a building summary following the format in prompts/building_summary.md
# Extract equipment, plant topology, AHU→zone service, sensor samples, and prefix declarations
summary = "..."   # your summary here

for q in queries:
    user_message = f"{summary}\n\nQuestion: {q['nl']}\nSPARQL:"

    # --- replace with your model call ---
    response = your_model(
        system=system_prompt,
        user=user_message,
    )
    # ------------------------------------

    # Execute predicted SPARQL against the graph
    try:
        results = list(g.query(f"{prefixes}\n{response}"))
        print(f"{q['id']}: {len(results)} rows")
    except Exception as e:
        print(f"{q['id']}: SPARQL error — {e}")
```

### Few-shot loop additions

1. Run `scripts/run_benchmark.py` on your pool buildings first to identify which
   (building, query) pairs return results (`status == "pass"`) — these are your
   candidate examples. Only examples where the gold SPARQL produces real results
   should be shown to the model.
2. For each test query, pick 3 pool-building examples from the same tier, spanning
   categories 1, 3, and 5.
3. Prepend each example as a `(user, assistant)` turn pair before the test user turn.
   The assistant turn contains the gold SPARQL body with full PREFIX declarations.

---

## Design Notes

### Why a building summary instead of raw Turtle?
Passing the full TTL file would exceed context limits for large buildings (up to ~11,000
triples / ~200KB for a dense 2013 hospital). The structured summary compresses the
relevant information — equipment inventory, topology, sensor types, and exact URI prefixes
— into ~500 tokens while preserving what the model needs to write valid SPARQL.

### Why categories 1, 3, 5 for few-shot examples?
Category 1 (equipment listing) teaches the model basic `?x a brick:ClassName` patterns
and the `bldg:` prefix style. Category 3 (topological traversal) teaches `brick:feeds+`
path queries. Category 5 (multi-hop) teaches complex joins across equipment, zones, and
points. Together they cover the main structural patterns needed for all five categories,
without repeating the same query type three times.

### Why does few-shot hurt Category 2 (Sensor/Point Relations)?
Category 2 queries specifically test both `brick:hasPoint` and `brick:isPointOf`
directions. The Category 1/3/5 examples do not demonstrate this pattern, so the model
is not primed to handle the direction ambiguity. In practice, the few-shot examples
lead the model to consistently use one direction, which is wrong for buildings that
use the other. This is a known limitation of the cross-category example selection
strategy and a motivation for category-matched example selection in future work.

### Sensor/Point direction heterogeneity
Each BuildGraph building independently samples one of three sensor-attachment styles:
50% `hasPoint`-only, 25% `isPointOf`-only, 25% both. A robust text-to-SPARQL system
must handle all three. A model that always generates `brick:hasPoint` will fail on
25% of buildings for point-relation queries. Queries in Category 2 use `UNION` to
cover both directions in the gold SPARQL.
