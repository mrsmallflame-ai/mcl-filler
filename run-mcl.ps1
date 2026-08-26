# MCL Filler — one-shot setup + run for Windows (PowerShell)
#
# First run:  .\run-mcl.ps1 -Url "https://www.mclcinema.com/MCLSelectSeat.aspx?ci=014&si=113882&visLang=2" -Workers 16
# Later runs: same command — it reuses the venv.
#
# Optional: -Seats 6  -IdlePoll 20  -Rounds 0   (0 = infinite)

param(
    [Parameter(Mandatory=$true)][string]$Url,
    [int]$Workers = 12,
    [int]$Seats = 6,
    [int]$IdlePoll = 20,
    [int]$Rounds = 0
)

$ErrorActionPreference = "Stop"

# --- go to repo dir (clone if missing) ---
if (-not (Test-Path ".\mcl_filler.py")) {
    if (-not (Test-Path ".\mcl-filler")) {
        Write-Host "[*] cloning repo..." -ForegroundColor Cyan
        git clone https://github.com/mrsmallflame-ai/mcl-filler.git
    }
    Set-Location .\mcl-filler
}

# --- python check ---
try { $pyVer = python --version 2>&1 } catch {
    Write-Host "Python not found. Install Python 3.10+ from https://python.org (tick 'Add to PATH')" -ForegroundColor Red
    exit 1
}
Write-Host "[*] using $pyVer"

# --- venv ---
if (-not (Test-Path ".\.venv")) {
    Write-Host "[*] creating virtualenv..." -ForegroundColor Cyan
    python -m venv .venv
}
$venvPython = ".\.venv\Scripts\python.exe"

# --- deps ---
Write-Host "[*] ensuring httpx installed..." -ForegroundColor Cyan
& $venvPython -m pip install --quiet --disable-pip-version-check httpx

# --- env knobs ---
$env:BLAZE_SEATS    = "$Seats"
$env:BLAZE_IDLE_POLL = "$IdlePoll"
if ($Rounds -gt 0) { $env:BLAZE_ROUNDS = "$Rounds" } else { Remove-Item Env:BLAZE_ROUNDS -ErrorAction SilentlyContinue }

# --- go ---
Write-Host "[*] launching filler: workers=$Workers seats=$Seats" -ForegroundColor Green
& $venvPython mcl_filler.py --url $Url $Workers

Write-Host "`n👋 done." -ForegroundColor Yellow