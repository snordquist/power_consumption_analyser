#!/usr/bin/env zsh
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
OUT_ZIP="${REPO_ROOT}/power_consumption_analyser.zip"
COMP_DIR="${REPO_ROOT}/custom_components/power_consumption_analyser"

if [[ ! -d "${COMP_DIR}" ]]; then
  echo "Error: Integration folder not found: ${COMP_DIR}" >&2
  exit 1
fi

# Ensure required files exist
REQUIRED=(manifest.json __init__.py)
for f in $REQUIRED; do
  if [[ ! -f "${COMP_DIR}/${f}" ]]; then
    echo "Error: Missing required file: ${COMP_DIR}/${f}" >&2
    exit 1
  fi
done

# Create ZIP with correct root structure: custom_components/power_consumption_analyser/*
rm -f "${OUT_ZIP}"
cd "${REPO_ROOT}"
zip -r "${OUT_ZIP}" custom_components/power_consumption_analyser \
  -x "**/__pycache__/**" "**/*.pyc" "**/.DS_Store" "**/.git/**"

echo "Built release asset: ${OUT_ZIP}"

