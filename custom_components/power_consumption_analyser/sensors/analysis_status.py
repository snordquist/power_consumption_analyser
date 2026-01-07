from __future__ import annotations
from ..const import DOMAIN
from .base import BasePCASensor

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

