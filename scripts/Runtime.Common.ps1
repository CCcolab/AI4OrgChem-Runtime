Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RuntimeRoot { Split-Path -Parent $PSScriptRoot }
function Get-Engine([string] $Name) {
    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if (-not $command) { throw "$Name unavailable; platform validation NOT_EXECUTED. No automatic global update." }
    $command.Source
}
function Assert-EngineOption([string] $Engine, [string[]] $Command, [string[]] $Options) {
    $helpText = (& $Engine @Command --help 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect engine help: $Command" }
    foreach ($option in $Options) {
        if (-not $helpText.Contains($option)) { throw "Installed engine does not advertise required option $option" }
    }
}
function Get-SafeDirectory([string] $Path) {
    if (-not [IO.Path]::IsPathRooted($Path)) { throw 'Use an absolute output path' }
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath -eq [IO.Path]::GetPathRoot($fullPath) -or $fullPath.Contains(',') -or $fullPath.Contains('"') -or $fullPath.Contains("`n")) {
        throw 'Refusing drive root or ambiguous mount path'
    }
    $runtimeRoot = Get-RuntimeRoot
    $upstream = Join-Path (Split-Path -Parent $runtimeRoot) 'AI4OrgChem'
    foreach ($protected in @($runtimeRoot, $upstream)) {
        if ($fullPath -eq $protected -or $fullPath.StartsWith($protected + '\', [StringComparison]::OrdinalIgnoreCase) -or
            $protected.StartsWith($fullPath.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Output/lock directory must be outside source repositories'
        }
    }
    $ancestor = $fullPath
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $entry = Get-Item -LiteralPath $ancestor -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing output paths through symlinks/junctions' }
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    [IO.Directory]::CreateDirectory($fullPath) | Out-Null
    $probe = Join-Path $fullPath ('.write-probe-' + [guid]::NewGuid().ToString('N'))
    [IO.File]::WriteAllText($probe, 'probe')
    [IO.File]::Delete($probe)
    $fullPath
}
function Get-ImageIdentity([string] $Engine, [string] $Image) {
    if ($Image.StartsWith('-')) { throw 'Invalid image reference' }
    $jsonText = (& $Engine image inspect $Image | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Image inspect failed; build or pull an image explicitly first' }
    $imageInfo = @($jsonText | ConvertFrom-Json)[0]
    $root = Get-RuntimeRoot
    $source = Get-Content -LiteralPath (Join-Path $root 'locks/source.lock.json') -Raw | ConvertFrom-Json
    $lockHash = (Get-FileHash -LiteralPath (Join-Path $root 'locks/requirements-linux-amd64.txt') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($imageInfo.Config.Labels.'ai4orgchem.source.commit' -ne $source.source_commit -or
        $imageInfo.Config.Labels.'ai4orgchem.dependency-lock.sha256' -ne $lockHash) { throw 'Image source/dependency identity does not match locks' }
    if ($imageInfo.Os -ne 'linux' -or $imageInfo.Architecture -ne 'amd64') { throw 'Requires linux/amd64 image' }
    if ($imageInfo.Config.User -ne '10001:10001') { throw 'Image must use the runtime non-root user' }
    $imageInfo
}
