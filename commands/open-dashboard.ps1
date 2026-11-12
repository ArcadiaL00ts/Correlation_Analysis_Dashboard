$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    # Prefer the py launcher: a bare `python` may be the Microsoft Store stub, which runs nothing.
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    throw "Python was not found. Install Python 3.11+ and the project requirements first."
}

$python = Resolve-PythonCommand
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$projectRoot\src"

if ($python -eq "py") {
    & $python -3 "$projectRoot\scripts\run_dashboard.py"
}
else {
    & $python "$projectRoot\scripts\run_dashboard.py"
}
