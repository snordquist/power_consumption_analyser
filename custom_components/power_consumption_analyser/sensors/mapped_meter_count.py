from __future__ import annotations
from ..const import DOMAIN
from .meter_count import _BaseCountSensor

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

