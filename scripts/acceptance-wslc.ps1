#requires -Version 7.3
[CmdletBinding()]
param([string] $Image, [Parameter(Mandatory)] [string] $OutputRoot)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing = 'Standard'
$output = Get-SafeDirectory $OutputRoot
$probeDir = Join-Path $output ('acceptance-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($probeDir) | Out-Null
& (Join-Path $PSScriptRoot 'probe-wslc.ps1') -OutputDirectory $probeDir
$record = [ordered]@{ status='NOT_EXECUTED'; checks=@(); notes=@('Advanced scientific runs and GHCR availability require separate target-host execution.') }
$enginePath = Get-Command wslc.exe -ErrorAction SilentlyContinue
if (-not $enginePath -or -not $Image) {
    $record.reason = 'wslc.exe or candidate image not supplied'
    $record | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $probeDir 'acceptance.json') -Encoding utf8
    exit 2
}
$identity = Get-ImageIdentity $enginePath.Source $Image
Assert-EngineOption $enginePath.Source @('run') @('--mount','--entrypoint','--rm')
$unicodeOutput = Get-SafeDirectory (Join-Path $probeDir '带空格 output')
$readonly = Join-Path $probeDir 'readonly-input'
[IO.Directory]::CreateDirectory($readonly) | Out-Null
[IO.File]::WriteAllText((Join-Path $readonly 'token.txt'),'ai4orgchem-readonly-probe')
$probeArguments = @('run','--rm','--mount',"type=bind,source=$unicodeOutput,target=/work",
    '--mount',"type=bind,source=$readonly,target=/probe-readonly,readonly",'--entrypoint','/opt/venv/bin/python',
    $identity.Id,'-m','runtime.platform_probe','--readonly-file','/probe-readonly/token.txt')
& $enginePath.Source @probeArguments 1> (Join-Path $probeDir 'mount-stdout.log') 2> (Join-Path $probeDir 'mount-stderr.log')
$code = $LASTEXITCODE
$persisted = @(Get-ChildItem -LiteralPath $unicodeOutput -Filter 'platform-probe-*.json')
$record.checks += @{name='non-root-readonly-unicode-mount-persistence';status=$(if($code -eq 0 -and $persisted.Count -eq 1){'PASS'}else{'FAIL'});exit_code=$code}
& $enginePath.Source run --rm --entrypoint /opt/venv/bin/python $identity.Id -c 'import sys; sys.exit(37)'
$record.checks += @{name='exit-code-propagation';status=$(if($LASTEXITCODE -eq 37){'PASS'}else{'FAIL'});exit_code=$LASTEXITCODE}
# High-memory rejection must be demonstrated against a real resource limit.
$runHelp = (& $enginePath.Source run --help | Out-String)
if ($runHelp.Contains('--memory')) {
    $locks = Get-SafeDirectory (Join-Path $output '.host-locks')
    & $enginePath.Source run --rm --memory 256m --mount "type=bind,source=$unicodeOutput,target=/work" --mount "type=bind,source=$locks,target=/locks" $identity.Id run p14-fixed --lock-root /locks
    $record.checks += @{name='cgroup-low-memory-refusal';status=$(if($LASTEXITCODE -eq 3){'PASS'}else{'FAIL'});exit_code=$LASTEXITCODE}
} else { $record.checks += @{name='cgroup-low-memory-refusal';status='NOT_EXECUTED';reason='Installed CLI does not advertise --memory; check actual resource API separately'} }
foreach ($task in @('evidence','core-tests','p14-smoke')) {
    & (Join-Path $PSScriptRoot 'run-wslc.ps1') -Task $task -Image $identity.Id -OutputRoot $unicodeOutput
    $record.checks += @{name=$task;status=$(if($LASTEXITCODE -eq 0){'PASS'}else{'FAIL'});exit_code=$LASTEXITCODE}
}
$containerName = 'ai4orgchem-interrupt-' + [guid]::NewGuid().ToString('N')
$checkpoint = Join-Path $unicodeOutput 'stop-probe-checkpoint.json'
$stopArgs = @('run','-d','--name',$containerName,'--mount',"type=bind,source=$unicodeOutput,target=/work",
    '--entrypoint','/opt/venv/bin/python',$identity.Id,'-c',
    'import time; from pathlib import Path; Path("/work/stop-probe-checkpoint.json").write_text("synthetic-checkpoint"); time.sleep(120)')
& $enginePath.Source @stopArgs
$created = $LASTEXITCODE -eq 0
if ($created) {
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while (-not (Test-Path -LiteralPath $checkpoint) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }
    & $enginePath.Source container stop $containerName
    $stopCode = $LASTEXITCODE
    & $enginePath.Source container inspect $containerName 1> (Join-Path $probeDir 'stopped-container.json')
    $inspectCode = $LASTEXITCODE
    & $enginePath.Source container rm $containerName
    $removeCode = $LASTEXITCODE
    $record.checks += @{name='stop-and-checkpoint-after-delete';status=$(if($stopCode -eq 0 -and $inspectCode -eq 0 -and $removeCode -eq 0 -and (Test-Path -LiteralPath $checkpoint)){'PASS'}else{'FAIL'});synthetic=$true}
} else { $record.checks += @{name='stop-and-checkpoint-after-delete';status='FAIL';reason='probe container creation failed'} }
$record.status = if (@($record.checks | Where-Object {$_.status -eq 'FAIL'}).Count) {'FAIL'} else {'PASS'}
$record | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $probeDir 'acceptance.json') -Encoding utf8
# PASS covers only checks recorded as executed; it does not certify missing checks.
exit $(if($record.status -eq 'PASS'){0}else{1})
