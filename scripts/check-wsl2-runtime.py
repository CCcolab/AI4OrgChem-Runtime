"""Read-only native WSL2 Check. This entry never grants Compute rights."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA = "native-wsl2-check-v1"
PACKAGES = ("pyscf", "numpy", "scipy", "geometric", "PyYAML", "jsonschema", "Pillow")
WORKER = Path(__file__).with_name("native-wsl2-check-worker.py")


class CheckFailure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_output(value):
    if isinstance(value, str):
        return value
    if value.startswith((b"\xff\xfe", b"\xfe\xff")):
        return value.decode("utf-16")
    return value.decode("utf-16-le" if b"\x00" in value else "utf-8-sig")


def run_command(argv, *, timeout, input_bytes=None, runner=subprocess.run):
    try:
        result = runner(argv, input=input_bytes, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise CheckFailure("wsl_unavailable", "WSL executable unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise CheckFailure("timeout", "Read-only Check command exceeded its deadline") from exc
    except OSError as exc:
        raise CheckFailure("command_unavailable", type(exc).__name__) from exc
    if result.returncode:
        # Do not echo arbitrary environment stderr or scan environment variables.
        raise CheckFailure("environment_unavailable", f"Check command exited {result.returncode}")
    try:
        return decode_output(result.stdout)
    except UnicodeError as exc:
        raise CheckFailure("invalid_output", "Check command returned invalid text encoding") from exc


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError("non-finite JSON value")
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    except (ValueError, TypeError) as exc:
        raise CheckFailure("invalid_json", "Worker returned invalid or ambiguous JSON") from exc


def validate_observation(data, args):
    if not isinstance(data, dict) or data.get("schema_version") != "native-wsl2-observation-v1":
        raise CheckFailure("invalid_json", "Unexpected worker schema")
    identity = data.get("environment_identity")
    if not isinstance(identity, dict) or identity.get("backend") != "native-wsl2" or identity.get("image_id") is not None:
        raise CheckFailure("invalid_json", "Worker must provide an independent native identity")
    if data.get("compute_enabled") is not False or data.get("qm_calls") != 0:
        raise CheckFailure("invalid_json", "Worker did not declare the Check-only boundary")
    if any(data.get(key) is not True for key in ("python_isolated", "bytecode_disabled", "user_site_disabled")):
        raise CheckFailure("environment_mismatch", "Worker Python isolation/bytecode flags are not active")
    if identity.get("python_executable") != args.python or identity.get("python_prefix") != str(Path(args.python).parent.parent).replace("\\", "/"):
        raise CheckFailure("environment_mismatch", "Python executable/prefix differs from the explicitly selected environment")
    if type(data.get("uid")) is not int or data["uid"] <= 0:
        raise CheckFailure("root_user_refused", "Native Check requires a non-root WSL user")
    if "microsoft" not in str(identity.get("kernel_release", "")).lower():
        raise CheckFailure("environment_mismatch", "Kernel does not identify WSL")
    packages = identity.get("packages")
    if not isinstance(packages, dict) or any(not isinstance(packages.get(p), dict) or not packages[p].get("version") for p in PACKAGES):
        raise CheckFailure("missing_package", "Required scientific package metadata is unavailable")
    memory = data.get("memory")
    if not isinstance(memory, dict) or any(type(memory.get(k)) is not int or memory[k] < 0 for k in ("MemTotal_bytes", "MemAvailable_bytes", "SwapTotal_bytes", "SwapFree_bytes")):
        raise CheckFailure("missing_memory_snapshot", "Required proc memory observation unavailable")
    sources = identity.get("source_files")
    if not isinstance(sources, list) or [x.get("path") for x in sources if isinstance(x, dict)] != args.source_file:
        raise CheckFailure("invalid_json", "Source observation differs from explicit arguments")
    if any(not isinstance(x.get("sha256"), str) or len(x["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in x["sha256"]) for x in sources):
        raise CheckFailure("source_unavailable", "Explicit source file identity unavailable")
    return data


def make_report(args, *, runner=subprocess.run, find_wsl=shutil.which):
    report = {"schema_version": SCHEMA, "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "backend": "native-wsl2", "action": args.action, "status": "FAIL", "image_id": None,
              "compute_enabled": False, "qm_calls": 0, "scientific_acceptance": "NOT_EXECUTED",
              "native_p12_compute": "NOT_IMPLEMENTED", "declaration_grants_execution_authorization": False}
    if args.action != "Check":
        report.update(status="REFUSED", error={"code": "compute_disabled", "message": "Native WSL2 supports read-only Check only; Compute is not implemented or authorized"})
        return report
    try:
        wsl = find_wsl("wsl.exe")
        if not wsl:
            raise CheckFailure("wsl_unavailable", "WSL executable unavailable")
        version = run_command([wsl, "--version"], timeout=args.timeout, runner=runner)
        inventory = run_command([wsl, "--list", "--verbose"], timeout=args.timeout, runner=runner)
        running = run_command([wsl, "--list", "--running", "--quiet"], timeout=args.timeout, runner=runner)
        was_running = args.distribution in [row.strip() for row in running.splitlines()]
        report["distribution_running_before_check"] = was_running
        if args.require_running and not was_running:
            raise CheckFailure("distribution_not_running", "Selected distribution is not running; this Check does not start it")
        found_v2 = any(row.lstrip().lstrip("*").strip().startswith(args.distribution + " ") and row.rsplit(None, 1)[-1] == "2" for row in inventory.splitlines())
        if not found_v2:
            raise CheckFailure("not_wsl2", "Selected distribution is not listed as WSL version 2")
        argv = [wsl, "--distribution", args.distribution, "--exec", "/usr/bin/env", "PYTHONNOUSERSITE=1", args.python, "-I", "-B", "-"]
        for path in args.source_file:
            argv.extend(["--source-file", path])
        raw = run_command(argv, timeout=args.timeout, input_bytes=WORKER.read_bytes(), runner=runner)
        observation = validate_observation(strict_json(raw), args)
        running_after = run_command([wsl, "--list", "--running", "--quiet"], timeout=args.timeout, runner=runner)
        report["distribution_running_after_check"] = args.distribution in [row.strip() for row in running_after.splitlines()]
        identity = observation["environment_identity"]
        identity.update(distribution=args.distribution, wsl_distribution_version=2, wsl_version_text=version.strip(),
                        checker_sha256=digest(__file__), worker_sha256=digest(WORKER))
        identity_bytes = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        report.update(status="PASS", environment_identity=identity,
                      environment_fingerprint_sha256=hashlib.sha256(identity_bytes).hexdigest(), observation=observation)
    except CheckFailure as exc:
        report["error"] = {"code": exc.code, "message": str(exc)}
    except (OSError, ValueError) as exc:
        report["error"] = {"code": "check_unavailable", "message": type(exc).__name__}
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("Check", "Compute"), default="Check")
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    parser.add_argument("--python", default="/home/cascade/micromamba/envs/ai4orgchem/bin/python")
    parser.add_argument("--source-file", action="append", default=[], help="Explicit Linux source path to hash without importing; repeatable")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--require-running", action="store_true", help="Refuse a stopped distribution instead of invoking its normal WSL startup")
    parser.add_argument("--record-dir", type=Path, help="New host directory for check.json; existing directories are refused")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 60:
        parser.error("--timeout must be finite, > 0 and <= 60 seconds")
    if not args.python.startswith("/") or any(not p.startswith("/") for p in args.source_file):
        parser.error("Python and source paths must be absolute Linux paths")
    if not args.distribution.strip() or "\x00" in args.distribution:
        parser.error("Invalid distribution name")
    if args.record_dir and (not args.record_dir.is_absolute() or args.record_dir.exists()):
        parser.error("--record-dir must be an absolute, new host directory")
    return args


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    report = make_report(args)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.record_dir:
        args.record_dir.mkdir(parents=True, exist_ok=False)
        (args.record_dir / "check.json").write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "PASS" else 2 if report["status"] == "REFUSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
