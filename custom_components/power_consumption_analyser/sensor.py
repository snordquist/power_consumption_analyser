from __future__ import annotations

import logging
from typing import Optional, Set, List, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, PCAData

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities = [
        TrackedPowerSumSensor(data),
        CalculatedUntrackedPowerSensor(data),
        TrackedCoverageSensor(data),
        TrackedToUntrackedRatioSensor(data),
        MeterCountSensor(data),
        LabelMeterCountSensor(data),
        MappedMeterCountSensor(data),
        UnavailableMeterCountSensor(data),
        AnalysisStatusSensor(data),
    ]
    # Per-circuit effect sensors
    for cid in data.circuits.keys():
        entities.append(CircuitEffectSensor(data, cid))  # type: ignore[list-item]
    # Measurement status
    entities.append(MeasurementStatusSensor(data))  # type: ignore[list-item]
    # Summary sensor
    entities.append(SummaryEffectSensor(data))  # type: ignore[list-item]
    async_add_entities(entities, True)

class BasePCASensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, data: PCAData):
        self.data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

class TrackedPowerSumSensor(BasePCASensor):
    _attr_name = "Tracked Power Sum"
    _attr_native_unit_of_measurement = "W"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._unsub_listeners: List[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_tracked_power_sum"

    @property
    def native_value(self) -> Optional[float]:
        total = 0.0
        # Combine circuit-linked meters and label-based meters
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        for eid in list(meter_ids):
            state = self.hass.states.get(eid)
            try:
                v = float(state.state) if state and state.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            total += v
        return round(total, 2)

    async def async_added_to_hass(self) -> None:
        self._refresh_listeners()

        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_label_meters_changed(event):
            self._refresh_listeners()
            self.async_schedule_update_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_label_meters_changed))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return

        @callback
        def _state_change_handler(event):
            self.async_schedule_update_ha_state()

        # Listen for state changes of both circuit-linked and label-based meters
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        if meter_ids:
            unsub = async_track_state_change_event(self.hass, list(meter_ids), _state_change_handler)
            self._unsub_listeners.append(unsub)

class CalculatedUntrackedPowerSensor(BasePCASensor):
    _attr_name = "Untracked Power"
    _attr_native_unit_of_measurement = "W"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._home_entity: Optional[str] = data.baseline_sensors.get("home_consumption") if data.baseline_sensors else None
        self._unsub_listeners: List[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_untracked_power"

    @property
    def native_value(self) -> Optional[float]:
        if not self._home_entity:
            return None
        home_state = self.hass.states.get(self._home_entity)
        try:
            home_w = float(home_state.state) if home_state and home_state.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            home_w = 0.0
        tracked = 0.0
        # Combine meters
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        for eid in list(meter_ids):
            st = self.hass.states.get(eid)
            try:
                v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            tracked += v
        value = home_w - tracked
        return round(value if value >= 0 else 0.0, 2)

    async def async_added_to_hass(self) -> None:
        self._refresh_listeners()

        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_label_meters_changed(event):
            self._refresh_listeners()
            self.async_schedule_update_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_label_meters_changed))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return
        entities = set(self._meter_entities) | set(self.data.label_meters)
        if self._home_entity:
            entities.add(self._home_entity)

        @callback
        def _state_change_handler(event):
            self.async_schedule_update_ha_state()

        if entities:
            unsub = async_track_state_change_event(self.hass, list(entities), _state_change_handler)
            self._unsub_listeners.append(unsub)

class AnalysisStatusSensor(BasePCASensor):
    _attr_name = "Analysis Status"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_analysis_status"

    @property
    def native_value(self) -> str:
        if self.data.step_active and self.data.current_circuit:
            return f"active:{self.data.current_circuit}"
        return "idle"

class MeasurementStatusSensor(BasePCASensor):
    _attr_name = "Measurement Status"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_measurement_status"

    @property
    def native_value(self) -> str:
        if getattr(self.data, "stopping_workflow", False):
            return "idle"
        if self.data.measuring_circuit:
            return f"measuring:{self.data.measuring_circuit}:{self.data.measure_duration_s}s"
        return "idle"

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_event(event):
            self.async_write_ha_state()
        @callback
        def _on_signal(*_):
            self.async_write_ha_state()
        # Bus events
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measurement_started", _on_event))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measure_finished", _on_event))
        # Dispatcher immediate signal
        self.async_on_remove(async_dispatcher_connect(self.hass, f"{DOMAIN}_measure_state", _on_signal))

