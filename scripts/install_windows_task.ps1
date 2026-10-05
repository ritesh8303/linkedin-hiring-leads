# Register Windows Task Scheduler job for daily scrape at 18:30
# Run once as Administrator if Register-ScheduledTask fails due to permissions.

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Project ".venv\Scripts\python.exe"
$TaskName = "DataForgePersonalJobRadar"

if (-not (Test-Path $Python)) {
  throw "Python venv not found at $Python"
}

$Action = New-ScheduledTaskAction `
  -Execute $Python `
  -Argument "-m src" `
  -WorkingDirectory $Project

$Trigger = New-ScheduledTaskTrigger -Daily -At 18:30

$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Principal $Principal `
  -Description "Daily Data/AI job scrape (LinkedIn guest + SerpAPI + Apify) before evening applications" `
  -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' daily at 18:30"
Write-Host "Project: $Project"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State
Get-ScheduledTaskInfo -TaskName $TaskName | Format-List NextRunTime, LastRunTime, LastTaskResult
