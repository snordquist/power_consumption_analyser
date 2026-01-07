from __future__ import annotations
from typing import Optional
from homeassistant.core import callback
from ..model import PCAData
from .base import BasePCASensor
from ..const import DOMAIN

class SummaryEffectSensor(BasePCASensor):
    _attr_name = "Measurement Summary"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_summary"

    @property
    def native_value(self) -> Optional[float]:
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
