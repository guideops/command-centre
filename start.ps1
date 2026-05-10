# Command Centre start script
$env:CC_PROJECT_ROOT = 'C:\Users\pawar\claude-projects\command-centre'
$env:CC_PORT = '8765'
if (Test-Path 'C:\Users\pawar\claude-projects\command-centre\.env') {
  Get-Content 'C:\Users\pawar\claude-projects\command-centre\.env' | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
      [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
    }
  }
}
& 'C:\Users\pawar\claude-projects\command-centre\.venv\Scripts\python.exe' 'C:\Users\pawar\claude-projects\command-centre\scripts\server.py'
