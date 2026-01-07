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
from homeassistant.components import persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = "power_consumption_analyser"
CONF_UNTERVERTEILUNG_PATH = "unterverteilung_path"
CONF_SAFE_CIRCUITS = "safe_circuits"
CONF_BASELINE_SENSORS = "baseline_sensors"
CONF_UNTRACKED_NUMBER = "untracked_number"

# Options key to persist dynamic energy meter mappings
OPT_ENERGY_METERS_MAP = "energy_meters_map"  # entity_id -> circuit_id

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]

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
        # label-based meters and label tracking
        self.label_meters: Set[str] = set()
        self.energy_label_id: Optional[str] = None
        self.devices_with_label: Set[str] = set()
        # Measurement workflow state
        self.measure_samples: Dict[str, List[float]] = {}
        self.measure_baseline: Dict[str, float] = {}
        self.measure_listeners: Dict[str, Optional[callable]] = {}
        self.measure_timers: Dict[str, Optional[callable]] = {}
        self.measure_results: Dict[str, float] = {}
        self.measure_duration_s: int = 30
        self.measuring_circuit: Optional[str] = None
        # History of measurements per circuit
        self.measure_history: Dict[str, List[dict]] = {}
        self.measure_history_max: int = 50
        # Guided workflow state
        self.workflow_active: bool = False
        self.workflow_queue: List[str] = []
        self.workflow_index: int = 0
        self.workflow_wait_s: int = 0
        self.workflow_notify_service: Optional[str] = None
        self._workflow_saved_duration: Optional[int] = None
        self.workflow_skip_circuits: Set[str] = set()
        self.workflow_notification_id: str = f"{DOMAIN}_workflow"
        self.workflow_ignore_result_for: Optional[str] = None
        # Guard to block starts while stopping workflow
        self.block_measure_starts: bool = False
        self.stopping_workflow: bool = False
        # Origin of current measurement: 'workflow' or 'manual'
        self.measurement_origin: Optional[str] = None

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

    # Ensure devices for mapped energy meters carry the 'EnergyMeter' label
    await _ensure_labels_for_energy_meters(hass, list(data.meter_to_circuit.keys()))

    # Discover EnergyMeter label id and initialize label-based meters
    _init_label_tracking(hass, data)

    hass.data[DOMAIN] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    register_services(hass, data, entry)

    # Apply options and listen for updates
    _apply_options_to_data(data, entry)
    entry.async_on_unload(entry.add_update_listener(_options_updated))

    # Listen for measure_finished to drive workflow steps
    async def _on_measure_finished(event):
        if not data.workflow_active:
            return
        cid = event.data.get("circuit_id")
        # Ignore if flagged for skip
        if data.workflow_ignore_result_for and cid == data.workflow_ignore_result_for:
            data.workflow_ignore_result_for = None
            # Move ahead to next step
            await _workflow_advance(hass, data)
            return
        # Only react if it's the current circuit
        if data.workflow_index < len(data.workflow_queue):
            current = data.workflow_queue[data.workflow_index]
        else:
            current = None
        if cid and cid == current:
            await _notify_step_result(hass, data, cid)
            await _workflow_advance(hass, data)
    hass.bus.async_listen(f"{DOMAIN}.measure_finished", _on_measure_finished)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry to support UI reload."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Optionally clean per-entry state if stored, keeping global services intact
        data: PCAData = hass.data.get(DOMAIN)
        if data:
            data.step_active = False
            data.current_circuit = None
    return unload_ok

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

    async def handle_reload(call: ServiceCall):
        """Reload this integration entry or a specific entry_id."""
        entry_id = call.data.get("entry_id")
        target_id = entry_id or entry.entry_id
        hass.async_create_task(hass.config_entries.async_reload(target_id))

    async def handle_workflow_start(call: ServiceCall):
        if data.workflow_active:
            _LOGGER.warning("Workflow already active; stop or restart first")
            return
        # Build queue
        circuits = call.data.get("circuits")
        skip = set(call.data.get("skip_circuits") or [])
        wait_s = int(call.data.get("wait_s") or data.measure_duration_s)
        notify_service = call.data.get("notify_service")
        # Determine queue: provided or all except safe and skipped
        if circuits:
            queue = [c for c in circuits if c in data.circuits and c not in data.safe_circuits and c not in skip]
        else:
            queue = [c for c in data.circuits.keys() if c not in data.safe_circuits and c not in skip]
        if not queue:
            persistent_notification.async_create(hass, "Keine geeigneten Stromkreise zum Messen gefunden.", title="PCA Workflow")
            return
        data.workflow_active = True
        data.workflow_queue = queue
        data.workflow_index = 0
        data.workflow_wait_s = max(5, min(3600, wait_s))
        data.workflow_notify_service = notify_service
        data.workflow_skip_circuits = skip
        data._workflow_saved_duration = data.measure_duration_s
        data.measure_duration_s = data.workflow_wait_s
        # Start first step
        await _workflow_start_current_step(hass, data)

    async def handle_workflow_skip_current(call: ServiceCall):
        if not data.workflow_active:
            return
        current = None
        # If measurement is running for current, stop it and ignore result
        if data.workflow_index < len(data.workflow_queue):
            current = data.workflow_queue[data.workflow_index]
            data.workflow_ignore_result_for = current
            # Attempt to stop switch if already on
            switch_eid = f"switch.measure_circuit_{current.lower()}"
            await hass.services.async_call("switch", "turn_off", {"entity_id": switch_eid}, blocking=False)
        # Move to next step
        await _simple_notify(hass, data, f"Überspringe Stromkreis {current or ''}.")
        await _workflow_advance(hass, data)

    async def handle_workflow_stop(call: ServiceCall):
        if not data.workflow_active:
            return
        # Mark inactive immediately and block new starts to prevent races
        data.workflow_active = False
        data.block_measure_starts = True
        data.stopping_workflow = True
        # Stop any ongoing measurements synchronously
        for cid in list(data.circuits.keys()):
            switch_eid = f"switch.measure_circuit_{cid.lower()}"
            try:
                await hass.services.async_call("switch", "turn_off", {"entity_id": switch_eid}, blocking=True)
            except Exception:
                pass
        # Restore duration if altered by workflow
        if data._workflow_saved_duration is not None:
            data.measure_duration_s = data._workflow_saved_duration
            data._workflow_saved_duration = None
        # Force-clear measuring status and notify sensors
        data.measuring_circuit = None
        data.measurement_origin = None
        async_dispatcher_send(hass, f"{DOMAIN}_measure_state")
        # Cleanup workflow fields
        data.workflow_queue = []
        data.workflow_index = 0
        data.workflow_wait_s = 0
        data.workflow_notify_service = None
        data.workflow_skip_circuits = set()
        data.workflow_ignore_result_for = None
        # Unblock starts
        data.block_measure_starts = False
        data.stopping_workflow = False
        # Notify user
        await _notify(hass, data, "Workflow abgebrochen.", title="PCA Workflow Ende")

    async def handle_workflow_restart(call: ServiceCall):
        if not data.workflow_active:
            return
        # Stop current measurement
        if data.workflow_index < len(data.workflow_queue):
            current = data.workflow_queue[data.workflow_index]
            switch_eid = f"switch.measure_circuit_{current.lower()}"
            await hass.services.async_call("switch", "turn_off", {"entity_id": switch_eid}, blocking=False)
        data.workflow_index = 0
        await _simple_notify(hass, data, "Starte den Workflow neu.")
        await _workflow_start_current_step(hass, data)

    hass.services.async_register(DOMAIN, "select_circuit", handle_select_circuit)
    hass.services.async_register(DOMAIN, "confirm_off", handle_confirm_off)
    hass.services.async_register(DOMAIN, "confirm_on", handle_confirm_on)
    hass.services.async_register(DOMAIN, "circuit_link_energy_meter", handle_link_energy_meter)
    hass.services.async_register(DOMAIN, "circuit_unlink_energy_meter", handle_unlink_energy_meter)
    hass.services.async_register(DOMAIN, "reload", handle_reload)
    hass.services.async_register(DOMAIN, "start_guided_analysis", handle_workflow_start)
    hass.services.async_register(DOMAIN, "workflow_skip_current", handle_workflow_skip_current)
    hass.services.async_register(DOMAIN, "workflow_stop", handle_workflow_stop)
    hass.services.async_register(DOMAIN, "workflow_restart", handle_workflow_restart)

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
    """Ensure the device for each entity has the 'EnergyMeter' label."""
    if not entity_ids:
        return
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    lbl_reg = lr.async_get(hass)

    def _norm(s: Optional[str]) -> str:
        if not s:
            return ""
        return "".join(ch for ch in s.lower() if ch.isalnum())

    # Find or create the new label by name (case/slug-insensitive) and detect old ones for cleanup
    energy_label = None
    old_energy_label = None
    try:
        for lbl in getattr(lbl_reg, "labels", {}).values():
            name = getattr(lbl, "name", None)
            norm = _norm(name)
            if norm == "energymeter":
                energy_label = lbl
            elif norm in ("energy_meter",):
                old_energy_label = lbl
        if energy_label is None:
            create = getattr(lbl_reg, "async_create", None)
            if create:
                energy_label = create(name="EnergyMeter")
    except Exception as ex:
        _LOGGER.debug("Label registry access failed: %s", ex)

    new_label_id: Optional[str] = getattr(energy_label, "id", None) if energy_label else None
    old_label_id: Optional[str] = getattr(old_energy_label, "id", None) if old_energy_label else None

    for eid in entity_ids:
        ent = ent_reg.async_get(eid)
        if not ent or not ent.device_id:
            continue
        dev = dev_reg.async_get(ent.device_id)
        if not dev:
            continue
        try:
            current_labels: Set[str] = set(getattr(dev, "labels", set()) or set())
            changed = False
            if new_label_id and new_label_id not in current_labels:
                current_labels.add(new_label_id)
                changed = True
            if old_label_id and old_label_id in current_labels:
                current_labels.remove(old_label_id)
                changed = True
            if changed:
                dev_reg.async_update_device(dev.id, labels=current_labels)
        except Exception as ex:
            _LOGGER.debug("Failed to update labels for device %s: %s", dev.id, ex)

