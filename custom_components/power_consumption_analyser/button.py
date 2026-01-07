from __future__ import annotations

from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .model import PCAData

async def async_setup_entry(hass, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities: List[ButtonEntity] = []
    # Global device-level buttons
    entities.append(StopWorkflowButton(data))
    entities.append(ResetValuesButton(data))
    # Per-circuit buttons
    for cid in data.circuits.keys():
        entities.append(StartMeasureButton(data, cid))
    async_add_entities(entities)

class _BaseDeviceButton(ButtonEntity):
    _attr_has_entity_name = False
    def __init__(self, data: PCAData):
        self.data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Power Consumption Analyser",
            manufacturer="Custom",
        )

class StopWorkflowButton(_BaseDeviceButton):
    def __init__(self, data: PCAData):
        super().__init__(data)
        self._attr_name = "Stop Workflow"
        self._attr_unique_id = f"{DOMAIN}_stop_workflow"
        self._attr_icon = "mdi:stop"
    @property
    def suggested_object_id(self) -> str:
        return "stop_workflow"
    async def async_press(self) -> None:
        await self.hass.services.async_call(DOMAIN, "workflow_stop", {}, blocking=False)

class ResetValuesButton(_BaseDeviceButton):
    def __init__(self, data: PCAData):
        super().__init__(data)
        self._attr_name = "Reset Values"
        self._attr_unique_id = f"{DOMAIN}_reset_values"
        self._attr_icon = "mdi:backup-restore"
    @property
    def suggested_object_id(self) -> str:
        return "reset_values"
    async def async_press(self) -> None:
        # Clear measurement results and history and notify sensors to refresh
        try:
            self.data.measure_results.clear()
            self.data.measure_history.clear()
            self.hass.bus.async_fire(f"{DOMAIN}.measure_finished", {"circuit_id": "reset"})
        except Exception:
            pass

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
