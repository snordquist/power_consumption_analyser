from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from .base import BasePCASensor
from ..const import DOMAIN

class CountdownSensor(BasePCASensor):
    _attr_name = "Countdown"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "s"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_countdown"

    @property
    def native_value(self) -> Optional[int]:
        if not self.data.workflow_active:
            return None
        started = self.data.workflow_step_started_at
        wait_s = int(self.data.workflow_wait_s or 0)
        if not started or wait_s <= 0:
            return None
        now = datetime.now(timezone.utc)
        elapsed = int((now - started).total_seconds())
        remaining = max(0, wait_s - elapsed)
        return remaining

