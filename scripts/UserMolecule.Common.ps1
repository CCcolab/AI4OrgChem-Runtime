#requires -Version 7.3
$ErrorActionPreference='Stop'
function Write-UserMoleculeJson([string]$Path,$Value){
    $temp=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
    [IO.File]::WriteAllText($temp,($Value|ConvertTo-Json -Depth 30)+"`n",[Text.UTF8Encoding]::new($false))
    [IO.File]::Move($temp,$Path,$true)
}
function Invoke-UserMoleculeDocker([string]$Engine,[string[]]$Arguments,[string]$ErrorLog){
    $info=[Diagnostics.ProcessStartInfo]::new($Engine)
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    foreach($argument in $Arguments){$info.ArgumentList.Add($argument)}
    $process=[Diagnostics.Process]::new();$process.StartInfo=$info
    if(-not $process.Start()){throw 'Docker CLI did not start'}
    $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
    if(-not $process.WaitForExit(15000)){
        $process.Kill($true);$process.WaitForExit()
        throw "Docker control command timed out: $($Arguments[0]); container state UNKNOWN"
    }
    $text=$stdout.GetAwaiter().GetResult();$errorText=$stderr.GetAwaiter().GetResult()
    [IO.File]::AppendAllText($ErrorLog,$errorText,[Text.UTF8Encoding]::new($false))
    if($Arguments[0] -eq 'logs'){
        $directory=Split-Path -Parent $ErrorLog
        [IO.File]::WriteAllText((Join-Path $directory 'stdout.log'),$text,[Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText((Join-Path $directory 'stderr.log'),$errorText,[Text.UTF8Encoding]::new($false))
    }
    $exitCode=$process.ExitCode;$process.Dispose()
    if($exitCode -ne 0){throw "Docker command failed ($exitCode): $($Arguments[0])"}
    return $text.Trim()
}
function Get-UserMoleculeContainer([string]$Engine,[string]$Id,[string]$RunId,[string]$ErrorLog){
    if($Id -notmatch '^[a-f0-9]{64}$'){throw 'Invalid saved container ID'}
    $row=(Invoke-UserMoleculeDocker $Engine @('inspect',$Id) $ErrorLog|ConvertFrom-Json)[0]
    if($row.Config.Labels.'ai4orgchem.user-molecule.run-id' -ne $RunId){throw 'Container ownership label differs'}
    return $row
}
function Wait-UserMoleculeContainer([string]$Engine,[string]$Id,[string]$RunId,[int]$Seconds,[string]$CancelFile,[string]$ErrorLog){
    $clock=[Diagnostics.Stopwatch]::StartNew()
    $reason=$null
    while($true){
        $row=Get-UserMoleculeContainer $Engine $Id $RunId $ErrorLog
        if(-not $row.State.Running){break}
        if($CancelFile -and (Test-Path -LiteralPath $CancelFile)){$reason='CANCELLED'}
        elseif($clock.Elapsed.TotalSeconds -ge $Seconds){$reason='TIMEOUT'}
        if($reason){
            Invoke-UserMoleculeDocker $Engine @('stop','--time','2',$Id) $ErrorLog|Out-Null
            $row=Get-UserMoleculeContainer $Engine $Id $RunId $ErrorLog
            if($row.State.Running){Invoke-UserMoleculeDocker $Engine @('kill',$Id) $ErrorLog|Out-Null}
            $row=Get-UserMoleculeContainer $Engine $Id $RunId $ErrorLog
            break
        }
        Start-Sleep -Milliseconds 500
    }
    return @{container_id=$Id;container_exit_code=$row.State.ExitCode;oom_killed=$row.State.OOMKilled;
        reason=$reason;engine_error=$row.State.Error;elapsed_seconds=$clock.Elapsed.TotalSeconds;
        limits=@{memory_bytes=$row.HostConfig.Memory;memory_swap_bytes=$row.HostConfig.MemorySwap;
            nano_cpus=$row.HostConfig.NanoCpus;network=$row.HostConfig.NetworkMode;readonly_rootfs=$row.HostConfig.ReadonlyRootfs;user=$row.Config.User};
        mounts=@($row.Mounts|Select-Object Type,Source,Destination,RW)}
}
function Write-UserMoleculeManifest([string]$Run,$HostRecord){
    $files=[ordered]@{}
    foreach($file in Get-ChildItem -LiteralPath $Run -File -Recurse){
        if($file.Name -eq 'run-manifest.json' -or $file.Name.EndsWith('.tmp')){continue}
        $relative=[IO.Path]::GetRelativePath($Run,$file.FullName).Replace('\','/')
        $files[$relative]=@{size_bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
    Write-UserMoleculeJson (Join-Path $Run 'run-manifest.json') @{schema_version=1;host=$HostRecord;files=$files}
}
function Assert-UserMoleculePlainPath([string]$Path){
    $item=Get-Item -LiteralPath $Path -Force
    while($null -ne $item){
        if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Input/output symlink or reparse point rejected'}
        $parent=Split-Path -Parent $item.FullName
        if(-not $parent -or $parent -eq $item.FullName){break}
        $item=Get-Item -LiteralPath $parent -Force
    }
}
