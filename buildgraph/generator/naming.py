from rdflib import URIRef, Namespace


_VINTAGE_TOKENS = {"pre1980", "ashrae2004", "ashrae2013"}
_VINTAGE_CLEAN  = {"pre1980": "pre1980", "ashrae2004": "2004", "ashrae2013": "2013"}
_MODE_TOKENS    = {"brick"}


def building_id(archetype_name: str, seed: int) -> str:
    """Return a human-readable building ID.

    Format: BG_{building_type}_{vintage}_{seed:04d}
    Examples:
      BG_hospital_2013_0002
      BG_medium_office_pre1980_0042
    """
    parts = archetype_name.split("_")
    # Strip ontology-mode suffix (brick)
    if parts and parts[-1] in _MODE_TOKENS:
        parts = parts[:-1]
    # Locate vintage token
    vi = next((i for i, p in enumerate(parts) if p in _VINTAGE_TOKENS), len(parts) - 1)
    building_type = "_".join(parts[:vi])
    vintage_clean = _VINTAGE_CLEAN.get(parts[vi], parts[vi])
    return f"BG_{building_type}_{vintage_clean}_{seed:04d}"


def bldg_namespace(bldg_id: str) -> Namespace:
    return Namespace(f"http://buildgraph.org/{bldg_id}#")


def ahu_uri(ns: Namespace, index: int) -> URIRef:
    return ns[f"AHU{index:02d}"]


def vav_uri(ns: Namespace, floor: int, zone: int) -> URIRef:
    return ns[f"VAV_F{floor}_Z{zone:02d}"]


def floor_uri(ns: Namespace, index: int) -> URIRef:
    return ns[f"Floor{index:02d}"]


def zone_uri(ns: Namespace, floor: int, zone: int) -> URIRef:
    return ns[f"Zone_F{floor}_Z{zone:02d}"]


def chiller_uri(ns: Namespace, index: int = 1) -> URIRef:
    return ns[f"Chiller{index:02d}"]


def boiler_uri(ns: Namespace, index: int = 1) -> URIRef:
    return ns[f"Boiler{index:02d}"]


def meter_uri(ns: Namespace, meter_type: str = "Electric") -> URIRef:
    return ns[f"{meter_type}Meter"]


def point_uri(ns: Namespace, equipment_local: str, point_class: str) -> URIRef:
    return ns[f"{equipment_local}.{point_class}"]


def conn_point_uri(ns: Namespace, equipment_local: str, direction: str, medium: str, index: int = 1) -> URIRef:
    return ns[f"{equipment_local}.{direction}_{medium}_{index:02d}"]


def connection_uri(ns: Namespace, from_local: str, to_local: str) -> URIRef:
    return ns[f"Conn_{from_local}_to_{to_local}"]


def obs_property_uri(ns: Namespace, equipment_local: str, quantity: str) -> URIRef:
    return ns[f"{equipment_local}.obs_{quantity}"]


# ── NamingStrategy ────────────────────────────────────────────────────────────
# Provides consistent, style-aware URI generation for spec-driven builders.
# All existing module-level functions above remain unchanged for backward compat.

from typing import Literal  # noqa: E402

NamingStyle = Literal["numeric", "hyphenated", "descriptive", "legacy"]


