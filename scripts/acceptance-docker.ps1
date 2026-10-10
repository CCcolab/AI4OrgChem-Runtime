#requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)][string] $Image, [Parameter(Mandatory)][string] $OutputRoot)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing='Standard'
$output=Get-SafeDirectory $OutputRoot
if (-not (Test-Path -LiteralPath (Join-Path (Get-RuntimeRoot) 'tests') -PathType Container)) { throw 'LOCAL_TEST_SUITE_REQUIRED: tests are local-only; use public CI for container probes' }
$engine=Get-Engine 'docker'
$identity=Get-ImageIdentity $engine $Image
$identity | ConvertTo-Json -Depth 30 | Set-Content (Join-Path $output 'image-inspect.json') -Encoding utf8
$runs=Get-SafeDirectory (Join-Path $output '离线 runs with spaces')
$locks=Get-SafeDirectory (Join-Path $output '.host-locks')
$checks=@()
function Invoke-Probe([string]$Label,[string[]]$Arguments,[int]$Expected=0) {
    & $engine @Arguments 1> (Join-Path $output "$Label-stdout.log") 2> (Join-Path $output "$Label-stderr.log")
    $code=$LASTEXITCODE
    $script:checks += @{name=$Label;status=$(if($code -eq $Expected){'PASS'}else{'FAIL'});exit_code=$code;expected_exit_code=$Expected;arguments=$Arguments}
    if($code -ne $Expected){throw "$Label failed with $code; logs retained"}
}
$digest='UNKNOWN'
if($identity.RepoDigests.Count -gt 0){$digest=($identity.RepoDigests[0] -split '@')[-1]}
$base=@('run','--rm','--network','none','--mount',"type=bind,source=$runs,target=/work",'--mount',"type=bind,source=$locks,target=/locks",
    '-e',"AI4ORGCHEM_IMAGE_ID=$($identity.Id)",'-e',"AI4ORGCHEM_IMAGE_DIGEST=$digest")
$completed=$false
try {
    Invoke-Probe 'permissions-offline' ($base + @('--entrypoint','python',$identity.Id,'-m','runtime.platform_probe'))
    foreach($task in @('evidence','core-tests','p14-smoke','p14-equivalence')) {
        $name='ai4orgchem-'+$task+'-'+[guid]::NewGuid().ToString('N')
        Invoke-Probe $task ($base + @('--name',$name,$identity.Id,'run',$task,'--lock-root','/locks'))
        $present=(& $engine container ls --all --filter "name=^/$name`$" --format '{{.ID}}' | Out-String).Trim()
        $checks += @{name="$task-container-deleted";status=$(if(-not $present){'PASS'}else{'FAIL'})}
    }
    Invoke-Probe 'exit-code-37' ($base+@('--entrypoint','python',$identity.Id,'-c','import sys; sys.exit(37)')) 37
    # No L3/L4 process is started: test only the resource helper under a real limit.
    Invoke-Probe 'low-memory-refusal' ($base+@('--memory','256m','--entrypoint','python',$identity.Id,'-c',
        'from runtime.resources import memory_snapshot,require_memory; s=memory_snapshot(); print(s); require_memory("p14-fixed",s)')) 1
    $memoryError=Get-Content (Join-Path $output 'low-memory-refusal-stderr.log') -Raw
    if(-not $memoryError.Contains('MemoryError: p14-fixed requires')){throw 'Expected explicit low-memory rejection was not observed'}
    $testRoot=Join-Path (Get-RuntimeRoot) 'tests'
    Invoke-Probe 'wrapper-tests' ($base+@('--mount',"type=bind,source=$testRoot,target=/tests,readonly",'--entrypoint','python',$identity.Id,'-m','unittest','discover','-s','/tests','-v'))
    $manifests=@(Get-ChildItem -LiteralPath $runs -Filter run-manifest.json -Recurse)
    if($manifests.Count -ne 4){throw 'Expected four persistent task manifests'}
    foreach($file in $manifests){
        $m=Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        if($m.status -ne 'PASS' -or $m.process_exit_code -ne 0){throw 'Task manifest not PASS'}
        foreach($property in $m.output_sha256.PSObject.Properties){
            $hash=(Get-FileHash -LiteralPath (Join-Path $file.DirectoryName $property.Name) -Algorithm SHA256).Hash.ToLowerInvariant()
            if($hash -ne $property.Value){throw 'Persistent output hash mismatch'}
        }
    }
    $checks += @{name='persistent-output-hashes-after-container-deletion';status='PASS';manifests=$manifests.Count}
    $completed=$true
} finally {
    $summary=@{status=$(if($completed -and -not @($checks | Where-Object {$_.status -ne 'PASS'}).Count){'PASS'}else{'FAIL'});image_id=$identity.Id;image_digest=$digest;repo_digests=$identity.RepoDigests;runtime_commit=$identity.Config.Labels.'org.opencontainers.image.revision';
        network='none';checks=$checks;run_directory=$runs;scope='Docker OCI only; no L3/L4'}
    $summary | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $output 'acceptance.json') -Encoding utf8
}
$summary | ConvertTo-Json -Depth 4
