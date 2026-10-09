"""Failure-path tests for the native metadata entry; no WSL or QM is started."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-wsl2-runtime.py"
spec = importlib.util.spec_from_file_location("native_wsl2_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def observation(args):
    return {"schema_version": "native-wsl2-observation-v1", "compute_enabled": False, "qm_calls": 0,
            "python_isolated": True, "bytecode_disabled": True, "user_site_disabled": True, "uid": 1000,
            "memory": {k: 1024 for k in ("MemTotal_bytes", "MemAvailable_bytes", "SwapTotal_bytes", "SwapFree_bytes")},
            "environment_identity": {"backend": "native-wsl2", "image_id": None,
                "python_executable": args.python, "python_prefix": "/home/cascade/micromamba/envs/ai4orgchem",
                "kernel_release": "6.6.87.2-microsoft-standard-WSL2",
                "packages": {p: {"version": "test"} for p in check.PACKAGES},
                "source_files": [{"path": p, "sha256": "a" * 64} for p in args.source_file]}}


class NativeWsl2CheckTests(unittest.TestCase):
    def setUp(self):
        self.args = check.parse_args([])
        self.data = observation(self.args)
        self.commands = []

    def runner(self, argv, **kwargs):
        self.commands.append((argv, kwargs))
        if "--version" in argv:
            value = "WSL version: 2.6.1"
        elif "--verbose" in argv:
            value = "NAME STATE VERSION\n* Ubuntu-24.04 Running 2\n"
        elif "--running" in argv:
            value = "Ubuntu-24.04\n"
        else:
            value = json.dumps(self.data)
        return subprocess.CompletedProcess(argv, 0, value.encode("utf-8"), b"")

    def report(self, runner=None, find_wsl=None):
        return check.make_report(self.args, runner=runner or self.runner, find_wsl=find_wsl or (lambda _: "wsl.exe"))

    def test_check_pass_has_native_identity_and_no_compute_rights(self):
        report = self.report()
        self.assertEqual(report["status"], "PASS")
        self.assertIsNone(report["image_id"])
        self.assertIsNone(report["environment_identity"]["image_id"])
        self.assertFalse(report["compute_enabled"])
        self.assertEqual(report["qm_calls"], 0)
        self.assertEqual(report["native_p12_compute"], "NOT_IMPLEMENTED")
        self.assertEqual(len(report["environment_fingerprint_sha256"]), 64)

    def test_compute_rejected_before_any_process_or_discovery(self):
        self.args.action = "Compute"
        def forbidden(*args, **kwargs):
            self.fail("Compute must never launch or discover WSL")
        report = check.make_report(self.args, runner=forbidden, find_wsl=forbidden)
        self.assertEqual(report["status"], "REFUSED")
        self.assertEqual(report["error"]["code"], "compute_disabled")

    def test_missing_wsl(self):
        report = self.report(find_wsl=lambda _: None)
        self.assertEqual(report["error"]["code"], "wsl_unavailable")
        self.assertEqual(self.commands, [])

    def test_missing_environment(self):
        def missing(argv, **kwargs):
            if "--exec" in argv:
                return subprocess.CompletedProcess(argv, 127, b"", b"private stderr must not be echoed")
            return self.runner(argv, **kwargs)
        report = self.report(runner=missing)
        self.assertEqual(report["error"]["code"], "environment_unavailable")
        self.assertNotIn("private", json.dumps(report))

    def test_timeout_fails_closed(self):
        def slow(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        self.assertEqual(self.report(runner=slow)["error"]["code"], "timeout")

    def test_invalid_worker_json(self):
        def invalid(argv, **kwargs):
            if "--exec" in argv:
                return subprocess.CompletedProcess(argv, 0, b"not json", b"")
            return self.runner(argv, **kwargs)
        self.assertEqual(self.report(runner=invalid)["error"]["code"], "invalid_json")

    def test_duplicate_and_nonfinite_json_rejected(self):
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(value=value), self.assertRaises(check.CheckFailure):
                check.strict_json(value)

    def test_stopped_distribution_does_not_start(self):
        self.args.require_running = True
        def stopped(argv, **kwargs):
            if "--running" in argv:
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            return self.runner(argv, **kwargs)
        report = self.report(runner=stopped)
        self.assertEqual(report["error"]["code"], "distribution_not_running")
        self.assertFalse(any("--exec" in argv for argv, _ in self.commands))

    def test_normal_metadata_check_can_invoke_stopped_distribution(self):
        def stopped(argv, **kwargs):
            if "--running" in argv:
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            return self.runner(argv, **kwargs)
        report = self.report(runner=stopped)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["distribution_running_before_check"])
        self.assertTrue(any("--exec" in argv for argv, _ in self.commands))

    def test_missing_package_and_environment_mismatch(self):
        for mutate, code in ((lambda x: x["environment_identity"]["packages"].pop("pyscf"), "missing_package"),
                             (lambda x: x["environment_identity"].update(python_prefix="/other"), "environment_mismatch"),
                             (lambda x: x.update(uid=0), "root_user_refused"),
                             (lambda x: x.update(bytecode_disabled=False), "environment_mismatch"),
                             (lambda x: x["environment_identity"].update(image_id="sha256:docker"), "invalid_json")):
            self.data = observation(self.args)
            mutate(self.data)
            with self.subTest(code=code):
                self.assertEqual(self.report()["error"]["code"], code)

    def test_unicode_space_and_metacharacters_remain_single_argv(self):
        path = "/mnt/d/中文 空格/源文件;$(never-run).py"
        self.args.source_file = [path]
        self.data = observation(self.args)
        self.assertEqual(self.report()["status"], "PASS")
        argv, kwargs = next((argv, kwargs) for argv, kwargs in self.commands if "--exec" in argv)
        self.assertEqual(argv[-2:], ["--source-file", path])
        self.assertIn("PYTHONNOUSERSITE=1", argv)
        self.assertEqual(argv[argv.index(self.args.python) + 1:argv.index(self.args.python) + 4], ["-I", "-B", "-"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["input"], check.WORKER.read_bytes())

    def test_utf16_wsl_inventory_decoding(self):
        text = "Ubuntu-24.04\r\n"
        self.assertEqual(check.decode_output(text.encode("utf-16")), text)
        self.assertEqual(check.decode_output(text.encode("utf-16-le")), text)

    def test_record_directory_cannot_overwrite_existing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                check.parse_args(["--record-dir", directory])


if __name__ == "__main__":
    unittest.main()
