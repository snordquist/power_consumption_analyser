from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .model import PCAData
from .sensors.tracked_power_sum import TrackedPowerSumSensor
from .sensors.untracked_power import CalculatedUntrackedPowerSensor
from .sensors.tracked_coverage import TrackedCoverageSensor
from .sensors.tracked_untracked_ratio import TrackedToUntrackedRatioSensor
from .sensors.meter_count import MeterCountSensor
from .sensors.label_meter_count import LabelMeterCountSensor
from .sensors.mapped_meter_count import MappedMeterCountSensor
from .sensors.unavailable_meter_count import UnavailableMeterCountSensor
from .sensors.analysis_status import AnalysisStatusSensor
from .sensors.measurement_status import MeasurementStatusSensor
from .sensors.circuit_effect import CircuitEffectSensor
from .sensors.summary_effect import SummaryEffectSensor

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    data: PCAData = hass.data[DOMAIN]
    entities = [
        TrackedPowerSumSensor(data),
        CalculatedUntrackedPowerSensor(data),
        TrackedCoverageSensor(data),
        TrackedToUntrackedRatioSensor(data),
        MeterCountSensor(data),
        LabelMeterCountSensor(data),
        MappedMeterCountSensor(data),
        UnavailableMeterCountSensor(data),
        AnalysisStatusSensor(data),
    ]
    for cid in data.circuits.keys():
        entities.append(CircuitEffectSensor(data, cid))
    entities.append(MeasurementStatusSensor(data))
    entities.append(SummaryEffectSensor(data))
    async_add_entities(entities, True)
