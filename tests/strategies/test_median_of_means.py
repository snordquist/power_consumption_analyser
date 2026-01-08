import pytest
from custom_components.power_consumption_analyser.strategies.base import MeasurementWindow
from custom_components.power_consumption_analyser.strategies.median_of_means import MedianOfMeansStrategy


def test_median_of_means_reduces_outlier_influence():
    on = MeasurementWindow(baseline=200.0, samples=[200.0])
    # Off samples with two clusters and one strong outlier
    off = MeasurementWindow(baseline=200.0, samples=[100, 110, 105, 95, 1000, 90, 115, 108, 102])
    s = MedianOfMeansStrategy(bins=3)
    res = s.compute(on, off)
    effect = res["effect"]
    # Expect effect close to 200 - ~105-110 (center of distribution), far from 200-mean(~191)
    assert 80.0 <= effect <= 110.0


def test_median_of_means_handles_small_samples():
    on = MeasurementWindow(baseline=150.0, samples=[150.0])
    off = MeasurementWindow(baseline=150.0, samples=[120.0])
    s = MedianOfMeansStrategy(bins=5)  # more bins than samples
    res = s.compute(on, off)
    assert pytest.approx(res["effect"], rel=1e-6, abs=1e-6) == 30.0

