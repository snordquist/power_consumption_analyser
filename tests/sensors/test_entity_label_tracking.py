import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_entity_label_tracking_add_remove(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    # Set up integration
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="test_label_entity",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]

    # Seed baseline
    hass.states.async_set("sensor.home_consumption_now_w", 500)
    await hass.async_block_till_done()

    # Prepare entity registry and monkeypatch async_get to simulate labeled entity
    ent_reg = er.async_get(hass)
    original_async_get = ent_reg.async_get

    class _FakeEnt:
        def __init__(self, entity_id: str, labels):
            self.entity_id = entity_id
            self.domain = "sensor"
            self.labels = labels

    # Ensure energy_label_id exists (simulate label registry lookup)
    data.energy_label_id = data.energy_label_id or "lbl_energy"

    try:
        ent_reg.async_get = lambda eid: _FakeEnt(eid, {data.energy_label_id}) if eid == "sensor.labeled_meter_power" else original_async_get(eid)

        # Fire entity_registry_updated to simulate label added on the entity
        hass.bus.async_fire("entity_registry_updated", {"action": "create", "entity_id": "sensor.labeled_meter_power"})
        await hass.async_block_till_done()

        # The label meters should include the entity now
        assert "sensor.labeled_meter_power" in data.label_meters

        # Meter count sensors should reflect it
        meter_count = hass.states.get("sensor.power_consumption_analyser_meter_count")
        label_count = hass.states.get("sensor.power_consumption_analyser_label_meter_count")
        assert meter_count is not None and int(meter_count.state) >= 1
        assert label_count is not None and int(label_count.state) >= 1

        # Now simulate label removal
        ent_reg.async_get = lambda eid: _FakeEnt(eid, set()) if eid == "sensor.labeled_meter_power" else original_async_get(eid)
        hass.bus.async_fire("entity_registry_updated", {"action": "update", "entity_id": "sensor.labeled_meter_power"})
        await hass.async_block_till_done()

        assert "sensor.labeled_meter_power" not in data.label_meters
        meter_count = hass.states.get("sensor.power_consumption_analyser_meter_count")
        label_count = hass.states.get("sensor.power_consumption_analyser_label_meter_count")
        assert meter_count is not None and int(meter_count.state) >= 0
        assert label_count is not None and int(label_count.state) >= 0
    finally:
        # Restore
        ent_reg.async_get = original_async_get

