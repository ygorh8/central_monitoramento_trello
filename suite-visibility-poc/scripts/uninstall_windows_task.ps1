param(
    [string]$TaskName = "SuiteVisibilityMonitor"
)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tarefa $TaskName removida."
} else {
    Write-Host "Tarefa $TaskName nao esta instalada."
}
