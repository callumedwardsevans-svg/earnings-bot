# Registers the paper-trading loop in Windows Task Scheduler (run once, as yourself).
#
#   Dry run (default):  powershell -ExecutionPolicy Bypass -File scripts\windows\register_paper_tasks.ps1
#   Live paper orders:  powershell -ExecutionPolicy Bypass -File scripts\windows\register_paper_tasks.ps1 -Send
#
# Times are UK local time and were chosen to work in every week of the year, including the
# weeks when UK and US clocks change on different dates:
#   13:25 UK  morning submit  = 08:25 New York normally, 09:25 in the mismatch weeks (both pre-open)
#   22:00 UK  evening run     = 17:00 New York normally, 18:00 in the mismatch weeks (after the close)
# The scripts check New York time themselves and refuse to send orders at/after 09:28 NY.
# Tasks run only while you're logged on (no stored password) and catch up after sleep.
param([switch]$Send)

$Wrapper = Join-Path $PSScriptRoot "run_live.ps1"
$SendArg = if ($Send) { " -Send" } else { "" }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
$weekdays = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

foreach ($t in @(
        @{Name = "EarningsBot-Morning-Submit"; Step = "morning"; At = "13:25"},
        @{Name = "EarningsBot-Evening-Reconcile-Plan"; Step = "evening"; At = "22:00"})) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Wrapper`" -Step $($t.Step)$SendArg"
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At $t.At
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Settings $settings -Force `
        -Description "Earnings bot paper loop ($($t.Step)); mode: $(if ($Send) {'LIVE PAPER ORDERS'} else {'dry run'})" |
        Select-Object TaskName, State
}
"Mode: " + $(if ($Send) { "LIVE PAPER ORDERS (--send)" } else { "dry run (nothing is sent)" })
# Remove with: Unregister-ScheduledTask -TaskName EarningsBot-* -Confirm:$false
