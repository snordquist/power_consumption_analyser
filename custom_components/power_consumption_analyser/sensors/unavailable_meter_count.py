from __future__ import annotations
from typing import Set, List, Callable
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from ..const import DOMAIN
from ..model import PCAData
from .base import BasePCASensor

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
