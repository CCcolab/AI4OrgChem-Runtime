#requires -Version 7.3
[CmdletBinding()]
param(
 [ValidateSet('Check','Compute','Report')][string]$Action='Check',
 [string]$Image,[string]$Request,[string]$CheckRun,[string]$RunDirectory,
 [string]$OutputRoot='D:\AI4Science\user-molecule-runs',
 [string]$LockRoot='D:\AI4Science\ai4orgchem-runtime-runs\.host-locks',
 [string]$CancelFile,[switch]$KeepContainer
)
. (Join-Path $PSScriptRoot 'UserMolecule.Common.ps1')
$PSNativeCommandArgumentPassing='Standard'
if($Action -eq 'Report'){
    if(-not $RunDirectory){throw 'Report requires -RunDirectory'}
    Get-Content -LiteralPath (Join-Path $RunDirectory 'report.md') -Encoding utf8
    exit 0
}
if(-not $Image -or -not $Request){throw 'Check/Compute requires -Image and -Request'}
$runId=$Action.ToLowerInvariant()+'-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N')
$output=[IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $output -Force|Out-Null
Assert-UserMoleculePlainPath $output
$run=Join-Path $output $runId
New-Item -ItemType Directory -Path $run|Out-Null
$errorLog=Join-Path $run 'docker-stderr.log'
$hostRecord=[ordered]@{run_id=$runId;action=$Action;started_utc=[DateTime]::UtcNow.ToString('o');
    status='PREPARING';container_id=$null;container_exit_code=$null;service_exit_code=$null;
    image_id=$null;launcher_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
    common_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'UserMolecule.Common.ps1')).Hash.ToLowerInvariant();
    termination_reason=$null;oom_killed=$null}
