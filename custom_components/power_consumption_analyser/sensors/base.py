from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN
from ..model import PCAData

class BasePCASensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, data: PCAData):
        self.data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

