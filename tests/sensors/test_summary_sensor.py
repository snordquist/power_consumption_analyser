import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_summary_sensor_attributes(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="testsum",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cids = list(data.circuits.keys())
    if len(cids) < 2:
        pytest.skip("need at least two circuits")

    data.measure_history[cids[0]] = [
        {"ts": "t1", "effect": 50.0, "baseline": 300.0, "avg_untracked": 250.0, "samples": 3, "duration_s": 30},
        {"ts": "t2", "effect": 60.0, "baseline": 310.0, "avg_untracked": 250.0, "samples": 4, "duration_s": 30},
    ]
    data.measure_history[cids[1]] = [
        {"ts": "t3", "effect": 20.0, "baseline": 310.0, "avg_untracked": 290.0, "samples": 2, "duration_s": 30},
    ]
    hass.bus.async_fire(f"{DOMAIN}.measure_finished", {"circuit_id": cids[0]})
    hass.bus.async_fire(f"{DOMAIN}.measure_finished", {"circuit_id": cids[1]})
    await hass.async_block_till_done()

    summary = hass.states.get("sensor.power_consumption_analyser_measurement_summary")
    assert summary is not None
    float(summary.state)
    attrs = summary.attributes
    assert "avg_effects" in attrs and isinstance(attrs["avg_effects"], dict)
    assert len(attrs["avg_effects"]) >= 2
    assert any(item["circuit_id"] == cids[0] for item in attrs["top3_by_avg"]) or any(item["circuit_id"] == cids[1] for item in attrs["top3_by_avg"])

