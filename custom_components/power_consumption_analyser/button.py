from __future__ import annotations

from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN, PCAData

async def async_setup_entry(hass, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities: List[ButtonEntity] = []
    for cid in data.circuits.keys():
        entities.append(StartMeasureButton(data, cid))
    async_add_entities(entities)

class StartMeasureButton(ButtonEntity):
    _attr_has_entity_name = False

    def __init__(self, data: PCAData, circuit_id: str):
        self.data = data
        self._circuit_id = circuit_id
        self._attr_name = f"Start Measure {circuit_id}"
        self._attr_unique_id = f"{DOMAIN}_start_measure_{circuit_id.lower()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

    @property
    def suggested_object_id(self) -> str:
        return f"start_measure_{self._circuit_id.lower()}"

    async def async_press(self) -> None:
        # Pressing the button turns on the corresponding measurement switch
        entity_id = f"switch.measure_circuit_{self._circuit_id.lower()}"
        await self.hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
