#requires -Version 7.3
<# Simulated engine failure contract: run the actual host script with overridden
engine functions. This is not Docker, numerical, or scientific acceptance. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][string]$OutputRoot,
 [Parameter(Mandatory)][string]$PowerShell7
)
$ErrorActionPreference='Stop'
$runtime=Split-Path -Parent $PSScriptRoot
$output=[IO.Path]::GetFullPath($OutputRoot)
if(Test-Path -LiteralPath $output){throw 'Use a new host-failure-test evidence directory'}
if(-not (Test-Path -LiteralPath $PowerShell7 -PathType Leaf)){throw 'Provide an existing PowerShell 7 executable'}
New-Item -ItemType Directory -Path $output|Out-Null
$encoding=[Text.UTF8Encoding]::new($false)
function Save-TestJson([string]$Path,$Value){
    [IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 30)+"`n",$encoding)
}
$copiedScripts=Join-Path $output 'controlled scripts with spaces'
$fixture=Join-Path $output 'input fixture with spaces'
$checkRun=Join-Path $output 'controlled check run'
foreach($directory in @($copiedScripts,$fixture,$checkRun)){New-Item -ItemType Directory -Path $directory|Out-Null}
$copiedRun=Join-Path $copiedScripts 'run-user-molecule.ps1'
$copiedCommon=Join-Path $copiedScripts 'UserMolecule.Common.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run-user-molecule.ps1') -Destination $copiedRun
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'UserMolecule.Common.ps1') -Destination $copiedCommon
foreach($name in @('request.json','molecule.xyz')){
    Copy-Item -LiteralPath (Join-Path $runtime "examples/user-molecule/templates/$name") -Destination (Join-Path $fixture $name)
}
$overrides=@'

# ENGINE SIMULATION ONLY. No Process.Start or real Docker command is called.
$script:mockInspectCalls=0
function Add-MockEvent([string]$Event){
    [IO.File]::AppendAllText((Join-Path $PSScriptRoot 'mock-trace.log'),"SIMULATED: $Event`n",[Text.UTF8Encoding]::new($false))
}
function Get-Command {
    [CmdletBinding()]param([string]$Name)
    if($Name -ne 'docker.exe'){throw "Unexpected command discovery in engine simulation: $Name"}
    Add-MockEvent 'Get-Command docker.exe (fake Source; never executed)'
    return [pscustomobject]@{Source=(Join-Path $PSScriptRoot 'SIMULATED_NO_ENGINE.exe')}
}
function Invoke-UserMoleculeDocker([string]$Engine,[string[]]$Arguments,[string]$ErrorLog){
    Add-MockEvent ("Invoke boundary: "+$Arguments[0])
    [IO.File]::AppendAllText($ErrorLog,"SIMULATED engine boundary: $($Arguments[0])`n",[Text.UTF8Encoding]::new($false))
    switch($Arguments[0]){
        'image' {
            return ConvertTo-Json -Depth 6 -InputObject @(@{Id=('sha256:'+('d'*64));Config=@{Labels=@{
                'ai4orgchem.user-molecule.status'='engineering-only-compute-gated';
                'org.opencontainers.image.revision'=('c'*40);'ai4orgchem.source.commit'=('b'*40)}}})
        }
        'create' {return ('a'*64)}
        'start' {return ''}
        default {throw "Unexpected engine command in controlled simulation: $($Arguments[0])"}
    }
}
function Wait-UserMoleculeContainer([string]$Engine,[string]$Id,[string]$RunId,[int]$Seconds,[string]$CancelFile,[string]$ErrorLog){
    Add-MockEvent 'Wait boundary: simulated BLOCKED, container_exit_code=20'
    $script:mockRunId=$RunId
    $directory=Split-Path -Parent $ErrorLog
    Write-UserMoleculeJson (Join-Path $directory 'result.json') @{schema_version=1;
        execution_status='BLOCKED';comparison_available=$false;delta_hartree=$null;
        test_scope='SIMULATED ENGINE OUTPUT; NO SCIENTIFIC OR DOCKER ACCEPTANCE'}
    [IO.File]::WriteAllText((Join-Path $directory 'report.md'),"SIMULATED BLOCKED report; Docker and science NOT_EXECUTED.`n",[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $directory 'stdout.log'),"SIMULATED stdout retained.`n",[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $directory 'stderr.log'),"SIMULATED stderr retained.`n",[Text.UTF8Encoding]::new($false))
    return @{container_id=$Id;container_exit_code=20;oom_killed=$false;reason=$null;
        engine_error='';elapsed_seconds=0;limits=@{simulation_only=$true};mounts=@()}
}
function Get-UserMoleculeContainer([string]$Engine,[string]$Id,[string]$RunId,[string]$ErrorLog){
    if($Id -ne ('a'*64) -or $RunId -ne $script:mockRunId){throw 'Unexpected simulated container identity'}
    $script:mockInspectCalls++
    Add-MockEvent ("Inspect boundary: "+$script:mockInspectCalls)
    if($script:mockInspectCalls -eq 2){throw 'CONTROLLED COLLECTION FAILURE: second final inspection'}
    return [pscustomobject]@{State=[pscustomobject]@{Running=$false;ExitCode=20;OOMKilled=$false}}
}
'@
[IO.File]::AppendAllText($copiedCommon,$overrides,$encoding)
$runs=Join-Path $output 'runs'
$arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$copiedRun,'-Action','Compute',
    '-Image',('sha256:'+('d'*64)),'-Request',(Join-Path $fixture 'request.json'),
    '-CheckRun',$checkRun,'-OutputRoot',$runs,'-LockRoot',(Join-Path $output 'locks'))
