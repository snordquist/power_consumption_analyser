from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from . import DOMAIN, CONF_UNTERVERTEILUNG_PATH, CONF_SAFE_CIRCUITS, CONF_UNTRACKED_NUMBER, CONF_BASELINE_SENSORS

class PCAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Power Consumption Analyser", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_UNTERVERTEILUNG_PATH): str,
            vol.Optional(CONF_SAFE_CIRCUITS, default=[]): [str],
            vol.Optional(CONF_UNTRACKED_NUMBER, default="number.stromberbrauch_nicht_erfasst"): str,
            vol.Optional(
                CONF_BASELINE_SENSORS,
                default={
                    "home_consumption": "sensor.home_consumption_now_w",
                    "grid_power": "sensor.grid_power",
                    "tracked_power_sum": "sensor.tracked_power_sum",
                },
            ): dict,
        })
        return self.async_show_form(step_id="user", data_schema=schema)
