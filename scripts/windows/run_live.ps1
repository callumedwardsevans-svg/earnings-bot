# Wrapper for the scheduled paper-trading runs. Output is appended to logs/live_YYYY-MM.log.
#   -Step morning   -> scripts/submit_orders.py
#   -Step evening   -> scripts/evening.py
#   -Send           -> pass --send (live paper orders); without it, a dry run
param(
    [Parameter(Mandatory = $true)][ValidateSet("morning", "evening")][string]$Step,
    [switch]$Send
)

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $env:USERPROFILE "anaconda3\envs\earnings-bot\python.exe"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("live_{0:yyyy-MM}.log" -f (Get-Date))
$env:PYTHONIOENCODING = "utf-8"
$Script = if ($Step -eq "morning") { "scripts\submit_orders.py" } else { "scripts\evening.py" }
$Flag = if ($Send) { "--send" } else { "" }

Set-Location $Root
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Step $Flag start ====="
# cmd does the redirection: PowerShell 5.1 would turn Python's stderr logging into error records.
cmd /c "`"$Python`" $Script $Flag >> `"$Log`" 2>&1"
$code = $LASTEXITCODE
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Step exit $code ====="
exit $code
