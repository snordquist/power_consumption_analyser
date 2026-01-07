from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from . import DOMAIN, CONF_UNTERVERTEILUNG_PATH, CONF_SAFE_CIRCUITS, CONF_UNTRACKED_NUMBER, CONF_BASELINE_SENSORS

HOME_CONS_KEY = "home_consumption"
GRID_POWER_KEY = "grid_power"
TRACKED_SUM_KEY = "tracked_power_sum"

class PCAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Normalize safe circuits from comma-separated string to list
            safe_str = user_input.get(CONF_SAFE_CIRCUITS, "") or ""
            if isinstance(safe_str, str):
                safe_list = [s.strip() for s in safe_str.split(",") if s.strip()]
                user_input[CONF_SAFE_CIRCUITS] = safe_list
            # Pack baseline sensors into dict
            baseline = {
                HOME_CONS_KEY: user_input.get(HOME_CONS_KEY, "sensor.home_consumption_now_w"),
                GRID_POWER_KEY: user_input.get(GRID_POWER_KEY, "sensor.grid_power"),
                TRACKED_SUM_KEY: user_input.get(TRACKED_SUM_KEY, "sensor.tracked_power_sum"),
            }
            user_input[CONF_BASELINE_SENSORS] = baseline
            # Remove standalone fields to keep data tidy
            for k in (HOME_CONS_KEY, GRID_POWER_KEY, TRACKED_SUM_KEY):
                user_input.pop(k, None)
            return self.async_create_entry(title="Power Consumption Analyser", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_UNTERVERTEILUNG_PATH): str,
            vol.Optional(CONF_SAFE_CIRCUITS, default=""): str,  # comma-separated IDs
            vol.Optional(CONF_UNTRACKED_NUMBER, default="number.stromberbrauch_nicht_erfasst"): str,
            vol.Optional(HOME_CONS_KEY, default="sensor.home_consumption_now_w"): str,
            vol.Optional(GRID_POWER_KEY, default="sensor.grid_power"): str,
            vol.Optional(TRACKED_SUM_KEY, default="sensor.tracked_power_sum"): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema)
