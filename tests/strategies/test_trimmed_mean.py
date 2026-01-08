import pytest
from custom_components.power_consumption_analyser.strategies.base import MeasurementWindow
from custom_components.power_consumption_analyser.strategies.trimmed_mean import TrimmedMeanStrategy


def test_trims_extremes_and_matches_center_mean():
    strat = TrimmedMeanStrategy(trim=0.2)
    on = MeasurementWindow(baseline=200.0, samples=[200.0])
    off = MeasurementWindow(baseline=200.0, samples=[10, 100, 110, 120, 1000])
    # After sorting: [10, 100, 110, 120, 1000], trim 1 each side -> [100,110,120], mean=110
    res = strat.compute(on, off)
    assert pytest.approx(res["effect"], rel=1e-6, abs=1e-6) == 200.0 - 110.0


def test_falls_back_to_mean_if_too_few_samples():
    strat = TrimmedMeanStrategy(trim=0.4)
    on = MeasurementWindow(baseline=150.0, samples=[150.0])
    off = MeasurementWindow(baseline=150.0, samples=[120.0, 180.0])
    # trim would remove all; fallback to mean(120, 180)=150, effect=0
    res = strat.compute(on, off)
    assert pytest.approx(res["effect"], rel=1e-6, abs=1e-6) == 0.0
