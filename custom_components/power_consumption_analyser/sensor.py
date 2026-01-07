from __future__ import annotations

import logging
from typing import Optional, Set, List

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event

from . import DOMAIN, PCAData

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities = [
        TrackedPowerSumSensor(data),
        CalculatedUntrackedPowerSensor(data),
        AnalysisStatusSensor(data),
    ]
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
        self._unsub_listeners: List[callable] = []

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_tracked_power_sum"

    @property
    def native_value(self) -> Optional[float]:
        total = 0.0
        for eid in list(self._meter_entities):
            state = self.hass.states.get(eid)
            try:
                v = float(state.state) if state and state.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            total += v
        return round(total, 2)

    async def async_added_to_hass(self) -> None:
        # Listen to meters state changes to refresh
        self._refresh_listeners()
        # Listen to dynamic link/unlink events to adjust the set
        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_write_ha_state()
        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_write_ha_state()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return
        def _state_change_handler(event):
            self.async_write_ha_state()
        if self._meter_entities:
            unsub = async_track_state_change_event(self.hass, list(self._meter_entities), _state_change_handler)
            self._unsub_listeners.append(unsub)

class CalculatedUntrackedPowerSensor(BasePCASensor):
    _attr_name = "Untracked Power"
    _attr_native_unit_of_measurement = "W"

    def __init__(self, data: PCAData):
        super().__init__(data)
        self._meter_entities: Set[str] = set(data.meter_to_circuit.keys())
        self._home_entity: Optional[str] = data.baseline_sensors.get("home_consumption") if data.baseline_sensors else None
        self._unsub_listeners: List[callable] = []

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
        for eid in list(self._meter_entities):
            st = self.hass.states.get(eid)
            try:
                v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
            except Exception:
                v = 0.0
            tracked += v
        value = home_w - tracked
        # Clamp to >= 0 to avoid minor negative due to rounding/noise
        return round(value if value >= 0 else 0.0, 2)

    async def async_added_to_hass(self) -> None:
        # Listen to home consumption and meters
        self._refresh_listeners()
        # Listen to dynamic link/unlink events
        @callback
        def _on_meter_linked(event):
            eid = event.data.get("entity_id")
            if eid:
                self._meter_entities.add(eid)
                self._refresh_listeners()
                self.async_write_ha_state()
        @callback
        def _on_meter_unlinked(event):
            eid = event.data.get("entity_id")
            if eid and eid in self._meter_entities:
                self._meter_entities.remove(eid)
                self._refresh_listeners()
                self.async_write_ha_state()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_linked", _on_meter_linked))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.meter_unlinked", _on_meter_unlinked))

    def _refresh_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        if not self.hass:
            return
        entities = set(self._meter_entities)
        if self._home_entity:
            entities.add(self._home_entity)
        def _state_change_handler(event):
            self.async_write_ha_state()
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
