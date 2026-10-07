"""One fixed registered-case container; bounded host supervision, no retries."""
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

TASKS = ("p02-statistics", "p13-graph-ledger", "p01-orbital-density")
LABEL = "ai4orgchem.registered.execution-id"
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
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def _source_api():
    from runtime.registered_cases import verify_source, source_snapshot_sha256, validate_contract
    return verify_source, source_snapshot_sha256, validate_contract


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
    required = {"image_id", "image_build_runtime_commit", "source_snapshot_sha256", "dependency_lock_sha256", "base_image_id"}
    if not isinstance(record, dict) or not required <= set(record):
        raise ValueError("Complete registered image identity required")
    if not IMAGE_SHA.fullmatch(str(record["image_id"])) or not IMAGE_SHA.fullmatch(str(record["base_image_id"])):
        raise ValueError("Complete immutable image and base IDs required")
    if not re.fullmatch(r"[0-9a-f]{40}", str(record["image_build_runtime_commit"])):
        raise ValueError("Complete image build commit required")
    for key in ("source_snapshot_sha256", "dependency_lock_sha256"):
        if not SHA.fullmatch(str(record[key])):
            raise ValueError("Complete source/dependency digest required")
    return record


def verify_image_inspection(value, record):
    validate_image_record(record)
    expected = {
        "ai4orgchem.registered.schema": "fixed-registered-cases-v1",
        "ai4orgchem.registered.runtime-commit": record["image_build_runtime_commit"],
        "ai4orgchem.registered.source-sha256": record["source_snapshot_sha256"],
        "ai4orgchem.registered.dependency-sha256": record["dependency_lock_sha256"],
        "ai4orgchem.registered.base-image-id": record["base_image_id"],
    }
    if value.get("Id") != record["image_id"] or value.get("Os") != "linux" or value.get("Architecture") != "amd64":
        raise ValueError("Image ID/platform differs from candidate")
    labels = value.get("Config", {}).get("Labels") or {}
    if any(labels.get(key) != item for key, item in expected.items()):
        raise ValueError("Registered image labels differ from source/build/dependency identity")


