#!/usr/bin/env zsh
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
OUT_ZIP="${REPO_ROOT}/power_consumption_analyser.zip"
SRC_DIR="${REPO_ROOT}/custom_components/power_consumption_analyser"

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Error: Integration folder not found: ${SRC_DIR}" >&2
  exit 1
fi

# Ensure required files exist
REQUIRED=(manifest.json __init__.py)
for f in $REQUIRED; do
  if [[ ! -f "${SRC_DIR}/${f}" ]]; then
    echo "Error: Missing required file: ${SRC_DIR}/${f}" >&2
    exit 1
  fi
done

# Create a temp staging dir with files at ZIP root
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

cp -R "${SRC_DIR}/." "$STAGE/"

rm -f "${OUT_ZIP}"
cd "$STAGE"
zip -r "${OUT_ZIP}" . \
  -x "**/__pycache__/**" "**/*.pyc" "**/.DS_Store" "**/.git/**"

echo "Built release asset: ${OUT_ZIP}"
