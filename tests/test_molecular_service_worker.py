"""Durable ordinary-worker admission refusals, never native/engine dispatch."""

from __future__ import annotations

import builtins
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import runtime.molecular_service as registry
from runtime.molecular_service import __main__ as worker
from tests.test_molecular_service_contract import contract_value


WATER = b"3\nengineering input fixture in angstrom\nO 0 0 0\nH 0.758602 0 0.504284\nH -0.758602 0 0.504284\n"
REQUEST = {"schema": "molecular-single-point-v1", "task": "single-point", "profile": "rhf-631gd-small-v1",
           "structure": {"file": "molecule.xyz", "format": "xyz", "unit": "angstrom"},
           "charge": 0, "multiplicity": 1, "method": "RHF", "basis": "6-31G(d)"}


class MolecularServiceWorkerAdmissionTests(unittest.TestCase):
    def run_refusal(self, *, profile_error=False, source_error=None, source_sha=None,
                    dependency_sha=None, installed_version="PINNED_TOY_VERSION",
                    environment_change=None, input_tamper=None, resource=None):
        forbidden_imports = []
        original_import = builtins.__import__
        forbidden_prefixes = ("pyscf", "runtime.molecular_service.engine", "runtime.molecular_service.native_guard",
                              "runtime.registered_cases.native_guard", "runtime.user_molecule.root_native_lifecycle")

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            resolved = importlib.util.resolve_name("." * level + name, globals["__package__"]) if level and globals and globals.get("__package__") else name
            if any(resolved == prefix or resolved.startswith(prefix + ".") for prefix in forbidden_prefixes):
                forbidden_imports.append(resolved)
                raise AssertionError("Blocked admission must not import scientific dispatch: " + resolved)
            return original_import(name, globals, locals, fromlist, level)

        with tempfile.TemporaryDirectory(prefix="molecular worker admission ") as temporary:
            root = Path(temporary).resolve()
            output = root / "output"
            snapshot = root / "input"
            output.mkdir()
            snapshot.mkdir()
            request_path = snapshot / "request.json"
            structure_path = snapshot / "molecule.xyz"
            manifest_path = snapshot / "INPUT_MANIFEST.json"
            request_path.write_text(json.dumps(REQUEST), encoding="utf-8")
            structure_path.write_bytes(WATER)
            contract = contract_value()
            real_digest = registry.digest
            contract["request_sha256"] = real_digest(request_path)
            contract["structure_sha256"] = real_digest(structure_path)
            manifest = {"schema": "molecular-service-input-snapshot-v1", "task": "single-point",
                        "request_file": "request.json", "structure_file": "molecule.xyz",
                        **{key: contract[key] for key in ("request_sha256", "structure_sha256", "profile_sha256")}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            contract["input_manifest_sha256"] = real_digest(manifest_path)
            if profile_error:
                contract["profile_sha256"] = "0" * 64
            contract_path = root / "task-contract.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            dependency_lock = {"packages": {"toy-package": "PINNED_TOY_VERSION"}, "python_version": "TOY_PYTHON_VERSION"}
            environment = {"AI4ORGCHEM_RUNTIME_COMMIT": contract["runtime_commit"],
                           "AI4ORGCHEM_MOLECULAR_SOURCE_SHA256": contract["source_snapshot_sha256"],
                           "AI4ORGCHEM_MOLECULAR_DEPENDENCY_SHA256": contract["dependency_lock_sha256"]}
            environment.update(environment_change or {})
            if input_tamper == "structure":
                structure_path.write_bytes(WATER.replace(b"0.758602", b"0.858602"))
            elif input_tamper == "request":
                request_path.write_bytes(request_path.read_bytes() + b"\n")
            elif input_tamper == "manifest":
                manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")

            def paths(value):
                replacements = {"/output": output, "/input": snapshot, "/input/request.json": request_path,
                                "/input/INPUT_MANIFEST.json": manifest_path}
                return replacements.get(str(value), Path(value))

            real_load = registry.strict_load
            def load(path):
                if Path(path) == worker.DEPENDENCY_LOCK:
                    return copy.deepcopy(dependency_lock)
                if Path(path) in (contract_path, manifest_path):
                    return real_load(path)
                raise AssertionError("Unexpected fixture JSON input: " + str(path))

            def hashes(path):
                if Path(path) == worker.DEPENDENCY_LOCK:
                    return dependency_sha or contract["dependency_lock_sha256"]
                return real_digest(path)

            refused_resource = resource or {"registered_status": "BLOCKED", "registered_reasons": ["toy resource refusal"],
                                            "scope": "ENGINEERING_FAKE_RESOURCE_NOT_NATIVE_EXECUTION"}
            resources = Mock(return_value=refused_resource)
            stdout = io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(worker, "Path", side_effect=paths))
                stack.enter_context(patch.object(worker, "strict_load", side_effect=load))
                source_check = stack.enter_context(patch.object(worker, "verify_source", side_effect=source_error))
                stack.enter_context(patch.object(worker, "source_snapshot_sha256", return_value=source_sha or contract["source_snapshot_sha256"]))
                stack.enter_context(patch.object(worker, "digest", side_effect=hashes))
                stack.enter_context(patch.object(worker.metadata, "version", return_value=installed_version))
                stack.enter_context(patch.object(worker.platform, "python_version", return_value="TOY_PYTHON_VERSION"))
                stack.enter_context(patch.object(worker, "resource_observation", resources))
                stack.enter_context(patch.dict(worker.os.environ, environment))
                stack.enter_context(patch.object(builtins, "__import__", side_effect=guarded_import))
                stack.enter_context(redirect_stdout(stdout))
                code = worker.main(["--task", "single-point", "--request", "/input/request.json",
                                    "--contract", str(contract_path), "--output-dir", "/output"])
            receipt = json.loads((output / "worker-receipt.json").read_text(encoding="utf-8"))
            run_manifest = json.loads((output / "run-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 2)
            self.assertEqual(receipt["worker_exit_code"], 2)
            self.assertEqual(receipt["status"], "BLOCKED")
            self.assertFalse(receipt["automatic_retry"])
            self.assertFalse(receipt["resume"])
            self.assertEqual(receipt["conditional_user_compute"], "BLOCKED")
            for key in ("actual_scf_kernel_calls", "actual_boys_kernel_calls", "actual_pipek_mezey_kernel_calls", "new_conditional_NR_calls"):
                self.assertIn(key, receipt)
                self.assertIsNone(receipt[key], "Unobserved dispatch counts must not be fabricated zero")
            self.assertFalse(forbidden_imports)
            self.assertFalse((output / "calculation").exists())
            self.assertFalse((output / "guard-receipt.json").exists())
            self.assertNotIn("guard_check", receipt)
            self.assertNotIn("persistence_check", receipt)
            self.assertEqual(receipt["run_manifest_sha256"], real_digest(output / "run-manifest.json"))
            self.assertEqual(run_manifest["task"], "single-point")
            self.assertIn('"status": "BLOCKED"', stdout.getvalue())
            for name, expected in run_manifest["output_sha256"].items():
                self.assertEqual(real_digest(output / name), expected)
            self.assertNotIn("worker-receipt.json", run_manifest["output_sha256"])
            self.assertNotIn("run-manifest.json", run_manifest["output_sha256"])
            phases = [call.args[0] for call in resources.call_args_list]
            end_resource = json.loads((output / "resource-end.json").read_text())
            self.assertEqual(end_resource, refused_resource)
            return receipt, phases, source_check.call_count, output / "resource-start.json" in output.iterdir()

    def test_actual_profile_contract_mismatch_persists_refusal_before_source_or_dispatch(self):
        receipt, phases, source_calls, start_saved = self.run_refusal(profile_error=True)
        self.assertIn("Actual profile differs", receipt["error"]["message"])
        self.assertEqual(source_calls, 0)
        self.assertEqual(phases, ["failure-end"])
        self.assertFalse(start_saved)
        self.assertNotIn("source_check", receipt)
        self.assertNotIn("execution_id", receipt)

    def test_source_bytes_refusal_never_imports_engine_guard_or_controller(self):
        receipt, phases, source_calls, start_saved = self.run_refusal(source_error=ValueError("Source bytes differ: locked.py"))
        self.assertIn("Source bytes differ", receipt["error"]["message"])
        self.assertEqual(source_calls, 1)
        self.assertEqual(phases, ["failure-end"])
        self.assertFalse(start_saved)
        self.assertNotIn("dependency_check", receipt)

    def test_source_or_dependency_lock_mismatch_is_not_substituted_by_old_success(self):
        for change in ({"source_sha": "0" * 64}, {"dependency_sha": "0" * 64}):
            with self.subTest(change=change):
                receipt, phases, source_calls, start_saved = self.run_refusal(**change)
                self.assertIn("Execution source/dependency lock differs", receipt["error"]["message"])
                self.assertEqual(source_calls, 1)
                self.assertEqual(phases, ["failure-end"])
                self.assertFalse(start_saved)

    def test_image_environment_and_installed_dependency_mismatch_block_before_input(self):
        cases = [({"environment_change": {"AI4ORGCHEM_RUNTIME_COMMIT": "f" * 40}}, "Image build identity differs"),
                 ({"installed_version": "WRONG_TOY_VERSION"}, "Installed dependency identity differs")]
        for change, message in cases:
            with self.subTest(change=change):
                receipt, phases, _, start_saved = self.run_refusal(**change)
                self.assertIn(message, receipt["error"]["message"])
                self.assertEqual(phases, ["failure-end"])
                self.assertFalse(start_saved)
                self.assertNotIn("input_check", receipt)

    def test_readonly_snapshot_identity_mismatch_is_durable_before_resource_preflight(self):
        for tamper in ("request", "structure", "manifest"):
            with self.subTest(tamper=tamper):
                receipt, phases, _, start_saved = self.run_refusal(input_tamper=tamper)
                expected = "Input manifest identity differs" if tamper == "manifest" else "Input hash differs: " + tamper + "_sha256"
                self.assertIn(expected, receipt["error"]["message"])
                self.assertEqual(receipt["source_check"], "PASS")
                self.assertEqual(receipt["dependency_check"], "PASS")
                self.assertNotIn("input_check", receipt)
                self.assertEqual(phases, ["failure-end"])
                self.assertFalse(start_saved)

    def test_resource_blocked_preserves_start_and_end_without_native_dispatch(self):
        resource = {"registered_status": "BLOCKED", "registered_reasons": ["fake memory/swap/CPU refusal"],
                    "source_readonly": {"/input": False}, "scope": "ENGINEERING_FAKE_PLATFORM_NOT_EXECUTED"}
        receipt, phases, _, start_saved = self.run_refusal(resource=resource)
        self.assertIn("Resource/platform preflight failed", receipt["error"]["message"])
        self.assertEqual(receipt["source_check"], "PASS")
        self.assertEqual(receipt["dependency_check"], "PASS")
        self.assertEqual(receipt["input_check"], "PASS")
        self.assertNotIn("resource_check", receipt)
        self.assertEqual(phases, ["start", "failure-end"])
        self.assertTrue(start_saved)


if __name__ == "__main__":
    unittest.main()
