import pytest
from custom_components.power_consumption_analyser.strategies.base import MeasurementWindow
from custom_components.power_consumption_analyser.strategies.average import AverageStrategy
from custom_components.power_consumption_analyser.strategies.median import MedianStrategy

@pytest.mark.parametrize(
    "baseline, off, expected",
    [
        (200.0, [120.0, 100.0, 110.0], 200.0 - (120.0 + 100.0 + 110.0) / 3),
        (150.0, [], 0.0),  # falls back to baseline-average; effect becomes 0
    ],
)
def computes_effect_with_average(baseline, off, expected):
    strat = AverageStrategy()
    on = MeasurementWindow(baseline=baseline, samples=[baseline])
    offw = MeasurementWindow(baseline=baseline, samples=off or [baseline])
    res = strat.compute(on, offw)
    assert pytest.approx(res["effect"], rel=1e-6, abs=1e-6) == expected

@pytest.mark.parametrize(
    "baseline, off, expected",
    [
        (200.0, [120.0, 100.0, 110.0], 200.0 - 110.0),  # median(120,100,110)=110
        (150.0, [], 0.0),
        (180.0, [180.0], 0.0),
    ],
)
def computes_effect_with_median(baseline, off, expected):
    strat = MedianStrategy()
    on = MeasurementWindow(baseline=baseline, samples=[baseline])
    offw = MeasurementWindow(baseline=baseline, samples=off or [baseline])
    res = strat.compute(on, offw)
    assert pytest.approx(res["effect"], rel=1e-6, abs=1e-6) == expected

