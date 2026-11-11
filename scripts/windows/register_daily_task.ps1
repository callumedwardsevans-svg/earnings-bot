# Registers the daily data update in Windows Task Scheduler (run once, as yourself).
#   powershell -ExecutionPolicy Bypass -File scripts\windows\register_daily_task.ps1
#
# 06:00 UK is always after midnight US Eastern (and UTC), so Alpha Vantage's daily
# allowance has reset and yesterday's US daily bars are final.
# StartWhenAvailable: if the PC was off/asleep at 06:00, it runs at next wake/log-on.
# Runs only while you're logged on, so no password is stored.

$TaskName = "EarningsBot-DailyDataUpdate"
$Script = Join-Path $PSScriptRoot "daily_data_update.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`""
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Earnings bot: refresh prices and backfill Alpha Vantage earnings history (25/day)." -Force |
    Select-Object TaskName, State
"Next run: " + (Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo).NextRunTime
# Remove later with:  Unregister-ScheduledTask -TaskName EarningsBot-DailyDataUpdate -Confirm:$false
