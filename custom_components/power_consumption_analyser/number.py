from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.components.number import NumberEntity
from .const import DOMAIN, OPT_MEASURE_DURATION_S
from .model import PCAData

NAME = "Measure Duration"
UNIT = "s"
MIN_S = 5
MAX_S = 3600
STEP = 1

class MeasureDurationNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = NAME
    _attr_native_unit_of_measurement = UNIT
    _attr_icon = "mdi:timer-cog"
    _attr_native_min_value = MIN_S
    _attr_native_max_value = MAX_S
    _attr_native_step = STEP

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_measure_duration_s"

    @property
    def native_value(self) -> float:
        return float(self._data.measure_duration_s)

    async def async_set_native_value(self, value: float) -> None:
        new_val = int(value)
        new_val = max(MIN_S, min(MAX_S, new_val))
        # If workflow is running, apply at next step; otherwise apply immediately
        if self._data.workflow_active:
            self._data._workflow_saved_duration = new_val
        else:
            self._data.measure_duration_s = new_val
        # Persist to options if we have an entry
        entry = getattr(self.hass.data.get(DOMAIN), "config_entry", None)
        if entry:
            opts = dict(entry.options)
            opts[OPT_MEASURE_DURATION_S] = new_val
            self.hass.config_entries.async_update_entry(entry, options=opts)
        self.async_write_ha_state()

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    # Stash entry to allow persisting options from entity
    setattr(hass.data[DOMAIN], "config_entry", entry)
    async_add_entities([MeasureDurationNumber(data)], True)
