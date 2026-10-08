#requires -Version 5.1
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('P11','P12')][string]$Task,
 [Parameter(Mandatory=$true)][ValidateSet('ledger','preflight','live')][string]$Mode,
 [Parameter(Mandatory=$true)][string]$OutputRoot,
 [string]$Unit,[string]$Budget,[string]$Inputs,
 [string]$PythonExe='python',[string]$DockerExe='docker'
)
$ErrorActionPreference='Stop'
$entry=Join-Path $PSScriptRoot 'run-high-cost-case.py'
$arguments=@($entry,'--task',$Task,'--mode',$Mode,'--output-root',$OutputRoot,'--docker-executable',$DockerExe)
if($Unit){$arguments+=@('--unit',$Unit)}
if($Budget){$arguments+=@('--budget',$Budget)}
if($Inputs){$arguments+=@('--inputs',$Inputs)}
& $PythonExe @arguments
exit $LASTEXITCODE
