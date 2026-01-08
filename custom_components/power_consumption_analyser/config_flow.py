from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from . import DOMAIN, CONF_UNTERVERTEILUNG_PATH, CONF_SAFE_CIRCUITS, CONF_UNTRACKED_NUMBER, CONF_BASELINE_SENSORS
from .const import (
    OPT_EFFECT_STRATEGY,
    OPT_MEASURE_DURATION_S,
    OPT_MIN_EFFECT_W,
    OPT_PRE_WAIT_S,
    OPT_DISCARD_FIRST_N,
)

HOME_CONS_KEY = "home_consumption"
GRID_POWER_KEY = "grid_power"
TRACKED_SUM_KEY = "tracked_power_sum"

# Available strategies
_STRATEGY_KEYS = ["average", "median", "trimmed_mean", "median_of_means"]

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


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Persist options
            options = dict(self._entry.options)
            options[OPT_MEASURE_DURATION_S] = int(user_input.get(OPT_MEASURE_DURATION_S, 30))
            options["history_size"] = int(user_input.get("history_size", 50))
            options[OPT_MIN_EFFECT_W] = int(user_input.get(OPT_MIN_EFFECT_W, 20))
            options[OPT_PRE_WAIT_S] = int(user_input.get(OPT_PRE_WAIT_S, 3))
            options[OPT_DISCARD_FIRST_N] = int(user_input.get(OPT_DISCARD_FIRST_N, 2))
            strategy = user_input.get(OPT_EFFECT_STRATEGY, "average")
            if strategy not in _STRATEGY_KEYS:
                strategy = "average"
            options[OPT_EFFECT_STRATEGY] = strategy
            return self.async_create_entry(title="Options", data=options)

        current = self._entry.options.get(OPT_MEASURE_DURATION_S, 30)
        current_hx = self._entry.options.get("history_size", 50)
        current_me = self._entry.options.get(OPT_MIN_EFFECT_W, 20)
        current_strategy = self._entry.options.get(OPT_EFFECT_STRATEGY, "average")
        current_pw = self._entry.options.get(OPT_PRE_WAIT_S, 3)
        current_dn = self._entry.options.get(OPT_DISCARD_FIRST_N, 2)
        schema = vol.Schema({
            vol.Optional(OPT_MEASURE_DURATION_S, default=current): int,
            vol.Optional("history_size", default=current_hx): int,
            vol.Optional(OPT_MIN_EFFECT_W, default=current_me): int,
            vol.Optional(OPT_EFFECT_STRATEGY, default=current_strategy): vol.In(_STRATEGY_KEYS),
            vol.Optional(OPT_PRE_WAIT_S, default=current_pw): int,
            vol.Optional(OPT_DISCARD_FIRST_N, default=current_dn): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema)


async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
