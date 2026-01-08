from __future__ import annotations
from typing import Optional
from homeassistant.core import callback
from ..const import DOMAIN
from ..model import PCAData
from .base import BasePCASensor

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
        attrs = {}
        if self._circuit_id in self.data.measure_results:
            valid = getattr(self.data, "measure_valid", {}).get(self._circuit_id)
            reason = getattr(self.data, "measure_reason", {}).get(self._circuit_id)
            if valid is not None:
                attrs["valid"] = valid
            if reason:
                attrs["reason"] = reason
            clamped = getattr(self.data, "measure_clamped", {}).get(self._circuit_id)
            if clamped is not None:
                attrs["clamped"] = clamped

        hist = self.data.measure_history.get(self._circuit_id, [])
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
