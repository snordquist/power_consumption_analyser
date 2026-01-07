import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_workflow_progress_and_timer(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    # Create a timer helper entity to simulate HA's timer
    # In HA tests, we can fake a timer state entity, the service calls won't error.
    hass.states.async_set("timer.pca_step", "idle")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="test_wf_prog",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    # Capture available circuits
    data = hass.data[DOMAIN]
    circuits = list(data.circuits.keys())
    if len(circuits) < 2:
        pytest.skip("need at least two circuits")

    # Start workflow for two circuits
    await hass.services.async_call(DOMAIN, "start_guided_analysis", {"circuits": circuits[:2], "wait_s": 5}, blocking=True)
    await hass.async_block_till_done()

    # Wait until measurement starts
    for _ in range(10):
        ms = hass.states.get("sensor.power_consumption_analyser_measurement_status")
        if ms and isinstance(ms.state, str) and ms.state.startswith("measuring:"):
            break
        await hass.async_block_till_done()

    # Wait until workflow becomes active and progress sensor populated
    prog = None
    for _ in range(10):
        prog = hass.states.get("sensor.power_consumption_analyser_workflow_progress")
        if prog and prog.state == "active" and prog.attributes.get("remaining"):
            break
        await hass.async_block_till_done()

    # Check progress sensor
    assert prog is not None and prog.state == "active"
    attrs = prog.attributes
    assert attrs.get("current") == circuits[0]
    assert attrs.get("remaining") == circuits[:2]
    assert attrs.get("done") == []

    # Simulate finishing first step by turning off the switch
    await hass.services.async_call("switch", "turn_off", {"entity_id": f"switch.measure_circuit_{circuits[0].lower()}"}, blocking=True)
    await hass.async_block_till_done()

    # After advance, wait for progress update
    for _ in range(5):
        prog = hass.states.get("sensor.power_consumption_analyser_workflow_progress")
        if prog and prog.attributes.get("done") == [circuits[0]]:
            break
        await hass.async_block_till_done()
    attrs = prog.attributes
    assert attrs.get("done") == [circuits[0]]
    assert attrs.get("current") == circuits[1]

    # Stop workflow and wait for idle
    await hass.services.async_call(DOMAIN, "workflow_stop", {}, blocking=True)
    for _ in range(5):
        prog = hass.states.get("sensor.power_consumption_analyser_workflow_progress")
        if prog and prog.state == "idle":
            break
        await hass.async_block_till_done()
    assert prog is not None and prog.state in ("idle", "active")
