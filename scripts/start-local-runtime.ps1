# Windows PowerShell 5.1 compatible local navigation and thin service routing.
[CmdletBinding()]
param(
 [ValidateSet('Capabilities','List','Show','Review','Check','Report','Run')][string]$Action='Capabilities',
 [string]$Proposition,[string]$SourceDirectory,[string]$OutputDirectory,
 [string]$PythonExecutable,[string]$Image,[string]$Request,[string]$RunDirectory,
 [string]$OutputRoot,[string]$ReportExportDirectory,[string]$PowerShell7,[string]$DockerExecutable='docker',[string]$LockRoot,[switch]$Json
)
$ErrorActionPreference='Stop'
$localRoot=Split-Path -Parent $PSScriptRoot
if($Action -eq 'Run'){
 if($Proposition -notin @('P02','P13','P01')){throw 'Run supports only the three fixed registered P02/P13/P01 cases'}
 if(-not $OutputRoot){throw 'Run requires a separate -OutputRoot'}
 if($SourceDirectory -or $OutputDirectory -or $Request -or $RunDirectory -or $ReportExportDirectory -or $PowerShell7 -or $Json){throw 'Run accepts no molecule, protocol, source or report overrides'}
 $registeredTasks=@{P02='p02-statistics';P13='p13-graph-ledger';P01='p01-orbital-density'}
 $registeredArgs=@{Task=$registeredTasks[$Proposition];OutputRoot=$OutputRoot;DockerExecutable=$DockerExecutable}
 foreach($name in @('Image','PythonExecutable','LockRoot')){$value=Get-Variable -Name $name -ValueOnly;if($value){$registeredArgs[$name]=$value}}
 & (Join-Path $PSScriptRoot 'start-registered-case.ps1') @registeredArgs
 $global:LASTEXITCODE=$LASTEXITCODE
 exit $LASTEXITCODE
}
if($LockRoot -or $DockerExecutable -ne 'docker'){throw '-LockRoot/-DockerExecutable require Run'}
if($Action -notin @('Show','Review') -and ($Proposition -or $SourceDirectory)){throw '-Proposition/-SourceDirectory require Show or Review'}
if($Action -ne 'Review' -and $OutputDirectory){throw '-OutputDirectory requires Review'}
if($Action -notin @('Check','Report') -and ($Image -or $Request -or $RunDirectory -or $OutputRoot -or $ReportExportDirectory -or $PowerShell7)){throw 'Service parameters require Check or Report'}
if($Action -eq 'Check' -or $Action -eq 'Report'){
 if($Json){throw '-Json is supported only for local capability/proposition metadata'}
 if($Action -eq 'Check' -and ($RunDirectory -or $ReportExportDirectory)){throw 'Check does not accept Report run/export parameters'}
 if($Action -eq 'Report' -and ($Image -or $Request -or $OutputRoot)){throw 'Report does not accept Check image/request/output parameters'}
 $serviceArgs=@{Action=$Action}
 foreach($name in @('Image','Request','RunDirectory','OutputRoot','PythonExecutable','ReportExportDirectory','PowerShell7')){
  $value=Get-Variable -Name $name -ValueOnly
  if($value){$serviceArgs[$name]=$value}
 }
 if($Action -eq 'Check' -and -not $Image){
  $record=Get-Content -LiteralPath (Join-Path $localRoot 'validation/user-molecule/candidate-image.json') -Raw | ConvertFrom-Json
  if($record.image_id -notmatch '^sha256:[0-9a-f]{64}$'){throw 'Explicit identified user-molecule image required'}
  $serviceArgs.Image=$record.image_id
 }
 & (Join-Path $PSScriptRoot 'start-user-molecule.ps1') @serviceArgs
 $routeExitCode=$LASTEXITCODE
 $global:LASTEXITCODE=$routeExitCode
 exit $routeExitCode
}
$pythonCandidates=@()
if($PythonExecutable){$pythonCandidates=@($PythonExecutable)}else{
 $command=Get-Command python.exe -ErrorAction SilentlyContinue
 if($command -and $command.Source -notmatch '[\\/]WindowsApps[\\/]'){$pythonCandidates+= $command.Source}
 $pythonCandidates+= (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
}
$selectedPython=$null
foreach($candidate in $pythonCandidates){
 if(Test-Path -LiteralPath $candidate -PathType Leaf){
  $versionText=(& $candidate -B -c 'import sys; print(chr(46).join(map(str,sys.version_info[:3])))' | Out-String).Trim()
  if($LASTEXITCODE -eq 0 -and [version]$versionText -ge [version]'3.12'){$selectedPython=$candidate;break}
 }
}
if(-not $selectedPython){throw 'Existing Python 3.12+ required; supply -PythonExecutable. No tools were installed.'}
if($Action -eq 'Capabilities'){
 $arguments=@('-B',(Join-Path $PSScriptRoot 'local-runtime-capabilities.py'))
 if($Json){$arguments+='--json'}
}else{
 $arguments=@('-B',(Join-Path $PSScriptRoot 'review-proposition.py'),$Action.ToLowerInvariant())
 if($Action -eq 'Show' -or $Action -eq 'Review'){
  if(-not $Proposition){throw 'Show/Review requires -Proposition P01 through P14'}
  $arguments+=$Proposition
 }
 if($Action -in @('Show','Review') -and $SourceDirectory){$arguments+=@('--source-dir',$SourceDirectory)}
 if($Action -eq 'Review'){
  if(-not $OutputDirectory){throw 'Review requires a fresh -OutputDirectory outside source materials'}
  $arguments+=@('--output-dir',$OutputDirectory)
 }
 if($Json){$arguments+='--json'}
}
$previousConsoleEncoding=[Console]::OutputEncoding
try{
 [Console]::OutputEncoding=New-Object Text.UTF8Encoding $false
 & $selectedPython @arguments
 $localRuntimeExitCode=$LASTEXITCODE
}finally{[Console]::OutputEncoding=$previousConsoleEncoding}
$global:LASTEXITCODE=$localRuntimeExitCode
if($localRuntimeExitCode -ne 0){Write-Error "Local review returned $localRuntimeExitCode; original evidence was preserved." -ErrorAction Continue}
exit $localRuntimeExitCode
