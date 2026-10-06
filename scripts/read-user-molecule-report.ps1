#requires -Version 7.3
# Read saved evidence only. Never starts Docker, computes, or changes the run.
[CmdletBinding()]
param([string]$RunDirectory,[string]$PythonExecutable,[string]$ReportExportDirectory)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'UserMolecule.Common.ps1')
try{
    if(-not $RunDirectory){throw 'Report requires -RunDirectory'}
    $root=(Resolve-Path -LiteralPath $RunDirectory -ErrorAction Stop).Path
    if(-not (Test-Path -LiteralPath $root -PathType Container)){throw 'Report requires a directory'}
    Assert-UserMoleculePlainPath $root
    if($PythonExecutable){
        $python=(Resolve-Path -LiteralPath $PythonExecutable -ErrorAction Stop).Path
        Assert-UserMoleculePlainPath $python
        $arguments=@('-B',(Join-Path $PSScriptRoot 'report-user-molecule.py'),'report','--run-directory',$root)
        if($ReportExportDirectory){$arguments+=@('--export-directory',$ReportExportDirectory)}
        & $python @arguments
        exit $LASTEXITCODE
    }
    if($ReportExportDirectory){throw 'Derived report export needs an existing ordinary Python executable via -PythonExecutable; no scientific libraries needed'}
    # Preserve the Python-free cached brief path, but verify all declared bytes
    # and present terminal errors before any cached Check text.
    $manifestName=if(Test-Path -LiteralPath (Join-Path $root 'run-manifest.json')){'run-manifest.json'}else{'manifest.json'}
    $manifestPath=Join-Path $root $manifestName
    if(-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'Saved run manifest missing; evidence UNVERIFIED. Full diagnostic mode is available with -PythonExecutable'}
    Assert-UserMoleculePlainPath $manifestPath
    if((Get-Item -LiteralPath $manifestPath).Length -gt 4194304){throw 'Report manifest exceeds 4 MiB'}
    $registry=Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8|ConvertFrom-Json -AsHashtable -Depth 64
    if($registry.files -isnot [System.Collections.IDictionary] -or $registry.files.Count -gt 10000){throw 'Invalid saved file registry'}
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach($entry in $registry.files.GetEnumerator()){
        $name=[string]$entry.Key
        if(-not $name -or $name -match '[:\x00-\x1f]' -or [IO.Path]::IsPathRooted($name) -or
            ($name -split '[\\/]') -contains '..' -or ($name -split '[\\/]') -contains '.' -or
            ($name -split '[\\/]') -contains '' -or -not $seen.Add($name.Replace('\','/'))){throw 'Unsafe or duplicate saved file path'}
        $path=[IO.Path]::GetFullPath((Join-Path $root $name))
        if(-not $path.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Saved path escapes run'}
        Assert-UserMoleculePlainPath $path
        $expected=$entry.Value
        if($expected.size_bytes -isnot [long] -and $expected.size_bytes -isnot [int]){throw 'Invalid saved file size'}
        if($expected.size_bytes -lt 0 -or $expected.sha256 -cnotmatch '^[0-9a-f]{64}$'){throw 'Invalid saved hash receipt'}
        $actual=Get-Item -LiteralPath $path -Force
        if($actual.PSIsContainer -or $actual.Length -ne $expected.size_bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.sha256){throw "Saved evidence byte mismatch: $name"}
    }
    function Read-Registered([string]$Name){
        $path=Join-Path $root $Name
        if(-not (Test-Path -LiteralPath $path -PathType Leaf)){return $null}
        if(-not $registry.files.Contains($Name)){throw "Read evidence is absent from manifest: $Name"}
        if((Get-Item -LiteralPath $path).Length -gt 4194304){throw 'Report JSON exceeds 4 MiB'}
        return Get-Content -LiteralPath $path -Raw -Encoding utf8|ConvertFrom-Json -AsHashtable -Depth 64
    }
    $hostRecord=Read-Registered 'host-execution.json'
    $errorRecord=Read-Registered 'error.json'
    $result=Read-Registered 'result.json'
    $preflight=Read-Registered 'preflight.json'
    Write-Output '# Saved user-molecule run (read only)'
    Write-Output "Manifest bytes: MATCHED ($($registry.files.Count) files); hashes do not certify scientific or method validity."
    Write-Output 'Report exit 0 means successful reading, not successful computation. Original records are unchanged.'
    if($hostRecord){
        Write-Output "Host status: $($hostRecord.status); service exit: $($hostRecord.service_exit_code); container exit: $($hostRecord.container_exit_code)"
        Write-Output "Termination reason: $($hostRecord.termination_reason); collection error: $($hostRecord.collection_error)"
    }
    if($errorRecord -or ($hostRecord -and ($hostRecord.status -in @('FAILED','BLOCKED') -or $hostRecord.collection_error))){
        if($errorRecord){Write-Output "Saved error: $($errorRecord.error_type): $($errorRecord.message); original exit: $($errorRecord.exit_code)"}
        Write-Output 'Failure/blocking records take precedence over a cached Check brief. Use -PythonExecutable for the full derived report.'
        exit 0
    }
    if($preflight){Write-Output "Input status: $($preflight.input_status); compute_eligible: $($preflight.compute_eligible); input validity does not grant method qualification."}
    if($result){
        Write-Output "Saved status: $($result.status); execution: $($result.execution_status); numerical: $($result.numerical_status); comparison_available: $($result.comparison_available)"
    }
    $brief=Join-Path $root 'report.md'
    if(Test-Path -LiteralPath $brief -PathType Leaf){
        if(-not $registry.files.Contains('report.md')){throw 'Cached brief is absent from saved manifest'}
        Write-Output 'The following is the original cached snapshot. Its historical blocking reasons do not update current acceptance or method status.'
        Get-Content -LiteralPath $brief -Encoding utf8
    }elseif($result -or $hostRecord -or $preflight){
        Write-Output 'No cached brief was generated. The raw status above is only a saved-record summary; full gate/identity reporting needs -PythonExecutable.'
    }else{throw 'No readable service, acceptance or host records found'}
    exit 0
}catch{
    Write-Error ('Report failed; original evidence unchanged: '+$_.Exception.Message) -ErrorAction Continue
    exit 40
}