$engine=$null;$containerId=$null;$lock=$null;$code=40;$removed=$false;$failureCode=40
Write-UserMoleculeJson (Join-Path $run 'host-execution.json') $hostRecord
try{
    $engine=(Get-Command docker.exe -ErrorAction Stop).Source
    $failureCode=10
    $requestPath=(Resolve-Path -LiteralPath $Request).Path
    Assert-UserMoleculePlainPath $requestPath
    $bytes=[IO.File]::ReadAllBytes($requestPath)
    if($bytes.Length -gt 262144){throw 'Request exceeds 256 KiB'}
    $requestText=[Text.UTF8Encoding]::new($false,$true).GetString($bytes)
    $requestValue=ConvertFrom-Json -InputObject $requestText -AsHashtable
    $geometryName=$requestValue.geometry_file
    if($geometryName -isnot [string] -or $geometryName -match '[:\x00-\x1f]' -or
        [IO.Path]::IsPathRooted($geometryName) -or ($geometryName -split '[\\/]') -contains '..' -or
        ($geometryName -split '[\\/]') -contains '.' -or ($geometryName -split '[\\/]') -contains ''){throw 'Unsafe geometry_file path'}
    $inputRoot=Split-Path -Parent $requestPath
    $geometry=[IO.Path]::GetFullPath((Join-Path $inputRoot $geometryName))
    if(-not $geometry.StartsWith($inputRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Geometry path escapes input directory'}
    Assert-UserMoleculePlainPath $geometry
    if((Get-Item -LiteralPath $geometry).Length -gt 4194304){throw 'XYZ exceeds 4 MiB'}
    $resources=$requestValue.resources
    foreach($name in @('threads','memory_limit_mib','wall_time_limit_seconds')){
        if($resources[$name] -isnot [long] -and $resources[$name] -isnot [int]){throw "resources.$name must be an integer"}
    }
    if($resources.threads -lt 1 -or $resources.threads -gt 2 -or $resources.memory_limit_mib -lt 128 -or $resources.memory_limit_mib -gt 4096 -or $resources.wall_time_limit_seconds -lt 1 -or $resources.wall_time_limit_seconds -gt 900){throw 'Resources exceed engineering candidate limits'}
    $hostRecord['original_request_sha256']=(Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $hostRecord['original_geometry_sha256']=(Get-FileHash -LiteralPath $geometry -Algorithm SHA256).Hash.ToLowerInvariant()
    $failureCode=40
    $snapshot=Join-Path (Join-Path $output '.inputs') $runId
    New-Item -ItemType Directory -Path $snapshot -Force|Out-Null
    Assert-UserMoleculePlainPath $snapshot
    [IO.File]::WriteAllBytes((Join-Path $snapshot 'request.json'),$bytes)
    $snapshotGeometry=Join-Path $snapshot $geometryName
    New-Item -ItemType Directory -Path (Split-Path -Parent $snapshotGeometry) -Force|Out-Null
    Copy-Item -LiteralPath $geometry -Destination $snapshotGeometry
    if((Get-FileHash -LiteralPath $snapshotGeometry).Hash.ToLowerInvariant() -ne $hostRecord.original_geometry_sha256){throw 'Geometry changed during snapshot; check again'}
    $identity=(Invoke-UserMoleculeDocker $engine @('image','inspect',$Image) $errorLog|ConvertFrom-Json)[0]
    if($identity.Config.Labels.'ai4orgchem.user-molecule.status' -ne 'engineering-only-compute-gated'){throw 'Use the new user-molecule candidate, not the legacy image'}
    $hostRecord.image_id=$identity.Id
    $hostRecord['runtime_build_commit']=$identity.Config.Labels.'org.opencontainers.image.revision'
    $hostRecord['science_commit']=$identity.Config.Labels.'ai4orgchem.source.commit'
    New-Item -ItemType Directory -Path $LockRoot -Force|Out-Null
    Assert-UserMoleculePlainPath $LockRoot
    if($Action -eq 'Compute'){
        if(-not $CheckRun){throw 'Compute requires -CheckRun'}
        $CheckRun=(Resolve-Path -LiteralPath $CheckRun).Path
        Assert-UserMoleculePlainPath $CheckRun
        $lock=[IO.File]::Open((Join-Path $LockRoot 'windows-quantum.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    }
    $memory="$($resources.memory_limit_mib)m"
    $args=@('create','--read-only','--network','none','--memory',$memory,'--memory-swap',$memory,
        '--cpus',"$($resources.threads)",'--cap-drop','ALL','--security-opt','no-new-privileges',
        '--user','10001:10001','--label',"ai4orgchem.user-molecule.run-id=$runId",
        '--mount',"type=bind,source=$snapshot,target=/input,readonly",
        '--mount',"type=bind,source=$run,target=/output",
        '--mount',"type=bind,source=$LockRoot,target=/locks",
        '--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
        '-e',"AI4ORGCHEM_IMAGE_ID=$($identity.Id)",'-e',"OMP_NUM_THREADS=$($resources.threads)",
        '-e',"OPENBLAS_NUM_THREADS=$($resources.threads)",'-e',"MKL_NUM_THREADS=$($resources.threads)")
    $runtimeArgs=@($Action.ToLowerInvariant(),'--request','/input/request.json','--output-dir','/output')
    if($Action -eq 'Compute'){$args+=@('--mount',"type=bind,source=$CheckRun,target=/check,readonly");$runtimeArgs+=@('--check-run','/check','--lock-root','/locks')}
    $args+=@($identity.Id)+$runtimeArgs
    $hostRecord['docker_executable']=$engine
    $hostRecord['container_create_arguments']=$args
    $hostRecord['runtime_arguments']=$runtimeArgs
    $hostRecord['input_snapshot_directory']=$snapshot
    Write-UserMoleculeJson (Join-Path $run 'host-execution.json') $hostRecord
    $containerId=Invoke-UserMoleculeDocker $engine $args $errorLog
    if($containerId -notmatch '^[a-f0-9]{64}$'){throw 'Docker did not return an actual container ID'}
    $hostRecord.container_id=$containerId;$hostRecord.status='CREATED'
    Write-UserMoleculeJson (Join-Path $run 'host-execution.json') $hostRecord
    Invoke-UserMoleculeDocker $engine @('start',$containerId) $errorLog|Out-Null
    $hostRecord.status='RUNNING';Write-UserMoleculeJson (Join-Path $run 'host-execution.json') $hostRecord
    $observed=Wait-UserMoleculeContainer $engine $containerId $runId $resources.wall_time_limit_seconds $CancelFile $errorLog
    $hostRecord['observation']=$observed
    $hostRecord.container_exit_code=$observed.container_exit_code;$hostRecord.oom_killed=$observed.oom_killed
    $hostRecord.termination_reason=$observed.reason
    $code=if($observed.reason -eq 'TIMEOUT'){50}elseif($observed.reason -eq 'CANCELLED'){60}elseif($observed.oom_killed){40}else{[int]$observed.container_exit_code}
    $hostRecord.status=if($code -eq 0){'COMPLETED'}elseif($code -eq 20){'BLOCKED'}else{'FAILED'}
}catch{
    $hostRecord.status='FAILED';$hostRecord['error']=$_.Exception.Message
    $hostRecord.termination_reason=if($failureCode -eq 10){'INVALID_INPUT'}else{'HOST_OR_ENGINE_ERROR'};$code=$failureCode
}finally{
    if($containerId -and $engine){
        try{
            $row=Get-UserMoleculeContainer $engine $containerId $runId $errorLog
            if($row.State.Running){Invoke-UserMoleculeDocker $engine @('stop','--time','2',$containerId) $errorLog|Out-Null;$hostRecord.termination_reason='INTERRUPTED'}
            $row=Get-UserMoleculeContainer $engine $containerId $runId $errorLog
            $hostRecord.container_exit_code=$row.State.ExitCode;$hostRecord.oom_killed=$row.State.OOMKilled
            Invoke-UserMoleculeDocker $engine @('logs',$containerId) $errorLog|Out-Null
            if(-not $KeepContainer){Invoke-UserMoleculeDocker $engine @('rm',$containerId) $errorLog|Out-Null;$removed=$true}
        }catch{$hostRecord['collection_error']=$_.Exception.Message;$hostRecord.termination_reason='UNKNOWN';$code=40}
    }
    if($lock){$lock.Dispose()}
    $hostRecord['container_removed']=$removed;$hostRecord.service_exit_code=$code
    $hostRecord['finished_utc']=[DateTime]::UtcNow.ToString('o')
    Write-UserMoleculeJson (Join-Path $run 'host-execution.json') $hostRecord
    Write-UserMoleculeManifest $run $hostRecord
    Write-Host "Status: $($hostRecord.status); exit: $code; records: $run"
}
exit $code
