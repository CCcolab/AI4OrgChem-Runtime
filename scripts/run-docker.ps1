#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateSet('evidence','core-tests','p14-smoke','p14-equivalence','p14-fixed','p14-optimize','p14-classify')] [string] $Task,
    [Parameter(Mandatory)] [string] $Image,
    [string] $OutputRoot = (Join-Path (Split-Path -Parent $PSScriptRoot | Split-Path -Parent) 'ai4orgchem-runtime-runs'),
    [string] $LockRoot = (Join-Path (Split-Path -Parent $PSScriptRoot | Split-Path -Parent) 'ai4orgchem-runtime-runs/.host-locks'),
    [ValidateRange(1,256)] [int] $Threads = 8,
    [string] $SmokeRun, [string] $OptimizationRun, [string] $EquivalenceRun, [string] $SourceLevelRun
)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing = 'Standard'
$enginePath = Get-Engine 'docker'
Assert-EngineOption $enginePath @('run') @('--mount','--rm','--env','--network')
$output = Get-SafeDirectory $OutputRoot
$locks = Get-SafeDirectory $LockRoot
$identity = Get-ImageIdentity $enginePath $Image
$imageDigest = 'UNKNOWN'
if ($identity.RepoDigests.Count -gt 0) { $imageDigest = ($identity.RepoDigests[0] -split '@')[-1] }
$arguments = @('run','--rm','--network','none','--mount',"type=bind,source=$output,target=/work",
    '--mount',"type=bind,source=$locks,target=/locks",'-e',"AI4ORGCHEM_IMAGE_DIGEST=$imageDigest",
    '-e',"AI4ORGCHEM_IMAGE_ID=$($identity.Id)")
$runtimeArgs = @('run',$Task,'--threads',"$Threads",'--lock-root','/locks')
if ($Task -eq 'p14-classify') {
    $inputs = @(@('smoke',$SmokeRun),@('optimization',$OptimizationRun),@('equivalence',$EquivalenceRun),@('source-level',$SourceLevelRun))
    foreach ($item in $inputs) {
        if (-not $item[1]) { throw "Classification requires $($item[0]) run directory" }
        $resolved = (Resolve-Path -LiteralPath $item[1]).Path
        if (-not $resolved.StartsWith($output + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Classification runs must be under OutputRoot' }
        $relative = $resolved.Substring($output.Length + 1).Replace('\','/')
        $runtimeArgs += @("--$($item[0])-run","/work/$relative")
    }
}
$hostLock = $null
try {
    if ($Task -in @('p14-smoke','p14-equivalence','p14-fixed','p14-optimize')) {
        # Same Windows lock for all managed container runs, outside each run dir.
        $hostLock = [IO.File]::Open((Join-Path $locks 'windows-quantum.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    }
    # Execute the inspected immutable ID, not a mutable tag that might move.
    & $enginePath @arguments $identity.Id @runtimeArgs
    $taskExit = $LASTEXITCODE
} finally { if ($null -ne $hostLock) { $hostLock.Dispose() } }
exit $taskExit
