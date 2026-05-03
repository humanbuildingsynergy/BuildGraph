"""Loads empirical pattern databases and provides probability lookups."""
import json
from pathlib import Path
from typing import NamedTuple

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class PatternEntry(NamedTuple):
    object_class: str
    probability: float  # building_count / total_buildings


# ── Noise filter ───────────────────────────────────────────────────────────────
# These are SPARQL inference artifacts or abstract superclasses that appear in
# the mined corpus but carry no discriminating information as Brick class types.
_NOISE_CLASSES = {
    "Class", "Point", "Sensor", "Command", "Setpoint", "Status", "Mode",
    "Parameter", "Limit", "Min_Limit",
    # Generic superclasses made redundant by specific subclasses in curated data
    "Temperature_Sensor", "Air_Temperature_Sensor",
    "Flow_Sensor", "Air_Flow_Sensor",
    "Temperature_Setpoint", "Air_Temperature_Setpoint",
    "Pressure_Sensor",
    "Water_Temperature_Sensor",
    "Water_Flow_Sensor",
    # Other abstract catch-alls from mining
    "Supply_Air_flow",  # typo artifact in empirical data
}


# ── Curated point patterns ─────────────────────────────────────────────────────
# Per-equipment authoritative (class, base_probability) pairs.
# Probabilities are pre-density; the builder multiplies by density scale.
# Using only class names validated against Brick schema or empirical data.
_CURATED_BRICK_POINTS: dict[str, list[tuple[str, float]]] = {

    "AHU": [
        # Temperature sensors — standard trunk instrumentation
        ("Supply_Air_Temperature_Sensor",          0.92),
        ("Return_Air_Temperature_Sensor",           0.82),
        ("Mixed_Air_Temperature_Sensor",            0.72),
        ("Outside_Air_Temperature_Sensor",          0.88),
        ("Discharge_Air_Temperature_Sensor",        0.55),
        # Flow / pressure
        ("Supply_Air_Flow_Sensor",                  0.78),
        ("Return_Air_Flow_Sensor",                  0.62),
        ("Outside_Air_Flow_Sensor",                 0.68),
        ("Supply_Air_Static_Pressure_Sensor",       0.82),
        ("Filter_Differential_Pressure_Sensor",     0.58),
        ("Return_Air_Differential_Pressure_Sensor", 0.42),
        # Humidity
        ("Supply_Air_Humidity_Sensor",              0.45),
        ("Return_Air_Humidity_Sensor",              0.32),
        ("Outside_Air_Humidity_Sensor",             0.38),
        # Setpoints
        ("Supply_Air_Temperature_Setpoint",         0.88),
        ("Supply_Air_Static_Pressure_Setpoint",     0.82),
        # Commands / status
        ("Start_Stop_Command",                      0.78),
        ("On_Off_Command",                          0.55),
    ],

    "Supply_Fan": [
        ("Start_Stop_Command",   0.88),
        ("Fan_Speed_Setpoint",   0.82),  # alias: Speed_Setpoint
        ("Speed_Setpoint",       0.75),
        ("Speed_Status",         0.72),
        ("Fan_Status",           0.68),
        ("Static_Pressure_Sensor", 0.58),
        ("Output_Frequency_Sensor", 0.42),
    ],

    "Return_Fan": [
        ("Start_Stop_Command",   0.82),
        ("Speed_Setpoint",       0.72),
        ("Speed_Status",         0.65),
        ("Fan_Status",           0.62),
    ],

    "Economizer_Damper": [
        ("Damper_Position_Setpoint",    0.82),
        ("Damper_Position_Command",     0.72),
        ("Outside_Air_Damper_Command",  0.50),
        ("Outside_Air_Temperature_Sensor", 0.58),
    ],

    "Cooling_Coil": [
        ("Discharge_Air_Temperature_Sensor",  0.72),
        ("Chilled_Water_Valve_Command",        0.85),
        ("Valve_Command",                      0.60),
        ("Chilled_Water_Differential_Pressure_Sensor", 0.38),
    ],

    "Heating_Coil": [
        ("Discharge_Air_Temperature_Sensor",  0.65),
        ("Hot_Water_Valve_Command",           0.80),
        ("Valve_Command",                     0.55),
    ],

    # ── Terminal units ────────────────────────────────────────────────────────

    "VAV": [
        # Zone temperature — nearly universal
        ("Zone_Air_Temperature_Sensor",              0.92),
        # Setpoints — the most important control-side points
        ("Zone_Air_Cooling_Temperature_Setpoint",    0.88),
        ("Zone_Air_Heating_Temperature_Setpoint",    0.88),
        ("Zone_Air_Temperature_Setpoint",            0.72),  # legacy combined setpoint
        # Airflow
        ("Supply_Air_Flow_Sensor",                   0.82),
        ("Air_Flow_Setpoint",                        0.65),
        # Supply air temp at the box
        ("Supply_Air_Temperature_Sensor",            0.62),
        ("Discharge_Air_Temperature_Sensor",         0.45),
        # Control
        ("Damper_Position_Setpoint",                 0.85),
        ("Damper_Position_Command",                  0.68),
        ("Heating_Command",                          0.55),
        ("Valve_Command",                            0.48),
        # IAQ
        ("CO2_Sensor",                               0.28),
        ("Occupancy_Sensor",                         0.22),
    ],

    "Variable_Air_Volume_Box_With_Reheat": [
        ("Zone_Air_Temperature_Sensor",              0.92),
        ("Zone_Air_Cooling_Temperature_Setpoint",    0.88),
        ("Zone_Air_Heating_Temperature_Setpoint",    0.88),
        ("Supply_Air_Flow_Sensor",                   0.82),
        ("Discharge_Air_Temperature_Sensor",         0.75),
        ("Damper_Position_Setpoint",                 0.85),
        ("Damper_Position_Command",                  0.70),
        ("Heating_Command",                          0.72),
        ("Hot_Water_Valve_Command",                  0.62),
        ("Valve_Command",                            0.55),
        ("CO2_Sensor",                               0.28),
    ],

    "Terminal_Unit": [
        # Used for FCU
        ("Zone_Air_Temperature_Sensor",              0.92),
        ("Zone_Air_Cooling_Temperature_Setpoint",    0.88),
        ("Zone_Air_Heating_Temperature_Setpoint",    0.85),
        ("Cooling_Command",                          0.78),
        ("Heating_Command",                          0.75),
        ("Chilled_Water_Valve_Command",              0.68),
        ("Hot_Water_Valve_Command",                  0.62),
        ("Speed_Setpoint",                           0.65),
        ("Fan_Status",                               0.58),
        ("CO2_Sensor",                               0.22),
        ("Occupancy_Sensor",                         0.30),
    ],

    # ── Zone (sensors placed on zone itself, not terminal unit) ───────────────

    "HVAC_Zone": [
        ("Zone_Air_Temperature_Sensor",           0.92),
        ("Zone_Air_Cooling_Temperature_Setpoint", 0.85),
        ("Zone_Air_Heating_Temperature_Setpoint", 0.85),
        ("CO2_Sensor",                            0.38),
        ("Occupancy_Sensor",                      0.42),
        ("Air_Quality_Sensor",                    0.22),
    ],

    # ── Central plant ─────────────────────────────────────────────────────────

    "Chiller": [
        ("Chilled_Water_Supply_Temperature_Sensor",    0.95),
        ("Chilled_Water_Return_Temperature_Sensor",    0.95),
        ("Chilled_Water_Flow_Sensor",                  0.82),
        ("Chilled_Water_Differential_Pressure_Sensor", 0.62),
        ("Chilled_Water_Supply_Temperature_Setpoint",  0.72),
        ("Chilled_Water_Return_Temperature_Setpoint",  0.55),
        ("Chilled_Water_Differential_Pressure_Setpoint", 0.58),
        ("Enable_Command",                             0.82),
        ("On_Off_Command",                             0.68),
        ("Power_Sensor",                               0.58),
        ("Cooling_Request_Percent_Setpoint",           0.45),
    ],

    "Boiler": [
        ("Hot_Water_Supply_Temperature_Sensor",   0.92),
        ("Hot_Water_Return_Temperature_Sensor",   0.85),
        ("Hot_Water_Flow_Sensor",                 0.78),
        ("Hot_Water_Supply_Flow_Sensor",          0.65),
        ("Enable_Command",                        0.80),
        ("On_Off_Command",                        0.65),
        ("Gas_Sensor",                            0.52),
        ("Power_Sensor",                          0.48),
    ],

    "Cooling_Tower": [
        ("Entering_Water_Temperature_Sensor",         0.88),  # condenser water in
        ("Supply_Water_Temperature_Sensor",           0.82),  # condenser water out
        ("Water_Differential_Temperature_Sensor",     0.62),
        ("Enable_Command",                            0.80),
        ("On_Off_Command",                            0.65),
        ("Speed_Setpoint",                            0.72),
        ("Water_Differential_Pressure_Sensor",        0.48),
    ],
}


