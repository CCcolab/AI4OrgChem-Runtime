# Windows PowerShell 5.1 compatible; uses an existing Python, installs nothing.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('p02-statistics','p13-graph-ledger','p01-orbital-density')][string]$Task,
 [Parameter(Mandatory=$true)][string]$OutputRoot,
 [string]$Image,[string]$PythonExecutable,[string]$DockerExecutable='docker',[string]$LockRoot
)
$ErrorActionPreference='Stop'
$pythonCandidates=@()
if($PythonExecutable){$pythonCandidates=@($PythonExecutable)}else{
 foreach($commandName in @('python.exe','python3.exe','python','python3')){
  $command=Get-Command $commandName -ErrorAction SilentlyContinue
  if($command -and $command.Source -notmatch '[\\/]WindowsApps[\\/]'){$pythonCandidates+=$command.Source}
 }
 $pythonCandidates+=(Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
}
$selectedPython=$null
foreach($candidate in $pythonCandidates){
 if(Test-Path -LiteralPath $candidate -PathType Leaf){
  $versionText=(& $candidate -B -c 'import sys; print(chr(46).join(map(str,sys.version_info[:3])))' | Out-String).Trim()
  if($LASTEXITCODE -eq 0 -and [version]$versionText -ge [version]'3.12'){$selectedPython=$candidate;break}
 }
}
if(-not $selectedPython){throw 'Existing Python 3.12+ required; supply -PythonExecutable. No installation was performed.'}
$hostArguments=@('-B',(Join-Path $PSScriptRoot 'run-registered-case.py'),'--task',$Task,'--output-root',$OutputRoot,'--docker-executable',$DockerExecutable)
if($Image){$hostArguments+=@('--image',$Image)}
if($LockRoot){$hostArguments+=@('--lock-root',$LockRoot)}
$previousEncoding=[Console]::OutputEncoding
try{
 [Console]::OutputEncoding=New-Object Text.UTF8Encoding $false
 & $selectedPython @hostArguments
 $registeredExitCode=$LASTEXITCODE
}finally{[Console]::OutputEncoding=$previousEncoding}
$global:LASTEXITCODE=$registeredExitCode
if($registeredExitCode -ne 0){Write-Error "Registered fixed case returned $registeredExitCode; retained records identify its actual status." -ErrorAction Continue}
exit $registeredExitCode
