from homeassistant.const import Platform

DOMAIN = "power_consumption_analyser"

CONF_UNTERVERTEILUNG_PATH = "unterverteilung_path"
CONF_SAFE_CIRCUITS = "safe_circuits"
CONF_BASELINE_SENSORS = "baseline_sensors"
CONF_UNTRACKED_NUMBER = "untracked_number"

# Options key to persist dynamic energy meter mappings
OPT_ENERGY_METERS_MAP = "energy_meters_map"  # entity_id -> circuit_id
OPT_DEFAULT_NOTIFY_SERVICE = "default_notify_service"
OPT_MEASURE_DURATION_S = "measure_duration_s"
OPT_EFFECT_STRATEGY = "effect_strategy"

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON, Platform.NUMBER, Platform.SELECT]