$summary=[ordered]@{status='RUNNING';scope='HOST COLLECTION FAILURE SIMULATION ONLY';
    docker='NOT_EXECUTED';scientific_scf='NOT_EXECUTED';
    run_script_sha256=(Get-FileHash -LiteralPath $copiedRun -Algorithm SHA256).Hash.ToLowerInvariant();
    common_base_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'UserMolecule.Common.ps1') -Algorithm SHA256).Hash.ToLowerInvariant();
    common_with_overrides_sha256=(Get-FileHash -LiteralPath $copiedCommon -Algorithm SHA256).Hash.ToLowerInvariant();
    command=@($PowerShell7)+$arguments}
Save-TestJson (Join-Path $output 'summary.json') $summary
try{
    $info=[Diagnostics.ProcessStartInfo]::new($PowerShell7)
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    foreach($argument in $arguments){$info.ArgumentList.Add($argument)}
    $process=[Diagnostics.Process]::new();$process.StartInfo=$info
    try{
        if(-not $process.Start()){throw 'Controlled host process did not start'}
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(30000)){
            $process.Kill($true);$process.WaitForExit();throw 'Controlled host test timed out'
        }
        [IO.File]::WriteAllText((Join-Path $output 'host-stdout.log'),$stdout.GetAwaiter().GetResult(),$encoding)
        [IO.File]::WriteAllText((Join-Path $output 'host-stderr.log'),$stderr.GetAwaiter().GetResult(),$encoding)
        $summary['actual_process_exit_code']=$process.ExitCode
    }finally{$process.Dispose()}
    $directories=@(Get-ChildItem -LiteralPath $runs -Directory|Where-Object Name -ne '.inputs')
    if($directories.Count -ne 1){throw 'Expected one retained simulated host run'}
    $run=$directories[0].FullName
    $hostRecord=Get-Content -LiteralPath (Join-Path $run 'host-execution.json') -Raw|ConvertFrom-Json -AsHashtable
    $manifest=Get-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Raw|ConvertFrom-Json -AsHashtable
    $summary['run_directory']=$run;$summary['observed_host']=$hostRecord
    if($summary.actual_process_exit_code -ne 40 -or $hostRecord.status -ne 'FAILED' -or
        $hostRecord.service_exit_code -ne 40 -or $hostRecord.termination_reason -ne 'UNKNOWN' -or
        $hostRecord.container_exit_code -ne 20 -or $hostRecord.container_removed -ne $false -or
        $hostRecord.collection_error -notlike 'CONTROLLED COLLECTION FAILURE:*'){
        throw 'Collection failure did not preserve the required FAILED/40/UNKNOWN/container-20 state'
    }
    if(($hostRecord|ConvertTo-Json -Depth 30 -Compress) -cne ($manifest.host|ConvertTo-Json -Depth 30 -Compress)){
        throw 'Retained manifest host identity differs from host-execution.json'
    }
    $required=@('host-execution.json','result.json','report.md','stdout.log','stderr.log','docker-stderr.log')
    foreach($name in $required){if(-not $manifest.files.Contains($name)){throw "Retained output missing from manifest: $name"}}
    foreach($entry in $manifest.files.GetEnumerator()){
        $path=Join-Path $run $entry.Key
        if((Get-Item -LiteralPath $path).Length -ne $entry.Value.size_bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value.sha256){
            throw "Retained output changed or manifest is invalid: $($entry.Key)"
        }
    }
    $trace=Get-Content -LiteralPath (Join-Path $copiedScripts 'mock-trace.log')
    if(@($trace|Where-Object {$_ -like 'SIMULATED: Inspect boundary:*'}).Count -ne 2){throw 'Expected the controlled second-inspection failure'}
    foreach($name in @('request.json','molecule.xyz')){
        $snapshot=Join-Path $hostRecord.input_snapshot_directory $name
        if((Get-FileHash -LiteralPath $snapshot).Hash -cne (Get-FileHash -LiteralPath (Join-Path $fixture $name)).Hash){
            throw "Retained input snapshot differs: $name"
        }
    }
    if([IO.File]::ReadAllText((Join-Path $run 'report.md')) -cne "SIMULATED BLOCKED report; Docker and science NOT_EXECUTED.`n" -or
        [IO.File]::ReadAllText((Join-Path $run 'stdout.log')) -cne "SIMULATED stdout retained.`n" -or
        [IO.File]::ReadAllText((Join-Path $run 'stderr.log')) -cne "SIMULATED stderr retained.`n"){
        throw 'Previously generated simulated report or logs were lost'
    }
    $summary.status='PASS';$summary['manifest_files_verified']=$manifest.files.Count
    Write-Host 'PASS: simulated collection failure retained FAILED/40/UNKNOWN/container-20 and all outputs'
}catch{
    $summary.status='FAIL';$summary['error']=$_.Exception.Message
    throw
}finally{Save-TestJson (Join-Path $output 'summary.json') $summary}
