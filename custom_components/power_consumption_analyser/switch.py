from __future__ import annotations

from statistics import mean
from typing import Optional, Callable, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback, HassJob
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from . import DOMAIN, PCAData


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities: List[SwitchEntity] = []
    for cid in data.circuits.keys():
        entities.append(CircuitMeasureSwitch(data, cid))
    async_add_entities(entities)


class CircuitMeasureSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, data: PCAData, circuit_id: str):
        self.data = data
        self._circuit_id = circuit_id
        self._is_on = False
        self._attr_name = f"Measure Circuit {circuit_id}"
        self._attr_unique_id = f"{DOMAIN}_measure_{circuit_id.lower()}"
        self._unsub_state: Optional[Callable[[], None]] = None
        self._unsub_timer: Optional[Callable[[], None]] = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        # Start measurement: reset samples and record baseline (current untracked)
        if self._is_on:
            return
        self._is_on = True
        hass = self.hass
        # compute current untracked
        untracked = _current_untracked(hass, self.data)
        self.data.measure_baseline[self._circuit_id] = untracked
        self.data.measure_samples[self._circuit_id] = []
        # subscribe to untracked changes
        self._subscribe_state_changes()
        # auto-finish after duration
        duration = self.data.measure_duration_s
        def _timer_cb(_now):
            hass.async_add_job(self._finish_measure())
        self._unsub_timer = async_call_later(hass, duration, HassJob(_timer_cb))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        # Stop measurement early and finalize
        if not self._is_on:
            return
        await self._finalize()

    def _subscribe_state_changes(self) -> None:
        hass = self.hass
        # track changes for home consumption and all meters to recompute untracked
        entities = set(self.data.meter_to_circuit.keys()) | set(self.data.label_meters)
        home = self.data.baseline_sensors.get("home_consumption") if self.data.baseline_sensors else None
        if home:
            entities.add(home)

        @callback
        def _on_change(event):
            if not self._is_on:
                return
            untracked = _current_untracked(hass, self.data)
            self.data.measure_samples[self._circuit_id].append(untracked)

        if entities:
            self._unsub_state = async_track_state_change_event(hass, list(entities), _on_change)

    async def _finish_measure(self):
        # Called when the timer expires
        await self._finalize()

    async def _finalize(self):
        # Compute average effect: baseline - average_untracked
        self._is_on = False
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None

        samples = self.data.measure_samples.get(self._circuit_id, [])
        baseline = self.data.measure_baseline.get(self._circuit_id, 0.0)
        avg_untracked = mean(samples) if samples else _current_untracked(self.hass, self.data)
        effect = baseline - avg_untracked
        self.data.measure_results[self._circuit_id] = effect
        # fire event for sensors to update
        self.hass.bus.async_fire(f"{DOMAIN}.measure_finished", {
            "circuit_id": self._circuit_id,
            "baseline": baseline,
            "avg_untracked": avg_untracked,
            "effect": effect,
            "samples": len(samples),
        })
        self.async_write_ha_state()


def _current_untracked(hass: HomeAssistant, data: PCAData) -> float:
    # helper: compute current untracked as home - tracked
    home = data.baseline_sensors.get("home_consumption") if data.baseline_sensors else None
    home_w = 0.0
    if home:
        st = hass.states.get(home)
        try:
            home_w = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            home_w = 0.0
    tracked = 0.0
    for eid in set(data.meter_to_circuit.keys()) | set(data.label_meters):
        st = hass.states.get(eid)
        try:
            v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            v = 0.0
        tracked += v
    val = home_w - tracked
    return round(val if val >= 0 else 0.0, 2)