# ── JSON loader (empirical data) ──────────────────────────────────────────────

def _load(path: Path, total_override: int | None = None) -> dict[str, list[PatternEntry]]:
    if not path.exists():
        return {}
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        entries = raw.get("patterns", [])
        total_override = total_override or raw.get("mined_from")
    else:
        entries = raw
    counts = [e.get("building_count", 1) for e in entries]
    total = total_override or (max(counts) if counts else 1)
    result: dict[str, list[PatternEntry]] = {}
    for e in entries:
        subj = e.get("subject_class", "")
        prop = e.get("property", "")
        obj = e.get("object_class", "")
        if obj in _NOISE_CLASSES:
            continue
        prob = e.get("building_count", 1) / total
        key = f"{subj}::{prop}"
        result.setdefault(key, []).append(PatternEntry(obj, min(prob, 0.95)))
    return result


_BRICK_PATTERNS = _load(_DATA_DIR / "empirical_patterns.json", total_override=65)


# ── Public API ────────────────────────────────────────────────────────────────

def get_brick_points(equipment_class: str) -> list[PatternEntry]:
    """Return (point_class, probability) list for a Brick equipment class.

    Curated entries are used when available (authoritative, noise-free, includes
    setpoints/commands). Falls back to empirical patterns for uncovered classes.
    """
    if equipment_class in _CURATED_BRICK_POINTS:
        return [
            PatternEntry(cls, prob)
            for cls, prob in _CURATED_BRICK_POINTS[equipment_class]
        ]
    return _BRICK_PATTERNS.get(f"{equipment_class}::hasPoint", [])
