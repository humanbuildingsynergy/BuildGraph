# Building Summary Template

Each building is represented as a structured ~500-token plain-text summary extracted
from the RDF graph via SPARQL. The summary is injected into the user turn immediately
before the NL question. It contains five sections described below.

---

## Annotated Template

```
BUILDING: {building_id}
Type: {building_type} | Vintage: {vintage} | Climate: {climate_zone} | Style: {naming_style}

EQUIPMENT:
  {EquipmentLabel} ({count}): {name1}, {name2}, {name3}, {name4}, {name5} … {lastName} ({count} total)
  ...

PLANT TOPOLOGY:
  {plant_equip} --feeds--> {downstream1}, {downstream2}
  ...

AHU→ZONE SERVICE (via feeds chain):
  {ahu} --feeds+--> {zone1}, {zone2}, {zone3}, {zone4} … ({N} zones)
  ...

SENSOR POINTS (sample):
  {equip_name}: {PointType1}, {PointType2}, {PointType3}
  ...

SPARQL PREFIXES (use exactly these):
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/{building_id}/>
PREFIX meta: <https://buildgraph.org/meta#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
```

---

## Annotated Example (BG_medium_office_2004_0001)

```
BUILDING: BG_medium_office_2004_0001
Type: medium_office | Vintage: ashrae2004 | Climate: 4A | Style: numeric

EQUIPMENT:
  AHU (3): AHU01, AHU02, AHU03
  VAV (18): VAV_F1_Z01, VAV_F1_Z02, VAV_F1_Z03, VAV_F2_Z01, VAV_F2_Z02 … VAV_F3_Z06 (18 total)
  Chiller (1): Chiller01
  Boiler (1): Boiler01
  CHWPump (2): CHWPump01, CHWPump02
  HWPump (2): HWPump01, HWPump02
  SupplyFan (3): SupplyFan_AHU01, SupplyFan_AHU02, SupplyFan_AHU03
  HVAC_Zone (18): Zone_F1_Z01, Zone_F1_Z02, Zone_F1_Z03, Zone_F2_Z01, Zone_F2_Z02 … Zone_F3_Z06 (18 total)

PLANT TOPOLOGY:
  Boiler01 --feeds--> HWPump01, HWPump02
  Chiller01 --feeds--> CHWPump01, CHWPump02
  CHWPump01 --feeds--> AHU01, AHU02
  CHWPump02 --feeds--> AHU03
  HWPump01 --feeds--> AHU01, AHU02
  HWPump02 --feeds--> AHU03

AHU→ZONE SERVICE (via feeds chain):
  AHU01 --feeds+--> Zone_F1_Z01, Zone_F1_Z02, Zone_F1_Z03, Zone_F2_Z01 … (6 zones)
  AHU02 --feeds+--> Zone_F2_Z02, Zone_F2_Z03, Zone_F2_Z04, Zone_F2_Z05 … (6 zones)
  AHU03 --feeds+--> Zone_F3_Z01, Zone_F3_Z02, Zone_F3_Z03, Zone_F3_Z04 … (6 zones)

SENSOR POINTS (sample):
  AHU01: Mixed_Air_Temperature_Sensor, Return_Air_Temperature_Sensor, Supply_Air_Temperature_Sensor
  Boiler01: Hot_Water_Return_Temperature_Sensor, Hot_Water_Supply_Temperature_Sensor
  CHWPump01: Chilled_Water_Differential_Pressure_Sensor
  Chiller01: Chilled_Water_Supply_Temperature_Sensor, Enable_Command
  VAV_F1_Z01: Damper_Position_Sensor, Zone_Air_Temperature_Sensor

SPARQL PREFIXES (use exactly these):
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://buildgraph.org/bldg/BG_medium_office_2004_0001/>
PREFIX meta: <https://buildgraph.org/meta#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
```

---

## Section Descriptions

### BUILDING header
- `building_id` — TTL filename stem (e.g., `BG_medium_office_2004_0001`)
- `building_type` — one of: `small_office`, `medium_office`, `large_office`, `primary_school`,
  `hospital`, `hotel`, `strip_mall`, `outpatient`
- `vintage` — `pre1980`, `ashrae2004`, or `ashrae2013`
- `climate_zone` — ASHRAE climate zone (e.g., `4A`, `5A`)
- `naming_style` — one of four URI naming conventions: `numeric`, `hyphenated`, `descriptive`,
  `legacy` (controls how entity local names look in SPARQL results)

### EQUIPMENT
Each equipment class present in the graph is listed with instance count and local names (up to 5
shown; truncated with `…` and total count for larger sets). Equipment classes covered:
AHU, VAV, Fan_Coil_Unit (FCU), Rooftop_Unit (RTU), Chiller, Boiler, Chilled_Water_Pump,
Hot_Water_Pump, Condenser_Water_Pump, Cooling_Tower, Supply_Fan, Return_Fan,
Variable_Frequency_Drive (VFD), Energy_Recovery_Ventilator (ERV), HVAC_Zone.

### PLANT TOPOLOGY
Direct `brick:feeds` relationships from central plant equipment (chillers, boilers, pumps,
cooling towers) to their downstream targets. Captures the hydronic distribution network — which
pump serves which AHUs, which chiller feeds which pumps.

### AHU→ZONE SERVICE
Transitive `brick:feeds+` paths from each AHU to HVAC zones (following the full
AHU → VAV/FCU → Zone chain). Up to 4 zones shown explicitly; remainder noted as `(N zones)`.
This section is the key context for topological traversal and zone-service queries (Categories 3
and 5 in the benchmark).

### SENSOR POINTS (sample)
Up to 6 equipment instances are shown, each with up to 3 sensor/point type names. Points are
discovered via both `brick:hasPoint` (equipment-to-point) and `brick:isPointOf`
(point-to-equipment) directions, since BuildGraph buildings vary in which direction is used
(50% `hasPoint`-only, 25% `isPointOf`-only, 25% both). Point type names are Brick class local
names (e.g., `Zone_Air_Temperature_Sensor`, `Damper_Position_Setpoint`).

### SPARQL PREFIXES
The four prefixes required to write valid SPARQL against this building's graph. The `bldg:`
namespace is building-specific and must match the TTL file's base URI exactly. The model is
instructed to use these declarations verbatim at the top of every generated query.

---

## Generation Code

The summary is generated by `build_building_summary()` in
`scripts/run_nl2sparql_eval.py` (development repo). It executes a series of SPARQL SELECT
queries against the rdflib graph object and formats the results as plain text. No raw Turtle
is passed to the model — only this structured summary — keeping the context compact and
forcing the model to rely on the summary for entity names and topology.
