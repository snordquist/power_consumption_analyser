import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_select_entity_changes_strategy_and_persists(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="select_strategy",
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sel = hass.states.get("select.power_consumption_analyser_effect_strategy")
    assert sel is not None
    assert sel.state in ("Average", "Median", "Trimmed Mean")

    # Switch to Median
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.power_consumption_analyser_effect_strategy", "option": "Median"},
        blocking=True,
    )
    await hass.async_block_till_done()

    sel = hass.states.get("select.power_consumption_analyser_effect_strategy")
    assert sel is not None and sel.state == "Median"
    # Options should now contain effect_strategy
    saved = hass.config_entries.async_entries(DOMAIN)[0].options.get("effect_strategy")
    assert saved == "median"
