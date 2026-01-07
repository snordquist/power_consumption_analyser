import pytest
from homeassistant.core import HomeAssistant

from custom_components.power_consumption_analyser.model.data import PCAData, Circuit

@pytest.mark.asyncio
async def initializes_with_empty_collections(hass: HomeAssistant):
    data = PCAData(hass)
    assert data.circuits == {}
    assert data.safe_circuits == []
    assert data.energy_meters_by_circuit == {}
    assert data.meter_to_circuit == {}
    assert data.label_meters == set()
    assert data.devices_with_label == set()
    assert data.measure_samples == {}
    assert data.measure_baseline == {}
    assert data.measure_listeners == {}
    assert data.measure_timers == {}
    assert data.measure_results == {}
    assert data.measure_history == {}
    assert data.workflow_queue == []
    assert data.workflow_index == 0
    assert data.workflow_wait_s == 0
    assert data.workflow_skip_circuits == set()
    assert data.rcd_groups == []
    assert data.rcd_to_circuits == {}

@pytest.mark.asyncio
async def is_safe_returns_true_for_configured_safe_circuit(hass: HomeAssistant):
    data = PCAData(hass)
    data.safe_circuits = ["1F1", "2F7"]
    assert data.is_safe("1F1") is True
    assert data.is_safe("2F7") is True

@pytest.mark.asyncio
async def is_safe_returns_false_for_other_circuit(hass: HomeAssistant):
    data = PCAData(hass)
    data.safe_circuits = ["1F1"]
    assert data.is_safe("1F2") is False
    assert data.is_safe("") is False

@pytest.mark.asyncio
async def can_register_circuits_and_meters(hass: HomeAssistant):
    data = PCAData(hass)
    # Add circuits
    data.circuits["1F1"] = Circuit(id="1F1", energy_meters=["sensor.m1"])
    data.circuits["1F2"] = Circuit(id="1F2", energy_meters=["sensor.m2", "sensor.m3"])
    # Build mappings as integration would
    data.energy_meters_by_circuit["1F1"] = ["sensor.m1"]
    data.energy_meters_by_circuit["1F2"] = ["sensor.m2", "sensor.m3"]
    data.meter_to_circuit["sensor.m1"] = "1F1"
    data.meter_to_circuit["sensor.m2"] = "1F2"
    data.meter_to_circuit["sensor.m3"] = "1F2"

    assert set(data.circuits.keys()) == {"1F1", "1F2"}
    assert data.energy_meters_by_circuit["1F1"] == ["sensor.m1"]
    assert data.energy_meters_by_circuit["1F2"] == ["sensor.m2", "sensor.m3"]
    assert data.meter_to_circuit["sensor.m3"] == "1F2"

@pytest.mark.asyncio
async def rcd_grouping_containers_are_mutable_and_preserve_order(hass: HomeAssistant):
    data = PCAData(hass)
    # Simulate parser adding RCD groups and circuits
    data.rcd_groups.append({"label": "RCD-A", "id": "rcd_a", "type": "RCD", "protects": ["1F1", "1F2", "1F3"]})
    data.rcd_groups.append({"label": "RCD-B", "id": "rcd_b", "type": "RCD", "protects": ["2F7", "3F11"]})
    data.rcd_to_circuits.setdefault("RCD-A", []).extend(["1F1", "1F2", "1F3"])
    data.rcd_to_circuits.setdefault("RCD-B", []).extend(["2F7", "3F11"])

    assert [g["label"] for g in data.rcd_groups] == ["RCD-A", "RCD-B"]
    assert data.rcd_to_circuits["RCD-A"] == ["1F1", "1F2", "1F3"]
    assert data.rcd_to_circuits["RCD-B"] == ["2F7", "3F11"]

@pytest.mark.asyncio
async def workflow_fields_change_as_expected(hass: HomeAssistant):
    data = PCAData(hass)
    data.workflow_active = True
    data.workflow_queue = ["1F1", "1F2"]
    data.workflow_index = 0
    data.workflow_wait_s = 30
    assert data.workflow_active is True
    assert data.workflow_queue == ["1F1", "1F2"]
    assert data.workflow_index == 0
    assert data.workflow_wait_s == 30
    # advance
    data.workflow_index += 1
    assert data.workflow_index == 1
    # stop
    data.workflow_active = False
    data.workflow_queue = []
    assert data.workflow_active is False
    assert data.workflow_queue == []

