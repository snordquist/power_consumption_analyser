from __future__ import annotations
from typing import Dict, List
from .base import BasePCASensor
from ..const import DOMAIN

class RCDLayoutSensor(BasePCASensor):
    _attr_name = "RCD Layout"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_rcd_layout"

    @property
    def native_value(self) -> str:
        return "ready"

    @property
    def extra_state_attributes(self) -> Dict[str, object]:
        # Expose rcd list and mapping for dashboard
        rcds = list(self.data.rcd_to_circuits.keys())
        layout = {rcd: list(self.data.rcd_to_circuits.get(rcd, [])) for rcd in rcds}
        # Progress for styling
        queue: List[str] = list(self.data.workflow_queue)
        idx = int(self.data.workflow_index or 0)
        done = queue[:idx] if queue else []
        remaining = queue[idx:] if queue else []
        current = remaining[0] if remaining else None
        return {
            "rcds": rcds,
            "layout": layout,
            "done": done,
            "remaining": remaining,
            "current": current,
        }

