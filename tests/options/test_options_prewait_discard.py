import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN


@pytest.mark.asyncio
async def test_options_flow_persists_pre_wait_and_discard(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="opts_prewait_discard",
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Change via numbers (device side) and assert data updated
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_pre_wait_s", "value": 5},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_discard_first_n", "value": 4},
        blocking=True,
    )
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    assert data.pre_wait_s == 5
    assert data.discard_first_n == 4

