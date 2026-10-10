# Windows PowerShell 5.1 bootstrap; scientific tasks run in a separate PS 7 process.
[CmdletBinding()]
param(
    [ValidateSet('evidence','core-tests','p14-smoke','p14-equivalence','p14-fixed','p14-optimize','p14-classify')][string]$Task='evidence',
    [string]$Image='ai4orgchem-runtime:oci-candidate-20261002',
    [string]$OutputRoot,
    [ValidateRange(1,256)][int]$Threads=8,
    [string]$PowerShell7,
    [string]$SmokeRun,[string]$OptimizationRun,[string]$EquivalenceRun,[string]$SourceLevelRun,
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
if(-not $OutputRoot){$OutputRoot=Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'ai4orgchem-runtime-runs/daily-use'}
$candidates=@()
if($PowerShell7){$candidates=@($PowerShell7)}else{
    $command=Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if($command){$candidates+= $command.Source}
    $candidates+= @((Join-Path $env:ProgramFiles 'PowerShell/7/pwsh.exe'),
        (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'))
}
$selected=$null
foreach($candidate in $candidates){
    if(Test-Path -LiteralPath $candidate -PathType Leaf){
        $versionText=(& $candidate -NoProfile -Command '$PSVersionTable.PSVersion.ToString()' | Out-String).Trim()
        if($LASTEXITCODE -eq 0 -and [version]$versionText -ge [version]'7.3'){$selected=$candidate;break}
    }
}
if(-not $selected){throw 'PowerShell 7.3+ not found. Supply -PowerShell7 with its absolute executable path.'}
Write-Host "PowerShell: $selected ($versionText)"
Write-Host "Task: $Task; engine: Docker; output: $OutputRoot"
if($CheckOnly){return}
$arguments=@('-NoProfile','-File',(Join-Path $PSScriptRoot 'run-docker.ps1'),
    '-Task',$Task,'-Image',$Image,'-OutputRoot',$OutputRoot,'-Threads',"$Threads")
foreach($name in @('SmokeRun','OptimizationRun','EquivalenceRun','SourceLevelRun')){
    $value=Get-Variable -Name $name -ValueOnly
    if($value){$arguments+=@("-$name",$value)}
}
$started=[DateTime]::UtcNow
& $selected @arguments
$code=$LASTEXITCODE
Write-Host "Exit code: $code"
if(Test-Path -LiteralPath $OutputRoot){
    Get-ChildItem -LiteralPath $OutputRoot -Recurse -Filter run-manifest.json | Where-Object {$_.LastWriteTimeUtc -ge $started} | ForEach-Object {
        $m=Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        Write-Host "Status: $($m.status); result directory: $($_.DirectoryName)"
    }
}
# Return control to an interactive Windows PowerShell caller instead of closing it.
$global:LASTEXITCODE=$code
if($code -ne 0){Write-Error "Task failed with exit code $code; logs retained under $OutputRoot" -ErrorAction Continue}
