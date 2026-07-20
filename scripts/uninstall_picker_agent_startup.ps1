param(
    [string]$TaskName = "Workflow Picker Agent"
)

$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed per-user startup task '$TaskName'."
