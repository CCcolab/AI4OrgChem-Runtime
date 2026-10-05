# Bounded, non-scientific probes through the same host supervision helpers.
# No WSL changes, public network use, scientific SCF or unrelated container cleanup.
#requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)][string]$OutputRoot,[Parameter(Mandatory)][string]$Image,
 [string]$RuntimeRoot=(Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference='Stop'
$stage=[IO.Path]::GetFullPath($OutputRoot)
$runtime=$RuntimeRoot
. (Join-Path $runtime 'scripts/UserMolecule.Common.ps1')
New-Item -ItemType Directory -Path $stage -Force|Out-Null
$engine=(Get-Command docker.exe).Source
$root=Join-Path $stage 'platform-probes'
if(Test-Path -LiteralPath $root){throw 'Probe evidence already exists; no overwrite'}
New-Item -ItemType Directory -Path $root|Out-Null
$probeInput=Join-Path $root 'readonly-input';New-Item -ItemType Directory -Path $probeInput|Out-Null
[IO.File]::WriteAllText((Join-Path $probeInput 'molecule.xyz'),'Read-only probe fixture')
$isolation=@'
import os,json,socket,errno
from runtime.user_molecule.preflight import observations
assert os.getuid()==10001
blocked=[]
for path in ['/opt/runtime/runtime/user_molecule/input.py','/opt/ai4orgchem/software/src/ai4orgchem/qm/p09_conditional_scf.py','/input/molecule.xyz']:
    try:
        with open(path,'ab'): pass
    except OSError as e:
        assert e.errno in (errno.EACCES,errno.EROFS),str(e)
        blocked.append(path)
    else: raise AssertionError('write unexpectedly allowed: '+path)
s=socket.socket();s.settimeout(2)
try: s.connect(('1.1.1.1',443))
except OSError as e: network_error=str(e)
else: raise AssertionError('network unexpectedly available')
finally: s.close()
open('/output/probe-survives.txt','w').write('persisted after container deletion')
print(json.dumps({'uid':os.getuid(),'write_rejected':blocked,'network_error':network_error,'resources':observations()}))
'@
$sleep=@'
import time
open('/output/probe-survives.txt','w').write('written before timeout or cancellation')
time.sleep(30)
'@
$oom=@'
import time
open('/output/probe-survives.txt','w').write('written before bounded OOM')
blocks=[]
while True:
    blocks.append(bytearray(16*1024*1024))
    time.sleep(.05)
'@
$results=@()
foreach($spec in @(@{Name='isolation';Code=$isolation;Seconds=15},@{Name='timeout';Code=$sleep;Seconds=1},
                  @{Name='cancel';Code=$sleep;Seconds=15},@{Name='oom';Code=$oom;Seconds=15})){
    $directory=Join-Path $root $spec.Name;New-Item -ItemType Directory -Path $directory|Out-Null
    $runId='probe-'+$spec.Name+'-'+[Guid]::NewGuid().ToString('N')
    $errorLog=Join-Path $directory 'docker-stderr.log';$id=$null
    $record=@{run_id=$runId;probe=$spec.Name;image_id=$image;status='PREPARING';container_id=$null}
    Write-UserMoleculeJson (Join-Path $directory 'host-execution.json') $record
    try{
        $arguments=@('create','--read-only','--network','none','--memory','128m','--memory-swap','128m','--cpus','1',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--label',"ai4orgchem.user-molecule.run-id=$runId",'--mount',"type=bind,source=$directory,target=/output",
            '--mount',"type=bind,source=$probeInput,target=/input,readonly",'--entrypoint','python',$image,'-c',$spec.Code)
        $record['container_create_arguments']=$arguments
        $record['supervision_helper_sha256']=(Get-FileHash -LiteralPath (Join-Path $runtime 'scripts/UserMolecule.Common.ps1')).Hash.ToLowerInvariant()
        $id=Invoke-UserMoleculeDocker $engine $arguments $errorLog
        $record.container_id=$id;$record.status='CREATED'
        Write-UserMoleculeJson (Join-Path $directory 'host-execution.json') $record
        Invoke-UserMoleculeDocker $engine @('start',$id) $errorLog|Out-Null
        $cancel=$null
        if($spec.Name -eq 'cancel'){$cancel=Join-Path $directory 'cancel.signal';Start-Sleep -Milliseconds 500;[IO.File]::WriteAllText($cancel,'cancel only this run')}
        $observed=Wait-UserMoleculeContainer $engine $id $runId $spec.Seconds $cancel $errorLog
        $record['observation']=$observed
        $pass=switch($spec.Name){
            'isolation' {$observed.container_exit_code -eq 0}
            'timeout' {$observed.reason -eq 'TIMEOUT'}
            'cancel' {$observed.reason -eq 'CANCELLED'}
            'oom' {$observed.oom_killed -eq $true -and $observed.container_exit_code -ne 0}
        }
        Invoke-UserMoleculeDocker $engine @('logs',$id) $errorLog|Out-Null
        Invoke-UserMoleculeDocker $engine @('rm',$id) $errorLog|Out-Null
        $record['container_removed']=$true
        $record['persisted_output_exists']=Test-Path -LiteralPath (Join-Path $directory 'probe-survives.txt')
        $record.status=if($pass -and $record.persisted_output_exists){'PASS'}else{'FAIL'}
    }catch{$record.status='FAIL';$record['error']=$_.Exception.Message}
    finally{
        # Stop/remove only the exact ID with the matching ownership label.
        if($id -and -not $record.container_removed){
            try{$row=Get-UserMoleculeContainer $engine $id $runId $errorLog
                if($row.State.Running){Invoke-UserMoleculeDocker $engine @('stop','--time','2',$id) $errorLog|Out-Null}
                Invoke-UserMoleculeDocker $engine @('rm',$id) $errorLog|Out-Null
            }catch{$record['cleanup_error']=$_.Exception.Message}
        }
        Write-UserMoleculeJson (Join-Path $directory 'host-execution.json') $record
        Write-UserMoleculeManifest $directory $record
    }
    $results+=@{name=$spec.Name;status=$record.status;directory=$directory}
    Write-Output "$($spec.Name): $($record.status)"
}
Write-UserMoleculeJson (Join-Path $stage 'platform-probe-summary.json') @{image_id=$image;probes=$results;
    scope='New candidate container/host supervision only; numerical science NOT_EXECUTED'}
if($results.status -contains 'FAIL'){exit 1}
