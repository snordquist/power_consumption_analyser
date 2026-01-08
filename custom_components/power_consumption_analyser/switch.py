from __future__ import annotations

from statistics import mean
from typing import Optional, Callable, List
from datetime import datetime, timezone

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback, HassJob
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .model import PCAData
from .strategies.base import MeasurementWindow
from .strategies.average import AverageStrategy
from .strategies.median import MedianStrategy
from .strategies.trimmed_mean import TrimmedMeanStrategy
from .strategies.median_of_means import MedianOfMeansStrategy

STRATEGIES = {
    "average": AverageStrategy(),
    "median": MedianStrategy(),
    "trimmed_mean": TrimmedMeanStrategy(),
    "median_of_means": MedianOfMeansStrategy(),
}


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities: List[SwitchEntity] = []
    for cid in data.circuits.keys():
        entities.append(CircuitMeasureSwitch(data, cid))
    async_add_entities(entities)


class CircuitMeasureSwitch(SwitchEntity):
    _attr_has_entity_name = False

    def __init__(self, data: PCAData, circuit_id: str):
        self.data = data
        self._circuit_id = circuit_id
        self._is_on = False
        self._attr_name = f"Measure Circuit {circuit_id}"
        self._attr_unique_id = f"{DOMAIN}_measure_{circuit_id.lower()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )
        self._unsub_state: Optional[Callable[[], None]] = None
        self._unsub_timer: Optional[Callable[[], None]] = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def suggested_object_id(self) -> str:
        return f"measure_circuit_{self._circuit_id.lower()}"

    async def async_turn_on(self, **kwargs) -> None:
        # Start measurement: reset samples and record baseline (current untracked)
        if self._is_on:
            return
        hass = self.hass
        # Abort starts if integration is blocking or stopping workflow (race safety)
        if getattr(self.data, "block_measure_starts", False) or getattr(self.data, "stopping_workflow", False):
            return
        # Double-check just before changing state to avoid race
        if getattr(self.data, "block_measure_starts", False) or getattr(self.data, "stopping_workflow", False):
            return
        self._is_on = True
        self.data.measuring_circuit = self._circuit_id
        # immediate dispatcher update
        async_dispatcher_send(hass, f"{DOMAIN}_measure_state")
        hass.bus.async_fire(f"{DOMAIN}.measurement_started", {"circuit_id": self._circuit_id, "duration_s": self.data.measure_duration_s})
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
        on_win = MeasurementWindow(baseline=baseline, samples=[baseline])
        off_win = MeasurementWindow(baseline=baseline, samples=samples or [ _current_untracked(self.hass, self.data) ])
        key = self.data.effect_strategy
        strat = STRATEGIES.get(key)
        if key == "trimmed_mean":
            # Use configured trim fraction (percent)
            try:
                from .strategies.trimmed_mean import TrimmedMeanStrategy as _TMS
                trim = float(getattr(self.data, "trim_fraction", 20) or 20) / 100.0
                strat = _TMS(trim=trim)
            except Exception:
                pass
        if strat is None:
            strat = STRATEGIES["average"]
        res = strat.compute(on_win, off_win)
        effect = float(res.get("effect", 0.0))
        # Clamp tiny effects
        thr = float(getattr(self.data, "min_effect_w", 0) or 0)
        clamped = False
        if abs(effect) < thr:
            effect = 0.0
            clamped = True
        # Compute stats on OFF samples
        n = len(samples)
        med = 0.0
        mad = 0.0
        sigma = 0.0
        if n:
            try:
                from statistics import median
                med = median(samples)
                mad = median([abs(x - med) for x in samples])
                sigma = 1.4826 * mad
            except Exception:
                med = mean(samples)
                mad = 0.0
                sigma = 0.0
        # Validity based on min samples
        min_samples = int(getattr(self.data, "min_samples", 0) or 0)
        valid = True
        reason = ""
        if n < min_samples:
            valid = False
            reason = f"too_few_samples:{n}<{min_samples}"

        self.data.measure_results[self._circuit_id] = effect
        self.data.measure_clamped[self._circuit_id] = clamped
        self.data.measure_valid[self._circuit_id] = valid
        if reason:
            self.data.measure_reason[self._circuit_id] = reason
        self.data.measure_stats[self._circuit_id] = {
            "samples": n,
            "median_off": round(med, 2),
            "mad": round(mad, 2),
            "sigma": round(sigma, 2),
        }
        # Record history
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "effect": round(effect, 2),
            "baseline": round(baseline, 2),
            "avg_untracked": round((mean(samples) if samples else baseline), 2),
            "samples": len(samples),
            "duration_s": self.data.measure_duration_s,
            "strategy": getattr(strat, "key", "average"),
            "clamped": clamped,
            "valid": valid,
            "reason": reason,
            "mad": round(mad, 2),
            "sigma": round(sigma, 2),
        }
        hist = self.data.measure_history.setdefault(self._circuit_id, [])
        hist.append(entry)
        # Cap history size
        maxlen = max(1, self.data.measure_history_max)
        if len(hist) > maxlen:
            del hist[: len(hist) - maxlen]
        # clear measuring flag
        self.data.measuring_circuit = None
        self.data.measurement_origin = None
        # immediate dispatcher update
        async_dispatcher_send(self.hass, f"{DOMAIN}_measure_state")
        # fire event for sensors to update
        self.hass.bus.async_fire(f"{DOMAIN}.measure_finished", {
            "circuit_id": self._circuit_id,
            "baseline": baseline,
            "avg_untracked": mean(samples) if samples else baseline,
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
