"""Host-only synthetic Docker/clock evidence; no container or scientific call."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-registered-case.py"
SPEC = importlib.util.spec_from_file_location("registered_case_supervisor_under_test", SCRIPT)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def sleep(self, duration):
        self.value += duration


def image_record(source_sha="1" * 64, dependency_sha="2" * 64):
    return {"image_id": "sha256:" + "a" * 64, "image_build_runtime_commit": "b" * 40, "source_snapshot_sha256": source_sha, "dependency_lock_sha256": dependency_sha, "base_image_id": "sha256:" + "c" * 64}


def contract_fixture(task="p02-statistics"):
    limit = int(task == "p01-orbital-density")
    protocols = {"p02-statistics": "P02_STRUCTURE_UV_SOURCE_FREEZE_V0.1", "p13-graph-ledger": "p13-polycyclic-benzenoid/0.1", "p01-orbital-density": "P01_ETHENE_OCCUPIED_GAUGE_CONTROL_V0.1"}
    result = {"schema": "registered-case-execution-v1", "task": task, "protocol_id": protocols[task], "scientific_execution_authorized": bool(limit), "runtime_commit": "b" * 40,
            "source_snapshot_sha256": "1" * 64, "dependency_lock_sha256": "2" * 64, "execution_id": "d" * 32,
            "memory_limit_bytes": host.MEMORY_BYTES, "threads": 1, "maximum_processes": 1, "wall_time_limit_seconds": 120, "stop_after_seconds": 100,
            "started_epoch": 10000.0, "stop_deadline_epoch": 10100.0, "hard_deadline_epoch": 10120.0,
            "scf_kernel_call_limit": limit, "boys_kernel_call_limit": limit, "pipek_mezey_kernel_call_limit": limit}
    if limit:
        result["p01_protocol_sha256"] = "d137c04a22fd221129f7a1e62fcafa6928e7ddee1493082ca40158a3c230ac47"
    return result


def write_worker_fixture(output, contract, contract_sha):
    """Synthetic receipt fixture only; never represents an actual worker run."""
    output = Path(output)
    (output / "case").mkdir()
    limit = int(contract["scientific_execution_authorized"])
    case_id = {"p02-statistics": "P02", "p13-graph-ledger": "P13", "p01-orbital-density": "P01"}[contract["task"]]
    host.save(output / "case/case-result.json", {"status": "P01_FIXED_CONTROL_PASSED" if limit else "PASS", "task": contract["task"], "protocol_id": contract["protocol_id"], "case_id": case_id, "proposition_id": case_id, "test_scope": "ENGINEERING_SYNTHETIC_RECEIPT_ONLY"})
    (output / "case/case-report.md").write_text("Synthetic engineering fixture, no scientific execution.\n", encoding="utf-8")
    host.save(output / "guard-receipt.json", {"status": "PASS", "counts": {"scf_kernel": limit, "boys_kernel": limit, "pipek_mezey_kernel": limit, "conditional_NR": 0}, "guard_operations": ["fixed-operation-fixture"], "forbidden_attempts": [], "changed_guards": [],
        "engine_kind": "PINNED_PYSCF_MODULES", "closed": True, "held_at_close": True, "restored_attributes_intact": True,
        "call_outcomes": {name: {"returned": limit, "failed": 0} for name in ("scf_kernel", "boys_kernel", "pipek_mezey_kernel")}, "test_scope": "ENGINEERING_SYNTHETIC_RECEIPT_ONLY_NOT_REAL_GUARD"})
    for file in ("resource-start.json", "resource-end.json"):
        host.save(output / file, {"scope": "ENGINEERING_SYNTHETIC_RECEIPT_ONLY"})
    receipt = {key: contract[key] for key in ("task", "execution_id", "runtime_commit", "source_snapshot_sha256", "dependency_lock_sha256", "scientific_execution_authorized")}
    receipt.update(status="PASS_SCOPED_FIXED_CASE", contract_sha256=contract_sha, source_check="PASS", dependency_check="PASS", resource_check="PASS", guard_check="PASS", persistence_check="PASS", new_conditional_NR_calls=0,
                   actual_scf_kernel_calls=limit, actual_boys_kernel_calls=limit, actual_pipek_mezey_kernel_calls=limit, worker_exit_code=0,
                   guard_receipt_sha256=host.digest(output / "guard-receipt.json"), case_result_sha256=host.digest(output / "case/case-result.json"), case_report_sha256=host.digest(output / "case/case-report.md"))
    hashes = {str(path.relative_to(output)).replace("\\", "/"): host.digest(path) for path in output.rglob("*") if path.is_file()}
    host.save(output / "run-manifest.json", {"output_sha256": hashes})
    receipt["run_manifest_sha256"] = host.digest(output / "run-manifest.json")
    host.save(output / "worker-receipt.json", receipt)


class FakeDocker:
    """Pure Python command simulator used solely for lifecycle protection tests."""
    def __init__(self, image, clock, *, expire=False, foreign_cleanup=False, alter_on_removal=None):
        self.image, self.clock = image, clock
        self.expire, self.foreign_cleanup = expire, foreign_cleanup
        self.alter_on_removal = alter_on_removal
        self.calls, self.inspections = [], 0
        self.container_id = "e" * 64
        self.removed, self.running = False, False

    def __call__(self, command, *, capture_output, timeout):
        args = command[1:]
        self.calls.append((list(args), timeout))
        stdout, stderr, code = b"", b"", 0
        if args[:2] == ["image", "inspect"]:
            value = {"Id": self.image["image_id"], "Os": "linux", "Architecture": "amd64", "Config": {"Labels": {
                "ai4orgchem.registered.schema": "fixed-registered-cases-v1", "ai4orgchem.registered.runtime-commit": self.image["image_build_runtime_commit"],
                "ai4orgchem.registered.source-sha256": self.image["source_snapshot_sha256"], "ai4orgchem.registered.dependency-sha256": self.image["dependency_lock_sha256"], "ai4orgchem.registered.base-image-id": self.image["base_image_id"]}}}
            stdout = json.dumps([value]).encode()
        elif args[0] == "create":
            self.create_args = args
            mounts = [args[index + 1] for index, arg in enumerate(args) if arg == "--mount"]
            self.contract_path = Path(next(item for item in mounts if "target=/task-contract.json" in item).split("source=", 1)[1].split(",target=", 1)[0])
            self.output = Path(next(item for item in mounts if "target=/output" in item).split("source=", 1)[1].split(",target=", 1)[0])
            self.contract = host.read_json(self.contract_path)
            self.token = self.contract["execution_id"]
            stdout = self.container_id.encode()
        elif args[0] == "start":
            self.running = self.expire
            if not self.expire:
                write_worker_fixture(self.output, self.contract, host.digest(self.contract_path))
        elif args[0] == "inspect":
            if self.removed:
                code, stderr = 1, b"Error: No such object: owned-fixed-case"
            else:
                self.inspections += 1
                value = self.inspection()
                if self.foreign_cleanup and self.inspections == 4:
                    value["Config"]["Labels"][host.LABEL] = "f" * 32
                stdout = json.dumps([value]).encode()
                if self.expire and self.running and self.inspections == 2:
                    self.clock.value += 100
        elif args[0] == "stop":
            self.running = False
        elif args[0] == "rm":
            self.removed = True
            if self.alter_on_removal == "tamper":
                (self.output / "case/case-report.md").write_text("changed after removal", encoding="utf-8")
            elif self.alter_on_removal == "delete":
                (self.output / "guard-receipt.json").unlink()
        elif args[0] != "logs":
            raise AssertionError("Unexpected simulated command: " + str(args))
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    def inspection(self):
        return {"Id": self.container_id, "Image": self.image["image_id"], "Config": {"User": "10001:10001", "Labels": {host.LABEL: self.token}, "Entrypoint": ["/opt/venv/bin/python"], "Cmd": ["-B", "-m", "runtime.registered_cases", "--task", self.contract["task"], "--contract", "/task-contract.json", "--output-dir", "/output"]},
                "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "Memory": host.MEMORY_BYTES, "MemorySwap": host.MEMORY_BYTES, "NanoCpus": 1000000000, "PidsLimit": 128, "NetworkMode": "none", "CapDrop": ["ALL"], "CapAdd": [], "SecurityOpt": ["no-new-privileges"], "Tmpfs": {"/tmp": "rw,nosuid,nodev,size=134217728"}},
                "Mounts": [{"Type": "bind", "Source": str(self.contract_path), "Destination": "/task-contract.json", "RW": False}, {"Type": "bind", "Source": str(self.output), "Destination": "/output", "RW": True}],
                "State": {"Running": self.running, "ExitCode": 137 if self.expire else 0, "OOMKilled": False}}


class RegisteredCaseSupervisorTests(unittest.TestCase):
    def test_only_three_fixed_tasks_are_accepted(self):
        args = host.argument_parser().parse_args(["--task", "p02-statistics", "--output-root", "x"])
        self.assertEqual(args.task, "p02-statistics")
        for task in ("Compute", "p14-fixed", "p01-custom"):
            with self.assertRaises(SystemExit):
                host.argument_parser().parse_args(["--task", task, "--output-root", "x"])

    def test_valid_receipt_and_bytes_are_accepted_for_both_counter_modes(self):
        for task in ("p02-statistics", "p01-orbital-density"):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as tmp:
                contract = contract_fixture(task)
                write_worker_fixture(Path(tmp), contract, "9" * 64)
                self.assertEqual(host.verify_worker_evidence(tmp, contract, "9" * 64)["status"], "PASS_SCOPED_FIXED_CASE_EVIDENCE")

    def test_missing_boolean_counts_and_claim_only_pass_are_rejected(self):
        for field, value in (("actual_scf_kernel_calls", False), ("worker_exit_code", False), ("scientific_execution_authorized", 0), ("resource_check", "NOT_EXECUTED"), ("contract_sha256", "8" * 64)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                contract = contract_fixture()
                write_worker_fixture(output, contract, "9" * 64)
                receipt = host.read_json(output / "worker-receipt.json")
                receipt[field] = value
                host.save(output / "worker-receipt.json", receipt)
                with self.assertRaises(ValueError):
                    host.verify_worker_evidence(output, contract, "9" * 64)

    def test_output_tamper_and_incomplete_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            contract = contract_fixture()
            write_worker_fixture(output, contract, "9" * 64)
            report = output / "case/case-report.md"
            report.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output changed"):
                host.verify_worker_evidence(output, contract, "9" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_worker_fixture(output, contract, "9" * 64)
            manifest = host.read_json(output / "run-manifest.json")
            del manifest["output_sha256"]["resource-end.json"]
            host.save(output / "run-manifest.json", manifest)
            receipt = host.read_json(output / "worker-receipt.json")
            receipt["run_manifest_sha256"] = host.digest(output / "run-manifest.json")
            host.save(output / "worker-receipt.json", receipt)
            with self.assertRaisesRegex(ValueError, "mandatory actual evidence"):
                host.verify_worker_evidence(output, contract, "9" * 64)

    def test_changed_guard_or_conditional_nr_is_rejected(self):
        for field, value in (("changed_guards", ["replacement"]), ("forbidden_attempts", ["attempt"]), ("counts", {"scf_kernel": 0, "boys_kernel": 0, "pipek_mezey_kernel": 0, "conditional_NR": 1})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                contract = contract_fixture()
                write_worker_fixture(output, contract, "9" * 64)
                guard = host.read_json(output / "guard-receipt.json")
                guard[field] = value
                host.save(output / "guard-receipt.json", guard)
                with self.assertRaises(ValueError):
                    host.verify_worker_evidence(output, contract, "9" * 64)

    def test_commands_are_clamped_even_during_cleanup(self):
        clock = Clock()
        observed = []
        def execute(command, *, capture_output, timeout):
            observed.append(timeout)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with tempfile.TemporaryDirectory() as tmp:
            docker = host.DockerCommands("not-a-real-docker", tmp, clock=clock, executor=execute)
            docker.hard_deadline = clock() + 0.5
            docker("inspect", "fixture", timeout=20)
            self.assertEqual(observed, [0.5])
            clock.value += 0.5
            with self.assertRaises(TimeoutError):
                docker("rm", "--force", "fixture")
            self.assertEqual(len(docker.commands), 1)

    def test_stop_reserves_evidence_without_extending_hard_deadline(self):
        clock = Clock()
        calls = []
        def docker(*args, **kwargs):
            calls.append((args, kwargs))
        receipt = host.stop_owned_container(docker, "owned", hard_deadline=clock() + 20, clock=clock)
        self.assertEqual(receipt["grace_seconds"], 13)
        self.assertEqual(receipt["command_timeout_seconds"], 15)
        with self.assertRaises(TimeoutError):
            host.stop_owned_container(docker, "owned", hard_deadline=clock() + 7, clock=clock)
        self.assertEqual(len(calls), 1)

    def test_source_and_ambiguous_mount_output_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            with self.assertRaises(ValueError):
                host.validate_directory(source / "outputs", protected=[source])
            with self.assertRaises(ValueError):
                host.validate_directory(Path(tmp), protected=[source])
            with self.assertRaises(ValueError):
                host.validate_directory(Path(tmp) / "unsafe,readonly", protected=[source])

    def test_create_contract_is_not_alias_writable_through_output(self):
        contract = contract_fixture()
        args = host.create_command("sha256:" + "a" * 64, contract, Path("/fresh/contract/task-contract.json"), Path("/fresh/output"))
        mounts = [args[i + 1] for i, item in enumerate(args) if item == "--mount"]
        self.assertIn("source=/fresh/contract/task-contract.json,target=/task-contract.json,readonly", mounts[0].replace("\\", "/"))
        self.assertIn("source=/fresh/output,target=/output", mounts[1].replace("\\", "/"))
        self.assertIn("--network", args)
        self.assertNotIn("--privileged", args)

    def test_contract_uses_actual_source_api_and_separate_build_identity(self):
        import runtime.registered_cases as source_api
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "locks").mkdir()
            (root / "configs").mkdir()
            (root / "source.py").write_text("# synthetic source fixture\n", encoding="utf-8")
            host.save(root / "locks/registered-cases-dependencies.json", {"fixture_only": True})
            host.save(root / "configs/registered-cases-v1.json", {"tasks": {
                "p02-statistics": {"protocol_id": "fixed-p02"}, "p01-orbital-density": {"protocol_id": "fixed-p01", "protocol_sha256": "7" * 64}}})
            host.save(root / "locks/registered-cases-source.json", {"schema": "registered-case-source-v1", "files": {"source.py": host.digest(root / "source.py")}})
            image = image_record(host.digest(root / "locks/registered-cases-source.json"), host.digest(root / "locks/registered-cases-dependencies.json"))
            with patch.object(host, "ROOT", root), patch.multiple(source_api, ROOT=root, SOURCE_LOCK=root / "locks/registered-cases-source.json", DEPENDENCY_LOCK=root / "locks/registered-cases-dependencies.json", REGISTRY=root / "configs/registered-cases-v1.json"):
                pure = host.build_contract("p02-statistics", image, "d" * 32, now=10000.0)
                self.assertIs(pure["scientific_execution_authorized"], False)
                self.assertEqual(pure["scf_kernel_call_limit"], 0)
                self.assertEqual(pure["runtime_commit"], image["image_build_runtime_commit"])
                self.assertEqual(pure["stop_deadline_epoch"], 10100.0)
                bounded = host.build_contract("p01-orbital-density", image, "d" * 32, now=10000.0)
                self.assertIs(bounded["scientific_execution_authorized"], True)
                self.assertEqual(bounded["scf_kernel_call_limit"], 1)
                self.assertEqual(bounded["p01_protocol_sha256"], "7" * 64)
                wrong_image = {**image, "source_snapshot_sha256": "0" * 64}
                with self.assertRaisesRegex(ValueError, "source snapshot"):
                    host.build_contract("p01-orbital-density", wrong_image, "d" * 32, now=10000.0)
                (root / "source.py").write_text("# changed source fixture\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Source bytes differ"):
                    host.build_contract("p02-statistics", image, "d" * 32, now=10000.0)

    def lifecycle(self, tmp, *, expire=False, foreign_cleanup=False, alter_on_removal=None):
        root = Path(tmp)
        source = root / "source"
        (source / "validation/registered-cases").mkdir(parents=True)
        image = image_record()
        host.save(source / "validation/registered-cases/candidate-image.json", image)
        clock = Clock()
        docker = FakeDocker(image, clock, expire=expire, foreign_cleanup=foreign_cleanup, alter_on_removal=alter_on_removal)
        args = host.argument_parser().parse_args(["--task", "p02-statistics", "--output-root", str(root / "runs")])
        def build(task, record, token, **kwargs):
            value = contract_fixture(task)
            value["execution_id"] = token
            return value
        # Directory probing is verified separately; retain this fixture's full
        # scientific receipt, resource, deadline and output persistence checks.
        with patch.object(host, "probe_output_writable", return_value=None), patch.object(host, "ROOT", source), patch.object(host, "build_contract", side_effect=build), patch.object(host, "host_git_identity", return_value={"runtime_source_head": None, "status": "ENGINEERING_FIXTURE"}):
            code, run, execution = host.supervise(args, clock=clock, sleep=clock.sleep, executor=docker)
        return code, run, execution, docker

    def test_nominal_simulated_lifecycle_removes_container_and_keeps_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "PASS_SCOPED_FIXED_CASE")
            self.assertTrue(receipt["container_removed"])
            self.assertTrue((run / "output/case/case-result.json").is_file())
            self.assertTrue((run / "COMMANDS.json").is_file())
            self.assertFalse((Path(tmp) / "runs/.registered-case-locks/active.lock").exists())
            self.assertEqual(sum(args[0] == "create" for args, _ in docker.calls), 1)

    def test_timeout_closes_owned_container_without_retry_or_false_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp, expire=True)
            self.assertEqual(code, 50)
            self.assertTrue(receipt["wall_stop_requested"])
            self.assertTrue(receipt["container_removed"])
            self.assertNotIn("evidence_review", receipt)
            self.assertEqual(sum(args[0] == "create" for args, _ in docker.calls), 1)
            self.assertEqual(sum(args[0] == "stop" for args, _ in docker.calls), 1)
            self.assertTrue((run / "host-execution.json").is_file())

    def test_foreign_cleanup_inspection_prevents_blind_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, run, receipt, docker = self.lifecycle(tmp, foreign_cleanup=True)
            self.assertNotEqual(code, 0)
            self.assertFalse(receipt["container_removed"])
            self.assertTrue("ownership" in receipt["cleanup_error"].lower())
            self.assertFalse(any(args[0] == "rm" for args, _ in docker.calls))

    def test_deleted_or_changed_outputs_after_removal_cannot_pass(self):
        for alteration in ("tamper", "delete"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as tmp:
                code, run, receipt, docker = self.lifecycle(tmp, alter_on_removal=alteration)
                self.assertNotEqual(code, 0)
                self.assertTrue(receipt["container_removed"])
                self.assertNotIn("post_removal_evidence_review", receipt)
                self.assertIsNone(receipt["scientific_actual_counts"])
                self.assertIn("cleanup_error", receipt)

    def test_open_fake_or_failed_native_outcome_guard_cannot_pass(self):
        edits = [lambda guard: guard.update(closed=False), lambda guard: guard.update(engine_kind="ENGINEERING_FAKE_MODULES"), lambda guard: guard["call_outcomes"]["scf_kernel"].update(returned=False), lambda guard: guard["call_outcomes"]["boys_kernel"].update(failed=1)]
        for edit in edits:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                contract = contract_fixture()
                write_worker_fixture(output, contract, "9" * 64)
                guard = host.read_json(output / "guard-receipt.json")
                edit(guard)
                host.save(output / "guard-receipt.json", guard)
                with self.assertRaises(ValueError):
                    host.verify_worker_evidence(output, contract, "9" * 64)

    def test_case_for_wrong_proposition_cannot_be_relabelled_as_another_pure_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            contract = contract_fixture()
            write_worker_fixture(output, contract, "9" * 64)
            result_path = output / "case/case-result.json"
            case = host.read_json(result_path)
            case.update(case_id="P13", proposition_id="P13", protocol_id="p13-polycyclic-benzenoid/0.1")
            host.save(result_path, case)
            manifest = host.read_json(output / "run-manifest.json")
            manifest["output_sha256"]["case/case-result.json"] = host.digest(result_path)
            host.save(output / "run-manifest.json", manifest)
            receipt = host.read_json(output / "worker-receipt.json")
            receipt.update(case_result_sha256=host.digest(result_path), run_manifest_sha256=host.digest(output / "run-manifest.json"))
            host.save(output / "worker-receipt.json", receipt)
            with self.assertRaises(ValueError):
                host.verify_worker_evidence(output, contract, "9" * 64)

    def test_actual_container_limits_and_mount_permissions_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, docker = self.lifecycle(tmp)
            original = docker.inspection()
            for change in (lambda v: v["HostConfig"].update(MemorySwap=2 * host.MEMORY_BYTES), lambda v: v["Mounts"][0].update(RW=True), lambda v: v["Config"].update(User="0"), lambda v: v["HostConfig"].update(NetworkMode="bridge")):
                altered = deepcopy(original)
                change(altered)
                with self.assertRaises(ValueError):
                    host.verify_container(altered, docker.image["image_id"], docker.contract, docker.container_id, docker.contract_path, docker.output)


if __name__ == "__main__":
    unittest.main()