class CircuitEffectSensor(BasePCASensor):
    _attr_native_unit_of_measurement = "W"

    def __init__(self, data: PCAData, circuit_id: str):
        super().__init__(data)
        self._circuit_id = circuit_id
        self._attr_name = f"Circuit {circuit_id} Effect"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_circuit_{self._circuit_id.lower()}_effect"

    @property
    def native_value(self) -> Optional[float]:
        val = self.data.measure_results.get(self._circuit_id)
        if val is None:
            return 0.0
        return round(val, 2)

    @property
    def extra_state_attributes(self) -> dict:
        hist = self.data.measure_history.get(self._circuit_id, [])
        # Compute stats
        effects = [h.get("effect", 0.0) for h in hist]
        count = len(effects)
        avg = round(sum(effects) / count, 2) if count else 0.0
        mn = round(min(effects), 2) if effects else 0.0
        mx = round(max(effects), 2) if effects else 0.0
        return {
            "history_size": len(hist),
            "history_max": self.data.measure_history_max,
            "avg_effect": avg,
            "min_effect": mn,
            "max_effect": mx,
            "last": hist[-1] if hist else None,
        }

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_measure_finished(event):
            if event.data.get("circuit_id") == self._circuit_id:
                self.async_schedule_update_ha_state()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measure_finished", _on_measure_finished))

class SummaryEffectSensor(BasePCASensor):
    _attr_name = "Measurement Summary"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_summary"

    @property
    def native_value(self) -> Optional[float]:
        # Optional single-number summary: the maximum average effect across circuits
        max_avg = 0.0
        for cid, hist in self.data.measure_history.items():
            effects = [h.get("effect", 0.0) for h in hist]
            if effects:
                avg = sum(effects) / len(effects)
                if avg > max_avg:
                    max_avg = avg
        return round(max_avg, 2)

    @property
    def extra_state_attributes(self) -> dict:
        last_effects = {}
        avg_effects = {}
        total_entries = 0
        for cid, hist in self.data.measure_history.items():
            total_entries += len(hist)
            if hist:
                last_effects[cid] = hist[-1].get("effect", 0.0)
                effects = [h.get("effect", 0.0) for h in hist]
                avg_effects[cid] = round(sum(effects) / len(effects), 2)
            else:
                last_effects[cid] = 0.0
                avg_effects[cid] = 0.0
        # sort top 3
        top3_avg = sorted(avg_effects.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_last = sorted(last_effects.items(), key=lambda x: x[1], reverse=True)[:3]
        return {
            "circuits": list(self.data.circuits.keys()),
            "last_effects": last_effects,
            "avg_effects": avg_effects,
            "top3_by_avg": [{"circuit_id": k, "avg_effect": v} for k, v in top3_avg],
            "top3_by_last": [{"circuit_id": k, "last_effect": v} for k, v in top3_last],
            "history_entries_total": total_entries,
            "history_max_per_circuit": self.data.measure_history_max,
        }

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_measure_finished(event):
            self.async_schedule_update_ha_state()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measure_finished", _on_measure_finished))

class TrackedCoverageSensor(BasePCASensor):
    _attr_name = "Tracked Coverage"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._home_entity: Optional[str] = data.baseline_sensors.get("home_consumption") if data.baseline_sensors else None
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._unsub_listeners: List[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_tracked_coverage_percent"

    @property
    def native_value(self) -> Optional[float]:
        if not self._home_entity:
            return None
        home_state = self.hass.states.get(self._home_entity)
        try:
            home_w = float(home_state.state) if home_state and home_state.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            home_w = 0.0
        tracked = 0.0
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        for eid in meter_ids:
            st = self.hass.states.get(eid)
            try:
                v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            tracked += v
        if home_w <= 0:
            return 0.0
        return round((tracked / home_w) * 100.0, 2)

    async def async_added_to_hass(self) -> None:
        self._refresh_listeners()

        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_label_meters_changed(event):
            self._refresh_listeners()
            self.async_schedule_update_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_label_meters_changed))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return
        entities = set(self._meter_entities) | set(self.data.label_meters)
        if self._home_entity:
            entities.add(self._home_entity)

        @callback
        def _state_change_handler(event):
            self.async_schedule_update_ha_state()

        if entities:
            unsub = async_track_state_change_event(self.hass, list(entities), _state_change_handler)
            self._unsub_listeners.append(unsub)

