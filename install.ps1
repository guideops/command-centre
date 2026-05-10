#Requires -Version 5.1
<#
.SYNOPSIS
  Command Centre installer for Windows
.DESCRIPTION
  Sets up the Command Centre dashboard: Python venv, dependencies, UI build, env file,
  OTEL wizard, optional Telegram, Windows Task Scheduler tasks.
.PARAMETER Port
  Port for the dashboard (default: 8765)
.PARAMETER NoOtel
  Skip OTEL wizard
.PARAMETER NoTelegram
  Skip Telegram wizard
.PARAMETER NoScheduler
  Skip Windows Task Scheduler setup
.PARAMETER NoStart
  Don't start the server after install
.PARAMETER Yes
  Non-interactive mode (accept all defaults)
#>
param(
  [int]$Port = 8765,
  [switch]$NoOtel,
  [switch]$NoTelegram,
  [switch]$NoScheduler,
  [switch]$NoStart,
  [switch]$Yes
)

$ErrorActionPreference = "Stop"
$INSTALL_DIR = $PSScriptRoot

Write-Host ""
Write-Host "  Command Centre Installer" -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor Cyan
Write-Host ""

# ─── Find Python ──────────────────────────────────────────────────────────────

$PYTHON = $null
foreach ($candidate in @("python3.12", "python3.11", "python3.10", "python3.9", "python3", "python")) {
  $p = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($p) {
    $ver = & $p.Source --version 2>&1
    if ($ver -match "Python (\d+)\.(\d+)") {
      $major = [int]$Matches[1]
      $minor = [int]$Matches[2]
      if ($major -eq 3 -and $minor -ge 9) {
        $PYTHON = $p.Source
        Write-Host "  Python: $ver ($PYTHON)" -ForegroundColor Green
        if ($minor -lt 10) { Write-Warning "Python 3.10+ recommended." }
        break
      }
    }
  }
}
if (-not $PYTHON) {
  Write-Error "Python 3.9+ not found. Install from python.org and add to PATH."
  exit 1
}

# ─── Check Node.js ───────────────────────────────────────────────────────────

$NPM = Get-Command npm -ErrorAction SilentlyContinue
if (-not $NPM) {
  Write-Warning "npm not found. Frontend will not be built. Install Node.js from nodejs.org."
  $skipUI = $true
} else {
  $skipUI = $false
  Write-Host "  npm: $((npm --version 2>&1).Trim())" -ForegroundColor Green
}

# ─── Create directories ───────────────────────────────────────────────────────

Write-Host ""
Write-Host "  Creating directories..." -ForegroundColor Gray

$dirs = @("data", "logs", ".tmp\mission-control-queue\pids")
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\$d" | Out-Null
}

# ─── Copy .env ───────────────────────────────────────────────────────────────

$envFile = "$INSTALL_DIR\.env"
if (-not (Test-Path $envFile)) {
  Copy-Item "$INSTALL_DIR\.env.example" $envFile
}

# Set CC_PROJECT_ROOT in .env
$envContent = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
if ($envContent -notmatch "CC_PROJECT_ROOT=.+") {
  $envContent = $envContent -replace "CC_PROJECT_ROOT=", "CC_PROJECT_ROOT=$INSTALL_DIR"
  $envContent | Set-Content $envFile -Encoding UTF8
}
if ($envContent -notmatch "CC_PORT=$Port") {
  $envContent = $envContent -replace "CC_PORT=\d+", "CC_PORT=$Port"
  $envContent | Set-Content $envFile -Encoding UTF8
}

# ─── Python venv ─────────────────────────────────────────────────────────────

$VENV = "$INSTALL_DIR\.venv"
if (-not (Test-Path "$VENV\Scripts\python.exe")) {
  Write-Host "  Creating Python venv..." -ForegroundColor Gray
  & $PYTHON -m venv $VENV
}

$VENV_PY = "$VENV\Scripts\python.exe"
$VENV_PIP = "$VENV\Scripts\pip.exe"

Write-Host "  Installing Python dependencies..." -ForegroundColor Gray
& $VENV_PIP install -r "$INSTALL_DIR\requirements.txt" -q

# ─── Build UI ────────────────────────────────────────────────────────────────

