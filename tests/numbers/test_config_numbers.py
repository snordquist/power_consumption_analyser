import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_numbers_exist_and_persist_options(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="numbers",
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Measure duration
    md = hass.states.get("number.power_consumption_analyser_measure_duration")
    assert md is not None
    await hass.services.async_call("number", "set_value", {"entity_id": md.entity_id, "value": 15}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].measure_duration_s == 15

    # Min effect threshold
    me = hass.states.get("number.power_consumption_analyser_min_effect_w")
    assert me is not None
    await hass.services.async_call("number", "set_value", {"entity_id": me.entity_id, "value": 12}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].min_effect_w == 12

    # Min samples
    ms = hass.states.get("number.power_consumption_analyser_min_samples")
    assert ms is not None
    await hass.services.async_call("number", "set_value", {"entity_id": ms.entity_id, "value": 7}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].min_samples == 7

    # Trim fraction
    tf = hass.states.get("number.power_consumption_analyser_trim_fraction")
    assert tf is not None
    await hass.services.async_call("number", "set_value", {"entity_id": tf.entity_id, "value": 30}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].trim_fraction == 30

