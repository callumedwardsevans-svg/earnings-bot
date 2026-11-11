# Daily data refresh for Windows Task Scheduler.
# Updates prices + universe and spends the day's Alpha Vantage budget (25 calls) on
# symbols whose earnings history isn't cached yet. Output is appended to logs/.
# Keys are read from .env by the Python code and are never written to the log.

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $env:USERPROFILE "anaconda3\envs\earnings-bot\python.exe"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("data_update_{0:yyyy-MM}.log" -f (Get-Date))
$env:PYTHONIOENCODING = "utf-8"

Set-Location $Root
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') start ====="
# cmd does the redirection: PowerShell 5.1 would turn Python's stderr logging into error records.
cmd /c "`"$Python`" scripts\update_data.py --earnings-backfill >> `"$Log`" 2>&1"
$code = $LASTEXITCODE
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') exit $code ====="
exit $code
