# Wrapper for the scheduled Setup E runs. Output is appended to logs/setup_e_YYYY-MM.log.
#   -Job morning | close | evening    -> scripts/e_live.py <job>
#   -Send                             -> live paper orders in Setup E's own account; without it, a dry run
param(
    [Parameter(Mandatory = $true)][ValidateSet("morning", "close", "evening")][string]$Job,
    [switch]$Send
)

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $env:USERPROFILE "anaconda3\envs\earnings-bot\python.exe"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("setup_e_{0:yyyy-MM}.log" -f (Get-Date))
$env:PYTHONIOENCODING = "utf-8"
$Flag = if ($Send) { "--send" } else { "" }

Set-Location $Root
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Job $Flag start ====="
# cmd does the redirection: PowerShell 5.1 would turn Python's stderr logging into error records.
cmd /c "`"$Python`" scripts\e_live.py $Job $Flag >> `"$Log`" 2>&1"
$code = $LASTEXITCODE
Add-Content -Encoding utf8 $Log "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Job exit $code ====="
exit $code