def build_contract(task, image, execution_id, *, now=None):
    """A fixed-task CLI request never reuses the separate root diagnostic budget."""
    if task not in TASKS or not re.fullmatch(r"[0-9a-f]{32}", str(execution_id)):
        raise ValueError("Registered task and fresh execution identity required")
    verify_source, source_snapshot_sha256, validate_contract = _source_api()
    verify_source()
    image = validate_image_record(image)
    if source_snapshot_sha256() != image["source_snapshot_sha256"]:
        raise ValueError("Host critical source snapshot differs from image")
    if digest(ROOT / "locks/registered-cases-dependencies.json") != image["dependency_lock_sha256"]:
        raise ValueError("Host dependency lock differs from image")
    registry = read_json(ROOT / "configs/registered-cases-v1.json")
    entries = registry.get("tasks", registry.get("cases"))
    if isinstance(entries, list):
        spec = next((item for item in entries if item.get("task") == task or item.get("id") == task), None)
    elif isinstance(entries, dict):
        spec = entries.get(task)
    else:
        spec = None
    if not isinstance(spec, dict) or not isinstance(spec.get("protocol_id"), str):
        raise ValueError("Registered task protocol missing")
    started = time.time() if now is None else now
    if type(started) not in (int, float) or not (0 < started < 1e12):
        raise ValueError("Finite host start epoch required")
    authorized = task == "p01-orbital-density"
    limit = 1 if authorized else 0
    contract = {
        "schema": "registered-case-execution-v1", "task": task,
        "protocol_id": spec["protocol_id"], "scientific_execution_authorized": authorized,
        "runtime_commit": image["image_build_runtime_commit"],
        "source_snapshot_sha256": image["source_snapshot_sha256"],
        "dependency_lock_sha256": image["dependency_lock_sha256"],
        "execution_id": execution_id, "memory_limit_bytes": MEMORY_BYTES, "threads": 1,
        "maximum_processes": 1, "wall_time_limit_seconds": WALL_SECONDS, "stop_after_seconds": STOP_SECONDS,
        "started_epoch": started, "stop_deadline_epoch": started + STOP_SECONDS,
        "hard_deadline_epoch": started + WALL_SECONDS,
        "scf_kernel_call_limit": limit, "boys_kernel_call_limit": limit, "pipek_mezey_kernel_call_limit": limit,
    }
    if authorized:
        value = spec.get("p01_protocol_sha256", spec.get("protocol_sha256"))
        if not isinstance(value, str) or not SHA.fullmatch(value):
            raise ValueError("P01 original protocol SHA required")
        contract["p01_protocol_sha256"] = value
    validate_contract(contract)
    return contract


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
    expected = {"Memory": MEMORY_BYTES, "MemorySwap": MEMORY_BYTES, "NanoCpus": 1000000000, "PidsLimit": 128, "NetworkMode": "none"}
    if any(type(host.get(key)) is not type(wanted) or host[key] != wanted for key, wanted in expected.items()):
        raise ValueError("Actual container resource/network limits differ")
    if "ALL" not in (host.get("CapDrop") or []) or host.get("CapAdd") or host.get("Devices") or host.get("DeviceRequests"):
        raise ValueError("Capability/device isolation differs")
    if not any(option in ("no-new-privileges", "no-new-privileges=true", "no-new-privileges:true") for option in (host.get("SecurityOpt") or [])):
        raise ValueError("No-new-privileges required")
    tmpfs = (host.get("Tmpfs") or {}).get("/tmp", "")
    if not all(option in tmpfs.split(",") for option in ("rw", "nosuid", "nodev", "size=134217728")):
        raise ValueError("Fixed writable scratch tmpfs required")
    expected_cmd = ["-B", "-m", "runtime.registered_cases", "--task", contract["task"], "--contract", "/task-contract.json", "--output-dir", "/output"]
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
    output = Path(output)
    receipt = read_json(output / "worker-receipt.json")
    expected = {"status": "PASS_SCOPED_FIXED_CASE", "task": contract["task"], "execution_id": contract["execution_id"], "contract_sha256": contract_sha256,
                "source_snapshot_sha256": contract["source_snapshot_sha256"], "dependency_lock_sha256": contract["dependency_lock_sha256"], "runtime_commit": contract["runtime_commit"]}
    if any(receipt.get(key) != wanted for key, wanted in expected.items()):
        raise ValueError("Worker identity or scoped PASS receipt differs")
    if type(receipt.get("scientific_execution_authorized")) is not bool or receipt["scientific_execution_authorized"] is not contract["scientific_execution_authorized"]:
        raise ValueError("Worker scientific authorization declaration differs")
    if any(receipt.get(key) != "PASS" for key in ("source_check", "dependency_check", "resource_check", "guard_check", "persistence_check")):
        raise ValueError("Worker did not verify all source/resource/guard/persistence gates")
    limit = 1 if contract["scientific_execution_authorized"] else 0
    counters = {"new_conditional_NR_calls": 0, "actual_scf_kernel_calls": limit, "actual_boys_kernel_calls": limit, "actual_pipek_mezey_kernel_calls": limit, "worker_exit_code": 0}
    if any(type(receipt.get(key)) is not int or receipt[key] != wanted for key, wanted in counters.items()):
        raise ValueError("Actual worker dispatch counts are missing or outside fixed limits")
    guard_path = output / "guard-receipt.json"
    guard = read_json(guard_path)
    if guard.get("status") != "PASS" or guard.get("forbidden_attempts") != [] or guard.get("changed_guards") != []:
        raise ValueError("Held native guards did not pass")
    if guard.get("engine_kind") != "PINNED_PYSCF_MODULES" or any(guard.get(key) is not True for key in ("closed", "held_at_close", "restored_attributes_intact")):
        raise ValueError("Pinned real guards must be held at close and fully restored")
    outcomes = guard.get("call_outcomes")
    names = {"scf_kernel", "boys_kernel", "pipek_mezey_kernel"}
    if not isinstance(outcomes, dict) or set(outcomes) != names:
        raise ValueError("Observed native call outcomes are incomplete")
    for row in outcomes.values():
        if not isinstance(row, dict) or set(row) != {"returned", "failed"} or type(row["returned"]) is not int or type(row["failed"]) is not int or row["returned"] != limit or row["failed"] != 0:
            raise ValueError("Required native calls did not return cleanly")
    expected_counts = {"scf_kernel": limit, "boys_kernel": limit, "pipek_mezey_kernel": limit, "conditional_NR": 0}
    if not isinstance(guard.get("counts"), dict) or set(guard["counts"]) != set(expected_counts) or any(type(guard["counts"][key]) is not int or guard["counts"][key] != wanted for key, wanted in expected_counts.items()):
        raise ValueError("Guard counters disagree with task dispatch counts")
    operations = guard.get("guard_operations")
    if not isinstance(operations, list) or not operations or any(not isinstance(item, str) or not item for item in operations) or len(set(operations)) != len(operations):
        raise ValueError("Actual held guard operations must be recorded distinctly")
    if receipt.get("guard_receipt_sha256") != digest(guard_path):
        raise ValueError("Worker guard receipt hash differs")
    for key, file in (("case_result_sha256", "case/case-result.json"), ("case_report_sha256", "case/case-report.md")):
        if receipt.get(key) != digest(output / file):
            raise ValueError("Saved case output changed after worker receipt")
    case = read_json(output / "case/case-result.json")
    expected_status = "P01_FIXED_CONTROL_PASSED" if limit else "PASS"
    if case.get("status") != expected_status:
        raise ValueError("Case-specific numerical gate did not pass")
    from runtime.registered_cases import validate_case_result
    validate_case_result(case, contract)
    manifest = read_json(output / "run-manifest.json")
    if receipt.get("run_manifest_sha256") != digest(output / "run-manifest.json"):
        raise ValueError("Worker run manifest hash differs")
    hashes = manifest.get("output_sha256")
    required_files = {"case/case-result.json", "case/case-report.md", "guard-receipt.json", "resource-start.json", "resource-end.json"}
    if not isinstance(hashes, dict) or not required_files <= set(hashes):
        raise ValueError("Worker manifest does not bind mandatory actual evidence")
    if "worker-receipt.json" in hashes or "run-manifest.json" in hashes:
        raise ValueError("Worker evidence hash relationships must not be circular")
    for relative, expected_hash in hashes.items():
        path = Path(relative)
        if not isinstance(relative, str) or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative or not SHA.fullmatch(str(expected_hash)):
            raise ValueError("Unsafe manifest output identity")
        file = output / path
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(output.resolve()) or digest(file) != expected_hash:
            raise ValueError("Worker manifest output hash differs")
    for file in ("resource-start.json", "resource-end.json"):
        read_json(output / file)
    return {"status": "PASS_SCOPED_FIXED_CASE_EVIDENCE", "worker_receipt_sha256": digest(output / "worker-receipt.json"), "guard_receipt_sha256": digest(guard_path), "case_result_sha256": receipt["case_result_sha256"], "actual_dispatch_counts": guard["counts"], "source_native_scope": "FIXED_REGISTERED_TASK_ONLY_NOT_GENERAL_COMPUTE"}


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
    return ["create", "--label", LABEL + "=" + contract["execution_id"], "--network", "none", "--read-only", "--user", "10001:10001", "--cpus", "1", "--memory", str(MEMORY_BYTES), "--memory-swap", str(MEMORY_BYTES), "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=134217728",
            "--env", "OMP_NUM_THREADS=1", "--env", "OPENBLAS_NUM_THREADS=1", "--env", "MKL_NUM_THREADS=1", "--env", "NUMEXPR_NUM_THREADS=1", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={contract_path},target=/task-contract.json,readonly", "--mount", f"type=bind,source={output},target=/output", "--entrypoint", "/opt/venv/bin/python", image,
            "-B", "-m", "runtime.registered_cases", "--task", contract["task"], "--contract", "/task-contract.json", "--output-dir", "/output"]


