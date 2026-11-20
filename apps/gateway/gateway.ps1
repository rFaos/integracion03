# Envoltorio para PowerShell: ejecuta los scripts .sh del gateway con Git Bash
# (en Windows "bash" no suele estar en el PATH de PowerShell).
#
#   .\apps\gateway\gateway.ps1 start | stop | status | kill 5001
#   .\apps\gateway\gateway.ps1 falla        -> tests/pruebas_falla.sh
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args2)

$bash = @(
    "$env:ProgramFiles\Git\bin\bash.exe",
    "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
    "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $bash) { Write-Error "No se encontro Git Bash. Instala Git for Windows."; exit 1 }

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Args2.Count -gt 0 -and $Args2[0] -eq "falla") {
    & $bash "$here/tests/pruebas_falla.sh"
} else {
    & $bash "$here/levantar_local.sh" @Args2
}
