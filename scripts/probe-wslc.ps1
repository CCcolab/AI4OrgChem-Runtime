[CmdletBinding()]
param([Parameter(Mandatory)] [string] $OutputDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[IO.Directory]::CreateDirectory([IO.Path]::GetFullPath($OutputDirectory)) | Out-Null
$record = [ordered]@{ captured_utc=[DateTime]::UtcNow.ToString('o'); windows=[Environment]::OSVersion.VersionString; architecture=$env:PROCESSOR_ARCHITECTURE; status='NOT_EXECUTED'; checks=@() }
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if ($wsl) { & $wsl.Source --version 2>&1 | Out-File (Join-Path $OutputDirectory 'wsl-version.txt') -Encoding utf8 }
$command = Get-Command wslc.exe -ErrorAction SilentlyContinue
if ($command) {
    foreach ($arguments in @(@('version'),@('--help'),@('build','--help'),@('run','--help'),@('image','inspect','--help'),@('container','stop','--help'),@('system','info'))) {
        $label = ($arguments -join '-') -replace '[^a-zA-Z0-9-]',''
        & $command.Source @arguments 2>&1 | Out-File (Join-Path $OutputDirectory "$label.txt") -Encoding utf8
        $record.checks += @{command=($arguments -join ' ');exit_code=$LASTEXITCODE}
    }
    $record.status = 'PROBED_NOT_VALIDATED'
} else { $record.reason = 'wslc.exe not found; no global update performed' }
$record | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $OutputDirectory 'platform-probe.json') -Encoding utf8