class NamingStrategy:
    """Generates style-consistent URIs for all equipment in one building.

    Pass an instance to the extended builders instead of a raw Namespace so
    that naming style is applied uniformly across the entire graph.
    """

    def __init__(self, ns: Namespace, style: NamingStyle = "numeric") -> None:
        self.ns = ns
        self.style = style

    # ── helpers ────────────────────────────────────────────────────────────────

    def _u(self, label: str) -> URIRef:
        return self.ns[label]

    def local(self, uri: URIRef) -> str:
        """Extract the local fragment from a URIRef (after '#')."""
        return str(uri).split("#")[-1]

    # ── Floors / zones ─────────────────────────────────────────────────────────

    def floor(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"Floor{index:02d}",
            "hyphenated":  f"FL-{index:02d}",
            "descriptive": f"Building_Floor_{index}",
            "legacy":      f"LVL-{index:02d}",
        }[self.style])

    def zone(self, floor: int, zone_num: int) -> URIRef:
        return self._u({
            "numeric":     f"Zone_F{floor}_Z{zone_num:02d}",
            "hyphenated":  f"ZN-{floor}-{zone_num:02d}",
            "descriptive": f"HVAC_Zone_F{floor}_Z{zone_num}",
            "legacy":      f"ZN-L{floor}-{zone_num:02d}",
        }[self.style])

    # ── AHU ────────────────────────────────────────────────────────────────────

    def ahu_label(self, index: int) -> str:
        return {
            "numeric":     f"AHU{index:02d}",
            "hyphenated":  f"AH-{index}",
            "descriptive": f"Air_Handler_{index:02d}",
            "legacy":      f"AHU-L1-{index:02d}",
        }[self.style]

    def ahu(self, index: int) -> URIRef:
        return self._u(self.ahu_label(index))

    # ── Terminal units ─────────────────────────────────────────────────────────

    def vav(self, floor: int, zone_num: int) -> URIRef:
        return self._u({
            "numeric":     f"VAV_F{floor}_Z{zone_num:02d}",
            "hyphenated":  f"VAV-{floor}-{zone_num:02d}",
            "descriptive": f"VAV_Box_Floor{floor}_Zone{zone_num}",
            "legacy":      f"VAVB-{floor}-{zone_num:03d}",
        }[self.style])

    def fcu(self, floor: int, zone_num: int) -> URIRef:
        return self._u({
            "numeric":     f"FCU_F{floor}_Z{zone_num:02d}",
            "hyphenated":  f"FCU-{floor}-{zone_num:02d}",
            "descriptive": f"Fan_Coil_Floor{floor}_Zone{zone_num}",
            "legacy":      f"FCU-{floor}-{zone_num:03d}",
        }[self.style])

    def vrf_indoor_unit(self, floor: int, zone_num: int) -> URIRef:
        return self._u({
            "numeric":     f"VRF_IDU_F{floor}_Z{zone_num:02d}",
            "hyphenated":  f"IDU-{floor}-{zone_num:02d}",
            "descriptive": f"VRF_Indoor_Unit_F{floor}_Zone{zone_num}",
            "legacy":      f"VRFI-{floor}-{zone_num:02d}",
        }[self.style])

    def terminal(self, floor: int, zone_num: int, term_type: str) -> URIRef:
        """Dispatch to the correct terminal URI based on type string."""
        if term_type == "fcu":
            return self.fcu(floor, zone_num)
        if term_type == "vrf_indoor":
            return self.vrf_indoor_unit(floor, zone_num)
        return self.vav(floor, zone_num)

    # ── Plant: chillers / boilers ──────────────────────────────────────────────

    def chiller(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"Chiller{index:02d}",
            "hyphenated":  f"CH-{index:02d}",
            "descriptive": f"Central_Chiller_{index}",
            "legacy":      f"CHR-{index:02d}",
        }[self.style])

    def boiler(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"Boiler{index:02d}",
            "hyphenated":  f"BLR-{index:02d}",
            "descriptive": f"Central_Boiler_{index}",
            "legacy":      f"BLR-{index:02d}",
        }[self.style])

    def cooling_tower(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"CoolingTower{index:02d}",
            "hyphenated":  f"CT-{index:02d}",
            "descriptive": f"Cooling_Tower_{index}",
            "legacy":      f"CT-{index:03d}",
        }[self.style])

    # ── Pumps ──────────────────────────────────────────────────────────────────

    def chw_pump(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"CHWPump{index:02d}",
            "hyphenated":  f"CHWP-{index:02d}",
            "descriptive": f"Chilled_Water_Pump_{index}",
            "legacy":      f"CHWP-{index:03d}",
        }[self.style])

    def hw_pump(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"HWPump{index:02d}",
            "hyphenated":  f"HWP-{index:02d}",
            "descriptive": f"Hot_Water_Pump_{index}",
            "legacy":      f"HWP-{index:03d}",
        }[self.style])

    def condenser_pump(self, index: int) -> URIRef:
        return self._u({
            "numeric":     f"CondPump{index:02d}",
            "hyphenated":  f"CWP-{index:02d}",
            "descriptive": f"Condenser_Water_Pump_{index}",
            "legacy":      f"CWP-{index:03d}",
        }[self.style])

    # ── AHU sub-components (keyed by ahu_label string) ─────────────────────────

    def supply_fan(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"SupplyFan_{ahu_lbl}",
            "hyphenated":  f"SF-{ahu_lbl}",
            "descriptive": f"Supply_Fan_{ahu_lbl}",
            "legacy":      f"SF-{ahu_lbl}",
        }[self.style])

    def return_fan(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"ReturnFan_{ahu_lbl}",
            "hyphenated":  f"RF-{ahu_lbl}",
            "descriptive": f"Return_Fan_{ahu_lbl}",
            "legacy":      f"RF-{ahu_lbl}",
        }[self.style])

    def exhaust_fan(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"ExhaustFan_{ahu_lbl}",
            "hyphenated":  f"EF-{ahu_lbl}",
            "descriptive": f"Exhaust_Fan_{ahu_lbl}",
            "legacy":      f"EF-{ahu_lbl}",
        }[self.style])

    def cooling_coil(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"CoolingCoil_{ahu_lbl}",
            "hyphenated":  f"CC-{ahu_lbl}",
            "descriptive": f"Cooling_Coil_{ahu_lbl}",
            "legacy":      f"CC-{ahu_lbl}",
        }[self.style])

    def heating_coil(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"HeatingCoil_{ahu_lbl}",
            "hyphenated":  f"HC-{ahu_lbl}",
            "descriptive": f"Heating_Coil_{ahu_lbl}",
            "legacy":      f"HC-{ahu_lbl}",
        }[self.style])

    def economizer_damper(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"EconDamper_{ahu_lbl}",
            "hyphenated":  f"ECON-{ahu_lbl}",
            "descriptive": f"Economizer_Damper_{ahu_lbl}",
            "legacy":      f"DMPR-E-{ahu_lbl}",
        }[self.style])

    def return_damper(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"ReturnDamper_{ahu_lbl}",
            "hyphenated":  f"RD-{ahu_lbl}",
            "descriptive": f"Return_Damper_{ahu_lbl}",
            "legacy":      f"DMPR-R-{ahu_lbl}",
        }[self.style])

    def exhaust_damper(self, ahu_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"ExhaustDamper_{ahu_lbl}",
            "hyphenated":  f"ED-{ahu_lbl}",
            "descriptive": f"Exhaust_Damper_{ahu_lbl}",
            "legacy":      f"DMPR-EX-{ahu_lbl}",
        }[self.style])

    # ── VFD ────────────────────────────────────────────────────────────────────

    def vfd(self, attached_lbl: str) -> URIRef:
        return self._u({
            "numeric":     f"VFD_{attached_lbl}",
            "hyphenated":  f"VFD-{attached_lbl}",
            "descriptive": f"VFD_{attached_lbl}",
            "legacy":      f"VFD-{attached_lbl}",
        }[self.style])

    # ── Sensor / observable property points ───────────────────────────────────

    def point(self, equip_lbl: str, point_class: str) -> URIRef:
        return self.ns[f"{equip_lbl}.{point_class}"]

    def obs_property(self, equip_lbl: str, quantity: str) -> URIRef:
        return self.ns[f"{equip_lbl}.obs_{quantity}"]

    def conn_point(
        self, equip_lbl: str, direction: str, medium: str, index: int = 1
    ) -> URIRef:
        return self.ns[f"{equip_lbl}.{direction}_{medium}_{index:02d}"]

    def connection(self, from_lbl: str, to_lbl: str) -> URIRef:
        return self.ns[f"Conn_{from_lbl}_to_{to_lbl}"]
