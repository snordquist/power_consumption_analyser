# Power Consumption Analyser (Home Assistant custom integration)

Features:
- Reads `unterverteilung.yaml` to register circuits and RCD/RCBO groups.
- Tracks meters by label (EnergyMeter) and circuit mapping; computes Untracked Power = Home − Sum(meters).
- Guided manual analysis workflow (notifications + dashboard) to measure effect per circuit.
- Multiple robust effect strategies with quality/validity attributes.
- Device-level configuration entities and Options flow to tune behavior.

## Local development setup
To enable IDE resolution of Home Assistant and integration dependencies, create a virtual environment and install `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then point your IDE to use this interpreter (the `.venv`) for indexing and type hints. This installs Home Assistant and test tooling so imports resolve during development.

## Installing in Home Assistant
- Copy `custom_components/power_consumption_analyser` into your Home Assistant `config/custom_components` folder.
- Restart Home Assistant.
- Add integration via UI and set:
  - Path to `unterverteilung.yaml`.
  - Safe circuits list (IDs that must not be analyzed).
  - Untracked number entity (default `number.stromberbrauch_nicht_erfasst`).
  - Baseline sensors (grid power and tracked power sum).

Services (Developer Tools -> Services):
- `power_consumption_analyser.select_circuit` with `circuit_id`, `session_id` (optional)
- `power_consumption_analyser.confirm_off`
- `power_consumption_analyser.confirm_on`

Events:
- `power_consumption_analyser.step_selected`
- `power_consumption_analyser.circuit_off_confirmed` (with measured values)
- `power_consumption_analyser.circuit_on_confirmed`

## Install via HACS
HACS discovers custom integrations from GitHub repositories.

- Quick install link: https://hacs.xyz/docs/faq/custom_repositories/ (Add this repo as a Custom Repository under Integrations)
- Direct add link (copy/paste into HACS → Custom repositories):
  - Repository URL: https://github.com/snordquist/power_consumption_analyser
  - Category: Integration

Public repo requirements:
1. Integration folder: `custom_components/power_consumption_analyser/`
2. Include `hacs.json` at repo root.
3. Tag a release (e.g., `v0.1.0`).
4. In Home Assistant: HACS → Integrations → 3 dots → Custom repositories → Add your repo URL (Category: Integration) → Install → Restart.

Post-install:
- Restart Home Assistant.
- Add the integration via Settings → Devices & Services → Add Integration → Power Consumption Analyser.
- Complete the config flow.

## Sensors and metrics
- `sensor.power_consumption_analyser_untracked_power`
  - Current estimate of untracked power (W): Home − Tracked.
  - Tracked is the sum of all mapped EnergyMeter entities (by circuit mapping and label detection).
- `sensor.power_consumption_analyser_tracked_power_sum`
  - Sum of all mapped/labeled energy meters (W).
- `sensor.power_consumption_analyser_tracked_coverage`
  - Percentage of Home power covered by tracked meters: 100 · Tracked / Home (0 if Home is 0/unavailable).
- `sensor.power_consumption_analyser_tracked_untracked_ratio`
  - Ratio Tracked/Untracked (computed as float; undefined values show as 0 or unknown if inputs are unavailable).
- `sensor.power_consumption_analyser_meter_count`, `_label_meter_count`, `_mapped_meter_count`, `_unavailable_meter_count`
  - Counts for discovery/diagnostics of meters and mapping quality.
- `sensor.power_consumption_analyser_analysis_status`, `_measurement_status`
  - Textual status of the analysis/workflow, including step hints.
- `sensor.power_consumption_analyser_circuit_<ID>_effect`
  - Per-circuit measured effect on untracked power (W). Positive means turning OFF that circuit reduced untracked (candidate consumer on that circuit). Negative typically indicates opposing behavior or measurement noise (see Edge cases).
  - Attributes: valid (bool), clamped (bool), samples (int), mad (Median Absolute Deviation), sigma (≈ robust σ).
- `sensor.power_consumption_analyser_summary_effect`
  - Aggregation/summary across circuits for quick overview.
- `sensor.power_consumption_analyser_workflow_progress`
  - Attributes: queue, index, done, remaining, current.
- `sensor.power_consumption_analyser_countdown`
  - Remaining seconds for the current step; used by dashboard and notifications.
- `sensor.power_consumption_analyser_selected_strategy`
  - The effect strategy currently in use.
- `sensor.power_consumption_analyser_rcd_layout`
  - RCD group layout parsed from `unterverteilung.yaml` (rcds, layout, done/current from workflow).

## Effect strategies
Use Options flow or the device select to choose the default strategy.
- Average
  - Simple mean of OFF samples; best with low noise and no outliers.
- Median
  - Robust to outliers when sample count is small; uses the median of OFF samples.
- Trimmed Mean
  - Discards a fraction from both tails; configured by Trim Fraction (%). Good with heavy-tailed noise.
- Median of Means
  - Splits samples into equal bins, computes means, and takes the median of those means. Robust against bursts/outliers.

The computed effect is `baseline − avg_off`, where baseline is the initial untracked value at measurement start and avg_off is the strategy’s estimate of the OFF window. Small effects under Min Effect Threshold are clamped to 0 (clamped = true).

## Configuration entities (Device page)
- `number.power_consumption_analyser_measure_duration` (s)
  - Step duration for the guided analysis when not overridden by the workflow service.
- `number.power_consumption_analyser_min_effect_w` (W)
  - Clamp small effects to 0 under this threshold.
- `number.power_consumption_analyser_min_samples`
  - Minimum OFF samples required for a valid result; fewer samples set valid=false and reason.
- `number.power_consumption_analyser_trim_fraction` (%)
  - Used by Trimmed Mean; 0–45% of samples trimmed from both ends.
- `number.power_consumption_analyser_pre_wait_s` (s)
  - Pre-wait before collecting OFF samples to stabilize baseline (0–30s). Samples during this time are ignored.
- `number.power_consumption_analyser_discard_first_n`
  - Discard the first N OFF samples after pre-wait.
- `select.power_consumption_analyser_effect_strategy`
  - Choose Average, Median, Trimmed Mean, or Median of Means.

All of the above are also available in the Options flow (Settings → Devices & services → Power Consumption Analyser → Configure).

## Workflow and services
Services (Developer Tools → Services):
- `power_consumption_analyser.start_guided_analysis`
  - Data: `circuits` (optional list), `skip_circuits` (list), `wait_s` (int), `notify_service` (str)
  - Builds a queue from circuits or from all non-safe circuits; schedules steps with countdown and notifications.
- `power_consumption_analyser.workflow_finish_current`
  - Finish current step immediately (mapped to “Weiter” button on dashboard).
- `power_consumption_analyser.workflow_skip_current`
  - Ignore current result and move on.
- `power_consumption_analyser.workflow_stop` / `workflow_restart`
  - Stop or restart the workflow.
- `power_consumption_analyser.set_default_notify_service`
  - Persist default notify service to use for actionable notifications.
- `power_consumption_analyser.circuit_link_energy_meter` / `circuit_unlink_energy_meter`
  - Manage meter mapping to circuits.

Device buttons:
- Start Workflow, Stop Workflow, Reset Values, and per-circuit “Start Measure” buttons.

## Expected outcomes and their meaning
- Untracked Power gauge high (red):
  - Most of the home power is not covered by meters; add missing meters or confirm meter assignments.
- Circuit effect positive (+W):
  - When OFF, untracked decreased by this amount. The circuit likely contains untracked consumers.
- Circuit effect negative (−W):
  - When OFF, untracked increased. Typical causes: baseline drift (other loads changed), measurement noise, metered load on that circuit that was included in tracked baseline, or timing issues.
- clamped = true:
  - Effect magnitude is below Min Effect Threshold; treated as 0.
- valid = false and reason like `too_few_samples:X<Y`:
  - Not enough OFF samples; increase duration, reduce discard_first_n, or reduce min_samples.
- High MAD/σ even after pre-wait and discards:
  - Environment is too noisy; consider Trimmed Mean or Median of Means, increase duration, or schedule a quieter time.

Edge cases and guidance:
- Home or meters unavailable/unknown:
  - The integration guards against unavailable states; effects may be 0 or unknown if inputs are missing.
- Negative untracked values:
  - Clamped to ≥0 when computing untracked and baseline; persistent negatives indicate meter duplication or wrong sign on a meter.
- No meter change during OFF:
  - If mapped meters for the circuit never fluctuate when OFF, results may be invalid; ensure correct meter-to-circuit mapping.
- Quick clicks without switching OFF:
  - Pre-wait and discard_first_n reduce false readings; consider raising min_samples and using robust strategies.

## unterverteilung.yaml
- Circuits: `circuits: [{ id: '1F1', energy_meters: ['sensor.xyz_power'], ... }, ...]`
- Protection devices (RCD/RCBO):
  - `protection_devices: [{ type: RCD, label: 'FI Küche', protects: ['1F1','1F2',...]}]`
- Safe circuits: configure in the integration (not in YAML) so they won’t be scheduled.

## Lovelace "Power Analysis" Wizard dashboard
A ready-to-use Lovelace view is provided at `examples/lovelace/power_analysis_dashboard.yaml`.

Use it in one of two ways:
- YAML dashboard: reference the file under a dashboard in your configuration (Resources/Storage YAML).
- UI dashboard: copy the cards from this file via the Raw configuration editor into a new view.

What it includes:
- Status: measurement status, analysis status, un/tracked power, coverage, ratio, summary
- Instruction card shown while measuring (which circuit to switch off, and wait time)
- Controls: Start/Stop/Reset buttons (device buttons) and service buttons for skip/restart
- Effects per circuit (example sensors included — adjust to your circuit IDs)
- History graphs for quick insights

Tip: Set a default mobile notify service via the service `power_consumption_analyser.set_default_notify_service` to enable actionable notifications during the workflow.

## Troubleshooting
- Countdown shows warning “entity not provided by integration”:
  - Reload the integration and remove old, orphaned countdown entities; the entity_id is now stable.
- Can’t find effect strategy select:
  - Ensure the integration is updated; entity is `select.power_consumption_analyser_effect_strategy`.
- Updates don’t show:
  - Verify entity IDs and labels, and that your dashboard points to the correct sensors.
