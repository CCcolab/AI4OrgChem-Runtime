#requires -Version 7.3
<# Direct -File launcher contract tests. A controlled child replaces the runtime;
no Docker, scientific imports, dependency installation, or global settings. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][string]$OutputRoot,
 [Parameter(Mandatory)][string]$PowerShell7,
 [string]$WindowsPowerShell=(Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'),
 [int[]]$ExitCodes=@(0,1,10,20,30,40,50,60)
)
$ErrorActionPreference='Stop'
$launcher=Join-Path $PSScriptRoot 'start-user-molecule.ps1'
$output=[IO.Path]::GetFullPath($OutputRoot)
if(Test-Path -LiteralPath $output){throw 'Use a new launcher-test evidence directory'}
foreach($path in @($launcher,$PowerShell7,$WindowsPowerShell)){
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){throw "Required existing file missing: $path"}
}
New-Item -ItemType Directory -Path $output|Out-Null
$encoding=[Text.UTF8Encoding]::new($false)
function Save-TestJson([string]$Path,$Value){
    [IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 20)+"`n",$encoding)
}
$child=@'
#requires -Version 7.3
[CmdletBinding()]
param([string]$Action,[string]$Image,[string]$Request,[string]$CheckRun,[string]$RunDirectory,
 [string]$OutputRoot,[string]$LockRoot,[string]$CancelFile,[string]$PythonExecutable,
 [string]$ReportExportDirectory,[switch]$KeepContainer)
$ErrorActionPreference='Stop'
$case=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'stub-case.json') -Raw|ConvertFrom-Json
$receipt=[ordered]@{powershell_version=$PSVersionTable.PSVersion.ToString();parameters=[ordered]@{
 Action=$Action;Image=$Image;Request=$Request;CheckRun=$CheckRun;RunDirectory=$RunDirectory;
 OutputRoot=$OutputRoot;LockRoot=$LockRoot;CancelFile=$CancelFile;PythonExecutable=$PythonExecutable;
 ReportExportDirectory=$ReportExportDirectory;KeepContainer=[bool]$KeepContainer}}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'stub-receipt.json'),
 ($receipt|ConvertTo-Json -Depth 10)+"`n",[Text.UTF8Encoding]::new($false))
Write-Output "Controlled child exit: $($case.exit_code)"
exit ([int]$case.exit_code)
'@
$rows=[Collections.Generic.List[object]]::new()
$summary=[ordered]@{status='RUNNING';scope='Native -File launcher with controlled child; Docker and science NOT_EXECUTED';
 launcher_sha256=(Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant();
 powershell7=$PowerShell7;windows_powershell=$WindowsPowerShell;tests=$rows}
try{
    foreach($hostCase in @(@{name='windows-powershell51';executable=$WindowsPowerShell},
                           @{name='powershell7';executable=$PowerShell7})){
        foreach($code in $ExitCodes){
            $name="$($hostCase.name)-exit-$code"
            $directory=Join-Path $output $name
            New-Item -ItemType Directory -Path $directory|Out-Null
            $copied=Join-Path $directory 'start-user-molecule.ps1'
            Copy-Item -LiteralPath $launcher -Destination $copied
            [IO.File]::WriteAllText((Join-Path $directory 'run-user-molecule.ps1'),$child,$encoding)
            Save-TestJson (Join-Path $directory 'stub-case.json') @{exit_code=$code}
            $expected=[ordered]@{Action=if($code -eq 20){'Compute'}elseif($code -eq 0 -or $code -eq 40){'Report'}else{'Check'};
                Image='sha256:controlled-launcher-stub';Request=(Join-Path $directory '输入 with spaces/request.json');
                CheckRun=(Join-Path $directory '检查 with spaces');RunDirectory=(Join-Path $directory '记录 with spaces');
                OutputRoot=(Join-Path $directory '输出 with spaces');LockRoot=(Join-Path $directory '锁 with spaces');
                CancelFile=(Join-Path $directory '取消 signal with spaces');KeepContainer=($code -ne 0);
                PythonExecutable=(Join-Path $directory 'Python with spaces/python.exe');
                ReportExportDirectory=(Join-Path $directory '导出 with spaces')}
            $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$copied,'-PowerShell7',$PowerShell7)
            foreach($key in $expected.Keys){
                if($key -eq 'KeepContainer'){if($expected[$key]){$arguments+='-KeepContainer'}}
                else{$arguments+=@("-$key",[string]$expected[$key])}
            }
            $info=[Diagnostics.ProcessStartInfo]::new($hostCase.executable)
            $info.UseShellExecute=$false;$info.CreateNoWindow=$true
            $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
            foreach($argument in $arguments){$info.ArgumentList.Add($argument)}
            $process=[Diagnostics.Process]::new();$process.StartInfo=$info
            try{
                if(-not $process.Start()){throw 'Launcher process did not start'}
                $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
                if(-not $process.WaitForExit(30000)){
                    $process.Kill($true);$process.WaitForExit();throw "Launcher test timed out: $name"
                }
                [IO.File]::WriteAllText((Join-Path $directory 'stdout.log'),$stdout.GetAwaiter().GetResult(),$encoding)
                [IO.File]::WriteAllText((Join-Path $directory 'stderr.log'),$stderr.GetAwaiter().GetResult(),$encoding)
                $actual=$process.ExitCode
            }finally{$process.Dispose()}
            $receipt=Get-Content -LiteralPath (Join-Path $directory 'stub-receipt.json') -Raw|ConvertFrom-Json -AsHashtable
            $mismatches=@($expected.Keys|Where-Object {$expected[$_] -cne $receipt.parameters[$_]})
            $passed=$actual -eq $code -and $mismatches.Count -eq 0 -and [version]$receipt.powershell_version -ge [version]'7.3'
            $row=[ordered]@{name=$name;status=if($passed){'PASS'}else{'FAIL'};expected_exit_code=$code;
                actual_exit_code=$actual;parameter_mismatches=$mismatches;child_powershell_version=$receipt.powershell_version;
                command=@($hostCase.executable)+$arguments;expected_parameters=$expected}
            $rows.Add($row);Save-TestJson (Join-Path $directory 'execution.json') $row
            Save-TestJson (Join-Path $output 'summary.json') $summary
            Write-Host "$name`: $($row.status) (actual exit $actual)"
            if(-not $passed){throw "Launcher contract failed: $name"}
        }
    }
    $summary.status='PASS'
}catch{
    $summary.status='FAIL';$summary['error']=$_.Exception.Message
    throw
}finally{
    $summary['test_count']=$rows.Count
    Save-TestJson (Join-Path $output 'summary.json') $summary
}
