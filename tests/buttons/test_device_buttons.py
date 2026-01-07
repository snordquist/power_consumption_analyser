import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_device_buttons_stop_and_reset(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="testbtns",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Ensure buttons exist
    stop_btn = hass.states.get("button.stop_workflow")
    reset_btn = hass.states.get("button.reset_values")
    assert stop_btn is not None
    assert reset_btn is not None

    # Seed some measure results/history
    data = hass.data[DOMAIN]
    data.measure_results["2F7"] = 12.3
    data.measure_history["2F7"] = [{"ts": "t1", "effect": 12.3}]
    await hass.async_block_till_done()

    # Press reset -> clears values
    await hass.services.async_call("button", "press", {"entity_id": "button.reset_values"}, blocking=True)
    await hass.async_block_till_done()
    assert data.measure_results == {}
    assert data.measure_history == {}

    # Press stop (no active workflow, but service should exist and be callable)
    await hass.services.async_call("button", "press", {"entity_id": "button.stop_workflow"}, blocking=True)
    await hass.async_block_till_done()

