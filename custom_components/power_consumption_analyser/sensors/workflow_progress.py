from __future__ import annotations
from typing import List, Dict
from ..model import PCAData
from .base import BasePCASensor
from ..const import DOMAIN

class WorkflowProgressSensor(BasePCASensor):
    _attr_name = "Workflow Progress"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_workflow_progress"

    @property
    def native_value(self) -> str:
        # returns "idle" or "active"
        return "active" if self.data.workflow_active else "idle"

    @property
    def extra_state_attributes(self) -> Dict[str, object]:
        queue: List[str] = list(self.data.workflow_queue)
        idx = int(self.data.workflow_index or 0)
        done = queue[:idx] if queue else []
        remaining = queue[idx:] if queue else []
        current = remaining[0] if remaining else None
        return {
            "queue": queue,
            "index": idx,
            "done": done,
            "remaining": remaining,
            "current": current,
        }

