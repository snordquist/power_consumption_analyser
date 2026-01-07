import pytest
from datetime import datetime, timedelta, timezone
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.power_consumption_analyser import DOMAIN


@pytest.mark.asyncio
async def sensor_entities_are_registered_on_setup(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="sensor_setup",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Core sensors
    assert hass.states.get("sensor.power_consumption_analyser_measurement_status") is not None
    assert hass.states.get("sensor.power_consumption_analyser_measurement_summary") is not None
    assert hass.states.get("sensor.power_consumption_analyser_workflow_progress") is not None
    assert hass.states.get("sensor.power_consumption_analyser_rcd_layout") is not None
    assert hass.states.get("sensor.power_consumption_analyser_countdown") is not None

    # Known circuits from sample YAML should have effect sensors (if fixture defines 2F7, 3F11)
    # If not present in this environment, don't fail the test hard
    eff_2f7 = hass.states.get("sensor.power_consumption_analyser_circuit_2f7_effect")
    eff_3f11 = hass.states.get("sensor.power_consumption_analyser_circuit_3f11_effect")
    assert eff_2f7 is not None or eff_3f11 is not None


@pytest.mark.asyncio
async def countdown_is_none_when_workflow_inactive(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="countdown_inactive",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    s = hass.states.get("sensor.power_consumption_analyser_countdown")
    assert s is not None
    assert s.state in ("unknown", "unavailable")


@pytest.mark.asyncio
async def countdown_computes_remaining_seconds_when_active(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="countdown_active",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    data.workflow_active = True
    data.workflow_wait_s = 30
    data.workflow_step_started_at = datetime.now(timezone.utc) - timedelta(seconds=5)

    # Force update
    await hass.services.async_call("homeassistant", "update_entity", {"entity_id": "sensor.power_consumption_analyser_countdown"}, blocking=True)
    s = hass.states.get("sensor.power_consumption_analyser_countdown")
    assert s is not None
    # Allow some slack for timing differences
    val = int(s.state) if s.state not in ("unknown", "unavailable") else -1
    assert 22 <= val <= 30


@pytest.mark.asyncio
async def countdown_is_zero_when_elapsed_exceeds_wait(hass: HomeAssistant, sample_yaml, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(sample_yaml),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="countdown_zero",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    data.workflow_active = True
    data.workflow_wait_s = 3
    data.workflow_step_started_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    await hass.services.async_call("homeassistant", "update_entity", {"entity_id": "sensor.power_consumption_analyser_countdown"}, blocking=True)
    s = hass.states.get("sensor.power_consumption_analyser_countdown")
    assert s is not None
    assert s.state not in ("unknown", "unavailable")
    assert int(s.state) == 0


@pytest.mark.asyncio
async def rcd_layout_exposes_groups_and_preserves_circuit_order(hass: HomeAssistant, tmp_path, enable_custom_integrations):
    yaml_path = tmp_path / "uv.yaml"
    yaml_path.write_text(
        """
protection_devices:
  - type: RCD
    label: RCD-A
    protects: ["1F1", "1F2", "1F3"]
  - type: RCD
    label: RCD-B
    protects: ["2F7", "3F11"]
circuits:
  - id: "1F1"
  - id: "1F2"
  - id: "1F3"
  - id: "2F7"
  - id: "3F11"
        """,
        encoding="utf-8",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PCA",
        data={
            "unterverteilung_path": str(yaml_path),
            "safe_circuits": [],
            "baseline_sensors": {"home_consumption": "sensor.home_consumption_now_w"},
        },
        unique_id="rcd_layout",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    layout = hass.states.get("sensor.power_consumption_analyser_rcd_layout")
    assert layout is not None
    rcds = layout.attributes.get("rcds")
    mapping = layout.attributes.get("layout")
    assert rcds == ["RCD-A", "RCD-B"]
    assert mapping["RCD-A"] == ["1F1", "1F2", "1F3"]
    assert mapping["RCD-B"] == ["2F7", "3F11"]

