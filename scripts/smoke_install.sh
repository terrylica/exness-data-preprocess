#!/usr/bin/env bash
# Install the built wheel into a fresh, throwaway venv and import it (catches packaging gaps).
# Run after `uv build` (moon: repo:smoke-install depends on repo:build).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
wheel=$(ls dist/*.whl 2>/dev/null | head -1)
[[ -n "$wheel" ]] || { echo "✗ no wheel in dist/ — run uv build first"; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
uv venv "$tmp/venv" -q
uv pip install "$wheel" --python "$tmp/venv/bin/python" -q
"$tmp/venv/bin/python" -c "
import exness_data_preprocess as edp
assert edp.ExnessDataProcessor and edp.ClickHouseManager
print(f'✓ fresh install of {edp.__version__} imports')
"
