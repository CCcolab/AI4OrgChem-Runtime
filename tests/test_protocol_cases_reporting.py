"""Fake-only Git provenance reporting adapter checks; no scientific imports."""
from __future__ import annotations

import errno
import functools
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from runtime.protocol_cases import provenance_reporting as reporting


class ReportingAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="reporting-adapter-fake-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reference/protocol_cases/source_tree"
        file = self.root / reporting._REPORTER_RELATIVE
        file.parent.mkdir(parents=True)
        self.source_bytes = (b'def git_commit():\n'
                             b'    """Engineering fake reporter; no subprocess/science."""\n'
                             b'    value = _callback()\n'
                             b'    return value if value is not None else "unavailable"\n')
        file.write_bytes(self.source_bytes)
        self.canonical = ModuleType(reporting._REPORTER_MODULE)
        self.canonical.__file__ = str(file)
        self.canonical._callback = lambda: "a" * 40
        exec(compile(self.source_bytes, str(file), "exec"), self.canonical.__dict__)
        self.original = self.canonical.git_commit
        self.alias = ModuleType("_fake_reporting_source_alias")
        self.alias.__file__ = str(self.root / "scripts/fake_driver.py")
        self.alias.git_commit = self.original
        self.alias.imported_reporter_under_other_name = self.original
        self.external = ModuleType("_fake_reporting_external_alias")
        self.external.__file__ = str(Path(self.tmp.name) / "outside.py")
        self.external.git_commit = self.original
        self.modules_patch = patch.dict(sys.modules, {
            reporting._REPORTER_MODULE: self.canonical,
            self.alias.__name__: self.alias, self.external.__name__: self.external,
        })
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)
        self.state_patch = patch.object(reporting, "_STATE", None)
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)
        self.lock = Path(self.tmp.name) / "scientific-assets.json"
        self.lock_value = {"files": [{
            "path": "reference/protocol_cases/source_tree/" + reporting._REPORTER_RELATIVE,
            "sha256": hashlib.sha256(self.source_bytes).hexdigest(),
            "size": len(self.source_bytes),
            "captured_git_blob": hashlib.sha1(b"blob " + str(len(self.source_bytes)).encode() + b"\0" + self.source_bytes).hexdigest(),
            "source_path": reporting._REPORTER_RELATIVE,
            "source_context_head": "b" * 40, "provenance": "ENGINEERING_FAKE_ONLY",
        }]}
        self.lock.write_text(json.dumps(self.lock_value), encoding="utf-8")
        self.lock_patch = patch.object(reporting, "_LOCK_PATH", self.lock)
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)

    def raising(self, error):
        def callback():
            raise error
        self.canonical._callback = callback

    def test_exact_missing_git_returns_original_unavailable_sentinel(self):
        self.raising(FileNotFoundError(errno.ENOENT, "fake git is absent", "git"))
        metadata = reporting.apply(self.root)
        self.assertEqual(self.canonical.git_commit(), "unavailable")
        self.assertEqual(len(metadata["fallback_events"]), 1)
        self.assertEqual(metadata["fallback_events"][0]["filename"], "git")
        self.assertFalse(metadata["fallback_events"][0]["scientific_identity_substituted"])
        self.assertEqual(metadata["reporter_calls"], 1)
        self.assertEqual(metadata["reporter_returns_without_fallback"], 0)

    def test_other_missing_file_propagates_unchanged(self):
        error = FileNotFoundError(errno.ENOENT, "fake other missing file", "input.xyz")
        self.raising(error); metadata = reporting.apply(self.root)
        with self.assertRaises(FileNotFoundError) as actual: self.canonical.git_commit()
        self.assertIs(actual.exception, error)
        self.assertEqual(metadata["fallback_events"], [])

    def test_missing_filename_does_not_trigger_fallback(self):
        self.raising(FileNotFoundError("git not found but filename absent"))
        reporting.apply(self.root)
        with self.assertRaises(FileNotFoundError): self.canonical.git_commit()

    def test_git_executable_filename_is_exact(self):
        metadata = reporting.apply(self.root)
        for filename in ("GIT", "git.exe", "/usr/bin/git", r"C:\Program Files\Git\git.exe"):
            with self.subTest(filename=filename):
                self.raising(FileNotFoundError(errno.ENOENT, "fake missing", filename))
                with self.assertRaises(FileNotFoundError): self.canonical.git_commit()
        self.assertEqual(metadata["fallback_events"], [])

    def test_permission_error_for_git_propagates(self):
        error = PermissionError(errno.EACCES, "fake no permission", "git")
        self.raising(error); reporting.apply(self.root)
        with self.assertRaises(PermissionError) as actual: self.canonical.git_commit()
        self.assertIs(actual.exception, error)

    def test_unrelated_runtime_error_propagates(self):
        self.raising(RuntimeError("fake reporting failure")); reporting.apply(self.root)
        with self.assertRaisesRegex(RuntimeError, "fake reporting failure"): self.canonical.git_commit()

    def test_real_return_is_preserved_not_context_sha(self):
        metadata = reporting.apply(self.root)
        self.assertEqual(self.canonical.git_commit(), "a" * 40)
        self.assertEqual(metadata["source_context_heads"], ["b" * 40])
        self.assertFalse(metadata["git_sha_fabricated"])
        self.assertEqual(metadata["fallback_events"], [])
        self.assertEqual(metadata["reporter_returns_without_fallback"], 1)

    def test_original_nonzero_git_sentinel_is_preserved(self):
        self.canonical._callback = lambda: None
        metadata = reporting.apply(self.root)
        self.assertEqual(self.canonical.git_commit(), "unavailable")
        self.assertEqual(metadata["fallback_events"], [])

    def test_all_loaded_same_function_source_aliases_share_one_wrapper(self):
        metadata = reporting.apply(self.root)
        self.assertIs(self.alias.git_commit, self.canonical.git_commit)
        self.assertIs(self.alias.imported_reporter_under_other_name, self.canonical.git_commit)
        self.assertIs(self.canonical.git_commit.__wrapped__, self.original)
        self.assertEqual(len(metadata["wrapped_aliases"]), 3)

    def test_external_module_alias_is_not_mutated(self):
        reporting.apply(self.root)
        self.assertIs(self.external.git_commit, self.original)

    def test_wraps_preserves_function_metadata_and_signature(self):
        reporting.apply(self.root)
        wrapper = self.canonical.git_commit
        self.assertEqual(wrapper.__name__, self.original.__name__)
        self.assertEqual(wrapper.__module__, self.original.__module__)
        self.assertEqual(wrapper.__doc__, self.original.__doc__)
        self.assertEqual(inspect.signature(wrapper), inspect.signature(self.original))
        self.assertIs(inspect.unwrap(wrapper), self.original)

    def test_same_root_is_cached_and_not_wrapped_twice(self):
        first = reporting.apply(self.root); wrapper = self.canonical.git_commit
        second = reporting.apply(self.root)
        self.assertIs(first, second)
        self.assertIs(self.canonical.git_commit, wrapper)
        self.assertIs(wrapper.__wrapped__, self.original)
        self.assertEqual(len(second["wrapped_aliases"]), 3)

    def test_newly_loaded_source_alias_is_added_without_stack(self):
        first = reporting.apply(self.root); wrapper = self.canonical.git_commit
        extra = ModuleType("_fake_reporting_later_source")
        extra.__file__ = str(self.root / "scripts/later.py")
        extra.saved_git_commit = self.original
        with patch.dict(sys.modules, {extra.__name__: extra}):
            second = reporting.apply(self.root)
            self.assertIs(extra.saved_git_commit, wrapper)
            self.assertIs(first, second)
            self.assertEqual(len(second["wrapped_aliases"]), 4)

    def test_no_mixed_source_roots(self):
        reporting.apply(self.root)
        with self.assertRaisesRegex(ValueError, "cannot mix"):
            reporting.apply(Path(self.tmp.name) / "other-root")

    def test_changed_installed_alias_is_rejected(self):
        reporting.apply(self.root)
        self.alias.git_commit = self.original
        with self.assertRaisesRegex(ValueError, "alias changed"):
            reporting.apply(self.root)

    def test_source_bytes_and_subprocess_global_functions_are_untouched(self):
        before = (subprocess.run, subprocess.Popen, subprocess.check_output)
        file = self.root / reporting._REPORTER_RELATIVE
        reporting.apply(self.root)
        self.assertEqual(file.read_bytes(), self.source_bytes)
        self.assertEqual(before, (subprocess.run, subprocess.Popen, subprocess.check_output))

    def test_source_lock_sha_and_reporter_byte_identity_are_actual(self):
        metadata = reporting.apply(self.root)
        self.assertEqual(metadata["source_assets_lock_sha256"], hashlib.sha256(self.lock.read_bytes()).hexdigest())
        identity = metadata["original_reporter"]
        self.assertEqual(identity["source_file_sha256"], hashlib.sha256(self.source_bytes).hexdigest())
        self.assertEqual(identity["source_file_git_blob"], self.lock_value["files"][0]["captured_git_blob"])
        json.dumps(metadata, allow_nan=False)

    def test_unregistered_or_changed_source_is_rejected_before_mutation(self):
        file = self.root / reporting._REPORTER_RELATIVE
        file.write_bytes(self.source_bytes + b"# altered\n")
        with self.assertRaisesRegex(ValueError, "source-assets lock"):
            reporting.apply(self.root)
        self.assertIs(self.canonical.git_commit, self.original)

    def test_wrong_git_blob_is_rejected_before_mutation(self):
        self.lock_value["files"][0]["captured_git_blob"] = "f" * 40
        self.lock.write_text(json.dumps(self.lock_value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Git blob"):
            reporting.apply(self.root)
        self.assertIs(self.canonical.git_commit, self.original)

    def test_missing_loaded_reporter_has_no_function_side_effect(self):
        saved = sys.modules.pop(reporting._REPORTER_MODULE)
        try:
            metadata = reporting.apply(self.root)
            self.assertEqual(metadata["status"], "NOT_APPLICABLE_NO_LOADED_REPORTER")
            self.assertEqual(metadata["wrapped_aliases"], [])
            self.assertIs(self.alias.git_commit, self.original)
        finally:
            sys.modules[reporting._REPORTER_MODULE] = saved


if __name__ == "__main__":
    unittest.main()
