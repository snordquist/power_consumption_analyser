import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

@pytest.fixture
def temp_config_dir(tmp_path: Path):
    d = tmp_path / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d

@pytest.fixture
def sample_yaml(temp_config_dir: Path):
    yaml_path = temp_config_dir / "unterverteilung.yaml"
    yaml_path.write_text(
        """
        circuits:
          - id: "2F7"
            description: Kitchen
            phase: L1
            energy_meters:
              - sensor.kitchen_plug_power
          - id: "3F11"
            description: Media
        """,
        encoding="utf-8",
    )
    return yaml_path

