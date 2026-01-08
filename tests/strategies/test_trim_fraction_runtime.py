import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_trim_fraction_affects_trimmed_mean_runtime(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="trim_runtime",
        options={"effect_strategy": "trimmed_mean"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Setup states: baseline 200, noisy off samples
    hass.states.async_set("sensor.home_consumption_now_w", 200)
    # one labeled meter to keep tracked at 0 for untracked
    hass.states.async_set("sensor.kitchen_plug_power", 0)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cid = next(iter(data.circuits.keys()))
    eid = f"switch.measure_circuit_{cid.lower()}"

    # First with trim=0% (set number)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_trim_fraction", "value": 0},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_on", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()

    # generate changes
    for v in [1000, 110, 100, 120, 90, 105, 115, 2000]:
        hass.states.async_set("sensor.kitchen_plug_power", v)
        await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_off", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()

    s0 = hass.states.get(f"sensor.power_consumption_analyser_circuit_{cid.lower()}_effect")
    assert s0 is not None
    e0 = float(s0.state)

    # Now with trim=40%
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.power_consumption_analyser_trim_fraction", "value": 40},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_on", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()

    for v in [1000, 110, 100, 120, 90, 105, 115, 2000]:
        hass.states.async_set("sensor.kitchen_plug_power", v)
        await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_off", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()

    s1 = hass.states.get(f"sensor.power_consumption_analyser_circuit_{cid.lower()}_effect")
    assert s1 is not None
    e1 = float(s1.state)

    # With higher trim, low outliers are reduced, raising avg_off, hence effect (baseline - avg_off) should be smaller
    assert e1 < e0
