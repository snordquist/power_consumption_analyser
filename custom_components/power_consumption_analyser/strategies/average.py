from __future__ import annotations
from statistics import mean
from typing import Dict
from .base import EffectStrategy, MeasurementWindow

class AverageStrategy(EffectStrategy):
    key = "average"
    name = "Average"

    def compute(self, on: MeasurementWindow, off: MeasurementWindow) -> Dict[str, float]:
        avg_off = mean(off.samples) if off.samples else on.baseline
        effect = on.baseline - avg_off
        return {"effect": effect, "avg_off": avg_off}

