param([string]$Cmd = 'start', [string]$Sub = '')

$INSTALL_DIR = 'C:\Users\pawar\claude-projects\command-centre'
$VENV_PY = 'C:\Users\pawar\claude-projects\command-centre\.venv\Scripts\python.exe'
$PORT = 8765

# Load env
if (Test-Path "$INSTALL_DIR\.env") {
  Get-Content "$INSTALL_DIR\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
      [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
    }
  }
}
$env:CC_PROJECT_ROOT = $INSTALL_DIR

switch ($Cmd) {
  'start' {
    Write-Host 'Starting Command Centre...' -ForegroundColor Cyan
    Start-Process -FilePath $VENV_PY -ArgumentList "$INSTALL_DIR\scripts\server.py" -NoNewWindow
    Start-Sleep 2
    Write-Host "Dashboard: http://127.0.0.1:$PORT" -ForegroundColor Green
  }
  'stop' {
    Get-Process -Name python* | Where-Object { $_.CommandLine -like '*server.py*' } | Stop-Process -Force
    Write-Host 'Stopped.' -ForegroundColor Yellow
  }
  'restart' {
    & $PSCommandPath stop
    Start-Sleep 1
    & $PSCommandPath start
  }
  'doctor' {
    & $VENV_PY "$INSTALL_DIR\scripts\doctor.py"
  }
  'sync' {
    $result = Invoke-RestMethod -Uri "http://127.0.0.1:$PORT/api/sync" -Method POST
    Write-Host "Synced." -ForegroundColor Green
  }
  'logs' {
    Get-Content "$INSTALL_DIR\logs\server.log" -Tail 50 -Wait -ErrorAction SilentlyContinue
  }
  'setup' {
    if ($Sub -eq 'otel') {
      & $VENV_PY "$INSTALL_DIR\scripts\setup_otel.py"
    } elseif ($Sub -eq 'telegram') {
      & $VENV_PY "$INSTALL_DIR\scripts\setup_telegram.py"
    } else {
      Write-Host 'Usage: cc setup otel|telegram' -ForegroundColor Yellow
    }
  }
  default {
    Write-Host 'Usage: cc start|stop|restart|doctor|sync|logs|setup <otel|telegram>' -ForegroundColor Yellow
  }
}
