#requires -Version 7.3
[CmdletBinding()]
param([string] $Tag = 'ai4orgchem-runtime:candidate', [ValidateSet('wslc','docker')] [string] $Engine = 'wslc',
 [string]$PythonExecutable,[string]$ExpectedRuntimeCommit,[string]$ExpectedManifestSha256,[switch]$CheckOnly)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing = 'Standard'
$root = Get-RuntimeRoot
if ($Tag.StartsWith('-')) { throw 'Invalid image tag' }
if(Test-Path -LiteralPath (Join-Path $root 'SOURCE_IDENTITY.json')){
    if(-not $PythonExecutable){
        $pythonCommand=Get-Command python.exe -ErrorAction SilentlyContinue
        if($pythonCommand -and $pythonCommand.Source -notmatch '[\\/]WindowsApps[\\/]'){$PythonExecutable=$pythonCommand.Source}
        else{$PythonExecutable=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'}
    }
    if(-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)){throw 'Prepared-source verification requires an existing Python 3.12+ executable'}
    $pythonVersion=(& $PythonExecutable -B -c 'import sys; print(chr(46).join(map(str,sys.version_info[:3])))' | Out-String).Trim()
    if($LASTEXITCODE -ne 0 -or [version]$pythonVersion -lt [version]'3.12'){throw 'Prepared-source verification requires Python 3.12+'}
    $verifyArgs=@('-B',(Join-Path $PSScriptRoot 'prepare-runtime-source.py'),'verify','--source',$root)
    if($ExpectedRuntimeCommit){$verifyArgs+=@('--expected-commit',$ExpectedRuntimeCommit)}
    if($ExpectedManifestSha256){$verifyArgs+=@('--expected-manifest-sha256',$ExpectedManifestSha256)}
    $identityText=(& $PythonExecutable @verifyArgs | Out-String)
    if($LASTEXITCODE -ne 0){throw 'Prepared source byte/object verification failed; no engine accessed'}
    $sourceIdentity=$identityText | ConvertFrom-Json
    if($sourceIdentity.status -ne 'VERIFIED_PREPARED_SOURCE'){throw 'Unsupported prepared source identity'}
    $revision=$sourceIdentity.runtime_commit
    $sourceKind='VERIFIED_PREPARED_SOURCE'
}else{
    $gitTop=(& git -C $root rev-parse --show-toplevel | Out-String).Trim()
    if($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($gitTop) -ne [IO.Path]::GetFullPath($root)){throw 'Requires this runtime Git root or a verified project source snapshot'}
    $dirty = & git -C $root status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit reviewed runtime files before building an identified image' }
    $revision = (& git -C $root rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve runtime commit' }
    if($ExpectedRuntimeCommit -and $revision -ne $ExpectedRuntimeCommit){throw 'Git HEAD does not match independently pinned commit'}
    if($ExpectedManifestSha256){throw 'Manifest pin requires a prepared project snapshot'}
    $sourceKind='CLEAN_GIT_HEAD'
}
if($revision -notmatch '^([0-9a-f]{40}|[0-9a-f]{64})$'){throw 'Full verified runtime commit required'}
$lockHash = (Get-FileHash -LiteralPath (Join-Path $root 'locks/requirements-linux-amd64.txt') -Algorithm SHA256).Hash.ToLowerInvariant()
if($CheckOnly){
    [ordered]@{status='SOURCE_PREFLIGHT_PASS';runtime_commit=$revision;source_kind=$sourceKind;
        dependency_lock_sha256=$lockHash;image_build='NOT_EXECUTED';engine_access='NOT_EXECUTED';publisher_authenticated=$false;
        source_manifest_sha256=$(if($sourceKind -eq 'VERIFIED_PREPARED_SOURCE'){$sourceIdentity.source_manifest_sha256}else{$null});
        scope='LEGACY_FIXED_RUNTIME_DOCKERFILE_ONLY_NOT_USER_MOLECULE_IMAGE'} | ConvertTo-Json
    exit 0
}
$enginePath = Get-Engine $Engine
Assert-EngineOption $enginePath @('build') @('--file','--tag','--build-arg')
$arguments = @('build','--file',(Join-Path $root 'container/Dockerfile'),'--tag',$Tag,
    '--build-arg',"RUNTIME_COMMIT=$revision",'--build-arg',"DEPENDENCY_LOCK_SHA256=$lockHash",$root)
& $enginePath @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    if($sourceKind -eq 'VERIFIED_PREPARED_SOURCE'){
        $recordDirectory=Join-Path (Split-Path -Parent $root) ('runtime-build-records/'+[guid]::NewGuid().ToString('N'))
    }else{$recordDirectory=Join-Path $root '.build'}
    [IO.Directory]::CreateDirectory($recordDirectory) | Out-Null
    $identity = Get-ImageIdentity $enginePath $Tag
    $identity | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $recordDirectory 'image-inspect.json') -Encoding utf8
}
exit $exitCode
