from __future__ import annotations
from ..const import DOMAIN
from .meter_count import _BaseCountSensor

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

