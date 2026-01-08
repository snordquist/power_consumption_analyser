from __future__ import annotations

from typing import Dict, List
from math import ceil
from statistics import mean, median
from .base import EffectStrategy, MeasurementWindow

class MedianOfMeansStrategy(EffectStrategy):
    key = "median_of_means"
    name = "Median of Means"

    def __init__(self, bins: int = 3):
        self.bins = max(1, int(bins))

    def compute(self, on: MeasurementWindow, off: MeasurementWindow) -> Dict[str, float]:
        vals: List[float] = list(off.samples) if off.samples else []
        n = len(vals)
        if n == 0:
            return {"effect": 0.0, "bins": self.bins, "n": 0}
        b = min(self.bins, n)
        size = ceil(n / b)
        means: List[float] = []
        for i in range(0, n, size):
            chunk = vals[i : i + size]
            if chunk:
                means.append(mean(chunk))
        mom = median(means) if means else mean(vals)
        effect = on.baseline - mom
        return {"effect": effect, "bins": b, "n": n}

