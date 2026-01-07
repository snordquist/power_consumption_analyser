import pytest
from homeassistant.core import HomeAssistant
from homeassistant import config_entries

from custom_components.power_consumption_analyser import DOMAIN

@pytest.mark.asyncio
async def test_config_flow_user_form(hass: HomeAssistant, sample_yaml, temp_config_dir, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == "form"

    user_input = {
        "unterverteilung_path": str(sample_yaml),
        "safe_circuits": "1F7, 2F3",
        "untracked_number": "number.stromberbrauch_nicht_erfasst",
        "home_consumption": "sensor.home_consumption_now_w",
        "grid_power": "sensor.grid_power",
        "tracked_power_sum": "sensor.tracked_power_sum",
    }
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    assert result2["type"] == "create_entry"
    data = result2["data"]
    assert data["unterverteilung_path"] == str(sample_yaml)
    assert data["safe_circuits"] == ["1F7", "2F3"]
    assert data["baseline_sensors"]["home_consumption"] == "sensor.home_consumption_now_w"
