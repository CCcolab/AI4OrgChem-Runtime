"""Source snapshot contracts using small local Git fixtures, never engines/science."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

from runtime import distribution as source


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git_root = self.root / "checkout"
        self.git_root.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Source snapshot test")
        self.git("config", "user.email", "source-snapshot-test@localhost")
        self.git("config", "core.autocrlf", "false")
        (self.git_root / ".gitattributes").write_bytes(b"* text=auto eol=lf\n*.ps1 text eol=crlf\n")
        (self.git_root / "README.md").write_bytes(b"source payload\n")
        (self.git_root / "scripts").mkdir()
        (self.git_root / "scripts" / "start.ps1").write_bytes(b"Write-Output 'toy only'\n")
        (self.git_root / "runtime").mkdir()
        (self.git_root / "runtime" / "toy.py").write_bytes(b"answer = 42\n")
        self.git("add", ".")
        self.git("commit", "-m", "Local synthetic source fixture")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.git_root), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def exported(self):
        path = self.root / "source.zip"
        receipt = source.export_source_zip(self.git_root, path)
        return path, receipt

    def entries(self, path):
        with zipfile.ZipFile(path) as archive:
            return {item.filename: archive.read(item) for item in archive.infolist()}

    def rewritten(self, entries, *, filename="changed.zip", duplicates=None, symlink=None):
        path = self.root / filename
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, raw in entries.items():
                archive.writestr(name, raw)
            if duplicates:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(*duplicates)
            if symlink:
                info = zipfile.ZipInfo(symlink)
                info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, b"README.md")
        return path

    def refuse_zip(self, entries, **kwargs):
        path = self.rewritten(entries, **kwargs)
        target = self.root / "refused"
        with self.assertRaises(source.SourcePreparationError):
            source.prepare_runtime_source(path, target)
        self.assertFalse(target.exists(), "All archive checks must precede target creation")

    def test_git_preparation_binds_full_commit_tree_and_all_source_bytes_without_git_history(self):
        target = self.root / "prepared"
        value = source.prepare_runtime_source(self.git_root, target, expected_commit=self.commit)
        self.assertEqual(value["runtime_commit"], self.commit)
        self.assertEqual(value["status"], "VERIFIED_PREPARED_SOURCE")
        self.assertEqual(value["source_kind"], "CLEAN_GIT_CHECKOUT")
        self.assertEqual(value["file_count"], 4)
        self.assertFalse(value["git_history_created"])
        self.assertFalse((target / ".git").exists())
        manifest = json.loads((target / source.MANIFEST_NAME).read_bytes())
        for row in manifest["files"]:
            actual = (target / row["path"]).read_bytes()
            self.assertEqual(row["sha256"], hashlib.sha256(actual).hexdigest())
            self.assertEqual(len(row["git_blob_id"]), 40)
        self.assertEqual(source.verify_prepared_source(target), value)
        self.assertEqual(value["image_build"], "NOT_EXECUTED")

    def test_zip_roundtrip_is_git_free_and_has_independent_commit_and_manifest_pins(self):
        path, receipt = self.exported()
        target = self.root / "fromzip"
        value = source.prepare_runtime_source(path, target, expected_commit=self.commit,
                                              expected_manifest_sha256=receipt["source_manifest_sha256"])
        self.assertEqual(value["source_kind"], "PROJECT_SOURCE_ZIP")
        self.assertEqual(value["source_manifest_sha256"], receipt["source_manifest_sha256"])
        self.assertFalse((target / ".git").exists())
        self.assertEqual((target / "README.md").read_bytes(), b"source payload\n")

    def test_ps1_checkout_crlf_policy_is_explicit_and_preserves_actual_bytes(self):
        script = self.git_root / "scripts" / "start.ps1"
        self.git("config", "core.autocrlf", "true")
        script.unlink()
        self.git("checkout-index", "--force", "--", "scripts/start.ps1")
        self.assertIn(b"\r\n", script.read_bytes())
        # Refresh only this synthetic fixture's index/stat cache, retaining HEAD.
        self.git("add", "--", "scripts/start.ps1")
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.commit)
        self.assertEqual(self.git("status", "--porcelain"), b"")
        snapshot = source.inspect_git_source(self.git_root)
        row = next(row for row in snapshot["manifest"]["files"] if row["path"] == "scripts/start.ps1")
        self.assertEqual(row["checkout_byte_policy"], "PS1_CRLF_TO_LF")
        target = self.root / "crlf"
        source.prepare_runtime_source(self.git_root, target)
        self.assertEqual((target / "scripts/start.ps1").read_bytes(), script.read_bytes())

    def test_non_ps1_worktree_normalization_is_not_silently_accepted(self):
        (self.git_root / "README.md").write_bytes(b"source payload\r\n")
        with self.assertRaisesRegex(source.SourcePreparationError, "Checkout bytes differ|clean"):
            source.inspect_git_source(self.git_root)

    def test_dirty_tracked_and_untracked_git_sources_are_refused(self):
        for mutation in (lambda: (self.git_root / "README.md").write_bytes(b"changed\n"),
                         lambda: (self.git_root / "extra.txt").write_bytes(b"extra\n")):
            with self.subTest(mutation=mutation):
                mutation()
                with self.assertRaisesRegex(source.SourcePreparationError, "clean"):
                    source.inspect_git_source(self.git_root)
                (self.git_root / "README.md").write_bytes(b"source payload\n")
                if (self.git_root / "extra.txt").exists():
                    (self.git_root / "extra.txt").unlink()

    def test_git_inspection_does_not_mutate_source_or_git_metadata(self):
        before = {p.relative_to(self.git_root).as_posix(): p.read_bytes()
                  for p in self.git_root.rglob("*") if p.is_file()}
        source.inspect_git_source(self.git_root)
        after = {p.relative_to(self.git_root).as_posix(): p.read_bytes()
                 for p in self.git_root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_active_git_filters_are_refused_before_status_can_run_filter_code(self):
        attributes = self.git_root / ".gitattributes"
        attributes.write_bytes(attributes.read_bytes() + b"*.py filter=external-tool\n")
        self.git("add", ".gitattributes"); self.git("commit", "-m", "Declare unsupported synthetic filter")
        with mock.patch.object(source, "_git", wraps=source._git) as observed:
            with self.assertRaisesRegex(source.SourcePreparationError, "filters"):
                source.inspect_git_source(self.git_root)
        self.assertFalse(any("status" in call.args[1:] for call in observed.call_args_list))

    def test_expected_commit_or_manifest_mismatch_refuses_before_writing(self):
        path, receipt = self.exported()
        for kwargs in ({"expected_commit": "1" * 40}, {"expected_manifest_sha256": "1" * 64}):
            with self.subTest(kwargs=kwargs):
                target = self.root / "pin-refused"
                with self.assertRaises(source.SourcePreparationError):
                    source.prepare_runtime_source(path, target, **kwargs)
                self.assertFalse(target.exists())

    def test_ordinary_github_style_zip_is_not_a_verified_source(self):
        self.refuse_zip({"project-main/README.md": b"source payload\n"})

    def test_tampered_missing_and_extra_source_files_are_refused(self):
        path, _ = self.exported(); original = self.entries(path)
        for label, changed in (("tamper", {**original, "README.md": b"forged\n"}),
                               ("missing", {k: v for k, v in original.items() if k != "README.md"}),
                               ("extra", {**original, "untracked-extra.txt": b"surprise"})):
            with self.subTest(case=label):
                self.refuse_zip(changed, filename=label + ".zip")

    def test_traversal_absolute_backslash_and_reserved_zip_paths_are_refused(self):
        path, _ = self.exported(); original = self.entries(path)
        for index, name in enumerate(("../escape.txt", "/escape.txt", "C:/escape.txt", "scripts\\escape.txt", "CON.txt", ".git/config", "readme.md")):
            with self.subTest(name=name):
                self.refuse_zip({**original, name: b"unexpected"}, filename=str(index) + ".zip")

    def test_duplicate_zip_members_and_symlinks_are_refused(self):
        path, _ = self.exported(); original = self.entries(path)
        self.refuse_zip(original, filename="duplicate.zip", duplicates=("README.md", original["README.md"]))
        self.refuse_zip(original, filename="symlink.zip", symlink="link.txt")

    def test_case_colliding_directories_and_file_directory_collision_are_refused(self):
        path, _ = self.exported(); original = self.entries(path)
        self.refuse_zip({**original, "Scripts/extra.py": b"extra"}, filename="directory-case.zip")
        self.refuse_zip({**original, "scripts": b"file conflicts with directory"}, filename="file-directory.zip")

    def test_crc_corruption_is_refused_before_target_creation(self):
        path, _ = self.exported(); plain = self.rewritten(self.entries(path))
        raw = bytearray(plain.read_bytes()); position = raw.index(b"source payload\n")
        raw[position] ^= 1; plain.write_bytes(raw)
        with self.assertRaisesRegex(source.SourcePreparationError, "corrupted"):
            source.prepare_runtime_source(plain, self.root / "crc-target")
        self.assertFalse((self.root / "crc-target").exists())

    def test_self_rehashed_payload_cannot_replace_committed_blob(self):
        path, _ = self.exported(); entries = self.entries(path)
        manifest = json.loads(entries[source.MANIFEST_NAME]); row = next(r for r in manifest["files"] if r["path"] == "README.md")
        entries["README.md"] = b"self-rehashed payload\n"
        row["size_bytes"] = len(entries["README.md"]); row["sha256"] = hashlib.sha256(entries["README.md"]).hexdigest()
        row["git_blob_id"] = source._git_oid("blob", entries["README.md"], "sha1")
        entries[source.MANIFEST_NAME] = source._json_bytes(manifest)
        self.refuse_zip(entries)

    def test_commit_tree_and_tree_object_proofs_cannot_be_relabelled(self):
        path, _ = self.exported(); original = self.entries(path)
        for label in ("commit", "root-tree", "tree-bytes"):
            with self.subTest(case=label):
                entries = dict(original); manifest = json.loads(entries[source.MANIFEST_NAME])
                if label == "commit":
                    manifest["runtime_commit"] = "2" * 40
                elif label == "root-tree":
                    manifest["runtime_tree"] = "2" * 40
                else:
                    oid = manifest["runtime_tree"]
                    manifest["tree_objects_base64"][oid] = base64.b64encode(b"not a tree").decode()
                entries[source.MANIFEST_NAME] = source._json_bytes(manifest)
                self.refuse_zip(entries, filename=label + ".zip")

    def test_manifest_duplicate_keys_boolean_sizes_and_fake_commit_are_refused(self):
        path, _ = self.exported(); original = self.entries(path)
        cases = []
        duplicate = dict(original); duplicate[source.MANIFEST_NAME] = b'{"schema":"one","schema":"two"}'
        cases.append(duplicate)
        for key, value in (("runtime_commit", "UNKNOWN"), ("file_count", True)):
            entries = dict(original); manifest = json.loads(entries[source.MANIFEST_NAME]); manifest[key] = value
            entries[source.MANIFEST_NAME] = source._json_bytes(manifest); cases.append(entries)
        entries = dict(original); manifest = json.loads(entries[source.MANIFEST_NAME]); manifest["files"][0]["size_bytes"] = True
        entries[source.MANIFEST_NAME] = source._json_bytes(manifest); cases.append(entries)
        for index, entries in enumerate(cases):
            with self.subTest(case=index):
                self.refuse_zip(entries, filename="metadata-" + str(index) + ".zip")

    def test_malformed_prepared_json_and_extra_empty_directory_are_refused(self):
        target = self.root / "prepared"; source.prepare_runtime_source(self.git_root, target)
        path = target / source.MANIFEST_NAME; original = path.read_bytes()
        path.write_bytes(b"[]")
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)
        path.write_bytes(original)
        (target / "extra-empty").mkdir()
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)

    def test_zip_safety_limit_refuses_before_payload_extraction(self):
        path, _ = self.exported()
        with mock.patch.object(source, "MAX_FILE_BYTES", 8):
            with self.assertRaisesRegex(source.SourcePreparationError, "safety limits"):
                source.prepare_runtime_source(path, self.root / "limited")
        self.assertFalse((self.root / "limited").exists())

    def test_prepared_source_refuses_identity_tamper_and_unknown_git_metadata(self):
        target = self.root / "prepared"; source.prepare_runtime_source(self.git_root, target)
        identity_path = target / source.IDENTITY_NAME; original = identity_path.read_bytes()
        identity = json.loads(original); identity["runtime_commit"] = "3" * 40
        identity_path.write_bytes(source._json_bytes(identity))
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)
        identity_path.write_bytes(original)
        (target / ".git").mkdir(); (target / ".git" / "config").write_bytes(b"not real Git")
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)

    def test_prepared_source_missing_or_modified_bytes_are_never_repaired(self):
        target = self.root / "prepared"; source.prepare_runtime_source(self.git_root, target)
        readme = target / "README.md"; readme.write_bytes(b"changed\n")
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)
        self.assertEqual(readme.read_bytes(), b"changed\n")
        readme.unlink()
        with self.assertRaises(source.SourcePreparationError):
            source.verify_prepared_source(target)
        self.assertFalse(readme.exists())

    def test_existing_target_and_archive_are_preserved(self):
        path, _ = self.exported(); original = path.read_bytes()
        with self.assertRaises(source.SourcePreparationError):
            source.export_source_zip(self.git_root, path)
        self.assertEqual(path.read_bytes(), original)
        target = self.root / "existing"; target.mkdir(); marker = target / "keep.txt"; marker.write_bytes(b"keep")
        with self.assertRaises(source.SourcePreparationError):
            source.prepare_runtime_source(path, target)
        self.assertEqual(marker.read_bytes(), b"keep")

    def test_source_checkout_cannot_be_modified_by_nested_archive_or_prepared_output(self):
        for operation in (lambda: source.export_source_zip(self.git_root, self.git_root / "new.zip"),
                          lambda: source.prepare_runtime_source(self.git_root, self.git_root / "new-prepared")):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(source.SourcePreparationError, "outside"):
                    operation()
        self.assertFalse((self.git_root / "new.zip").exists())
        self.assertFalse((self.git_root / "new-prepared").exists())
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_cli_verify_returns_machine_json_and_refuses_without_traceback(self):
        target = self.root / "prepared"; source.prepare_runtime_source(self.git_root, target)
        script = Path(__file__).resolve().parents[1] / "scripts" / "prepare-runtime-source.py"
        result = subprocess.run([sys.executable, str(script), "verify", "--source", str(target),
                                 "--expected-commit", self.commit], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["runtime_commit"], self.commit)
        result = subprocess.run([sys.executable, str(script), "verify", "--source", str(target),
                                 "--expected-manifest-sha256", "4" * 64], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(json.loads(result.stderr)["status"], "SOURCE_PREPARATION_REFUSED")


if __name__ == "__main__":
    unittest.main()
