"""Bounded standard-library-only tests of public installation input guards."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_install_dependencies", ROOT / "scripts" / "prepare-install-dependencies.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallationDependencyTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "locks" / "installation-dependencies.json").read_text(encoding="utf-8"))
        self.temporary = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_existing_versions_and_hashes_retained(self):
        artifacts = installer.validate_lock(self.lock)
        retained = {}
        for filename in ("requirements-linux-amd64.txt", "requirements-registered-cases.txt"):
            for line in (ROOT / "locks" / filename).read_text().splitlines():
                if line and not line.startswith("#"):
                    name, version_hash = line.split("==")
                    retained[name.lower()] = version_hash
        for item in artifacts:
            if item["name"].lower() in retained:
                self.assertEqual(retained[item["name"].lower()], f"{item['version']} --hash=sha256:{item['sha256']}")
        self.assertEqual(len(retained), 19)
        installer.validate_requirements(ROOT / "locks" / "requirements-installation-linux-amd64.txt", artifacts)

    def test_prepare_refuses_nonempty_output_without_network(self):
        marker = self.tmp_path / "keep.txt"
        marker.write_text("preserve")
        with self.assertRaisesRegex(installer.InputError, "never overwritten"):
            installer.prepare(self.tmp_path)
        self.assertEqual(marker.read_text(), "preserve")

    def artifact_fixture(self):
        data = b"official-artifact-test-bytes"
        item = {"name": "test", "version": "1.0.0", "filename": "test-1.0.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/test/test-1.0.0-py3-none-any.whl",
                "metadata_url": "https://pypi.org/pypi/test/1.0.0/json", "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}
        class Response(io.BytesIO):
            def geturl(self):
                return item["url"]
        return item, data, lambda request, timeout: Response(data)

    def test_download_verifies_bytes_before_publishing_filename(self):
        item, data, opener = self.artifact_fixture()
        row = installer.download_artifact(item, self.tmp_path, opener=opener)
        self.assertEqual(row["status"], "VERIFIED")
        self.assertEqual((self.tmp_path / item["filename"]).read_bytes(), data)

    def test_download_rejects_wrong_hash_without_publishing_filename(self):
        item, data, opener = self.artifact_fixture()
        item["sha256"] = "0" * 64
        with self.assertRaisesRegex(installer.InputError, "identity mismatch"):
            installer.download_artifact(item, self.tmp_path, opener=opener)
        self.assertFalse((self.tmp_path / item["filename"]).exists())

    def test_requirement_drift_is_refused(self):
        artifacts = installer.validate_lock(self.lock)
        path = self.tmp_path / "requirements.txt"
        path.write_text(installer.requirements_text(artifacts).replace("attrs==26.1.0", "attrs==26.2.0"))
        with self.assertRaisesRegex(installer.InputError, "disagree"):
            installer.validate_requirements(path, artifacts)

    def copied_input_fixture(self):
        output = self.tmp_path / "copied-inputs"
        (output / "wheels").mkdir(parents=True)
        (output / "sources").mkdir()
        for item in self.lock["artifacts"]:
            payload = f"fixture:{item['name']}:{item['version']}".encode()
            item["size"] = len(payload)
            item["sha256"] = hashlib.sha256(payload).hexdigest()
            directory = "sources" if item["packagetype"] == "sdist" else "wheels"
            (output / directory / item["filename"]).write_bytes(payload)
        lock_path = self.tmp_path / "fixture-lock.json"
        lock_path.write_text(json.dumps(self.lock))
        return output, lock_path

    def test_independent_copied_input_verification_without_receipt(self):
        output, lock_path = self.copied_input_fixture()
        result = installer.verify(output, lock_path)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["receipt_status"], "NOT_PROVIDED")
        self.assertEqual(result["artifact_count"], 22)

    def test_copied_input_extra_artifact_refused(self):
        output, lock_path = self.copied_input_fixture()
        (output / "wheels" / "unregistered.whl").write_bytes(b"extra")
        with self.assertRaisesRegex(installer.InputError, "inventory differs"):
            installer.verify(output, lock_path)

    def test_copied_input_tampered_artifact_refused(self):
        output, lock_path = self.copied_input_fixture()
        (output / "wheels" / self.lock["artifacts"][0]["filename"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(installer.InputError, "identity mismatch"):
            installer.verify(output, lock_path)


MUTATIONS = {
    "unofficial_url": lambda lock: lock["artifacts"][0].update(url="https://mirror.invalid/package.whl"),
    "traversal_filename": lambda lock: lock["artifacts"][0].update(filename="../escape.whl"),
    "malformed_hash": lambda lock: lock["artifacts"][0].update(sha256="a" * 63),
    "version_mismatch": lambda lock: lock["artifacts"][0].update(version="27.0.0"),
    "duplicate_artifact": lambda lock: lock["artifacts"].append(copy.deepcopy(lock["artifacts"][0])),
    "unapproved_source_build": lambda lock: lock["artifacts"][0].update(packagetype="sdist"),
}


def rejection_test(mutation):
    def test(self):
        mutation(self.lock)
        with self.assertRaises(installer.InputError):
            installer.validate_lock(self.lock)
    return test


for name, mutation in MUTATIONS.items():
    setattr(InstallationDependencyTests, "test_lock_refuses_" + name, rejection_test(mutation))


if __name__ == "__main__":
    unittest.main()
