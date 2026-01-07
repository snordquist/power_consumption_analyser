"""Power Consumption Analyser - custom integration.
Reads unterverteilung.yaml, exposes sensors, and manual analysis services.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import entity_registry as er, device_registry as dr, label_registry as lr

_LOGGER = logging.getLogger(__name__)

DOMAIN = "power_consumption_analyser"
CONF_UNTERVERTEILUNG_PATH = "unterverteilung_path"
CONF_SAFE_CIRCUITS = "safe_circuits"
CONF_BASELINE_SENSORS = "baseline_sensors"
CONF_UNTRACKED_NUMBER = "untracked_number"

# Options key to persist dynamic energy meter mappings
OPT_ENERGY_METERS_MAP = "energy_meters_map"  # entity_id -> circuit_id

PLATFORMS = [Platform.SENSOR]

class Circuit:
    def __init__(self, id: str, phase: str, breaker: str, rating: str, description: str, energy_meters: Optional[List[str]] = None):
        self.id = id
        self.phase = phase
        self.breaker = breaker
        self.rating = rating
        self.description = description
        self.energy_meters = energy_meters or []

class PCAData:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.circuits: Dict[str, Circuit] = {}
        self.safe_circuits: List[str] = []
        self.session_id: Optional[str] = None
        self.current_circuit: Optional[str] = None
        self.step_active: bool = False
        self.untracked_number: Optional[str] = None
        self.baseline_sensors: Dict[str, str] = {}
        # energy meter mappings
        self.energy_meters_by_circuit: Dict[str, List[str]] = {}
        self.meter_to_circuit: Dict[str, str] = {}

    def is_safe(self, cid: str) -> bool:
        return cid in self.safe_circuits

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, PCAData(hass))
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data: PCAData = hass.data[DOMAIN]

    # Load config
    path = entry.data.get(CONF_UNTERVERTEILUNG_PATH)
    # Normalize safe circuits to list
    raw_safe = entry.data.get(CONF_SAFE_CIRCUITS) or []
    if isinstance(raw_safe, str):
        data.safe_circuits = [s.strip() for s in raw_safe.split(",") if s.strip()]
    else:
        data.safe_circuits = list(raw_safe)
    data.untracked_number = entry.data.get(CONF_UNTRACKED_NUMBER)
    data.baseline_sensors = dict(entry.data.get(CONF_BASELINE_SENSORS) or {})

    if not path:
        _LOGGER.error("unterverteilung_path not configured")
        return False

    try:
        yaml_path = Path(path)
        content = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        for c in content.get("circuits", []):
            cid = c.get("id")
            if not cid:
                continue
            meters = c.get("energy_meters") or c.get("meters") or []
            data.circuits[cid] = Circuit(
                id=cid,
                phase=c.get("phase", ""),
                breaker=c.get("breaker", ""),
                rating=c.get("rating", ""),
                description=c.get("description", ""),
                energy_meters=meters,
            )
            if meters:
                data.energy_meters_by_circuit[cid] = list(meters)
                for m in meters:
                    data.meter_to_circuit[m] = cid
    except Exception as e:
        _LOGGER.exception("Failed to load unterverteilung.yaml: %s", e)
        return False

    # Merge persisted options mapping (UI service-linked meters)
    opt_map = dict(entry.options.get(OPT_ENERGY_METERS_MAP, {}))
    for m, cid in opt_map.items():
        data.meter_to_circuit[m] = cid
        data.energy_meters_by_circuit.setdefault(cid, [])
        if m not in data.energy_meters_by_circuit[cid]:
            data.energy_meters_by_circuit[cid].append(m)

    # Ensure devices for mapped energy meters carry the 'energy_meter' label
    await _ensure_labels_for_energy_meters(hass, list(data.meter_to_circuit.keys()))

    hass.data[DOMAIN] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    register_services(hass, data, entry)

    return True

@callback
def register_services(hass: HomeAssistant, data: PCAData, entry: ConfigEntry) -> None:
    async def handle_select_circuit(call: ServiceCall):
        cid = str(call.data.get("circuit_id"))
        session_id = str(call.data.get("session_id", ""))
        if cid not in data.circuits:
            _LOGGER.warning("Unknown circuit_id %s", cid)
            return
        if data.is_safe(cid):
            _LOGGER.warning("Circuit %s is marked safe; cannot select for analysis", cid)
            return
        data.current_circuit = cid
        data.session_id = session_id or data.session_id
        data.step_active = True
        hass.bus.async_fire(
            f"{DOMAIN}.step_selected",
            {
                "session_id": data.session_id,
                "circuit_id": cid,
                "expected_meters": data.energy_meters_by_circuit.get(cid, []),
            },
        )

    async def handle_confirm_off(call: ServiceCall):
        if not data.step_active or not data.current_circuit:
            _LOGGER.warning("No active step to confirm OFF")
            return
        meas = {
            "home_w": await _state_float(hass, data.baseline_sensors.get("home_consumption") or data.baseline_sensors.get("grid_power")),
            "tracked_w": await _calc_tracked_power(hass, data),
            "untracked_w": None,  # sensor computes it; include computed value for snapshot
        }
        # Compute untracked as home - tracked for snapshot consistency
        if meas["home_w"] is not None and meas["tracked_w"] is not None:
            untracked = meas["home_w"] - meas["tracked_w"]
            meas["untracked_w"] = round(untracked if untracked >= 0 else 0.0, 2)
        hass.bus.async_fire(
            f"{DOMAIN}.circuit_off_confirmed",
            {
                "session_id": data.session_id,
                "circuit_id": data.current_circuit,
                "measured": meas,
                "expected_meters": data.energy_meters_by_circuit.get(data.current_circuit, []),
            },
        )

    async def handle_confirm_on(call: ServiceCall):
        if not data.current_circuit:
            _LOGGER.warning("No current circuit to restore ON")
            return
        hass.bus.async_fire(
            f"{DOMAIN}.circuit_on_confirmed",
            {
                "session_id": data.session_id,
                "circuit_id": data.current_circuit,
                "expected_meters": data.energy_meters_by_circuit.get(data.current_circuit, []),
            },
        )
        data.step_active = False
        data.current_circuit = None

    async def handle_link_energy_meter(call: ServiceCall):
        """Link an energy meter entity_id to a circuit and label its device."""
        entity_id = str(call.data.get("entity_id"))
        circuit_id = str(call.data.get("circuit_id"))
        if circuit_id not in data.circuits:
            _LOGGER.warning("Unknown circuit_id %s", circuit_id)
            return
        data.meter_to_circuit[entity_id] = circuit_id
        data.energy_meters_by_circuit.setdefault(circuit_id, [])
        if entity_id not in data.energy_meters_by_circuit[circuit_id]:
            data.energy_meters_by_circuit[circuit_id].append(entity_id)
        # Persist in options
        opt_map = dict(entry.options.get(OPT_ENERGY_METERS_MAP, {}))
        opt_map[entity_id] = circuit_id
        hass.config_entries.async_update_entry(entry, options={**entry.options, OPT_ENERGY_METERS_MAP: opt_map})
        # Ensure label
        await _ensure_labels_for_energy_meters(hass, [entity_id])
        hass.bus.async_fire(
            f"{DOMAIN}.meter_linked",
            {"entity_id": entity_id, "circuit_id": circuit_id},
        )

    async def handle_unlink_energy_meter(call: ServiceCall):
        entity_id = str(call.data.get("entity_id"))
        cid = data.meter_to_circuit.pop(entity_id, None)
        if cid and entity_id in data.energy_meters_by_circuit.get(cid, []):
            data.energy_meters_by_circuit[cid].remove(entity_id)
        opt_map = dict(entry.options.get(OPT_ENERGY_METERS_MAP, {}))
        if entity_id in opt_map:
            del opt_map[entity_id]
            hass.config_entries.async_update_entry(entry, options={**entry.options, OPT_ENERGY_METERS_MAP: opt_map})
        hass.bus.async_fire(
            f"{DOMAIN}.meter_unlinked",
            {"entity_id": entity_id, "circuit_id": cid},
        )

    hass.services.async_register(DOMAIN, "select_circuit", handle_select_circuit)
    hass.services.async_register(DOMAIN, "confirm_off", handle_confirm_off)
    hass.services.async_register(DOMAIN, "confirm_on", handle_confirm_on)
    hass.services.async_register(DOMAIN, "circuit_link_energy_meter", handle_link_energy_meter)
    hass.services.async_register(DOMAIN, "circuit_unlink_energy_meter", handle_unlink_energy_meter)

async def _state_float(hass: HomeAssistant, entity_id: Optional[str]) -> float:
    if not entity_id:
        return 0.0
    state = hass.states.get(entity_id)
    try:
        return float(state.state) if state else 0.0
    except Exception:
        return 0.0

async def _calc_tracked_power(hass: HomeAssistant, data: PCAData) -> float:
    total = 0.0
    for eid in list(data.meter_to_circuit.keys()):
        st = hass.states.get(eid)
        try:
            v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            v = 0.0
        total += v
    return round(total, 2)

async def _ensure_labels_for_energy_meters(hass: HomeAssistant, entity_ids: List[str]) -> None:
    """Ensure the device for each entity has the 'energy_meter' label."""
    if not entity_ids:
        return
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    lbl_reg = lr.async_get(hass)

    # Find or create the label entry by name
    energy_label = None
    try:
        # Attempt to find existing label named 'energy_meter'
        for lbl in getattr(lbl_reg, "labels", {}).values():
            if getattr(lbl, "name", None) == "energy_meter":
                energy_label = lbl
                break
        if energy_label is None:
            # Fallback: create if supported
            create = getattr(lbl_reg, "async_create", None)
            if create:
                energy_label = create(name="energy_meter")
    except Exception as ex:
        _LOGGER.debug("Label registry access failed: %s", ex)

    label_id: Optional[str] = getattr(energy_label, "id", None) if energy_label else None

    for eid in entity_ids:
        ent = ent_reg.async_get(eid)
        if not ent or not ent.device_id:
            continue
        dev = dev_reg.async_get(ent.device_id)
        if not dev:
            continue
        try:
            current_labels: Set[str] = set(getattr(dev, "labels", set()) or set())
            if label_id and label_id not in current_labels:
                current_labels.add(label_id)
                dev_reg.async_update_device(dev.id, labels=current_labels)
        except Exception as ex:
            _LOGGER.debug("Failed to update labels for device %s: %s", dev.id, ex)
