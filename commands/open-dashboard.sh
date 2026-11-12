#!/usr/bin/env bash
# Launch the Streamlit dashboard (pass --config data/etf/<ETF>/config.json or --port N).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
"${PYTHON[@]}" "$PROJECT_ROOT/scripts/run_dashboard.py" "$@"
