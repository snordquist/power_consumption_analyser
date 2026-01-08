from __future__ import annotations
from typing import List
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, OPT_EFFECT_STRATEGY
from .model import PCAData

OPTIONS = [
    ("average", "Average"),
    ("median", "Median"),
    ("trimmed_mean", "Trimmed Mean"),
]

class EffectStrategySelect(SelectEntity):
    _attr_has_entity_name = False
    _attr_name = "Effect Strategy"
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_effect_strategy"
        self._options = [name for _, name in OPTIONS]
        self._keys = [key for key, _ in OPTIONS]
        # default to average
        self._current_key = getattr(data, "effect_strategy", self._keys[0])
        # Attach to the same device as other PCA entities
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def suggested_object_id(self) -> str:
        # Ensure entity_id is select.power_consumption_analyser_effect_strategy
        return f"{DOMAIN}_effect_strategy"

    @property
    def options(self) -> List[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        try:
            idx = self._keys.index(self._current_key)
            return self._options[idx]
        except ValueError:
            return self._options[0]

    async def async_select_option(self, option: str) -> None:
        if option not in self._options:
            return
        idx = self._options.index(option)
        self._current_key = self._keys[idx]
        self._data.effect_strategy = self._current_key
        # Persist to options
        entry = getattr(self.hass.data.get(DOMAIN), "config_entry", None)
        if entry:
            opts = dict(entry.options)
            opts[OPT_EFFECT_STRATEGY] = self._current_key
            self.hass.config_entries.async_update_entry(entry, options=opts)
        self.async_write_ha_state()

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    setattr(hass.data[DOMAIN], "config_entry", entry)
    async_add_entities([EffectStrategySelect(data)], True)