def _single_inspection(result):
    value = json.loads(result.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError("Exactly one actual Docker inspection required")
    return value[0]


def supervise(args, *, clock=time.monotonic, sleep=time.sleep, executor=subprocess.run):
    root = validate_directory(args.output_root)
    locks = validate_directory(args.lock_root or root / ".registered-case-locks")
    root.mkdir(parents=True, exist_ok=True)
    locks.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    run = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.task + "-" + token)
    run.mkdir(exist_ok=False)
    output, contract_directory = run / "output", run / "contract"
    output.mkdir()
    contract_directory.mkdir()
    execution = {"schema_version": "registered-case-host-execution-v1", "task": args.task, "execution_id": token, "status": "NOT_EXECUTED", "container_id": None, "worker_started": False, "container_removed": False, "wall_stop_requested": False, "automatic_retry": False, "old_root_diagnostic_budget_reused": False, "started_utc": utc(), "worker_output_directory": str(output), "scientific_actual_counts": None}
    lock, cid, docker, started = locks / "active.lock", None, None, None
    locked, code = False, 40
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"execution_id": token, "task": args.task}, handle)
        locked = True
        image_record = validate_image_record(read_json(ROOT / "validation/registered-cases/candidate-image.json"))
        selected = args.image or image_record["image_id"]
        if selected != image_record["image_id"]:
            raise ValueError("Only the recorded immutable registered-case image is allowed")
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
            execution["status"] = "PASS_SCOPED_FIXED_CASE"
        execution.update(host_exit_code=code, ended_utc=utc())
        save(run / "host-execution.json", execution)
        files = {str(path.relative_to(run)).replace("\\", "/"): digest(path) for path in run.rglob("*") if path.is_file() and not path.is_symlink()}
        save(run / "host-run-manifest.json", {"schema_version": "registered-case-host-manifest-v1", "task": args.task, "execution_id": token, "status": execution["status"], "host_exit_code": code, "output_sha256": files, "scope": "ONE_FIXED_CASE_EXECUTION_NOT_GENERAL_COMPUTE", "container_removed": execution["container_removed"]})
    return code, run, execution


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--image")
    parser.add_argument("--docker-executable", default="docker")
    parser.add_argument("--lock-root", type=Path)
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    try:
        code, output, execution = supervise(args)
    except Exception as error:
        print("Registered-case host refused: " + str(error), file=sys.stderr)
        return 40
    print(json.dumps({"status": execution["status"], "exit_code": code, "records": str(output)}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
