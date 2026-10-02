[CmdletBinding()]
param([Parameter(Mandatory)] [string] $OutputDirectory)
$ErrorActionPreference = 'Continue'
[IO.Directory]::CreateDirectory([IO.Path]::GetFullPath($OutputDirectory)) | Out-Null
$checks = @()
foreach ($name in @('wsl.exe','wslc.exe','container.exe','docker.exe','podman.exe','nerdctl.exe')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    $checks += @{name=$name;accessible=[bool]$command;path=$(if($command){$command.Source}else{'UNKNOWN'})}
}
$processes = @(Get-Process -Name 'Docker Desktop','com.docker.backend','dockerd','podman' -ErrorAction SilentlyContinue | Select-Object ProcessName)
$dockerExe = Get-Command docker.exe -ErrorAction SilentlyContinue
$clientConfig = Join-Path (Split-Path -Parent $PSScriptRoot) '.build/docker-diagnostic-config'
[IO.Directory]::CreateDirectory($clientConfig) | Out-Null
if ($dockerExe) {
    & $dockerExe.Source --config $clientConfig version 2>&1 | Out-File (Join-Path $OutputDirectory 'docker-default-version.txt') -Encoding utf8
    $checks += @{name='docker-default-engine';exit_code=$LASTEXITCODE}
    & $dockerExe.Source --config $clientConfig --host npipe:////./pipe/dockerDesktopLinuxEngine version 2>&1 | Out-File (Join-Path $OutputDirectory 'docker-desktop-linux-version.txt') -Encoding utf8
    $checks += @{name='docker-desktop-linux-engine';exit_code=$LASTEXITCODE}
    & $dockerExe.Source --config $clientConfig desktop status 2>&1 | Out-File (Join-Path $OutputDirectory 'docker-desktop-status.txt') -Encoding utf8
    $checks += @{name='docker-desktop-status';exit_code=$LASTEXITCODE}
}
$wslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
if ($wslExe) {
    & $wslExe.Source --version 2>&1 | Out-File (Join-Path $OutputDirectory 'wsl-version.txt') -Encoding utf8
    $checks += @{name='wsl-version';exit_code=$LASTEXITCODE}
    & $wslExe.Source --list --verbose 2>&1 | Out-File (Join-Path $OutputDirectory 'wsl-distributions.txt') -Encoding utf8
    $checks += @{name='wsl-distributions';exit_code=$LASTEXITCODE}
}
$records = @{captured_utc=[DateTime]::UtcNow.ToString('o');checks=$checks;container_processes=$processes;
    known_wslc_path_exists=(Test-Path -LiteralPath 'C:\Program Files\WSL\wslc.exe');
    docker_desktop_executable_exists=(Test-Path -LiteralPath 'C:\Program Files\Docker\Docker\Docker Desktop.exe');
    installed_wsl_packages=@(Get-AppxPackage '*WindowsSubsystemForLinux*' -ErrorAction SilentlyContinue | Select-Object Name,Version)}
$records | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $OutputDirectory 'tool-diagnostics.json') -Encoding utf8