def _init_label_tracking(hass: HomeAssistant, data: PCAData) -> None:
    """Initialize EnergyMeter label id, seed label_meters, and subscribe to device updates."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    lbl_reg = lr.async_get(hass)

    def _norm(s: Optional[str]) -> str:
        if not s:
            return ""
        return "".join(ch for ch in s.lower() if ch.isalnum())

    # Find label id for 'EnergyMeter' (case/slug-insensitive)
    label_id = None
    try:
        for lbl in getattr(lbl_reg, "labels", {}).values():
            name = getattr(lbl, "name", None)
            if _norm(name) == "energymeter":
                label_id = getattr(lbl, "id", None)
                break
    except Exception as ex:
        _LOGGER.debug("Label registry enumeration failed: %s", ex)
    data.energy_label_id = label_id

    # Seed meters from devices carrying the label
    added_entities: List[str] = []
    if label_id:
        try:
            for device in getattr(dev_reg, "devices", {}).values():
                lbls: Set[str] = set(getattr(device, "labels", set()) or set())
                if label_id in lbls:
                    data.devices_with_label.add(device.id)
                    for ent in ent_reg.async_entries_for_device(device.id):
                        if ent.domain == "sensor":
                            eid = ent.entity_id
                            if eid not in data.label_meters:
                                data.label_meters.add(eid)
                                added_entities.append(eid)
        except Exception as ex:
            _LOGGER.debug("Seeding label meters failed: %s", ex)
    if added_entities:
        hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": added_entities, "removed": []})

    # Subscribe to device registry updates to react to label changes
    async def _on_device_registry_updated(event):
        device_id = event.data.get("device_id")
        action = event.data.get("action")
        if not device_id:
            return
        device = dev_reg.async_get(device_id)
        if action == "remove" or not device:
            # device removed
            removed = []
            if device_id in data.devices_with_label:
                data.devices_with_label.discard(device_id)
                # remove all sensor entities for that device from label_meters
                for ent in ent_reg.async_entries_for_device(device_id):
                    if ent.domain == "sensor" and ent.entity_id in data.label_meters:
                        data.label_meters.discard(ent.entity_id)
                        removed.append(ent.entity_id)
            if removed:
                hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": [], "removed": removed})
            return
        # update/create: check if label status changed
        has_label = False
        if data.energy_label_id:
            try:
                has_label = data.energy_label_id in (getattr(device, "labels", set()) or set())
            except Exception:
                has_label = False
        before = device_id in data.devices_with_label
        if has_label and not before:
            # label added
            data.devices_with_label.add(device_id)
            added = []
            for ent in ent_reg.async_entries_for_device(device_id):
                if ent.domain == "sensor":
                    eid = ent.entity_id
                    if eid not in data.label_meters:
                        data.label_meters.add(eid)
                        added.append(eid)
            if added:
                hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": added, "removed": []})
        elif not has_label and before:
            # label removed
            data.devices_with_label.discard(device_id)
            removed = []
            for ent in ent_reg.async_entries_for_device(device_id):
                if ent.domain == "sensor" and ent.entity_id in data.label_meters:
                    data.label_meters.discard(ent.entity_id)
                    removed.append(ent.entity_id)
            if removed:
                hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": [], "removed": removed})

    hass.bus.async_listen("device_registry_updated", _on_device_registry_updated)

@callback
def _apply_options_to_data(data: PCAData, entry: ConfigEntry) -> None:
    try:
        md = int(entry.options.get("measure_duration_s", data.measure_duration_s))
        data.measure_duration_s = max(5, min(3600, md))
    except Exception:
        pass
    try:
        hx = int(entry.options.get("history_size", data.measure_history_max))
        data.measure_history_max = max(1, min(500, hx))
    except Exception:
        pass

async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data: PCAData = hass.data.get(DOMAIN)
    if not data:
        return
    _apply_options_to_data(data, entry)

async def _workflow_start_current_step(hass: HomeAssistant, data: PCAData) -> None:
    if not data.workflow_active or data.workflow_index >= len(data.workflow_queue):
        await _workflow_finish(hass, data)
        return
    current = data.workflow_queue[data.workflow_index]
    # Notify user to turn off current circuit
    nxt = data.workflow_queue[data.workflow_index + 1] if data.workflow_index + 1 < len(data.workflow_queue) else None
    msg = f"Schalte jetzt Stromkreis {current} AUS. Warte {data.workflow_wait_s} Sekunden."
    if nxt:
        msg += f" Danach folgt: {nxt}."
    await _notify(hass, data, msg, title="PCA Schritt gestartet")
    # Mark origin and start measurement via switch turn_on
    data.measurement_origin = "workflow"
    switch_eid = f"switch.measure_circuit_{current.lower()}"
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_eid}, blocking=True)

async def _workflow_advance(hass: HomeAssistant, data: PCAData) -> None:
    if not data.workflow_active:
        return
    data.workflow_index += 1
    if data.workflow_index >= len(data.workflow_queue):
        await _workflow_finish(hass, data)
    else:
        await _workflow_start_current_step(hass, data)

async def _workflow_finish(hass: HomeAssistant, data: PCAData, reason: Optional[str] = None) -> None:
    # Restore duration
    if data._workflow_saved_duration is not None:
        data.measure_duration_s = data._workflow_saved_duration
        data._workflow_saved_duration = None
    if not data.workflow_active:
        return
    if reason:
        await _notify(hass, data, f"Workflow {reason}.", title="PCA Workflow Ende")
    else:
        await _notify(hass, data, "Workflow abgeschlossen.", title="PCA Workflow Ende")
    data.workflow_active = False
    data.workflow_queue = []
    data.workflow_index = 0
    data.workflow_wait_s = 0
    data.workflow_notify_service = None
    data.workflow_skip_circuits = set()
    data.workflow_ignore_result_for = None

async def _notify_step_result(hass: HomeAssistant, data: PCAData, circuit_id: str) -> None:
    effect = data.measure_results.get(circuit_id)
    if effect is None:
        msg = f"Ergebnis {circuit_id}: kein Wert verfügbar."
    else:
        msg = f"Ergebnis {circuit_id}: Auswirkung auf nicht erfasste Last {effect:.2f} W."
    await _notify(hass, data, msg, title="PCA Schritt Ergebnis")

async def _notify(hass: HomeAssistant, data: PCAData, message: str, title: str = "PCA") -> None:
    # Persistent notification
    try:
        persistent_notification.async_create(hass, message, title=title, notification_id=data.workflow_notification_id)
    except Exception:
        pass
    # Optional notify service
    if data.workflow_notify_service:
        try:
            await hass.services.async_call("notify", data.workflow_notify_service, {"message": message, "title": title}, blocking=False)
        except Exception:
            _LOGGER.debug("Notify service %s failed", data.workflow_notify_service)

async def _simple_notify(hass: HomeAssistant, data: PCAData, message: str) -> None:
    await _notify(hass, data, message, title="PCA Workflow")
