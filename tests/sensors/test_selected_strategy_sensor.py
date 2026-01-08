import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def exposes_selected_strategy_and_updates_on_select_change(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="selected_strategy_sensor",
        options={"effect_strategy": "average"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    s = hass.states.get("sensor.power_consumption_analyser_selected_strategy")
    assert s is not None
    assert s.state in ("Average", "Median")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.power_consumption_analyser_effect_strategy", "option": "Median"},
        blocking=True,
    )
    await hass.async_block_till_done()

    s = hass.states.get("sensor.power_consumption_analyser_selected_strategy")
    assert s is not None and s.state == "Median"
    assert s.attributes.get("key") == "median"

