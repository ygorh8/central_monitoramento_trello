param(
    [string]$TaskName = "SuiteVisibilityMonitor"
)

$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Ambiente virtual nao encontrado em $pythonExe. Execute a instalacao descrita no README primeiro."
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "-m suite_visibility.cli serve" `
    -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Tarefa $TaskName instalada e iniciada para $identity."
