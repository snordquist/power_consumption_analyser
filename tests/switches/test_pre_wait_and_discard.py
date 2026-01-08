import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN


@pytest.mark.asyncio
async def test_pre_wait_blocks_samples_until_deadline(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="prewait1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Set a large pre-wait so no samples will be recorded before we finalize
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_pre_wait_s", "value": 30},
        blocking=True,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    hass.states.async_set("sensor.kitchen_plug_power", 100)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cid = next(iter(data.circuits.keys()))
    switch_entity_id = f"switch.measure_circuit_{cid.lower()}"

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Generate some changes; due to pre-wait, none should be collected
    for v in [150, 120, 90, 110]:
        hass.states.async_set("sensor.kitchen_plug_power", v)
        await hass.async_block_till_done()

    # Finalize now
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_entity_id}, blocking=True)
    await hass.async_block_till_done()

    samples = data.measure_samples.get(cid, [])
    assert samples == []


@pytest.mark.asyncio
async def discard_first_n_ignores_initial_samples_after_pre_wait(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="discardn1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No pre-wait; discard first 2 samples
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_pre_wait_s", "value": 0},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_discard_first_n", "value": 2},
        blocking=True,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 400)
    hass.states.async_set("sensor.kitchen_plug_power", 50)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cid = next(iter(data.circuits.keys()))
    switch_entity_id = f"switch.measure_circuit_{cid.lower()}"

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_entity_id}, blocking=True)
    await hass.async_block_till_done()

    values = [60, 55, 45, 40]
    for v in values:
        hass.states.async_set("sensor.kitchen_plug_power", v)
        await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_entity_id}, blocking=True)
    await hass.async_block_till_done()

    samples = data.measure_samples.get(cid, [])
    # Expect len == len(values) - discard_first_n (>=0)
    assert len(samples) == max(0, len(values) - 2)

    # Effect sensor should exist
    eff = hass.states.get(f"sensor.power_consumption_analyser_circuit_{cid.lower()}_effect")
    assert eff is not None

