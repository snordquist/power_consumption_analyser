from __future__ import annotations
from typing import Optional
from homeassistant.components import persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..model import PCAData

async def notify(hass: HomeAssistant, data: PCAData, message: str, title: str = "PCA") -> None:
    try:
        persistent_notification.async_create(hass, message, title=title, notification_id=data.workflow_notification_id)
    except Exception:
        pass
    if data.workflow_notify_service:
        try:
            await hass.services.async_call("notify", data.workflow_notify_service, {"message": message, "title": title}, blocking=False)
        except Exception:
            pass

async def simple_notify(hass: HomeAssistant, data: PCAData, message: str) -> None:
    await notify(hass, data, message, title="PCA Workflow")

async def workflow_finish(hass: HomeAssistant, data: PCAData, reason: Optional[str] = None) -> None:
    if data._workflow_saved_duration is not None:
        data.measure_duration_s = data._workflow_saved_duration
        data._workflow_saved_duration = None
    if not data.workflow_active:
        return
    if reason:
        await notify(hass, data, f"Workflow {reason}.", title="PCA Workflow Ende")
    else:
        await notify(hass, data, "Workflow abgeschlossen.", title="PCA Workflow Ende")
    data.workflow_active = False
    data.workflow_queue = []
    data.workflow_index = 0
    data.workflow_wait_s = 0
    data.workflow_notify_service = None
    data.workflow_skip_circuits = set()
    data.workflow_ignore_result_for = None

async def workflow_start_current_step(hass: HomeAssistant, data: PCAData) -> None:
    if not data.workflow_active or data.workflow_index >= len(data.workflow_queue):
        await workflow_finish(hass, data)
        return
    current = data.workflow_queue[data.workflow_index]
    nxt = data.workflow_queue[data.workflow_index + 1] if data.workflow_index + 1 < len(data.workflow_queue) else None
    msg = f"Schalte jetzt Stromkreis {current} AUS. Warte {data.workflow_wait_s} Sekunden."
    if nxt:
        msg += f" Danach folgt: {nxt}."
    await notify(hass, data, msg, title="PCA Schritt gestartet")
    data.measurement_origin = "workflow"
    switch_eid = f"switch.measure_circuit_{current.lower()}"
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_eid}, blocking=True)

async def workflow_advance(hass: HomeAssistant, data: PCAData) -> None:
    if not data.workflow_active:
        return
    data.workflow_index += 1
    if data.workflow_index >= len(data.workflow_queue):
        await workflow_finish(hass, data)
    else:
        await workflow_start_current_step(hass, data)

