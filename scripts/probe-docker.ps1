#requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)] [string] $OutputDirectory)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$PSNativeCommandArgumentPassing = 'Standard'
$output = Get-SafeDirectory $OutputDirectory
$record = [ordered]@{
    captured_utc=[DateTime]::UtcNow.ToString('o')
    windows=[Environment]::OSVersion.VersionString
    architecture=$env:PROCESSOR_ARCHITECTURE
    engine='docker'
    status='NOT_EXECUTED'
    checks=@()
    scientific_calls=0
    scope='Docker discovery and read-only CLI checks; not calculation or platform acceptance'
}
$command = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($command) {
    foreach ($arguments in @(@('version'),@('--help'),@('build','--help'),@('run','--help'),@('image','inspect','--help'),@('container','stop','--help'),@('info'))) {
        $label = ($arguments -join '-') -replace '[^a-zA-Z0-9-]',''
        & $command.Source @arguments 2>&1 | Out-File (Join-Path $output "$label.txt") -Encoding utf8
        $record.checks += @{command=($arguments -join ' ');exit_code=$LASTEXITCODE}
    }
    $record.status = if (@($record.checks | Where-Object {$_.exit_code -ne 0}).Count) {'PROBE_ERRORS_NOT_VALIDATED'} else {'PROBED_NOT_VALIDATED'}
} else { $record.reason = 'docker.exe not accessible in this terminal; no system change performed' }
$record | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $output 'docker-probe.json') -Encoding utf8
exit $(if (-not $command) {2} elseif ($record.status -eq 'PROBE_ERRORS_NOT_VALIDATED') {1} else {0})
