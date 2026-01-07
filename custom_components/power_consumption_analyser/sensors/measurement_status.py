from __future__ import annotations
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from ..const import DOMAIN
from .base import BasePCASensor

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
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measurement_started", _on_event))
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}.measure_finished", _on_event))
        self.async_on_remove(async_dispatcher_connect(self.hass, f"{DOMAIN}_measure_state", _on_signal))

