#requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RecordRoot,
    [switch]$Restart,
    [string]$Docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe',
    [string]$ProbeImage = 'sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc'
)
# Host maintenance only. No scientific source, WSL configuration or image changes.
$ErrorActionPreference = 'Stop'
$destinationRoot = [IO.Path]::GetFullPath($RecordRoot)
if (Test-Path -LiteralPath $destinationRoot) { throw 'Use a new record directory; records are never overwritten.' }
New-Item -ItemType Directory -Path $destinationRoot | Out-Null
$report = [ordered]@{
    schema='local-docker-known-socket-startup-v1'; status='CHECKING'; started_utc=[DateTime]::UtcNow.ToString('o')
    restart_requested=[bool]$Restart; scientific_calls=0; wsl_shutdown=$false; configuration_modified=$false
    images_deleted=@(); files_deleted=@(); moves=@(); vendor_root_cause='UNRESOLVED'; command_count=0
}
function Save-Report { $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $destinationRoot 'result.json') -Encoding utf8 }
function Invoke-Docker([string[]]$Arguments, [int]$TimeoutSeconds=30) {
    $report.command_count++
    $stem='{0:D3}' -f $report.command_count
    $entry=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');argv=@($Docker)+$Arguments;timeout_seconds=$TimeoutSeconds}
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$Docker; $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $process=[Diagnostics.Process]::new(); $process.StartInfo=$start
    try {
        if (-not $process.Start()) { throw 'Docker CLI did not start.' }
        $outTask=$process.StandardOutput.ReadToEndAsync(); $errTask=$process.StandardError.ReadToEndAsync()
        $finished=$process.WaitForExit($TimeoutSeconds*1000)
        if (-not $finished) { $process.Kill($true); $process.WaitForExit(); $entry.error='TIMEOUT' }
        $stdout=$outTask.GetAwaiter().GetResult(); $stderr=$errTask.GetAwaiter().GetResult()
        $stdout | Set-Content -LiteralPath (Join-Path $destinationRoot ($stem+'.stdout')) -Encoding utf8
        $stderr | Set-Content -LiteralPath (Join-Path $destinationRoot ($stem+'.stderr')) -Encoding utf8
        $entry.exit_code=$process.ExitCode; $entry.stdout=$stem+'.stdout'; $entry.stderr=$stem+'.stderr'
        return @{ExitCode=$process.ExitCode;Stdout=$stdout;Stderr=$stderr;TimedOut=(-not $finished)}
    } finally {
        $entry | ConvertTo-Json -Compress -Depth 6 | Add-Content -LiteralPath (Join-Path $destinationRoot 'commands.jsonl') -Encoding utf8
        $process.Dispose()
    }
}
function Require-Success($Result, [string]$Message) {
    if ($Result.TimedOut -or $Result.ExitCode -ne 0) { throw ($Message+': '+$Result.Stderr.Trim()) }
}
function Get-ImageIds {
    $images=Invoke-Docker @('image','ls','--no-trunc','--quiet')
    Require-Success $images 'Could not enumerate existing images'
    return @($images.Stdout -split '\r?\n' | Where-Object { $_ } | Sort-Object -Unique)
}
function Assert-NoActiveWork {
    $containers=Invoke-Docker @('ps','--quiet')
    Require-Success $containers 'Could not check active containers; refusing restart'
    if ($containers.Stdout.Trim()) { throw 'Active containers exist; refusing maintenance.' }
    # An unrelated Docker CLI may be creating work. Do not interrupt it.
    if (Get-Process -Name 'docker' -ErrorAction SilentlyContinue) { throw 'Another Docker CLI is running; refusing maintenance.' }
}
try {
    if (-not (Test-Path -LiteralPath $Docker -PathType Leaf)) { throw 'Docker CLI is missing.' }
    $before=Invoke-Docker @('info','--format','{{json .}}') 15
    $healthy=($before.ExitCode -eq 0 -and -not $before.TimedOut)
    $report.engine_healthy_before=$healthy
    if ($healthy -and -not $Restart) {
        $report.status='PASS_HEALTHY_ENGINE_NO_CHANGE'
    } else {
        if ($Restart -and -not $healthy) { throw 'Restart acceptance requires a healthy engine and known image/container inventory. Use the saved manual recovery procedure for a failed engine.' }
        $imagesBefore=@()
        if ($healthy) {
            Assert-NoActiveWork
            $imagesBefore=@(Get-ImageIds); $report.images_before=$imagesBefore
            $stop=Invoke-Docker @('desktop','stop') 60
            Require-Success $stop 'Normal Docker Desktop stop failed'
        }
        $deadline=[DateTime]::UtcNow.AddSeconds(60)
        while ((Get-Process -Name 'Docker Desktop','com.docker.backend','docker' -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Seconds 2 }
        if (Get-Process -Name 'Docker Desktop','com.docker.backend','docker' -ErrorAction SilentlyContinue) { throw 'Docker processes remain active; no socket directories moved.' }
        $localRoot=[IO.Path]::GetFullPath($env:LOCALAPPDATA)
        $targets=@(
            @{Path=(Join-Path $localRoot 'Docker\run'); Allowed=@('dockerInference','dockerEthernetVfkit','userAnalyticsOtlpHttp.sock')},
            @{Path=(Join-Path $localRoot 'docker-secrets-engine'); Allowed=@('engine.sock')}
        )
        # Validate BOTH complete directories before moving either. Unknown content refuses maintenance.
        foreach ($target in $targets) {
            $absolute=[IO.Path]::GetFullPath($target.Path)
            if (-not (Test-Path -LiteralPath $absolute)) { continue }
            $item=Get-Item -LiteralPath $absolute -Force
            if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.FullName -ne $absolute) { throw 'Unexpected socket directory boundary/type.' }
            $children=@(Get-ChildItem -LiteralPath $absolute -Force)
            foreach ($child in $children) {
                if ($child.Name -notin $target.Allowed -or $child.PSIsContainer -or $child.Length -ne 0 -or -not ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ('Unexpected socket directory content: '+$child.Name) }
            }
            if (-not $children.Count) { continue }
            $backup=[IO.Path]::GetFullPath($absolute+'.quarantine-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N'))
            if ((Split-Path -Parent $backup) -ne (Split-Path -Parent $absolute) -or (Test-Path -LiteralPath $backup)) { throw 'Quarantine destination boundary check failed.' }
            $report.moves+=@{source=$absolute;backup=$backup;children=@($children | Select-Object Name,Length,Attributes);completed=$false}
        }
        Save-Report
        foreach ($move in $report.moves) {
            Move-Item -LiteralPath $move.source -Destination $move.backup
            $move.completed=$true; Save-Report
            New-Item -ItemType Directory -Path $move.source | Out-Null
        }
        $start=Invoke-Docker @('desktop','start','--detach') 30
        Require-Success $start 'Docker Desktop start request failed'
        $deadline=[DateTime]::UtcNow.AddSeconds(180); $ready=$false
        while ([DateTime]::UtcNow -lt $deadline) {
            $info=Invoke-Docker @('info','--format','{{json .}}') 12
            if ($info.ExitCode -eq 0 -and -not $info.TimedOut) { $ready=$true; break }
            Start-Sleep -Seconds 3
        }
        if (-not $ready) { throw 'Docker engine did not become ready within 180 seconds.' }
        $report.engine_after=($info.Stdout | ConvertFrom-Json | Select-Object ServerVersion,MemTotal,NCPU,OperatingSystem)
        $imagesAfter=@(Get-ImageIds); $report.images_after=$imagesAfter
        if ($imagesBefore.Count -and @(Compare-Object $imagesBefore $imagesAfter).Count) { throw 'Existing image inventory changed during restart.' }
        $name='runtime-startup-probe-'+[Guid]::NewGuid().ToString('N')
        $report.probe_name=$name
        $code='import os,json; from pathlib import Path; print(json.dumps({"uid":os.getuid(),"source_readonly":bool(os.statvfs("/opt/runtime").f_flag & os.ST_RDONLY),"interfaces":sorted(p.name for p in Path("/sys/class/net").iterdir())}))'
        $probe=Invoke-Docker @('run','--pull','never','--rm','--name',$name,'--label','ai4orgchem.runtime.maintenance=known-socket-startup-v1','--network','none','--read-only','--user','10001:10001','--memory','134217728','--memory-swap','134217728','--cpus','1','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/opt/venv/bin/python',$ProbeImage,'-B','-c',$code) 30
        Require-Success $probe 'Standard-library-only health probe failed'
        $report.probe=$probe.Stdout | ConvertFrom-Json
        if ($report.probe.uid -ne 10001 -or -not $report.probe.source_readonly -or @($report.probe.interfaces).Count -ne 1 -or $report.probe.interfaces[0] -ne 'lo') { throw 'Health probe isolation checks failed.' }
        $removed=Invoke-Docker @('inspect',$name)
        if ($removed.ExitCode -ne 1 -or $removed.Stderr -notmatch 'No such (object|container)') { throw 'Health probe removal unconfirmed.' }
        $report.probe_removed=$true
        $report.status='PASS_SCOPED_STARTUP_MITIGATION_VENDOR_CAUSE_UNRESOLVED'
    }
} catch {
    $report.status='FAILED_OR_PARTIAL'; $report.error=$_.Exception.Message
    # On a timed-out probe, remove only this newly created, UUID-named and
    # labelled maintenance container; never inspect/remove arbitrary work.
    if ($report.Contains('probe_name')) {
        try {
            $own=Invoke-Docker @('inspect','--format','{{json .Config.Labels}}',$report.probe_name) 15
            if ($own.ExitCode -eq 0 -and -not $own.TimedOut) {
                $labels=$own.Stdout | ConvertFrom-Json
                if ($labels.'ai4orgchem.runtime.maintenance' -ne 'known-socket-startup-v1') { throw 'Probe ownership label did not match.' }
                $cleanup=Invoke-Docker @('rm','--force',$report.probe_name) 15
                Require-Success $cleanup 'Owned maintenance probe cleanup failed'
                $report.probe_failure_cleanup='OWNED_CONTAINER_REMOVED'
            } elseif ($own.ExitCode -eq 1 -and $own.Stderr -match 'No such (object|container)') {
                $report.probe_failure_cleanup='OWNED_CONTAINER_ALREADY_ABSENT'
            } else { throw 'Owned probe cleanup state could not be established.' }
        } catch { $report.probe_failure_cleanup='UNKNOWN'; $report.cleanup_error=$_.Exception.Message }
    }
} finally {
    $report.finished_utc=[DateTime]::UtcNow.ToString('o'); Save-Report
    $report | ConvertTo-Json -Depth 12
}
if ($report.status -eq 'FAILED_OR_PARTIAL') { exit 1 }
