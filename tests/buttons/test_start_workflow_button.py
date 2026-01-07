import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_start_workflow_button(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="teststartbtn",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Ensure button is present
    btn = hass.states.get("button.start_workflow")
    assert btn is not None

    # Seed baseline and press
    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    await hass.services.async_call("button", "press", {"entity_id": "button.start_workflow"}, blocking=True)
    await hass.async_block_till_done()

    # It should start measuring on the first circuit
    # Allow a few cycles for the measurement switch to turn on
    for _ in range(5):
        status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
        if status and status.state.startswith("measuring:"):
            break
        await hass.async_block_till_done()
    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state.startswith("measuring:")

