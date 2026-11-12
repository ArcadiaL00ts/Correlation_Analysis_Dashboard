# Sourced by the other commands/*.sh scripts: picks a Python 3.11+ interpreter and sets PYTHONPATH.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON=("$VIRTUAL_ENV/bin/python")
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=(python3)
elif command -v python >/dev/null 2>&1; then
    PYTHON=(python)
elif command -v py >/dev/null 2>&1; then
    PYTHON=(py -3)  # Git Bash on Windows
else
    echo "Python was not found. Install Python 3.11+ and run: pip install -e ." >&2
    exit 1
fi
"${PYTHON[@]}" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || {
    echo "Python 3.11+ is required ($("${PYTHON[@]}" --version 2>&1) found)." >&2
    exit 1
}
