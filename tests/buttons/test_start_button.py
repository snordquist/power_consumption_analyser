import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_start_measure_button(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="testbtn1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cid = next(iter(data.circuits.keys()))

    await hass.services.async_call("button", "press", {"entity_id": f"button.start_measure_{cid.lower()}"}, blocking=True)
    await hass.async_block_till_done()

    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state.startswith("measuring:")

