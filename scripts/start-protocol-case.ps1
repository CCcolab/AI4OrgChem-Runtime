#requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet('P03','P04','P05','P06','P07','P08','P09','P10')][string]$Task,
      [Parameter(Mandatory=$true)][ValidateSet('ledger','preflight','live')][string]$Mode,
      [Parameter(Mandatory=$true)][string]$OutputRoot,[string]$Budget,
      [string]$PythonExe='python',[string]$DockerExe='docker')
$ErrorActionPreference='Stop'
$entry=Join-Path $PSScriptRoot 'run-protocol-case.py'
$parameters=@($entry,'--task',$Task,'--mode',$Mode,'--output-root',$OutputRoot,'--docker-executable',$DockerExe)
if($Budget){$parameters+=@('--budget',$Budget)}
& $PythonExe @parameters
exit $LASTEXITCODE
