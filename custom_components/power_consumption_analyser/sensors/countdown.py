from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from .base import BasePCASensor
from ..const import DOMAIN

class CountdownSensor(BasePCASensor):
    _attr_name = "Countdown"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "s"

    def __init__(self, data):
        super().__init__(data)
        self._unsub: Optional[callable] = None

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

    async def async_added_to_hass(self) -> None:
        @callback
        def _tick(now):
            # If inactive, stop ticking
            if not self.data.workflow_active:
                if self._unsub:
                    self._unsub()
                    self._unsub = None
                return
            self.async_schedule_update_ha_state()
        # Start ticking every second
        if self._unsub is None:
            self._unsub = async_track_time_interval(self.hass, _tick, interval=1.0)
