# Start HERMESX — both halves, each in its own window.
#
#   .\dev.ps1               both, skipping whatever is already up
#   .\dev.ps1 -Force        start anyway (will fail on a port clash)
#   .\dev.ps1 -CollectorOnly  just the feed collector
#
# Two windows because they are two different things to watch. The COLLECTOR
# window is the live source feed: one row per source per refresh, with item
# counts and the age of the bytes. The WEB window is just Next.js.
#
# IDEMPOTENT ON PURPOSE. Running this twice is the normal case — you come back
# to the project and do not remember which halves survived, and starting a
# second uvicorn on a bound port fails with an oblique WinError 10048. Each
# half is skipped if its port is already listening, which also makes "run the
# app" safe to ask for repeatedly.
#
# PORTS ARE 8100/3100, NOT 8000/3000. GEXYGEN owns those, this terminal reads
# GEXYGEN's gamma levels, and the two are expected to be up at the same time.
param(
    [switch]$Force,
    [switch]$CollectorOnly
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-Port([int]$Port) {
    $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# The parameter is $PsArgs, not $Args: `$Args` is a PowerShell automatic
# variable, so declaring it as a parameter silently binds nothing and launches
# a bare, scriptless window instead of the service. The path is quoted because
# -ArgumentList joins on spaces, so an unquoted one would split the moment this
# repo lives somewhere like "C:\My Projects\".
function Start-InWindow([string[]]$PsArgs) {
    Start-Process powershell -ArgumentList (@("-NoExit", "-NoProfile") + $PsArgs)
}

$collectorUp = Test-Port 8100
$webUp = Test-Port 3100

if ($collectorUp -and -not $Force) {
    Write-Host "Collector -> already running on 8100, leaving it alone" -ForegroundColor DarkGray
} else {
    Write-Host "Collector -> http://127.0.0.1:8100  (live source feed in its own window)" -ForegroundColor Green
    Start-InWindow @("-ExecutionPolicy", "Bypass", "-File", "`"$(Join-Path $here 'server\run.ps1')`"")

    # The terminal reads the collector on first paint, so give it a moment to
    # bind. Without this the first load lands on the offline banner and then
    # corrects itself on the next poll - alarming, and for no reason.
    for ($i = 0; $i -lt 24 -and -not (Test-Port 8100); $i++) { Start-Sleep -Milliseconds 500 }
    if (-not (Test-Port 8100)) {
        Write-Host "  (still binding - check the collector window if the page shows the offline banner)" -ForegroundColor Yellow
    }
}

if ($CollectorOnly) {
    Write-Host ""
    Write-Host "Collector only. Ctrl-C in that window stops it." -ForegroundColor DarkGray
    return
}

if (-not (Test-Path (Join-Path $here "node_modules"))) {
    Write-Host "node_modules missing - run 'npm install' first." -ForegroundColor Red
    exit 1
}

if ($webUp -and -not $Force) {
    Write-Host "Web app   -> already running on 3100, leaving it alone" -ForegroundColor DarkGray
} else {
    Write-Host "Web app   -> http://localhost:3100" -ForegroundColor Green
    # -WorkingDirectory rather than a `-Command "Set-Location X; npm run dev"`
    # chain: -ArgumentList joins its array on spaces without quoting, so that
    # chain reaches powershell.exe unquoted, launches, serves one request and
    # the window dies. Keeping -Command to a single bare token avoids it.
    Start-Process powershell -WorkingDirectory $here `
        -ArgumentList @("-NoExit", "-NoProfile", "-Command", "npm run dev")
}

if (-not (Test-Port 8000)) {
    Write-Host ""
    Write-Host "Note: GEXYGEN is not running on 8000, so the gamma panel will say so." -ForegroundColor DarkGray
    Write-Host "      Start it from the GEXYGEN folder if you want the walls and flip." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Ctrl-C in a window stops that half." -ForegroundColor DarkGray
