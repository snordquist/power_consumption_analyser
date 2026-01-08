from __future__ import annotations
from statistics import median
from typing import Dict
from .base import EffectStrategy, MeasurementWindow

class MedianStrategy(EffectStrategy):
    key = "median"
    name = "Median"

    def compute(self, on: MeasurementWindow, off: MeasurementWindow) -> Dict[str, float]:
        med_off = median(off.samples) if off.samples else on.baseline
        effect = on.baseline - med_off
        return {"effect": effect, "median_off": med_off}

