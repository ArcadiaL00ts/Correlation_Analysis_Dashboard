$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
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
