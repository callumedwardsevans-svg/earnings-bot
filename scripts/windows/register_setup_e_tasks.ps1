# Registers Setup E's paper loop in Windows Task Scheduler (run once, as yourself).
#
#   Dry run (default):  powershell -ExecutionPolicy Bypass -File scripts\windows\register_setup_e_tasks.ps1
#   Live paper orders:  powershell -ExecutionPolicy Bypass -File scripts\windows\register_setup_e_tasks.ps1 -Send
#                       (needs ALPACA_E_KEY_ID / ALPACA_E_SECRET_KEY for a SEPARATE paper account in .env)
#
# UK times, valid in every week of the year (including when UK and US clocks change on different dates):
#   13:27 UK  morning  = 08:27 or 09:27 New York: market-on-open order (refused at/after 09:28 NY)
#   19:35 UK  close    = 14:35 or 15:35 New York: the script waits until 15:35 NY, then (only on
#                        turn-of-month entry/exit days) sends a market-on-close order; refused after 15:48
#   22:05 UK  evening  = after the US close: settle, journal, backtest shadow, report
param([switch]$Send)

$Wrapper = Join-Path $PSScriptRoot "run_e.ps1"
$SendArg = if ($Send) { " -Send" } else { "" }
$weekdays = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

foreach ($t in @(
        @{Name = "EarningsBot-E-Morning"; Job = "morning"; At = "13:27"; Hours = 1},
        @{Name = "EarningsBot-E-Close"; Job = "close"; At = "19:35"; Hours = 2},
        @{Name = "EarningsBot-E-Evening"; Job = "evening"; At = "22:05"; Hours = 1})) {
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours $t.Hours) -MultipleInstances IgnoreNew
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Wrapper`" -Job $($t.Job)$SendArg"
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At $t.At
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Settings $settings -Force `
        -Description "Earnings bot Setup E ($($t.Job)); mode: $(if ($Send) {'LIVE PAPER ORDERS'} else {'dry run'})" |
        Select-Object TaskName, State
}
"Mode: " + $(if ($Send) { "LIVE PAPER ORDERS (--send), Setup E's own paper account" } else { "dry run (virtual `$10k book)" })
# Remove with: Unregister-ScheduledTask -TaskName EarningsBot-E-* -Confirm:$false
