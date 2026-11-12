#!/usr/bin/env bash
# Refresh the NASDAQ-100 universe, prices, correlations, pairs and workbooks (prompts for lookbacks).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
"${PYTHON[@]}" "$PROJECT_ROOT/scripts/update_dashboard.py" --config "$PROJECT_ROOT/config/dashboard_config.json" "$@"
