import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_guided_workflow_services(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="testwf1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    cids = list(data.circuits.keys())
    if len(cids) < 2:
        pytest.skip("need at least two circuits for workflow test")

    await hass.services.async_call(DOMAIN, "start_guided_analysis", {"circuits": cids[:2], "wait_s": 5}, blocking=True)
    await hass.async_block_till_done()

    for _ in range(5):
        status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
        if status is not None and status.state.startswith("measuring:"):
            break
        await hass.async_block_till_done()
    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state.startswith("measuring:")

    await hass.services.async_call(DOMAIN, "workflow_skip_current", {}, blocking=True)
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "workflow_stop", {}, blocking=True)
    for cid in cids[:2]:
        await hass.services.async_call("switch", "turn_off", {"entity_id": f"switch.measure_circuit_{cid.lower()}"}, blocking=True)
    await hass.async_block_till_done()

    for _ in range(5):
        status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
        if status is not None and status.state == "idle":
            break
        await hass.async_block_till_done()
    status = hass.states.get("sensor.power_consumption_analyser_measurement_status")
    assert status is not None and status.state == "idle"

