param(
    [Parameter(Mandatory = $true)]
    [string]$AgentExecutable,
    [string]$Server = "ws://127.0.0.1:8000",
    [string]$TaskName = "Workflow Picker Agent"
)

$ErrorActionPreference = "Stop"

$resolvedAgent = (Resolve-Path -LiteralPath $AgentExecutable -ErrorAction Stop).Path
$serverUri = [Uri]$Server
if ($serverUri.Scheme -notin @("ws", "wss")) {
    throw "Server must use ws:// or wss://"
}
if ([string]::IsNullOrWhiteSpace($serverUri.Host) -or $Server.Contains('"') -or $Server -match "\s") {
    throw "Server must be a single ws:// or wss:// URL without quotes or whitespace"
}

$action = New-ScheduledTaskAction `
    -Execute $resolvedAgent `
    -Argument "--server `"$Server`"" `
    -WorkingDirectory (Split-Path -Parent $resolvedAgent)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "Installed per-user startup task '$TaskName'."
Write-Host "The agent will run in your interactive desktop session at next logon."
