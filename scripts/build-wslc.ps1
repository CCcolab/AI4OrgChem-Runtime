#requires -Version 7.3
[CmdletBinding()]
param([string] $Tag = 'ai4orgchem-runtime:candidate', [ValidateSet('wslc','docker')] [string] $Engine = 'wslc')
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing = 'Standard'
$root = Get-RuntimeRoot
$enginePath = Get-Engine $Engine
Assert-EngineOption $enginePath @('build') @('--file','--tag','--build-arg')
if ($Tag.StartsWith('-')) { throw 'Invalid image tag' }
$dirty = & git -C $root status --porcelain
if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit reviewed runtime files before building an identified image' }
$revision = (& git -C $root rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve runtime commit' }
$lockHash = (Get-FileHash -LiteralPath (Join-Path $root 'locks/requirements-linux-amd64.txt') -Algorithm SHA256).Hash.ToLowerInvariant()
$arguments = @('build','--file',(Join-Path $root 'container/Dockerfile'),'--tag',$Tag,
    '--build-arg',"RUNTIME_COMMIT=$revision",'--build-arg',"DEPENDENCY_LOCK_SHA256=$lockHash",$root)
& $enginePath @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    [IO.Directory]::CreateDirectory((Join-Path $root '.build')) | Out-Null
    $identity = Get-ImageIdentity $enginePath $Tag
    $identity | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $root '.build/image-inspect.json') -Encoding utf8
}
exit $exitCode
