import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_measure_switch_flow(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="test9012",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Set baseline states
    hass.states.async_set("sensor.home_consumption_now_w", 500)
    hass.states.async_set("sensor.kitchen_plug_power", 100)
    await hass.async_block_till_done()

    # Find the switch for a known circuit id from sample_yaml
    # Assume sample_yaml contains a circuit with id 'KITCHEN' for this test emulation
    # If not, we take any available circuit id
    data = hass.data[DOMAIN]
    circuit_id = next(iter(data.circuits.keys()))

    switch_entity_id = f"switch.measure_circuit_{circuit_id.lower()}"

    # Turn on the switch → starts measurement window
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_entity_id}, blocking=True)

    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state.startswith("measuring:")

    # During measurement: change untracked by changing meter/home values
    hass.states.async_set("sensor.kitchen_plug_power", 150)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.kitchen_plug_power", 50)
    await hass.async_block_till_done()

    # Stop early
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_entity_id}, blocking=True)

    # Effect sensor should be updated
    effect_entity_id = f"sensor.power_consumption_analyser_circuit_{circuit_id.lower()}_effect"
    effect_state = hass.states.get(effect_entity_id)
    assert effect_state is not None
    # The effect sign will depend on sample order; ensure it returns a float
    float(effect_state.state)

    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state == "idle"