if (-not $skipUI) {
  Write-Host "  Installing UI dependencies..." -ForegroundColor Gray
  Push-Location "$INSTALL_DIR\ui"
  try {
    npm install --silent 2>&1 | Out-Null
    Write-Host "  Building UI..." -ForegroundColor Gray
    npm run build 2>&1 | Out-Null
    Write-Host "  UI built successfully." -ForegroundColor Green
  } catch {
    Write-Warning "UI build failed: $_. Run 'cd ui && npm run build' manually."
  } finally {
    Pop-Location
  }
} else {
  Write-Host "  Skipping UI build (npm not found)." -ForegroundColor Yellow
}

# ─── Start script ────────────────────────────────────────────────────────────

$startScript = @"
# Command Centre start script
`$env:CC_PROJECT_ROOT = '$INSTALL_DIR'
`$env:CC_PORT = '$Port'
if (Test-Path '$envFile') {
  Get-Content '$envFile' | ForEach-Object {
    if (`$_ -match '^\s*([^#=]+)=(.*)$') {
      [System.Environment]::SetEnvironmentVariable(`$Matches[1].Trim(), `$Matches[2].Trim(), 'Process')
    }
  }
}
& '$VENV_PY' '$INSTALL_DIR\scripts\server.py'
"@
$startScript | Set-Content "$INSTALL_DIR\start.ps1" -Encoding UTF8

# ─── cc launcher ─────────────────────────────────────────────────────────────

$ccScript = @"
param([string]`$Cmd = 'start', [string]`$Sub = '')

`$INSTALL_DIR = '$INSTALL_DIR'
`$VENV_PY = '$VENV_PY'
`$PORT = $Port

# Load env
if (Test-Path "`$INSTALL_DIR\.env") {
  Get-Content "`$INSTALL_DIR\.env" | ForEach-Object {
    if (`$_ -match '^\s*([^#=]+)=(.*)$') {
      [System.Environment]::SetEnvironmentVariable(`$Matches[1].Trim(), `$Matches[2].Trim(), 'Process')
    }
  }
}
`$env:CC_PROJECT_ROOT = `$INSTALL_DIR

switch (`$Cmd) {
  'start' {
    Write-Host 'Starting Command Centre...' -ForegroundColor Cyan
    Start-Process -FilePath `$VENV_PY -ArgumentList "`$INSTALL_DIR\scripts\server.py" -NoNewWindow
    Start-Sleep 2
    Write-Host "Dashboard: http://127.0.0.1:`$PORT" -ForegroundColor Green
  }
  'stop' {
    Get-Process -Name python* | Where-Object { `$_.CommandLine -like '*server.py*' } | Stop-Process -Force
    Write-Host 'Stopped.' -ForegroundColor Yellow
  }
  'restart' {
    & `$PSCommandPath stop
    Start-Sleep 1
    & `$PSCommandPath start
  }
  'doctor' {
    & `$VENV_PY "`$INSTALL_DIR\scripts\doctor.py"
  }
  'sync' {
    `$result = Invoke-RestMethod -Uri "http://127.0.0.1:`$PORT/api/sync" -Method POST
    Write-Host "Synced." -ForegroundColor Green
  }
  'logs' {
    Get-Content "`$INSTALL_DIR\logs\server.log" -Tail 50 -Wait -ErrorAction SilentlyContinue
  }
  'setup' {
    if (`$Sub -eq 'otel') {
      & `$VENV_PY "`$INSTALL_DIR\scripts\setup_otel.py"
    } elseif (`$Sub -eq 'telegram') {
      & `$VENV_PY "`$INSTALL_DIR\scripts\setup_telegram.py"
    } else {
      Write-Host 'Usage: cc setup otel|telegram' -ForegroundColor Yellow
    }
  }
  default {
    Write-Host 'Usage: cc start|stop|restart|doctor|sync|logs|setup <otel|telegram>' -ForegroundColor Yellow
  }
}
"@
$ccScript | Set-Content "$INSTALL_DIR\cc.ps1" -Encoding UTF8

# Create cc.bat shim
@"
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0cc.ps1" %*
"@ | Set-Content "$INSTALL_DIR\cc.bat" -Encoding ASCII

Write-Host "  Launcher created: cc.bat / cc.ps1" -ForegroundColor Green

# ─── OTEL wizard ─────────────────────────────────────────────────────────────

if (-not $NoOtel) {
  Write-Host ""
  Write-Host "  Setting up OTEL telemetry..." -ForegroundColor Gray
  if ($Yes) {
    & $VENV_PY "$INSTALL_DIR\scripts\setup_otel.py" --yes
  } else {
    & $VENV_PY "$INSTALL_DIR\scripts\setup_otel.py"
  }
}

# ─── Telegram ────────────────────────────────────────────────────────────────

if (-not $NoTelegram -and -not $Yes) {
  Write-Host ""
  $resp = Read-Host "  Set up Telegram notifications? [y/N]"
  if ($resp -match "^y") {
    & $VENV_PY "$INSTALL_DIR\scripts\setup_telegram.py"
  }
}

# ─── Windows Task Scheduler ───────────────────────────────────────────────────

if (-not $NoScheduler) {
  Write-Host ""
  Write-Host "  Registering Windows Task Scheduler task..." -ForegroundColor Gray
  try {
    # Server task
    $action = New-ScheduledTaskAction -Execute $VENV_PY -Argument "`"$INSTALL_DIR\scripts\server.py`"" -WorkingDirectory "$INSTALL_DIR\scripts"
    $triggers = @(
      (New-ScheduledTaskTrigger -AtLogOn),
      (New-ScheduledTaskTrigger -AtStartup)
    )
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName "CommandCentre\Server" -Action $action -Trigger $triggers -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  Task Scheduler: CommandCentre\Server registered." -ForegroundColor Green

    # Dispatcher task
    $dAction = New-ScheduledTaskAction -Execute $VENV_PY -Argument "`"$INSTALL_DIR\.claude\skills\mission-control\dispatcher.py`"" -WorkingDirectory $INSTALL_DIR
    $dTrigger = New-ScheduledTaskTrigger -AtLogOn
    Register-ScheduledTask -TaskName "CommandCentre\Dispatcher" -Action $dAction -Trigger $dTrigger -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  Task Scheduler: CommandCentre\Dispatcher registered." -ForegroundColor Green

    # Telegram handler (only if configured)
    $hasTelegram = $env:TELEGRAM_BOT_TOKEN -or ((Get-Content $envFile -Raw -ErrorAction SilentlyContinue) -match "TELEGRAM_BOT_TOKEN=.+")
    if ($hasTelegram) {
      $tAction = New-ScheduledTaskAction -Execute $VENV_PY -Argument "`"$INSTALL_DIR\.claude\skills\telegram\scripts\telegram_handler.py`"" -WorkingDirectory $INSTALL_DIR
      $tTrigger = New-ScheduledTaskTrigger -AtLogOn
      Register-ScheduledTask -TaskName "CommandCentre\TelegramHandler" -Action $tAction -Trigger $tTrigger -Settings $settings -Force | Out-Null
      Write-Host "  Task Scheduler: CommandCentre\TelegramHandler registered." -ForegroundColor Green
    }
  } catch {
    Write-Warning "Task Scheduler setup failed: $_. Start manually with: cc start"
  }
}

# ─── Start server ─────────────────────────────────────────────────────────────

if (-not $NoStart) {
  Write-Host ""
  Write-Host "  Starting Command Centre..." -ForegroundColor Cyan
  Start-Process -FilePath $VENV_PY -ArgumentList "$INSTALL_DIR\scripts\server.py" -NoNewWindow
  Start-Sleep 3

  Write-Host ""
  Write-Host "  ══════════════════════════════════════" -ForegroundColor Cyan
  Write-Host "  Dashboard: http://127.0.0.1:$Port" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Next steps:" -ForegroundColor White
  Write-Host "  1. Open http://127.0.0.1:$Port" -ForegroundColor Gray
  if (-not $NoOtel) {
    Write-Host "  2. Restart Claude Code for OTEL to take effect" -ForegroundColor Gray
  }
  Write-Host "  3. Run: .\cc.bat doctor" -ForegroundColor Gray
  Write-Host "  ══════════════════════════════════════" -ForegroundColor Cyan
}
