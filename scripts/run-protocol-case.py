"""One bounded protocol-case container; bounded host supervision, no retries."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASKS = ("P03", "P04", "P05", "P06", "P07", "P08", "P09", "P10")
LABEL = "ai4orgchem.protocol.execution-id"
MEMORY_BYTES = 1073741824
WALL_SECONDS, STOP_SECONDS = 120, 100
STOP_GRACE_SECONDS, STOP_COMMAND_TIMEOUT_SECONDS, EVIDENCE_RESERVE_SECONDS = 18, 20, 5
SHA = re.compile(r"^[0-9a-f]{64}$")
IMAGE_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def host_git_identity():
    """Optional local checkout context; prepared byte-verified sources need no Git."""
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, timeout=5)
        value = result.stdout.decode("ascii").strip()
        if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value):
            return {"runtime_source_head": value, "status": "READ_ONLY_CURRENT_HEAD_NOT_IMAGE_BUILD_IDENTITY"}
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return {"runtime_source_head": None, "status": "NOT_AVAILABLE_PREPARED_SOURCE_HASHES_REMAIN_REQUIRED"}


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Missing, unsafe or oversized JSON evidence: " + str(path))
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("Nonfinite JSON evidence: " + value)
    value=json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    json.dumps(value,allow_nan=False)
    return value


def _source_api():
    from runtime.protocol_cases import verify_source, validate_contract
    return verify_source, lambda: digest(ROOT/'locks/protocol-cases-source.json'), validate_contract



def validate_directory(path, *, protected=None):
    """Reject reparse ancestry, ambiguous mount syntax and source overlap."""
    path = Path(path).absolute()
    if any(char in str(path) for char in (",", '"', "\n", "\r", "\0")):
        raise ValueError("Output/lock path cannot contain Docker mount delimiters")
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                raise ValueError("Output/lock ancestry contains a symlink or reparse point")
            if not parent.is_dir():
                raise ValueError("Output/lock ancestry is not a directory")
    resolved = path.resolve()
    roots = [ROOT, ROOT.parent / "science"] if protected is None else list(protected)
    if os.name == "nt" and protected is None:
        roots.append(Path(r"D:\AI4Science\AI4OrgChem"))
        roots.append(Path(r"D:\AI4Science\ai4orgchem-runtime"))
    for source in roots:
        source = Path(source).resolve()
        if resolved == source or resolved.is_relative_to(source) or source.is_relative_to(resolved):
            raise ValueError("Output/lock directory overlaps protected source")
    return resolved


def validate_image_record(record):
    required={'image_id','image_build_runtime_commit','source_lock_sha256','dependency_lock_sha256','base_image_id'}
    if not isinstance(record,dict) or not required <= set(record): raise ValueError('Complete protocol candidate identity required')
    for k in ('image_id','base_image_id'):
        if not IMAGE_SHA.fullmatch(str(record[k])): raise ValueError('Full immutable image ID required')
    if not re.fullmatch('[0-9a-f]{40}',str(record['image_build_runtime_commit'])): raise ValueError('Full build commit required')
    for k in ('source_lock_sha256','dependency_lock_sha256'):
        if not SHA.fullmatch(str(record[k])): raise ValueError('Full lock digest required')
    return record



def verify_image_inspection(value, record):
    validate_image_record(record)
    expected={'ai4orgchem.protocol.schema':'protocol-cases-v1','ai4orgchem.protocol.runtime-commit':record['image_build_runtime_commit'],
        'ai4orgchem.protocol.source-sha256':record['source_lock_sha256'],'ai4orgchem.protocol.dependency-sha256':record['dependency_lock_sha256'],
        'ai4orgchem.protocol.base-image-id':record['base_image_id']}
    if value.get('Id')!=record['image_id'] or value.get('Os')!='linux' or value.get('Architecture')!='amd64': raise ValueError('Image identity/platform differs')
    if any((value.get('Config',{}).get('Labels') or {}).get(k)!=v for k,v in expected.items()): raise ValueError('Build identity labels differ')



def build_contract(task, image, execution_id, *, now=None):
    from runtime.protocol_cases import verify_source, validate_contract, limits, SOURCE_LOCK, DEPENDENCY_LOCK
    verify_source(); validate_image_record(image)
    if digest(SOURCE_LOCK)!=image['source_lock_sha256'] or digest(DEPENDENCY_LOCK)!=image['dependency_lock_sha256']: raise ValueError('Host/source image locks differ')
    started=time.time() if now is None else now
    value={'schema':'protocol-case-execution-v1','case':task,'mode':MODE,'execution_id':execution_id,
           'runtime_commit':image['image_build_runtime_commit'],'source_lock_sha256':image['source_lock_sha256'],
           'dependency_lock_sha256':image['dependency_lock_sha256'],'resources':limits(MODE),'started_epoch':started,
           'stop_deadline_epoch':started+STOP_SECONDS,'hard_deadline_epoch':started+WALL_SECONDS}
    validate_contract(value); return value



class DockerCommands:
    def __init__(self, executable, output, *, clock=time.monotonic, executor=subprocess.run):
        self.executable, self.output, self.clock, self.executor = executable, Path(output), clock, executor
        self.hard_deadline = None
        self.commands = []

    def __call__(self, *arguments, timeout=10, allow_failure=False):
        if self.hard_deadline is not None:
            remaining = self.hard_deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError("Hard wall deadline exhausted through cleanup")
            timeout = min(timeout, remaining)
        if timeout <= 0:
            raise TimeoutError("No command budget remains")
        command = [self.executable, *map(str, arguments)]
        number = len(self.commands) + 1
        row = {"arguments": command, "utc": utc(), "requested_timeout_seconds": timeout}
        self.commands.append(row)
        try:
            result = self.executor(command, capture_output=True, timeout=timeout)
            row["exit_code"] = result.returncode
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            row["status"] = "COMMAND_TIMEOUT"
            stdout, stderr = error.stdout or b"", error.stderr or b""
            raise
        except Exception as error:
            row.update(status="COMMAND_FAILED", error=type(error).__name__ + ": " + str(error))
            stdout, stderr = b"", str(error).encode("utf-8")
            raise
        finally:
            (self.output / f"command-{number:03d}.stdout").write_bytes(stdout)
            (self.output / f"command-{number:03d}.stderr").write_bytes(stderr)
            save(self.output / "COMMANDS.json", self.commands)
        if result.returncode and not allow_failure:
            raise RuntimeError("Docker command failed; see retained command logs")
        return result


def verify_ownership(value, image_id, execution_id, container_id):
    if value.get("Id") != container_id or value.get("Image") != image_id or value.get("Config", {}).get("Labels", {}).get(LABEL) != execution_id:
        raise ValueError("Container ownership/image identity differs")


def verify_container(value, image_id, contract, container_id, contract_path, worker_output):
    verify_ownership(value, image_id, contract["execution_id"], container_id)
    config, host = value.get("Config", {}), value.get("HostConfig", {})
    if config.get("User") != "10001:10001" or host.get("ReadonlyRootfs") is not True or host.get("Privileged") is not False:
        raise ValueError("Non-root read-only nonprivileged container required")
    expected = {"Memory": MEMORY_BYTES, "MemorySwap": MEMORY_BYTES, "NanoCpus": contract["resources"]["cpus"] * 1000000000, "PidsLimit": 128, "NetworkMode": "none"}
    if any(type(host.get(key)) is not type(wanted) or host[key] != wanted for key, wanted in expected.items()):
        raise ValueError("Actual container resource/network limits differ")
    if "ALL" not in (host.get("CapDrop") or []) or host.get("CapAdd") or host.get("Devices") or host.get("DeviceRequests"):
        raise ValueError("Capability/device isolation differs")
    if not any(option in ("no-new-privileges", "no-new-privileges=true", "no-new-privileges:true") for option in (host.get("SecurityOpt") or [])):
        raise ValueError("No-new-privileges required")
    tmpfs = (host.get("Tmpfs") or {}).get("/tmp", "")
    if not all(option in tmpfs.split(",") for option in ("rw", "nosuid", "nodev", "size=536870912")):
        raise ValueError("Fixed writable scratch tmpfs required")
    expected_cmd = ["-B", "-m", "runtime.protocol_cases", "--task", contract["case"], "--contract", "/task-contract.json", "--output-dir", "/output"]
    if config.get("Entrypoint") != ["/opt/venv/bin/python"] or config.get("Cmd") != expected_cmd:
        raise ValueError("Fixed worker command differs")
    mounts = value.get("Mounts", [])
    expected_mounts = {"/task-contract.json": (Path(contract_path), False), "/output": (Path(worker_output), True)}
    if len(mounts) != 2 or {mount.get("Destination") for mount in mounts} != set(expected_mounts):
        raise ValueError("Only isolated contract and output mounts allowed")
    for mount in mounts:
        source, writable = expected_mounts[mount["Destination"]]
        # Docker Desktop may report Windows bind sources in its Linux /run/desktop
        # path form. Actual read/write identity is additionally bound by the receipt.
        actual_source = str(mount.get("Source", ""))
        normalized = str(source).replace("\\", "/")
        actual_normalized = actual_source.replace("\\", "/")
        equivalent = actual_normalized == normalized
        if os.name == "nt" and re.match(r"^[A-Za-z]:/", normalized):
            suffix = "/" + normalized[0].lower() + normalized[2:]
            equivalent = actual_normalized.casefold() == normalized.casefold() or actual_source.casefold() in {("/run/desktop/mnt/host" + suffix).casefold(), ("/host_mnt" + suffix).casefold()}
        if not equivalent or mount.get("Type") != "bind" or mount.get("RW") is not writable:
            raise ValueError("Actual protected/output bind mount differs")


def verify_worker_evidence(output, contract, contract_sha256):
    output=Path(output); receipt=read_json(output/'worker-receipt.json'); guard=read_json(output/'guard-receipt.json')
    if receipt.get('status')!='PASS_SCOPED_PROTOCOL_CASE' or receipt.get('worker_exit_code')!=0 or receipt.get('contract')!=contract or receipt.get('contract_sha256')!=contract_sha256:
        raise ValueError('Scoped worker PASS identity differs')
    if guard.get('status')!='PASS' or guard.get('closed') is not True or guard.get('restored_attributes_intact') is not True or guard.get('denied') or guard.get('changed'):
        raise ValueError('Held native audit not closed')
    for key,name in (('case_result_sha256','case-result.json'),('guard_receipt_sha256','guard-receipt.json'),('run_manifest_sha256','run-manifest.json')):
        if receipt.get(key)!=digest(output/name): raise ValueError('Output identity differs: '+name)
    result=read_json(output/'case-result.json')
    if result.get('status')!='PASS': raise ValueError('Scoped numerical result failed')
    if result.get('case')!=contract['case'] or result.get('execution_mode')!=contract['mode'] or result.get('runtime_protocol_id')!='runtime-'+contract['case'].lower()+'-bounded/0.1':
        raise ValueError('Saved result case/mode/protocol linkage differs')
    if guard.get('case')!=contract['case'] or guard.get('mode')!=contract['mode'] or receipt.get('scientific_counts')!=guard.get('counts'):
        raise ValueError('Observed audit linkage differs')
    from runtime.protocol_cases import SCF_CAPS,CUSTOM_CAPS
    expected={**{'scf_'+k:v for k,v in SCF_CAPS[contract['case']].items()},**CUSTOM_CAPS.get(contract['case'],{})} if contract['mode']=='live' else {}
    if contract['mode']=='live' and contract['case']=='P09': expected['stability']=1
    counts=guard.get('counts')
    if not isinstance(counts,dict) or any(counts.get(k,0)!=v for k,v in expected.items()): raise ValueError('Required actual dispatch counts differ')
    if contract['mode']!='live' and any(counts.values()): raise ValueError('Kernel in metadata/ledger mode')
    for k,v in counts.items():
        if type(v) is not int or v<0 or v>guard['caps'].get(k,0): raise ValueError('Actual dispatch outside frozen cap')
        if guard.get('outcomes',{}).get(k)!={'returned':v,'failed':0}: raise ValueError('Scientific dispatch did not all return')
    manifest=read_json(output/'run-manifest.json')
    required={'case-result.json','guard-receipt.json','resource-start.json','resource-end.json','native-events.jsonl'}
    hashes=manifest.get('files')
    if not isinstance(hashes,dict) or not required<=set(hashes): raise ValueError('Incomplete output manifest')
    for name,sha in hashes.items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name: raise ValueError('Unsafe manifest path')
        if digest(output/relative)!=sha: raise ValueError('Manifest changed: '+name)
    for name in ('resource-start.json','resource-end.json'):
        if read_json(output/name).get('status')!='PASS': raise ValueError('Resource closure differs')
    return {'status':'PASS_SCOPED_PROTOCOL_CASE_EVIDENCE','worker_receipt_sha256':digest(output/'worker-receipt.json'),
            'case_result_sha256':receipt['case_result_sha256'],'actual_dispatch_counts':counts,'mode':contract['mode']}



def stop_owned_container(docker, container_id, *, hard_deadline, clock=time.monotonic):
    remaining = hard_deadline - clock()
    usable = remaining - EVIDENCE_RESERVE_SECONDS
    if usable <= 2:
        raise TimeoutError("No safe stop/evidence window remains")
    grace = min(STOP_GRACE_SECONDS, max(0, int(usable) - 2))
    timeout = min(STOP_COMMAND_TIMEOUT_SECONDS, usable)
    docker("stop", "--time", str(grace), container_id, timeout=timeout)
    return {"grace_seconds": grace, "command_timeout_seconds": timeout, "remaining_before_stop_seconds": remaining, "evidence_reserve_seconds": EVIDENCE_RESERVE_SECONDS}


def create_command(image, contract, contract_path, output):
    return ["create", "--label", LABEL + "=" + contract["execution_id"], "--network", "none", "--read-only", "--user", "10001:10001", "--cpus", str(contract["resources"]["cpus"]), "--memory", str(MEMORY_BYTES), "--memory-swap", str(MEMORY_BYTES), "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912",
            "--env", "OMP_NUM_THREADS="+str(contract["resources"]["threads"]), "--env", "OPENBLAS_NUM_THREADS="+str(contract["resources"]["threads"]), "--env", "MKL_NUM_THREADS="+str(contract["resources"]["threads"]), "--env", "NUMEXPR_NUM_THREADS="+str(contract["resources"]["threads"]), "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={contract_path},target=/task-contract.json,readonly", "--mount", f"type=bind,source={output},target=/output", "--entrypoint", "/opt/venv/bin/python", image,
            "-B", "-m", "runtime.protocol_cases", "--task", contract["case"], "--contract", "/task-contract.json", "--output-dir", "/output"]


def _single_inspection(result):
    value = json.loads(result.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError("Exactly one actual Docker inspection required")
    return value[0]


def supervise(args, *, clock=time.monotonic, sleep=time.sleep, executor=subprocess.run):
    root = validate_directory(args.output_root)
    locks = validate_directory(args.lock_root or root / ".protocol-case-locks")
    root.mkdir(parents=True, exist_ok=True)
    locks.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    run = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.task + "-" + token)
    run.mkdir(exist_ok=False)
    output, contract_directory = run / "output", run / "contract"
    output.mkdir()
    contract_directory.mkdir()
    execution = {"schema_version": "protocol-case-host-execution-v1", "task": args.task, "execution_id": token, "status": "NOT_EXECUTED", "container_id": None, "worker_started": False, "container_removed": False, "wall_stop_requested": False, "automatic_retry": False, "old_root_diagnostic_budget_reused": False, "started_utc": utc(), "worker_output_directory": str(output), "scientific_actual_counts": None}
    lock, cid, docker, started = locks / "active.lock", None, None, None
    locked, code = False, 40
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"execution_id": token, "task": args.task}, handle)
        locked = True
        image_record = validate_image_record(read_json(ROOT / "validation/protocol-cases/candidate-image.json"))
        selected = args.image or image_record["image_id"]
        if selected != image_record["image_id"]:
            raise ValueError("Only the recorded immutable protocol-case image is allowed")
        docker = DockerCommands(args.docker_executable, run, clock=clock, executor=executor)
        image_inspection = _single_inspection(docker("image", "inspect", selected))
        save(run / "image-inspect.json", image_inspection)
        verify_image_inspection(image_inspection, image_record)
        local_git_context = host_git_identity()
        started = clock()
        contract = build_contract(args.task, image_record, token, now=time.time())
        docker.hard_deadline = started + WALL_SECONDS
        contract_path = contract_directory / "task-contract.json"
        save(contract_path, contract)
        contract_sha = digest(contract_path)
        execution.update(contract_sha256=contract_sha, contract=contract, image_id=selected, source_check="PASS_CRITICAL_SOURCE_BYTES", host_identity={**local_git_context, "source_scope": "CURRENT_CHECKED_CRITICAL_SOURCE_NOT_IMAGE_BUILD_COMMIT", "runtime_source_directory": str(ROOT)})
        command = create_command(selected, contract, contract_path, output)
        save(run / "launch-command.json", [args.docker_executable, *command])
        cid = docker(*command, timeout=10).stdout.decode().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise ValueError("Complete owned container ID required")
        execution.update(container_id=cid, status="RUNNING")
        created = _single_inspection(docker("inspect", cid, timeout=3))
        verify_container(created, selected, contract, cid, contract_path, output)
        save(run / "container-inspect-created.json", created)
        if clock() >= started + STOP_SECONDS:
            raise TimeoutError("Soft deadline reached before worker start")
        docker("start", cid, timeout=10)
        execution["worker_started"] = True
        last = None
        while True:
            soft_remaining = started + STOP_SECONDS - clock()
            if soft_remaining <= 0:
                if last is None:
                    raise TimeoutError("No owned inspection before soft deadline")
                execution["wall_stop_requested"] = True
                execution["stop_request"] = stop_owned_container(docker, cid, hard_deadline=docker.hard_deadline, clock=clock)
                break
            last = _single_inspection(docker("inspect", cid, timeout=min(3, soft_remaining)))
            verify_container(last, selected, contract, cid, contract_path, output)
            save(run / "container-inspect-running.json", last)
            if last.get("State", {}).get("Running") is False:
                break
            if last.get("State", {}).get("Running") is not True:
                raise ValueError("Unknown actual container running state")
            sleep(min(0.2, max(0, started + STOP_SECONDS - clock())))
        finished = _single_inspection(docker("inspect", cid, timeout=2))
        verify_container(finished, selected, contract, cid, contract_path, output)
        save(run / "container-inspect-finished.json", finished)
        logs = docker("logs", cid, timeout=2, allow_failure=True)
        (run / "container.stdout").write_bytes(logs.stdout)
        (run / "container.stderr").write_bytes(logs.stderr)
        if logs.returncode != 0:
            raise RuntimeError("Container stdout/stderr collection failed")
        state = finished["State"]
        execution.update(container_exit_code=state.get("ExitCode"), oom_killed=state.get("OOMKilled"))
        if execution["wall_stop_requested"]:
            raise TimeoutError("Stopped at soft deadline; not a completed fixed-case PASS")
        if state.get("Running") is not False or state.get("OOMKilled") is not False or type(state.get("ExitCode")) is not int or state["ExitCode"] != 0:
            execution["status"] = "FAILED_WORKER_PROCESS"
            code = 20
        else:
            execution["evidence_review"] = verify_worker_evidence(output, contract, contract_sha)
            execution["status"] = "PASS_PENDING_OWNED_CLEANUP"
            code = 0
    except (TimeoutError, subprocess.TimeoutExpired) as error:
        execution.update(status="FAILED_OR_UNKNOWN_TIMEOUT", error=type(error).__name__ + ": " + str(error))
        code = 50
    except Exception as error:
        execution.update(status="REFUSED_OR_FAILED_UNVERIFIED", error=type(error).__name__ + ": " + str(error))
        code = 40
    finally:
        if cid and docker is not None:
            try:
                current = _single_inspection(docker("inspect", cid, timeout=2))
                verify_ownership(current, execution["image_id"], token, cid)
                save(run / "container-inspect-before-removal.json", current)
                if current.get("State", {}).get("Running") is True:
                    execution["forced_cleanup_of_running_container"] = True
                    if code == 0:
                        code = 50
                    execution["status"] = "FAILED_OR_UNKNOWN_FORCED_CLEANUP"
                docker("rm", "--force", cid, timeout=3)
                absent = docker("inspect", cid, timeout=2, allow_failure=True)
                message = absent.stderr.decode("utf-8", "replace").lower()
                if absent.returncode != 1 or not any(text in message for text in ("no such object", "no such container")):
                    raise ValueError("Actual container removal not confirmed")
                execution["container_removed"] = True
                if code == 0:
                    after = verify_worker_evidence(output, contract, contract_sha)
                    if after != execution["evidence_review"]:
                        raise ValueError("Worker evidence changed after container deletion")
                    execution["post_removal_evidence_review"] = after
                    execution["scientific_actual_counts"] = after["actual_dispatch_counts"]
                    execution["output_persistence_check"] = "PASS_AFTER_ACTUAL_CONTAINER_REMOVAL"
            except Exception as error:
                execution["cleanup_error"] = type(error).__name__ + ": " + str(error)
                execution["status"] = "FAILED_OR_UNKNOWN_CLEANUP"
                if code == 0:
                    code = 40
        if locked:
            try:
                if read_json(lock).get("execution_id") != token:
                    raise ValueError("Owned lock identity changed")
                lock.unlink()
                execution["owned_lock_released"] = True
            except Exception as error:
                execution["lock_cleanup_error"] = type(error).__name__ + ": " + str(error)
                if code == 0:
                    code = 40
                execution["status"] = "FAILED_OR_UNKNOWN_LOCK_CLEANUP"
        if started is not None:
            execution["through_cleanup_wall_seconds"] = clock() - started
            if clock() > started + WALL_SECONDS:
                code, execution["status"] = 50, "FAILED_HARD_WALL_EXCEEDED"
        if code == 0 and execution["container_removed"] is True:
            execution["status"] = "PASS_SCOPED_PROTOCOL_CASE"
        execution.update(host_exit_code=code, ended_utc=utc())
        save(run / "host-execution.json", execution)
        files = {str(path.relative_to(run)).replace("\\", "/"): digest(path) for path in run.rglob("*") if path.is_file() and not path.is_symlink()}
        save(run / "host-run-manifest.json", {"schema_version": "protocol-case-host-manifest-v1", "task": args.task, "execution_id": token, "status": execution["status"], "host_exit_code": code, "output_sha256": files, "scope": "ONE_FIXED_CASE_EXECUTION_NOT_GENERAL_COMPUTE", "container_removed": execution["container_removed"]})
    return code, run, execution


def argument_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task',choices=TASKS,required=True);p.add_argument('--mode',choices=('ledger','preflight','live'),required=True)
    p.add_argument('--output-root',type=Path,required=True);p.add_argument('--budget',type=Path)
    p.add_argument('--image');p.add_argument('--docker-executable',default='docker');p.add_argument('--lock-root',type=Path)
    return p



def main(argv=None):
    global MODE,MEMORY_BYTES,WALL_SECONDS,STOP_SECONDS
    args=argument_parser().parse_args(argv);MODE=args.mode
    from runtime.protocol_cases import limits
    resource=limits(MODE);MEMORY_BYTES=resource['memory_bytes'];WALL_SECONDS=resource['hard_wall_seconds'];STOP_SECONDS=resource['soft_wall_seconds']
    if args.task=='P07' and MODE=='live': print('P07 is ledger-only',file=sys.stderr);return 40
    reservation=None
    try:
        if MODE=='live': reservation=reserve_batch(args)
        code,output,execution=supervise(args)
        if reservation is not None: settle_batch(args,reservation,execution,str(output))
    except Exception as error:
        print('Protocol-case host refused: '+str(error),file=sys.stderr);return 40
    print(json.dumps({'status':execution['status'],'exit_code':code,'records':str(output)},ensure_ascii=False));return code




MODE=None
def reserve_batch(args):
    if (ROOT/'validation/protocol-cases/native-admission-pause.json').exists():
        raise ValueError('New native launch paused while enumerated backend-entry coverage is repaired; no new reservation')
    if args.budget is None: raise ValueError('A new durable batch2 budget is mandatory for live mode')
    path=validate_directory(args.budget.parent)/args.budget.name
    if not path.is_file(): raise ValueError('Frozen batch2 budget must already exist')
    from runtime.user_molecule.acceptance_resources import _lock, _atomic_write
    with _lock(path.with_suffix('.lock')):
        value=read_json(path)
        if value.get('schema')!='protocol-case-batch2-budget-v1' or value.get('ceiling_seconds')!=6300 or value.get('one_attempt_per_case') is not True: raise ValueError('Independent batch2 budget contract differs')
        if args.task in value['attempts']: raise ValueError('This case already has a reservation; automatic retry forbidden')
        if any(v.get('state')=='RESERVED' for v in value['attempts'].values()): raise ValueError('An unresolved batch2 attempt remains; refuse concurrent launch')
        charged=sum(v['charged_seconds'] for v in value['attempts'].values())
        if charged+900>6300: raise ValueError('Batch2 wall budget exhausted')
        token=uuid.uuid4().hex
        value['attempts'][args.task]={'reservation':token,'state':'RESERVED','charged_seconds':900,'reserved_utc':utc()}
        _atomic_write(path,value);return token

def settle_batch(args,token,execution,output):
    from runtime.user_molecule.acceptance_resources import _lock,_atomic_write
    path=args.budget
    with _lock(path.with_suffix('.lock')):
        value=read_json(path);row=value['attempts'][args.task]
        if row['reservation']!=token or row['state']!='RESERVED': raise ValueError('Budget reservation identity differs')
        if execution.get('container_removed') is not True and execution.get('container_id') is not None: return
        wall=execution.get('through_cleanup_wall_seconds')
        row.update(state='SETTLED',charged_seconds=wall if type(wall) in (int,float) and 0<=wall<=900 else 900,
                   status=execution['status'],records=output,settled_utc=utc())
        _atomic_write(path,value)


if __name__ == "__main__":
    raise SystemExit(main())
