import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_setup_entry_and_sensors(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": ["3F11"],
            "baseline_sensors": {
                "home_consumption": "sensor.home_consumption_now_w",
            },
        },
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    hass.states.async_set("sensor.kitchen_plug_power", 120)
    await hass.async_block_till_done()

    tracked = hass.states.get("sensor.power_consumption_analyser_tracked_power_sum")
    untracked = hass.states.get("sensor.power_consumption_analyser_untracked_power")
    assert tracked is not None
    assert untracked is not None
    assert float(tracked.state) == 120.0
    assert float(untracked.state) == 380.0

