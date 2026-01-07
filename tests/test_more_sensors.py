import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_coverage_ratio_and_counts(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    # Set up integration
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="test1234",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Seed states
    hass.states.async_set("sensor.home_consumption_now_w", 500)
    hass.states.async_set("sensor.kitchen_plug_power", 120)  # mapped via YAML
    hass.states.async_set("sensor.labeled_meter_power", 80)  # will be added via label event
    await hass.async_block_till_done()

    # Emulate that labeled meter is included via label handling
    data = hass.data[DOMAIN]
    data.label_meters.add("sensor.labeled_meter_power")
    hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": ["sensor.labeled_meter_power"], "removed": []})
    await hass.async_block_till_done()

    # Fetch sensors
    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    coverage = hass.states.get("sensor.power_consumption_analyser_tracked_coverage")
    ratio = hass.states.get("sensor.power_consumption_analyser_tracked_untracked_ratio")
    meter_count = hass.states.get("sensor.power_consumption_analyser_meter_count")
    label_count = hass.states.get("sensor.power_consumption_analyser_label_meter_count")
    mapped_count = hass.states.get("sensor.power_consumption_analyser_mapped_meter_count")
    unavailable_count = hass.states.get("sensor.power_consumption_analyser_unavailable_meter_count")

    assert tracked is not None and float(tracked.state) == 200.0
    assert untracked is not None and float(untracked.state) == 300.0
    assert coverage is not None and float(coverage.state) == 40.0
    assert ratio is not None and float(ratio.state) == 0.667
    assert meter_count is not None and int(meter_count.state) == 2
    assert label_count is not None and int(label_count.state) == 1
    assert mapped_count is not None and int(mapped_count.state) == 1
    assert unavailable_count is not None and int(unavailable_count.state) == 0

    # Make mapped meter unavailable
    hass.states.async_set("sensor.kitchen_plug_power", "unavailable")
    await hass.async_block_till_done()

    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    coverage = hass.states.get("sensor.power_consumption_analyser_tracked_coverage")
    ratio = hass.states.get("sensor.power_consumption_analyser_tracked_untracked_ratio")
    unavailable_count = hass.states.get("sensor.power_consumption_analyser_unavailable_meter_count")

    assert float(tracked.state) == 80.0
    assert float(untracked.state) == 420.0
    assert float(coverage.state) == 16.0
    # 80 / 420 ≈ 0.190476 -> rounds to 0.19 with 3 decimals
    assert float(ratio.state) == 0.19
    assert int(unavailable_count.state) == 1

    # Remove labeled meter via event
    data.label_meters.discard("sensor.labeled_meter_power")
    hass.bus.async_fire(f"{DOMAIN}.label_meters_changed", {"added": [], "removed": ["sensor.labeled_meter_power"]})
    await hass.async_block_till_done()

    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    coverage = hass.states.get("sensor.power_consumption_analyser_tracked_coverage")
    ratio = hass.states.get("sensor.power_consumption_analyser_tracked_untracked_ratio")
    meter_count = hass.states.get("sensor.power_consumption_analyser_meter_count")
    label_count = hass.states.get("sensor.power_consumption_analyser_label_meter_count")

    # tracked falls to 0 (mapped meter still unavailable), untracked back to 500
    assert float(tracked.state) == 0.0
    assert float(untracked.state) == 500.0
    assert float(coverage.state) == 0.0
    assert float(ratio.state) == 0.0
    assert int(meter_count.state) == 1
    assert int(label_count.state) == 0

@pytest.mark.asyncio
async def test_mapping_events_and_ratio_edge(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="test5678",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Seed states
    hass.states.async_set("sensor.home_consumption_now_w", 200)
    hass.states.async_set("sensor.m1", 200)
    await hass.async_block_till_done()

    # Link meter via event
    hass.bus.async_fire(f"{DOMAIN}.meter_linked", {"entity_id": "sensor.m1", "circuit_id": "X"})
    await hass.async_block_till_done()

    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    coverage = hass.states.get("sensor.power_consumption_analyser_tracked_coverage")
    ratio = hass.states.get("sensor.power_consumption_analyser_tracked_untracked_ratio")

    assert float(tracked.state) == 200.0
    assert float(untracked.state) == 0.0
    assert float(coverage.state) == 100.0
    # When untracked is 0, ratio sensor returns None -> HA state is 'unknown'
    assert ratio.state in ("unknown", "unavailable")

    # Unlink meter
    hass.bus.async_fire(f"{DOMAIN}.meter_unlinked", {"entity_id": "sensor.m1", "circuit_id": "X"})
    await hass.async_block_till_done()

    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    coverage = hass.states.get("sensor.power_consumption_analyser_tracked_coverage")
    ratio = hass.states.get("sensor.power_consumption_analyser_tracked_untracked_ratio")

    assert float(tracked.state) == 0.0
    assert float(untracked.state) == 200.0
    assert float(coverage.state) == 0.0
    assert float(ratio.state) == 0.0
