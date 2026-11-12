$ErrorActionPreference = "Stop"

# Prompts for the ETF ticker, then the price-history and cointegration lookbacks, then runs the
# correlation pipeline on that ETF's holdings and opens the dashboard on the result.
function Resolve-PythonCommand {
    # Prefer the py launcher: a bare `python` may be the Microsoft Store stub, which runs nothing.
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    throw "Python was not found. Install Python 3.11+ and the project requirements first."
}

$python = Resolve-PythonCommand
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$projectRoot\src"

$etf = (Read-Host "ETF ticker to analyse (e.g. TAN)").Trim().ToUpper()
if (-not $etf) { throw "No ETF ticker entered." }

& $python[0] $python[1..9] "$projectRoot\scripts\run_etf_correlation.py" --etf $etf @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python[0] $python[1..9] "$projectRoot\scripts\run_dashboard.py" --config "$projectRoot\data\etf\$etf\config.json"