class TrackedToUntrackedRatioSensor(BasePCASensor):
    _attr_name = "Tracked/Untracked Ratio"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._home_entity: Optional[str] = data.baseline_sensors.get("home_consumption") if data.baseline_sensors else None
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._unsub_listeners: List[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_tracked_untracked_ratio"

    @property
    def native_value(self) -> Optional[float]:
        if not self._home_entity:
            return None
        home_state = self.hass.states.get(self._home_entity)
        try:
            home_w = float(home_state.state) if home_state and home_state.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            home_w = 0.0
        tracked = 0.0
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        for eid in meter_ids:
            st = self.hass.states.get(eid)
            try:
                v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            tracked += v
        untracked = max(home_w - tracked, 0.0)
        if untracked <= 0:
            return None
        return round(tracked / untracked, 3)

    async def async_added_to_hass(self) -> None:
        self._refresh_listeners()

        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_label_meters_changed(event):
            self._refresh_listeners()
            self.async_schedule_update_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_label_meters_changed))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return
        entities = set(self._meter_entities) | set(self.data.label_meters)
        if self._home_entity:
            entities.add(self._home_entity)

        @callback
        def _state_change_handler(event):
            self.async_schedule_update_ha_state()

        if entities:
            unsub = async_track_state_change_event(self.hass, list(entities), _state_change_handler)
            self._unsub_listeners.append(unsub)

class _BaseCountSensor(BasePCASensor):
    _attr_native_unit_of_measurement = None

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._unsub: Optional[Callable[[], None]] = None

    def _subscribe(self, include_home: bool = False) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        @callback
        def _on_change(event):
            self.async_schedule_update_ha_state()
        # events that affect counts
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_change))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_change))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_change))

class MeterCountSensor(_BaseCountSensor):
    _attr_name = "Meter Count"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_meter_count"

    @property
    def native_value(self) -> int:
        return len(set(self.data.meter_to_circuit.keys()) | set(self.data.label_meters))

    async def async_added_to_hass(self) -> None:
        self._subscribe()

class LabelMeterCountSensor(_BaseCountSensor):
    _attr_name = "Label Meter Count"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_label_meter_count"

    @property
    def native_value(self) -> int:
        return len(self.data.label_meters)

    async def async_added_to_hass(self) -> None:
        self._subscribe()

class MappedMeterCountSensor(_BaseCountSensor):
    _attr_name = "Mapped Meter Count"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_mapped_meter_count"

    @property
    def native_value(self) -> int:
        return len(self.data.meter_to_circuit.keys())

    async def async_added_to_hass(self) -> None:
        self._subscribe()

class UnavailableMeterCountSensor(BasePCASensor):
    _attr_name = "Unavailable Meter Count"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._unsub_listeners: List[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_unavailable_meter_count"

    @property
    def native_value(self) -> int:
        count = 0
        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        for eid in meter_ids:
            st = self.hass.states.get(eid)
            if not st or st.state in ("unknown", "unavailable"):
                count += 1
        return count

    async def async_added_to_hass(self) -> None:
        self._refresh_listeners()

        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_schedule_update_ha_state()

        @callback
        def _on_label_meters_changed(event):
            self._refresh_listeners()
            self.async_schedule_update_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.label_meters_changed", _on_label_meters_changed))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return

        @callback
        def _state_change_handler(event):
            self.async_schedule_update_ha_state()

        meter_ids = set(self._meter_entities) | set(self.data.label_meters)
        if meter_ids:
            unsub = async_track_state_change_event(self.hass, list(meter_ids), _state_change_handler)
            self._unsub_listeners.append(unsub)
