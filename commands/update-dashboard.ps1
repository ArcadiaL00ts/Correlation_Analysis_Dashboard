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
    & $python -3 "$projectRoot\scripts\update_dashboard.py" --config "$projectRoot\config\dashboard_config.json"
}
else {
    & $python "$projectRoot\scripts\update_dashboard.py" --config "$projectRoot\config\dashboard_config.json"
}
