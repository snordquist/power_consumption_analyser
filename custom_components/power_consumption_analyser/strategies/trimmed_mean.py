from __future__ import annotations
from typing import Dict, List
from statistics import mean
from .base import EffectStrategy, MeasurementWindow

class TrimmedMeanStrategy(EffectStrategy):
    key = "trimmed_mean"
    name = "Trimmed Mean"

    def __init__(self, trim: float = 0.2):
        self.trim = max(0.0, min(0.45, float(trim)))

    def compute(self, on: MeasurementWindow, off: MeasurementWindow) -> Dict[str, float]:
        vals: List[float] = list(off.samples) if off.samples else []
        if not vals:
            # No samples -> effect 0 (baseline - baseline)
            return {"effect": 0.0, "trim": self.trim}
        vals.sort()
        n = len(vals)
        k = int(n * self.trim)
        if k * 2 >= n:
            # Too few samples to trim; fall back to mean
            avg = mean(vals)
        else:
            center = vals[k : n - k]
            avg = mean(center) if center else mean(vals)
        effect = on.baseline - avg
        return {"effect": effect, "trim": self.trim, "n": n}
