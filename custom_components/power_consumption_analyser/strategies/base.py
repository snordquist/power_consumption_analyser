from __future__ import annotations
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class MeasurementWindow:
    baseline: float
    samples: List[float]

class EffectStrategy:
    key: str = "base"
    name: str = "Base"

    def compute(self, on: MeasurementWindow, off: MeasurementWindow) -> Dict[str, float]:
        raise NotImplementedError

