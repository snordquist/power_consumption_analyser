from __future__ import annotations
from typing import Optional
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..model import PCAData

async def state_float(hass: HomeAssistant, entity_id: Optional[str]) -> float:
    if not entity_id:
        return 0.0
    state = hass.states.get(entity_id)
    try:
        return float(state.state) if state else 0.0
    except Exception:
        return 0.0

async def calc_tracked_power(hass: HomeAssistant, data: PCAData) -> float:
    total = 0.0
    for eid in list(data.meter_to_circuit.keys()):
        st = hass.states.get(eid)
        try:
            v = float(st.state) if st and st.state not in ("unknown", "unavailable") else 0.0
        except Exception:
            v = 0.0
        total += v
    return round(total, 2)

