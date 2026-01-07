from __future__ import annotations
from typing import List, Dict
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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

    async def async_added_to_hass(self) -> None:
        @callback
        def _state_update():
            self.async_schedule_update_ha_state()
        self.async_on_remove(async_dispatcher_connect(self.hass, f"{DOMAIN}_workflow_state", _state_update))
