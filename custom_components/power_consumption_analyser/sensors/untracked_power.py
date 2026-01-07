from __future__ import annotations
from typing import Optional, Set, List, Callable
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from ..const import DOMAIN
from ..model import PCAData
from .base import BasePCASensor

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

