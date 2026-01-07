from __future__ import annotations
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from homeassistant.core import HomeAssistant

from ..const import DOMAIN

@dataclass
class Circuit:
    id: str
    phase: str = ""
    breaker: str = ""
    rating: str = ""
    description: str = ""
    energy_meters: List[str] = field(default_factory=list)

class PCAData:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.circuits: Dict[str, Circuit] = {}
        self.safe_circuits: List[str] = []
        self.session_id: Optional[str] = None
        self.current_circuit: Optional[str] = None
        self.step_active: bool = False
        self.untracked_number: Optional[str] = None
        self.baseline_sensors: Dict[str, str] = {}
        # energy meter mappings
        self.energy_meters_by_circuit: Dict[str, List[str]] = {}
        self.meter_to_circuit: Dict[str, str] = {}
        # label-based meters and label tracking
        self.label_meters: Set[str] = set()
        self.energy_label_id: Optional[str] = None
        self.devices_with_label: Set[str] = set()
        # Measurement workflow state
        self.measure_samples: Dict[str, List[float]] = {}
        self.measure_baseline: Dict[str, float] = {}
        self.measure_listeners: Dict[str, Optional[callable]] = {}
        self.measure_timers: Dict[str, Optional[callable]] = {}
        self.measure_results: Dict[str, float] = {}
        self.measure_duration_s: int = 30
        self.measuring_circuit: Optional[str] = None
        # History of measurements per circuit
        self.measure_history: Dict[str, List[dict]] = {}
        self.measure_history_max: int = 50
        # Guided workflow state
        self.workflow_active: bool = False
        self.workflow_queue: List[str] = []
        self.workflow_index: int = 0
        self.workflow_wait_s: int = 0
        self.workflow_notify_service: Optional[str] = None
        self._workflow_saved_duration: Optional[int] = None
        self.workflow_skip_circuits: Set[str] = set()
        self.workflow_notification_id: str = f"{DOMAIN}_workflow"
        self.workflow_ignore_result_for: Optional[str] = None
        # Guard to block starts while stopping workflow
        self.block_measure_starts: bool = False
        self.stopping_workflow: bool = False
        # Origin of current measurement: 'workflow' or 'manual'
        self.measurement_origin: Optional[str] = None
        # Timestamp when the current workflow step started (UTC)
        self.workflow_step_started_at: Optional[object] = None
        # RCD layout/grouping parsed from unterverteilung.yaml
        self.rcd_groups: List[Dict[str, object]] = []
        self.rcd_to_circuits: Dict[str, List[str]] = {}

    def is_safe(self, cid: str) -> bool:
        return cid in self.safe_circuits
