#!/usr/bin/env bash
# Prompt for an ETF ticker, run the pipeline on its holdings (prompts for lookbacks), open the dashboard.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
read -r -p "ETF ticker to analyse (e.g. TAN): " ETF
ETF="$(echo "$ETF" | tr '[:lower:]' '[:upper:]' | xargs)"
[ -n "$ETF" ] || { echo "No ETF ticker entered." >&2; exit 1; }
"${PYTHON[@]}" "$PROJECT_ROOT/scripts/run_etf_correlation.py" --etf "$ETF" "$@"
"${PYTHON[@]}" "$PROJECT_ROOT/scripts/run_dashboard.py" --config "$PROJECT_ROOT/data/etf/$ETF/config.json"
