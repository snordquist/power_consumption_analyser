from __future__ import annotations
from typing import Optional
from .base import BasePCASensor
from ..const import DOMAIN

STRAT_NAMES = {
    "average": "Average",
    "median": "Median",
    "trimmed_mean": "Trimmed Mean",
    "median_of_means": "Median of Means",
}

class SelectedStrategySensor(BasePCASensor):
    _attr_name = "Selected Strategy"
    _attr_icon = "mdi:calculator-variant"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_selected_strategy"

    @property
    def native_value(self) -> Optional[str]:
        key = getattr(self.data, "effect_strategy", "average")
        return STRAT_NAMES.get(key, key)

    @property
    def extra_state_attributes(self) -> dict:
        key = getattr(self.data, "effect_strategy", "average")
        return {"key": key}
