#requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Destination,
    [string]$Image='ai4orgchem-runtime:oci-candidate-20261002',
    [string]$RunsRoot)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing='Standard'
$root=Get-RuntimeRoot
if(-not $RunsRoot){$RunsRoot=Join-Path (Split-Path -Parent $root) 'ai4orgchem-runtime-runs'}
$dest=Get-SafeDirectory $Destination
$runs=(Resolve-Path -LiteralPath $RunsRoot).Path
if($dest -eq $runs -or $dest.StartsWith($runs+'\',[StringComparison]::OrdinalIgnoreCase) -or $runs.StartsWith($dest.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Backup destination must be separate from runs'}
if(@(Get-ChildItem -LiteralPath $dest -Force).Count){throw 'Use an empty backup directory'}
if(& git -C $root status --porcelain){throw 'Commit reviewed files before backup'}
$revision=(& git -C $root rev-parse HEAD | Out-String).Trim()
$engine=Get-Engine 'docker'
$identity=Get-ImageIdentity $engine $Image
$running=(& $engine container ls --quiet | Out-String).Trim()
if($LASTEXITCODE -ne 0 -or $running){throw 'Complete container runs before taking a consistent backup'}
Add-Type -AssemblyName System.IO.Compression
$fileHashes=@(Get-ChildItem -LiteralPath $runs -Recurse -File | Where-Object {-not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)} | ForEach-Object {
    @{path=$_.FullName.Substring($runs.Length+1).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$fileHashes | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $dest 'run-files.sha256.json') -Encoding utf8
& $engine image save --output (Join-Path $dest 'candidate-image.tar') $identity.Id
if($LASTEXITCODE -ne 0){throw 'Image save failed; partial backup retained'}
# Container-only /opt links cannot be stat'ed by Windows bsdtar. Preserve all
# result copies and original runs; recover source separately from the image.
$exclusions=@('*/classifier-view/configs','*/classifier-view/evidence')
# Windows bsdtar stat's invalid links before applying excludes. An explicit
# regular-file list prevents descending into those entries at all.
$archiveList=Join-Path $dest 'run-archive-files.txt'
$prefix=(Split-Path -Leaf $runs)+'/'
[IO.File]::WriteAllLines($archiveList,[string[]]@($fileHashes | ForEach-Object {$prefix+$_.path}),[Text.UTF8Encoding]::new($false))
$archive=[IO.Compression.ZipArchive]::new([IO.File]::Create((Join-Path $dest 'runs.zip')),[IO.Compression.ZipArchiveMode]::Create)
try {
    foreach($file in $fileHashes){
        $entry=$archive.CreateEntry($prefix+$file.path,[IO.Compression.CompressionLevel]::Optimal)
        $inputStream=[IO.File]::OpenRead((Join-Path $runs $file.path))
        $outputStream=$entry.Open()
        try {$inputStream.CopyTo($outputStream)}finally{$outputStream.Dispose();$inputStream.Dispose()}
    }
}finally{$archive.Dispose()}
$verify=[IO.Compression.ZipArchive]::new([IO.File]::OpenRead((Join-Path $dest 'runs.zip')),[IO.Compression.ZipArchiveMode]::Read)
try {if($verify.Entries.Count -ne $fileHashes.Count){throw 'Archive file count differs'}}finally{$verify.Dispose()}
& git -C $root bundle create (Join-Path $dest 'runtime-history.bundle') --all
if($LASTEXITCODE -ne 0){throw 'Git bundle failed'}
& git -C $root bundle verify (Join-Path $dest 'runtime-history.bundle') 1> (Join-Path $dest 'bundle-verify.log') 2>&1
if($LASTEXITCODE -ne 0){throw 'Git bundle verification failed'}
$snapshot=Join-Path $dest 'runtime-source.zip'
& git -C $root archive --format=zip --output $snapshot HEAD
if($LASTEXITCODE -ne 0){throw 'Source snapshot failed'}
$record=[ordered]@{date_utc=[DateTime]::UtcNow.ToString('o');runtime_repository_commit=$revision;
    image_id=$identity.Id;image_repo_digests=$identity.RepoDigests;image_runtime_commit=$identity.Config.Labels.'org.opencontainers.image.revision';
    image_tag_hint=$Image;runs_root=$runs;run_files=$fileHashes.Count;wslc='BLOCKED / NOT_EXECUTED';L4_resume_supported=$false;
    scope='Local backup only; upstream project and global scientific environments excluded';excluded_container_source_symlinks=$exclusions;files=@()}
foreach($f in Get-ChildItem -LiteralPath $dest -File){$record.files+=@{name=$f.Name;bytes=$f.Length;sha256=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}}
$record|ConvertTo-Json -Depth 8|Set-Content (Join-Path $dest 'backup-manifest.json') -Encoding utf8
Get-FileHash -LiteralPath (Join-Path $dest 'backup-manifest.json') -Algorithm SHA256 | Format-List | Out-File (Join-Path $dest 'backup-manifest.sha256.txt') -Encoding utf8
Write-Host "Backup complete: $dest"
