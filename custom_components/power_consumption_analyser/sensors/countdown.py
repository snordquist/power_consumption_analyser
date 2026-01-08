from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone, timedelta
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .base import BasePCASensor
from ..const import DOMAIN

class CountdownSensor(BasePCASensor):
    _attr_name = "Countdown"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "s"

    def __init__(self, data):
        super().__init__(data)
        self._unsub: Optional[callable] = None
        self._sig_unsub: Optional[callable] = None

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_countdown"

    @property
    def suggested_object_id(self) -> str:
        # Ensure entity_id is sensor.power_consumption_analyser_countdown
        return f"{DOMAIN}_countdown"

    @property
    def native_value(self) -> Optional[int]:
        # When inactive, show 0 instead of unknown to avoid dashboard 'unknown'
        if not self.data.workflow_active:
            return 0
        started = self.data.workflow_step_started_at
        wait_s = int(self.data.workflow_wait_s or 0)
        if not started or wait_s <= 0:
            return 0
        now = datetime.now(timezone.utc)
        if not isinstance(started, datetime):
            return 0
        elapsed = int((now - started).total_seconds())
        remaining = max(0, wait_s - elapsed)
        return remaining

    async def async_added_to_hass(self) -> None:
        @callback
        def _tick(now):
            # If inactive, stop ticking until re-armed by workflow signal
            if not self.data.workflow_active:
                if callable(self._unsub):
                    self._unsub()
                    self._unsub = None
                # Ensure we still publish 0
                self.async_schedule_update_ha_state()
                return
            self.async_schedule_update_ha_state()

        @callback
        def _ensure_timer():
            # Arm timer when workflow is active; disarm otherwise
            if self.data.workflow_active:
                if not callable(self._unsub):
                    self._unsub = async_track_time_interval(self.hass, _tick, interval=timedelta(seconds=1))
                # Immediate update so UI reflects start
                self.async_schedule_update_ha_state()
            else:
                if callable(self._unsub):
                    self._unsub()
                    self._unsub = None
                self.async_schedule_update_ha_state()

        # Subscribe to workflow state changes
        if not self._sig_unsub:
            self._sig_unsub = async_dispatcher_connect(self.hass, f"{DOMAIN}_workflow_state", _ensure_timer)
        # Initial arming based on current state
        _ensure_timer()

    async def async_will_remove_from_hass(self) -> None:
        # Cleanup timers/signals
        if callable(self._unsub):
            self._unsub()
            self._unsub = None
        if callable(self._sig_unsub):
            self._sig_unsub()
            self._sig_unsub = None
