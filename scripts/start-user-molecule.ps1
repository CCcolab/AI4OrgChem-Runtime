# Compatible with Windows PowerShell 5.1; no host scientific Python required.
[CmdletBinding()]
param([ValidateSet('Check','Compute','Report')][string]$Action='Check',[string]$Image,[string]$Request,
 [string]$CheckRun,[string]$RunDirectory,[string]$OutputRoot,[string]$LockRoot,[string]$CancelFile,[string]$PowerShell7,[switch]$KeepContainer)
$ErrorActionPreference='Stop'
$candidates=@()
if($PowerShell7){$candidates=@($PowerShell7)}else{
    $command=Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if($command){$candidates+=$command.Source}
    $candidates+=@((Join-Path $env:ProgramFiles 'PowerShell/7/pwsh.exe'),
        (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'))
}
$selected=$null
foreach($candidate in $candidates){
    if(Test-Path -LiteralPath $candidate -PathType Leaf){
        $versionText=(& $candidate -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'|Out-String).Trim()
        if($LASTEXITCODE -eq 0 -and [version]$versionText -ge [version]'7.3'){$selected=$candidate;break}
    }
}
if(-not $selected){throw 'PowerShell 7.3+ not found; provide its existing executable using -PowerShell7.'}
$args=@('-NoProfile','-File',(Join-Path $PSScriptRoot 'run-user-molecule.ps1'),'-Action',$Action)
foreach($name in @('Image','Request','CheckRun','RunDirectory','OutputRoot','LockRoot','CancelFile')){
    $value=Get-Variable -Name $name -ValueOnly
    if($value){$args+=@("-$name",$value)}
}
if($KeepContainer){$args+='-KeepContainer'}
& $selected @args
$global:LASTEXITCODE=$LASTEXITCODE
if($LASTEXITCODE -ne 0){Write-Error "User molecule action exited $LASTEXITCODE; records retained." -ErrorAction Continue}
