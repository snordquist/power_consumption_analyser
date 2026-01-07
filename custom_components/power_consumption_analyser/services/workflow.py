from __future__ import annotations
from typing import Optional, List, Dict
from homeassistant.components import persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..model import PCAData

async def notify(hass: HomeAssistant, data: PCAData, message: str, title: str = "PCA", actions: Optional[List[Dict[str, str]]] = None) -> None:
    # Always create a persistent notification as a fallback
    try:
        persistent_notification.async_create(hass, message, title=title, notification_id=data.workflow_notification_id)
    except Exception:
        pass
    # If a notify service is configured, also send a mobile notification with actions
    if data.workflow_notify_service:
        payload = {"message": message, "title": title}
        # Add actions and tag for actionable notifications on mobile apps
        ndata: Dict[str, object] = {"tag": data.workflow_notification_id}
        if actions:
            ndata["actions"] = actions
        payload["data"] = ndata
        try:
            await hass.services.async_call("notify", data.workflow_notify_service, payload, blocking=False)
        except Exception:
            pass

async def simple_notify(hass: HomeAssistant, data: PCAData, message: str) -> None:
    await notify(hass, data, message, title="PCA Workflow")

async def workflow_finish(hass: HomeAssistant, data: PCAData, reason: Optional[str] = None) -> None:
    if data._workflow_saved_duration is not None:
        data.measure_duration_s = data._workflow_saved_duration
        data._workflow_saved_duration = None
    if not data.workflow_active:
        # Still inform user that we are done/cancelled
        await notify(hass, data, "Workflow abgeschlossen." if not reason else f"Workflow {reason}.", title="PCA Workflow Ende",
                     actions=[{"action": "PCA_RESTART", "title": "Neu starten"}])
        return
    if reason:
        await notify(hass, data, f"Workflow {reason}.", title="PCA Workflow Ende",
                     actions=[{"action": "PCA_RESTART", "title": "Neu starten"}])
    else:
        await notify(hass, data, "Workflow abgeschlossen.", title="PCA Workflow Ende",
                     actions=[{"action": "PCA_RESTART", "title": "Neu starten"}])
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
    # Actions presented to the user in the mobile notification
    actions = [
        {"action": "PCA_SKIP", "title": "Überspringen"},
        {"action": "PCA_FINISH", "title": "Jetzt abschließen"},
        {"action": "PCA_STOP", "title": "Stopp"},
        {"action": "PCA_RESTART", "title": "Neu starten"},
    ]
    await notify(hass, data, msg, title="PCA Schritt gestartet", actions=actions)
    # Start measurement via switch
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
