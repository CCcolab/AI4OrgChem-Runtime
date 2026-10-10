"""Explicit new-installation entrypoint for one frozen supported service task.

Frozen scientific catalogs and candidate-image records remain separate from the
reviewed engineering overlays. The adapter changes candidate-record lookup only
after full installation verification. Worker protocols, resource limits, input
snapshots and numerical gates retain their scientific definitions; reviewed
host supervision and platform metadata have their own exact source binding.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("_installation_identity", ROOT / "scripts/register-installation.py")
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def adapt_launcher(launcher, record, preflight):
    original_read = launcher.read_json
    is_high_cost = record["service"] == "high-cost-cases"
    original_docker = launcher.DockerJournal if is_high_cost else launcher.DockerCommands
    candidate = (ROOT / "validation" / record["service"] / "candidate-image.json").resolve()
    def read(path):
        if Path(path).resolve() == candidate:
            return identity.legacy_record(record)
        return original_read(path)
    class InstalledDockerCommands(original_docker):
        def __init__(self, executable, output, **kwargs):
            super().__init__(executable, output, **kwargs)
            identity.save_new(Path(output) / "INSTALLATION_RECORD.json", record)
            if identity.digest(Path(output) / "INSTALLATION_RECORD.json") != preflight["installation_record_canonical_sha256"]:
                raise ValueError("Installation record snapshot differs from verified identity")
            identity.save_new(Path(output) / "INSTALLATION_PREFLIGHT.json", preflight)
    launcher.read_json = read
    if is_high_cost:
        # The preserved host still validates all 107 rows. These two constants
        # identify the independently validated new installation baseline only.
        launcher.BASE_SOURCE_SHA256 = record["source_snapshot_sha256"]
        launcher.BASE_IMAGE_ID = record["image_id"]
        launcher.DockerJournal = InstalledDockerCommands
    else:
        launcher.DockerCommands = InstalledDockerCommands
    return launcher


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installation-record", type=Path, required=True)
    parser.add_argument("--backend", choices=("docker",), default="docker")
    parser.add_argument("--task", required=True, choices=tuple(task for spec in identity.SERVICES.values() for task in spec["tasks"]))
    parser.add_argument("--mode", choices=("ledger", "preflight", "live"), default="live")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--budget", type=Path)
    parser.add_argument("--unit")
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--docker-executable", default="docker")
    parser.add_argument("--lock-root", type=Path)
    args = parser.parse_args(argv)
    try:
        # Validate paths before even the stdlib-only installation inventory container.
        preliminary = identity.read_json(args.installation_record)
        identity.validate_record(preliminary)
        if args.task not in preliminary["tasks"] or args.mode not in preliminary["modes"]:
            raise ValueError("Task/mode does not belong to this installation")
        if preliminary["service"] == "molecular-service" and args.request is None:
            raise ValueError("Molecular single-point requires its explicit request")
        if preliminary["service"] != "molecular-service" and args.request is not None:
            raise ValueError("Fixed protocol tasks cannot accept user molecule requests")
        if preliminary["service"] not in ("protocol-cases", "high-cost-cases") and args.budget is not None:
            raise ValueError("This task has no independent protocol budget argument")
        if preliminary["service"] != "high-cost-cases" and (args.unit is not None or args.inputs is not None):
            raise ValueError("Only a fixed high-cost state can accept unit/input receipts")
        launcher = identity.load_launcher(preliminary["service"])
        launcher.validate_directory(args.output_root)
        launcher.validate_directory(args.lock_root or args.output_root / ".molecular-service-locks")
        record, preflight = identity.verify_installation(args.installation_record, args.docker_executable)
        launcher = adapt_launcher(launcher, record, preflight)
        if record["service"] == "protocol-cases":
            # Same assignments as the preserved protocol launcher's main().
            launcher.MODE = args.mode
            from runtime.protocol_cases import limits
            resource = limits(args.mode)
            launcher.MEMORY_BYTES = resource["memory_bytes"]
            launcher.WALL_SECONDS = resource["hard_wall_seconds"]
            launcher.STOP_SECONDS = resource["soft_wall_seconds"]
            if args.task == "P07" and args.mode == "live":
                raise ValueError("P07 is ledger-only")
        args.image = record["image_id"]
        reservation = None
        if record["service"] == "protocol-cases" and args.mode == "live":
            reservation = launcher.reserve_batch(args)
        if record["service"] == "high-cost-cases":
            code, output, execution = launcher.run(args)
        else:
            code, output, execution = launcher.supervise(args)
        if reservation is not None:
            launcher.settle_batch(args, reservation, execution, str(output))
    except Exception as error:
        print(json.dumps({"status": "REFUSED_INSTALLED_RUNTIME", "error": str(error)}))
        return 40
    print(json.dumps({"status": execution["status"], "exit_code": code, "records": str(output),
                      "installation_status": record["status"], "installation_scientific_acceptance": "UNKNOWN"}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
