# Power Consumption Analyser (Home Assistant custom integration)

Features:
- Reads `unterverteilung.yaml` to register circuits.
- Manual guided analysis services: select circuit, confirm off/on.
- Mirrors `number.stromberbrauch_nicht_erfasst` as an "Untracked Power" sensor.
- Shows analysis status.

## Local development setup
To enable IDE resolution of Home Assistant and integration dependencies, create a virtual environment and install `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then point your IDE to use this interpreter (the `.venv`) for indexing and type hints. This installs `homeassistant`, `pyyaml`, and `voluptuous` so imports resolve during development.

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

## Energy meters and circuits
- Label: Devices that track energy should carry the label `energy_meter`. The integration attempts to ensure this label exists and is applied to devices of linked entity IDs.
- Mapping: Each energy meter entity must be assigned to a circuit (it becomes unavailable when its circuit is turned off). You can:
  - Define meters per circuit in `unterverteilung.yaml` under `circuits[].energy_meters` (or `meters`).
  - Or link via services:
    - `power_consumption_analyser.circuit_link_energy_meter` with `entity_id` and `circuit_id`.
    - `power_consumption_analyser.circuit_unlink_energy_meter` with `entity_id`.
- Events include `expected_meters` for the current circuit to help validate availability during manual testing.

## Baseline sensors
Defaults in config flow:
- Home consumption: `sensor.home_consumption_now_w`
- Grid power: `sensor.grid_power`
- Tracked power sum: `sensor.tracked_power_sum`

Notes:
- Safe circuits cannot be selected for analysis.
- No automatic switching is performed; all steps rely on manual confirmation.
