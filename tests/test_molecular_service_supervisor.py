"""Host-only synthetic Docker tests: no container, engine or scientific call."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-molecular-service.py"
SPEC = importlib.util.spec_from_file_location("molecular_supervisor_under_test", SCRIPT)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


class Clock:
    def __init__(self): self.value = 1000.0
    def __call__(self): return self.value
    def sleep(self, duration): self.value += duration


def image_record(source="1" * 64, dependency="2" * 64):
    return {"image_id": "sha256:" + "a" * 64, "image_build_runtime_commit": "b" * 40,
            "source_snapshot_sha256": source, "dependency_lock_sha256": dependency,
            "base_image_id": "sha256:" + "c" * 64}


def identity():
    return dict(request_sha256="3" * 64, structure_sha256="4" * 64,
                profile_sha256="5" * 64, input_manifest_sha256="6" * 64)


def contract_fixture():
    return {"schema": "molecular-service-execution-v1", "task": "single-point",
            "protocol_id": "ORDINARY_MOLECULAR_SINGLE_POINT_V0.1", "profile_id": "rhf-631gd-small-v1",
            "scientific_execution_authorized": True, "runtime_commit": "b" * 40,
            "source_snapshot_sha256": "1" * 64, "dependency_lock_sha256": "2" * 64,
            "execution_id": "d" * 32, "memory_limit_bytes": host.MEMORY_BYTES, "threads": 1,
            "maximum_processes": 1, "wall_time_limit_seconds": 120, "stop_after_seconds": 100,
            "started_epoch": 10000.0, "stop_deadline_epoch": 10100.0, "hard_deadline_epoch": 10120.0,
            "scf_kernel_call_limit": 1, "boys_kernel_call_limit": 0, "pipek_mezey_kernel_call_limit": 0,
            **identity()}


def worker_fixture(output, contract, contract_sha):
    """These fixture receipts do not assert any real science or guard execution."""
    output = Path(output)
    (output / "calculation").mkdir()
    (output / "calculation/report.md").write_text("Synthetic host test only.\n", encoding="utf-8")
    (output / "calculation/orbitals-density.npz").write_bytes(b"SYNTHETIC NOT NUMPY DATA")
    ledger = {"schema": "molecular-single-point-operation-ledger-v1", "execution_id": contract["execution_id"],
        "task": "single-point", "status": "CLOSED", "closure_reason": "NUMERICALLY_QUALIFIED_ORDINARY_RHF",
        "automatic_retry": False, "refund": False, "entry_evidence": "SYNTHETIC_HOST_FIXTURE_ONLY",
        "events": [], "operations": {"scf_kernel": {"limit": 1, "charged": 1, "entered": 1,
            "returned": 1, "failed": 0, "status": "SUCCEEDED"}}}
    host.save(output / "calculation/operation-ledger.json", ledger)
    host.save(output / "calculation/result.json", {"status": "NUMERICALLY_QUALIFIED_ORDINARY_RHF",
        "task": "single-point", "execution_id": contract["execution_id"], "operation_ledger": ledger,
        "array_artifact_sha256": host.digest(output / "calculation/orbitals-density.npz"),
        "test_scope": "SYNTHETIC_HOST_RECEIPT_ONLY_NOT_SCIENCE"})
    counts = dict(scf_kernel=1, boys_kernel=0, pipek_mezey_kernel=0, conditional_NR=0)
    host.save(output / "guard-receipt.json", {"status": "PASS", "counts": counts,
        "guard_operations": ["synthetic-operation"], "forbidden_attempts": [], "changed_guards": [],
        "engine_kind": "PINNED_PYSCF_MODULES", "closed": True, "held_at_close": True,
        "restored_attributes_intact": True, "call_outcomes": {name: {"returned": counts[name], "failed": 0}
        for name in ("scf_kernel", "boys_kernel", "pipek_mezey_kernel")}, "test_scope": "SYNTHETIC_NOT_REAL_GUARD"})
    for file in ("resource-start.json", "resource-end.json"):
        host.save(output / file, {"scope": "SYNTHETIC_ONLY"})
    receipt = {key: contract[key] for key in ("task", "execution_id", "runtime_commit", "source_snapshot_sha256",
        "dependency_lock_sha256", "scientific_execution_authorized", "request_sha256", "structure_sha256",
        "profile_sha256", "input_manifest_sha256")}
    receipt.update(status="PASS_SCOPED_MOLECULAR_SINGLE_POINT", contract_sha256=contract_sha,
        source_check="PASS", dependency_check="PASS", resource_check="PASS", guard_check="PASS",
        persistence_check="PASS", input_check="PASS", new_conditional_NR_calls=0, actual_scf_kernel_calls=1,
        actual_boys_kernel_calls=0, actual_pipek_mezey_kernel_calls=0, worker_exit_code=0,
        guard_receipt_sha256=host.digest(output / "guard-receipt.json"),
        result_sha256=host.digest(output / "calculation/result.json"),
        report_sha256=host.digest(output / "calculation/report.md"))
    host.save(output / "run-manifest.json", {"output_sha256": {
        path.relative_to(output).as_posix(): host.digest(path) for path in output.rglob("*") if path.is_file()}})
    receipt["run_manifest_sha256"] = host.digest(output / "run-manifest.json")
    host.save(output / "worker-receipt.json", receipt)


def parse_fixture(request_path, input_root=None):
    """Input fixture; the production parser has a separate real input suite."""
    request_path = Path(request_path)
    raw = request_path.read_bytes()
    structure_path = request_path.parent / "molecule.xyz"
    xyz = structure_path.read_bytes()
    return {"request_bytes": raw, "structure_bytes": xyz, "structure_file": "molecule.xyz",
        "request_sha256": hashlib.sha256(raw).hexdigest(), "structure_sha256": hashlib.sha256(xyz).hexdigest(),
        "profile_sha256": "5" * 64, "request_path": str(request_path.resolve()),
        "structure_path": str(structure_path.resolve()), "atom_count": 2, "electron_count": 2}


class FakeDocker:
    def __init__(self, image, clock, *, expire=False, foreign_cleanup=False, alter=None):
        self.image, self.clock, self.expire = image, clock, expire
        self.foreign_cleanup, self.alter = foreign_cleanup, alter
        self.calls, self.inspections = [], 0
        self.container_id, self.removed, self.running = "e" * 64, False, False

    def __call__(self, command, *, capture_output, timeout):
        args = command[1:]
        self.calls.append((list(args), timeout))
        stdout, stderr, code = b"", b"", 0
        if args[:2] == ["image", "inspect"]:
            labels = {"ai4orgchem.molecular.schema": "molecular-single-point-v1",
                "ai4orgchem.molecular.runtime-commit": self.image["image_build_runtime_commit"],
                "ai4orgchem.molecular.source-sha256": self.image["source_snapshot_sha256"],
                "ai4orgchem.molecular.dependency-sha256": self.image["dependency_lock_sha256"],
                "ai4orgchem.molecular.base-image-id": self.image["base_image_id"]}
            stdout = json.dumps([{"Id": self.image["image_id"], "Os": "linux", "Architecture": "amd64",
                "Config": {"Labels": labels}}]).encode()
        elif args[0] == "create":
            mounts = [args[index + 1] for index, item in enumerate(args) if item == "--mount"]
            def source(destination):
                item = next(row for row in mounts if "target=" + destination + "," in row or row.endswith("target=" + destination))
                return Path(item.split("source=", 1)[1].split(",target=", 1)[0])
            self.contract_path, self.output, self.input = source("/task-contract.json"), source("/output"), source("/input")
            self.contract = host.read_json(self.contract_path)
            self.token = self.contract["execution_id"]
            stdout = self.container_id.encode()
        elif args[0] == "start":
            self.running = self.expire
            if not self.expire:
                worker_fixture(self.output, self.contract, host.digest(self.contract_path))
        elif args[0] == "inspect":
            if self.removed:
                code, stderr = 1, b"Error: No such object: owned-molecular-test"
            else:
                self.inspections += 1
                value = self.inspection()
                if self.foreign_cleanup and self.inspections == 4:
                    value["Config"]["Labels"][host.LABEL] = "f" * 32
                stdout = json.dumps([value]).encode()
                if self.expire and self.running and self.inspections == 2:
                    self.clock.value += 100
        elif args[0] == "stop": self.running = False
        elif args[0] == "rm":
            self.removed = True
            if self.alter == "output-tamper": (self.output / "calculation/report.md").write_text("changed", encoding="utf-8")
            elif self.alter == "output-delete": (self.output / "guard-receipt.json").unlink()
            elif self.alter == "input-tamper": (self.input / "molecule.xyz").write_bytes(b"changed")
        elif args[0] != "logs": raise AssertionError("Unexpected simulated command: " + str(args))
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    def inspection(self):
        command = ["-B", "-m", "runtime.molecular_service", "--task", "single-point", "--request", "/input/request.json",
                   "--contract", "/task-contract.json", "--output-dir", "/output"]
        return {"Id": self.container_id, "Image": self.image["image_id"],
            "Config": {"User": "10001:10001", "Labels": {host.LABEL: self.token},
                       "Entrypoint": ["/opt/venv/bin/python"], "Cmd": command},
            "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "Memory": host.MEMORY_BYTES,
                "MemorySwap": host.MEMORY_BYTES, "NanoCpus": 1000000000, "PidsLimit": 128, "NetworkMode": "none",
                "CapDrop": ["ALL"], "CapAdd": [], "SecurityOpt": ["no-new-privileges"],
                "Tmpfs": {"/tmp": "rw,nosuid,nodev,size=134217728"}},
            "Mounts": [{"Type": "bind", "Source": str(self.contract_path), "Destination": "/task-contract.json", "RW": False},
                {"Type": "bind", "Source": str(self.output), "Destination": "/output", "RW": True},
                {"Type": "bind", "Source": str(self.input), "Destination": "/input", "RW": False}],
            "State": {"Running": self.running, "ExitCode": 137 if self.expire else 0, "OOMKilled": False}}


class MolecularServiceSupervisorTests(unittest.TestCase):
    def verify(self, output, contract, sha):
        with patch.object(host, "_validate_case_result", return_value=True):
            return host.verify_worker_evidence(output, contract, sha)

    def test_user_task_requires_request_without_proposition_number(self):
        args = host.argument_parser().parse_args(["--request", "r.json", "--output-root", "out"])
        self.assertEqual(args.task, "single-point")
        for task in ("Compute", "p01-orbital-density", "optimization"):
            with self.assertRaises(SystemExit):
                host.argument_parser().parse_args(["--task", task, "--request", "r.json", "--output-root", "out"])

    def test_valid_synthetic_receipt_requires_one_ordinary_kernel(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = contract_fixture()
            worker_fixture(tmp, contract, "9" * 64)
            self.assertEqual(self.verify(tmp, contract, "9" * 64)["actual_dispatch_counts"],
                dict(scf_kernel=1, boys_kernel=0, pipek_mezey_kernel=0, conditional_NR=0))

    def test_missing_boolean_counts_input_or_claim_only_pass_rejected(self):
        for field, value in [("actual_scf_kernel_calls", False), ("worker_exit_code", False),
            ("scientific_execution_authorized", 1), ("input_check", "NOT_EXECUTED"), ("structure_sha256", "0" * 64),
            ("resource_check", "NOT_EXECUTED"), ("actual_boys_kernel_calls", 1), ("new_conditional_NR_calls", 1)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                contract = contract_fixture()
                worker_fixture(tmp, contract, "9" * 64)
                receipt = host.read_json(Path(tmp) / "worker-receipt.json")
                receipt[field] = value
                host.save(Path(tmp) / "worker-receipt.json", receipt)
                with self.assertRaises(ValueError): self.verify(tmp, contract, "9" * 64)

    def test_guard_tamper_and_unobserved_calls_rejected(self):
        for field, value in [("changed_guards", ["replacement"]), ("closed", False),
            ("counts", dict(scf_kernel=1, boys_kernel=0, pipek_mezey_kernel=0, conditional_NR=1))]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                contract = contract_fixture()
                worker_fixture(tmp, contract, "9" * 64)
                guard = host.read_json(Path(tmp) / "guard-receipt.json")
                guard[field] = value
                host.save(Path(tmp) / "guard-receipt.json", guard)
                with self.assertRaises(ValueError): self.verify(tmp, contract, "9" * 64)

    def test_result_tamper_and_omitted_array_evidence_rejected(self):
        for alteration in ("tamper", "omit-array"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as tmp:
                output, contract = Path(tmp), contract_fixture()
                worker_fixture(output, contract, "9" * 64)
                if alteration == "tamper": (output / "calculation/report.md").write_text("changed", encoding="utf-8")
                else:
                    manifest = host.read_json(output / "run-manifest.json")
                    del manifest["output_sha256"]["calculation/orbitals-density.npz"]
                    host.save(output / "run-manifest.json", manifest)
                    receipt = host.read_json(output / "worker-receipt.json")
                    receipt["run_manifest_sha256"] = host.digest(output / "run-manifest.json")
                    host.save(output / "worker-receipt.json", receipt)
                with self.assertRaises(ValueError): self.verify(output, contract, "9" * 64)

    def test_rehashed_outer_manifest_cannot_hide_declared_array_or_ledger_drift(self):
        for alteration in ("array", "ledger"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as tmp:
                output, contract = Path(tmp), contract_fixture()
                worker_fixture(output, contract, "9" * 64)
                if alteration == "array":
                    artifact = output / "calculation/orbitals-density.npz"
                    artifact.write_bytes(b"CHANGED SYNTHETIC BYTES, NOT SCIENCE")
                else:
                    artifact = output / "calculation/operation-ledger.json"
                    ledger = host.read_json(artifact)
                    ledger["operations"]["scf_kernel"].update(returned=0, failed=1, status="FAILED")
                    host.save(artifact, ledger)
                # Even internally consistent outer hashes must not replace the
                # engine result's own artifact identity and closed operation.
                manifest = host.read_json(output / "run-manifest.json")
                manifest["output_sha256"][artifact.relative_to(output).as_posix()] = host.digest(artifact)
                host.save(output / "run-manifest.json", manifest)
                receipt = host.read_json(output / "worker-receipt.json")
                receipt["run_manifest_sha256"] = host.digest(output / "run-manifest.json")
                host.save(output / "worker-receipt.json", receipt)
                with self.assertRaises(ValueError): self.verify(output, contract, "9" * 64)

    def test_snapshot_preserves_raw_bytes_and_detects_extra_or_changed_input(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host, "_parse_request", side_effect=parse_fixture):
            source = Path(tmp) / "source"
            source.mkdir()
            raw, xyz = b'{"synthetic": true}\r\n', b'2\r\nSynthetic only\r\nH 0 0 0\r\nH 0 0 .74\r\n'
            (source / "request.json").write_bytes(raw)
            (source / "molecule.xyz").write_bytes(xyz)
            target = Path(tmp) / "snapshot"
            hashes = host.snapshot_input(source / "request.json", target)
            self.assertEqual((target / "request.json").read_bytes(), raw)
            self.assertEqual((target / "molecule.xyz").read_bytes(), xyz)
            (target / "extra.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Only the validated"): host.verify_input_snapshot(target, hashes)
            (target / "extra.txt").unlink()
            (target / "molecule.xyz").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "snapshot bytes"): host.verify_input_snapshot(target, hashes)

    def test_contract_source_identity_and_input_hashes_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "locks").mkdir()
            (root / "configs").mkdir()
            host.save(root / "locks/molecular-service-dependencies.json", {"fixture": True})
            host.save(root / "configs/molecular-service-v1.json", {"tasks": {"single-point": {
                "protocol_id": "ORDINARY_MOLECULAR_SINGLE_POINT_V0.1"}}})
            image = image_record(dependency=host.digest(root / "locks/molecular-service-dependencies.json"))
            captured = []
            api = (lambda: {"fixture": True}, lambda: "1" * 64, captured.append)
            with patch.object(host, "ROOT", root), patch.object(host, "_source_api", return_value=api):
                value = host.build_contract("single-point", image, "d" * 32, identity(), now=10000.0)
                self.assertEqual(value["structure_sha256"], "4" * 64)
                self.assertEqual((value["scf_kernel_call_limit"], value["boys_kernel_call_limit"]), (1, 0))
                self.assertEqual(value["hard_deadline_epoch"], 10120.0)
                self.assertEqual(captured, [value])
                with self.assertRaisesRegex(ValueError, "input identity"):
                    host.build_contract("single-point", image, "d" * 32, {}, now=10000.0)
                with self.assertRaisesRegex(ValueError, "source snapshot"):
                    host.build_contract("single-point", {**image, "source_snapshot_sha256": "0" * 64}, "d" * 32, identity())

    def test_commands_clamp_cleanup_and_stop_reserves_evidence(self):
        clock, observed = Clock(), []
        def execute(command, *, capture_output, timeout):
            observed.append(timeout)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with tempfile.TemporaryDirectory() as tmp:
            docker = host.DockerCommands("synthetic", tmp, clock=clock, executor=execute)
            docker.hard_deadline = clock() + .5
            docker("inspect", "fixture", timeout=20)
            self.assertEqual(observed, [.5])
            clock.value += .5
            with self.assertRaises(TimeoutError): docker("rm", "--force", "fixture")
        calls = []
        value = host.stop_owned_container(lambda *args, **kwargs: calls.append((args, kwargs)),
                                         "owned", hard_deadline=clock() + 20, clock=clock)
        self.assertEqual((value["grace_seconds"], value["command_timeout_seconds"]), (13, 15))

    def test_outputs_cannot_overlap_source_or_mount_delimiters(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            for path in (source / "output", Path(tmp), Path(tmp) / "unsafe,readonly"):
                with self.subTest(path=path), self.assertRaises(ValueError): host.validate_directory(path, protected=[source])

    def test_input_and_contract_cannot_alias_writable_output(self):
        args = host.create_command(image_record()["image_id"], contract_fixture(), Path("/fresh/contract/task-contract.json"),
                                  Path("/fresh/output"), Path("/fresh/input-snapshot"))
        mounts = [args[index + 1].replace("\\", "/") for index, arg in enumerate(args) if arg == "--mount"]
        self.assertIn("source=/fresh/input-snapshot,target=/input,readonly", mounts[2])
        self.assertIn("source=/fresh/contract/task-contract.json,target=/task-contract.json,readonly", mounts[0])
        self.assertIn("source=/fresh/output,target=/output", mounts[1])
        self.assertNotIn("--privileged", args)

    def lifecycle(self, tmp, **options):
        root = Path(tmp)
        source = root / "source"
        (source / "validation/molecular-service").mkdir(parents=True)
        image = image_record()
        host.save(source / "validation/molecular-service/candidate-image.json", image)
        inputs = root / "inputs"
        inputs.mkdir()
        (inputs / "request.json").write_bytes(b'{"synthetic": true}\n')
        (inputs / "molecule.xyz").write_bytes(b"2\nSynthetic only\nH 0 0 0\nH 0 0 .74\n")
        clock = Clock()
        docker = FakeDocker(image, clock, **options)
        args = host.argument_parser().parse_args(["--request", str(inputs / "request.json"), "--output-root", str(root / "runs")])
        def build(task, image_record, token, hashes, **kwargs): return {**contract_fixture(), **hashes, "execution_id": token}
        with patch.object(host, "ROOT", source), patch.object(host, "build_contract", side_effect=build), \
             patch.object(host, "_parse_request", side_effect=parse_fixture), \
             patch.object(host, "_validate_case_result", return_value=True), \
             patch.object(host, "host_git_identity", return_value={"runtime_source_head": None, "status": "SYNTHETIC"}):
            code, run, receipt = host.supervise(args, clock=clock, sleep=clock.sleep, executor=docker)
        return code, run, receipt, docker

    def test_nominal_synthetic_lifecycle_retains_outputs_and_inputs_after_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp)
            self.assertEqual(code, 0, receipt)
            self.assertEqual(receipt["status"], "PASS_SCOPED_MOLECULAR_SINGLE_POINT")
            self.assertTrue(receipt["container_removed"])
            self.assertTrue((run / "output/calculation/result.json").is_file())
            self.assertTrue((run / "input-snapshot/molecule.xyz").is_file())
            self.assertFalse((Path(tmp) / "runs/.molecular-service-locks/active.lock").exists())
            self.assertEqual(sum(args[0] == "create" for args, _ in docker.calls), 1)

    def test_timeout_has_no_retry_or_false_scientific_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp, expire=True)
            self.assertEqual(code, 50)
            self.assertTrue(receipt["wall_stop_requested"])
            self.assertTrue(receipt["container_removed"])
            self.assertIsNone(receipt["scientific_actual_counts"])
            self.assertNotIn("evidence_review", receipt)
            self.assertEqual(sum(args[0] == "create" for args, _ in docker.calls), 1)
            self.assertEqual(sum(args[0] == "stop" for args, _ in docker.calls), 1)

    def test_foreign_owned_container_is_not_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp, foreign_cleanup=True)
            self.assertNotEqual(code, 0)
            self.assertFalse(receipt["container_removed"])
            self.assertIn("ownership", receipt["cleanup_error"].lower())
            self.assertFalse(any(args[0] == "rm" for args, _ in docker.calls))

    def test_post_removal_input_or_output_tamper_cannot_pass(self):
        for alteration in ("output-tamper", "output-delete", "input-tamper"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as tmp:
                code, run, receipt, docker = self.lifecycle(tmp, alter=alteration)
                self.assertNotEqual(code, 0)
                self.assertTrue(receipt["container_removed"])
                self.assertNotEqual(receipt["status"], "PASS_SCOPED_MOLECULAR_SINGLE_POINT")

    def test_existing_other_execution_lock_refuses_before_docker_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs, locks = root / "runs", root / "locks"
            locks.mkdir()
            foreign = {"execution_id": "f" * 32, "task": "single-point"}
            host.save(locks / "active.lock", foreign)
            args = host.argument_parser().parse_args(["--request", str(root / "unused.json"),
                "--output-root", str(runs), "--lock-root", str(locks)])
            with patch.object(host, "DockerCommands") as factory:
                code, run, receipt = host.supervise(args)
            self.assertEqual(code, 40)
            self.assertFalse(receipt["worker_started"])
            self.assertIsNone(receipt["scientific_actual_counts"])
            self.assertEqual(host.read_json(locks / "active.lock"), foreign)
            factory.assert_not_called()

    def test_input_refusal_stops_before_image_or_container_and_keeps_failure_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = host.argument_parser().parse_args(["--request", str(Path(tmp) / "invalid.json"),
                "--output-root", str(Path(tmp) / "runs")])
            with patch.object(host, "_parse_request", side_effect=ValueError("invalid user input")), \
                 patch.object(host, "DockerCommands") as factory:
                code, run, receipt = host.supervise(args)
            self.assertEqual(code, 40)
            self.assertFalse(receipt["worker_started"])
            self.assertIsNone(receipt["scientific_actual_counts"])
            self.assertTrue((run / "host-execution.json").is_file())
            self.assertFalse((Path(tmp) / "runs/.molecular-service-locks/active.lock").exists())
            factory.assert_not_called()


if __name__ == "__main__": unittest.main()
