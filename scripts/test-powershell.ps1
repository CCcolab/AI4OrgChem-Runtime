#requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)] [string] $OutputRoot)
. (Join-Path $PSScriptRoot 'Runtime.Common.ps1')
$count = 0
$root = Get-RuntimeRoot
foreach ($path in @('relative-path',[IO.Path]::GetPathRoot($root),$root,(Join-Path $root 'runs'),(Split-Path -Parent $root))) {
    $refused = $false
    try { Get-SafeDirectory $path | Out-Null } catch { $refused = $true }
    if (-not $refused) { throw "Unsafe mount was accepted: $path" }
    $count++
}
$target = Join-Path $OutputRoot ('path-test-' + [guid]::NewGuid().ToString('N') + ' 中文 space')
$resolved = Get-SafeDirectory $target
if (-not (Test-Path -LiteralPath $resolved)) { throw 'Unicode/space output failed' }
$count++
$errors = @()
foreach ($script in Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1') {
    $tokens=$null; $parseErrors=$null
    [System.Management.Automation.Language.Parser]::ParseFile($script.FullName,[ref]$tokens,[ref]$parseErrors) | Out-Null
    $errors += $parseErrors
}
if ($errors.Count) { throw ($errors | Out-String) }
$count++
@{status='PASS';checks=$count;scope='PowerShell AST and path safety; no Docker or scientific commands executed'} | ConvertTo-Json
