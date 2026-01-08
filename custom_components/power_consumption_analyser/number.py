from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from .const import DOMAIN, OPT_MEASURE_DURATION_S, OPT_MIN_EFFECT_W, OPT_MIN_SAMPLES
from .const import OPT_TRIM_FRACTION
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
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_measure_duration_s"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def native_value(self) -> float:
        return float(self._data.measure_duration_s)

    @property
    def suggested_object_id(self) -> str:
        return "measure_duration"

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

class MinEffectThresholdNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Min Effect Threshold"
    _attr_native_unit_of_measurement = "W"
    _attr_icon = "mdi:filter-variant"
    _attr_native_min_value = 0
    _attr_native_max_value = 200
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_min_effect_w"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def native_value(self) -> float:
        return float(getattr(self._data, "min_effect_w", 0) or 0)

    @property
    def suggested_object_id(self) -> str:
        return "min_effect_w"

    async def async_set_native_value(self, value: float) -> None:
        new_val = int(value)
        new_val = max(0, min(200, new_val))
        self._data.min_effect_w = new_val
        # Persist to options
        entry = getattr(self.hass.data.get(DOMAIN), "config_entry", None)
        if entry:
            opts = dict(entry.options)
            opts[OPT_MIN_EFFECT_W] = new_val
            self.hass.config_entries.async_update_entry(entry, options=opts)
        self.async_write_ha_state()

class MinSamplesNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Min Samples"
    _attr_icon = "mdi:counter"
    _attr_native_min_value = 0
    _attr_native_max_value = 600
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_min_samples"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def native_value(self) -> float:
        return float(getattr(self._data, "min_samples", 0) or 0)

    @property
    def suggested_object_id(self) -> str:
        return "min_samples"

    async def async_set_native_value(self, value: float) -> None:
        new_val = int(value)
        new_val = max(0, min(600, new_val))
        self._data.min_samples = new_val
        entry = getattr(self.hass.data.get(DOMAIN), "config_entry", None)
        if entry:
            opts = dict(entry.options)
            opts[OPT_MIN_SAMPLES] = new_val
            self.hass.config_entries.async_update_entry(entry, options=opts)
        self.async_write_ha_state()

class TrimFractionNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Trim Fraction"
    _attr_icon = "mdi:ray-start-end"
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 0
    _attr_native_max_value = 45
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: PCAData):
        self._data = data
        self._attr_unique_id = f"{DOMAIN}_trim_fraction"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def native_value(self) -> float:
        return float(getattr(self._data, "trim_fraction", 20))

    @property
    def suggested_object_id(self) -> str:
        return "trim_fraction"

    async def async_set_native_value(self, value: float) -> None:
        new_val = int(value)
        new_val = max(0, min(45, new_val))
        self._data.trim_fraction = new_val
        entry = getattr(self.hass.data.get(DOMAIN), "config_entry", None)
        if entry:
            opts = dict(entry.options)
            opts[OPT_TRIM_FRACTION] = new_val
            self.hass.config_entries.async_update_entry(entry, options=opts)
        self.async_write_ha_state()

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    # Stash entry to allow persisting options from entity
    setattr(hass.data[DOMAIN], "config_entry", entry)
    async_add_entities([MeasureDurationNumber(data), MinEffectThresholdNumber(data), MinSamplesNumber(data), TrimFractionNumber(data)], True)
