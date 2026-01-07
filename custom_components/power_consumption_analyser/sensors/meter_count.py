from __future__ import annotations
from homeassistant.core import callback
from ..const import DOMAIN
from ..model import PCAData
from .base import BasePCASensor

class _BaseCountSensor(BasePCASensor):
    _attr_native_unit_of_measurement = None
    def __init__(self, data: PCAData):
        super().__init__(data)
        self._unsub = None
    def _subscribe(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        @callback
        def _on_change(event):
            self.async_schedule_update_ha_state()
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

