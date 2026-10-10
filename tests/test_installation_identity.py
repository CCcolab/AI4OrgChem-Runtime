"""Installation identity refusal gates; no Docker or scientific kernels are run."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installation_test_runner", ROOT / "scripts/run-installed-runtime.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
identity = runner.identity


def record_fixture(service="molecular-service"):
    spec = identity.SERVICES[service]
    reviewed = identity.source_bindings.CATALOGS[service]
    binding = {"kind": identity.source_bindings.KIND, "baseline_sha256": spec["source_sha"],
               "source_sha256": "7"*64, "file_count": reviewed['count'],
               "unchanged_rows": reviewed['count']-len(reviewed['overrides']),
               "host_overrides": {name: {**row, "size": 100} for name, row in reviewed['overrides'].items()}}
    return {"schema": identity.SCHEMA, "backend": "docker", "service": service,
            "tasks": list(spec["tasks"]), "modes": list(spec["modes"]), "platform": "linux/amd64",
            "status": "ENGINEERING_VALIDATED", "scientific_acceptance": "UNKNOWN",
            "capabilities": identity.capabilities(service), "image_id": "sha256:" + "1" * 64,
            "base_image_id": "sha256:" + "2" * 64, "dependency_lock_base_image_id": "sha256:" + "3" * 64,
            "local_tag": "ai4orgchem-runtime:installation-test", "image_build_runtime_commit": "4" * 40,
            "source_snapshot_sha256": binding['source_sha256'], "dependency_lock_sha256": spec["dependency_sha"],
            "profile_sha256": spec["profile_sha"], "host_files": {name: "5" * 64 for name in identity.HOST_FILES},
            "evidence": {name: "6" * 64 for name in identity.EVIDENCE_FILES},
            "source_catalog_binding": binding, "registered_utc": "2026-10-09T00:00:00+00:00"}


def inspection_fixture(record):
    spec = identity.SERVICES[record["service"]]
    schemas = {"molecular-service": "molecular-single-point-v1", "registered-cases": "fixed-registered-cases-v1",
               "protocol-cases": "protocol-cases-v1", "high-cost-cases": "high-cost-cases-v1"}
    labels = {"ai4orgchem." + spec["prefix"] + "." + name: value for name, value in {
        "schema": schemas[record["service"]], "runtime-commit": record["image_build_runtime_commit"],
        "source-sha256": record["source_snapshot_sha256"], "dependency-sha256": record["dependency_lock_sha256"],
        "base-image-id": record["base_image_id"], "profile-sha256": record["profile_sha256"]}.items()}
    image = {"Id": record["image_id"], "Os": "linux", "Architecture": "amd64", "RepoTags": [record["local_tag"]],
             "RootFS": {"Layers": ["base-layer", "runtime-layer"]}, "Config": {"User": "10001:10001", "Labels": labels,
             "Env": [name + "=" + value for name, value in zip(spec["env"], (record["image_build_runtime_commit"], record["source_snapshot_sha256"], record["dependency_lock_sha256"]))]}}
    base = {"Id": record["base_image_id"], "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": ["base-layer"]}}
    return image, base


class InstallationIdentityTests(unittest.TestCase):
    def test_supported_record_scopes_are_closed(self):
        for family in identity.SERVICES:
            record = record_fixture(family)
            self.assertEqual(identity.validate_record(record), record)
            for key, value in (("backend", "native"), ("service", "conditional-compute"),
                               ("tasks", record["tasks"] + ["arbitrary-task"]), ("scientific_acceptance", "HISTORICAL_PASS"),
                               ("status", "NUMERICALLY_QUALIFIED"), ("platform", "linux/arm64")):
                changed = deepcopy(record)
                changed[key] = value
                with self.assertRaises(ValueError):
                    identity.validate_record(changed)
            changed = deepcopy(record)
            changed["capabilities"]["native_compute"] = "OPEN"
            with self.assertRaises(ValueError):
                identity.validate_record(changed)
            changed = {**record, "allow_override": True}
            with self.assertRaises(ValueError):
                identity.validate_record(changed)

    def test_arbitrary_frozen_source_identity_is_refused(self):
        for family in ("molecular-service", "registered-cases", "protocol-cases"):
            record = record_fixture(family)
            record["source_snapshot_sha256"] = "a" * 64
            record["source_catalog_binding"]["source_sha256"] = "a" * 64
            record["source_catalog_binding"]["host_overrides"][spec_name := next(iter(record['source_catalog_binding']['host_overrides']))]['sha256'] = 'b'*64
            with self.assertRaises(ValueError):
                identity.validate_record(record)

    def test_high_cost_cannot_add_an_unreviewed_host_or_scientific_override(self):
        record = record_fixture("high-cost-cases")
        record["source_catalog_binding"]["host_overrides"]["runtime/high_cost_cases/p12.py"] = {"base_sha256": "a" * 64, "sha256": "b" * 64, "size": 10}
        with self.assertRaises(ValueError):
            identity.validate_record(record)

    def test_high_cost_new_catalog_keeps_all_104_other_rows(self):
        original_path = ROOT / "locks/high-cost-source.json"
        original = identity.read_json(original_path)
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            (context / "locks").mkdir()
            (context / identity.HIGH_COST_BASELINE).write_bytes(original_path.read_bytes())
            raw, catalog, expected_binding = identity.source_bindings.derive('high-cost-cases', original_path.read_bytes(), lambda name: (ROOT/name).read_bytes())
            for row in catalog["files"]:
                target = context / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / row["path"], target)
            (context / "locks/high-cost-source.json").write_bytes(raw)
            with patch.object(identity, "ROOT", context):
                source, binding = identity.source_bindings.bind(context, 'high-cost-cases')
                self.assertEqual(binding["unchanged_rows"], 104)
                self.assertEqual(binding, expected_binding)
                self.assertEqual(source, catalog)
                # Even an internally self-consistent updated catalog cannot alter science.
                row = next(row for row in catalog["files"] if row["path"] == "runtime/high_cost_cases/p12.py")
                target = context / row["path"]
                target.write_bytes(target.read_bytes() + b"\n# changed science\n")
                row.update(sha256=identity.digest(target), size=target.stat().st_size)
                (context / "locks/high-cost-source.json").write_text(json.dumps(catalog), encoding="utf-8")
                with self.assertRaises(ValueError):
                    identity.source_bindings.bind(context, 'high-cost-cases')
        record = record_fixture("high-cost-cases")
        record["source_catalog_binding"]["host_overrides"]["scripts/run-high-cost-case.py"]["sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            identity.validate_record(record)

    def test_new_host_bytes_require_a_new_independently_registered_context(self):
        for family in ("molecular-service", "registered-cases", "protocol-cases"):
            with self.assertRaises(ValueError):
                identity.expected_host_identity(family)
            spec = identity.SERVICES[family]
            baseline = (ROOT/spec['source']).read_bytes()
            raw, catalog, binding = identity.source_bindings.derive(family, baseline, lambda name: (ROOT/name).read_bytes())
            with tempfile.TemporaryDirectory() as directory:
                context = Path(directory)
                names = set(identity.source_bindings.rows(catalog)) | set(identity.HOST_FILES) | {spec['dependency'], spec['profile']}
                for name in names:
                    target = context/name; target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT/name, target)
                (context/identity.source_bindings.baseline_path(family)).write_bytes(baseline)
                (context/spec['source']).write_bytes(raw)
                with patch.object(identity, 'ROOT', context):
                    expected = identity.expected_host_identity(family)
                self.assertEqual(expected['source_snapshot_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(expected['source_catalog_binding'], binding)
                self.assertNotEqual(expected['source_snapshot_sha256'], spec['source_sha'])
                self.assertGreater(len(expected['inventory']['files']), 1)

    def test_actual_image_labels_tag_platform_base_and_environment_are_required(self):
        for family in ("molecular-service", "registered-cases", "protocol-cases"):
            record = record_fixture(family)
            image, base = inspection_fixture(record)
            identity.verify_inspections(image, base, record)
            mutations = [lambda x: x.update(Id="sha256:" + "0" * 64), lambda x: x.update(Architecture="arm64"),
                         lambda x: x.update(RepoTags=["different:tag"]), lambda x: x["RootFS"].update(Layers=["unrelated-base", "runtime"]),
                         lambda x: x["Config"].update(User="root"), lambda x: x["Config"].update(Labels={}),
                         lambda x: x["Config"].update(Env=[])]
            for mutate in mutations:
                changed = deepcopy(image)
                mutate(changed)
                with self.assertRaises(ValueError):
                    identity.verify_inspections(changed, base, record)

    def test_duplicate_json_keys_and_overflow_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            for value in ('{"backend":"docker","backend":"native"}', '{"v":1e999}', '{"v":NaN}'):
                path.write_text(value, encoding="utf-8")
                with self.assertRaises(ValueError):
                    identity.read_json(path)

    def test_adapter_overrides_only_exact_candidate_and_preserves_other_checks(self):
        for family in identity.SERVICES:
            record = record_fixture(family)
            class Docker:
                def __init__(self, executable, output, **kwargs):
                    self.executable = executable
            marker = {"untouched": True}
            module = SimpleNamespace(read_json=lambda path: marker, DockerCommands=Docker, DockerJournal=Docker)
            canonical = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
            preflight = {"installation_record_canonical_sha256": hashlib.sha256(canonical).hexdigest()}
            runner.adapt_launcher(module, record, preflight)
            candidate = ROOT / "validation" / family / "candidate-image.json"
            self.assertEqual(module.read_json(candidate), identity.legacy_record(record))
            self.assertIs(module.read_json(ROOT / "any-other.json"), marker)
            with tempfile.TemporaryDirectory() as directory:
                cls = module.DockerJournal if family == "high-cost-cases" else module.DockerCommands
                cls("docker", Path(directory))
                self.assertEqual(identity.digest(Path(directory) / "INSTALLATION_RECORD.json"), preflight["installation_record_canonical_sha256"])
            if family == "high-cost-cases":
                self.assertEqual(module.BASE_IMAGE_ID, record["image_id"])
                self.assertEqual(module.BASE_SOURCE_SHA256, record["source_snapshot_sha256"])

    def test_task_and_mode_mismatch_refuse_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            identity.save_new(path, record_fixture())
            with patch.object(identity, "verify_installation") as live_verify:
                code = runner.main(["--installation-record", str(path), "--task", "P12", "--output-root", str(Path(directory) / "runs")])
                self.assertEqual(code, 40)
                live_verify.assert_not_called()

    def test_protocol_live_budget_refusal_prevents_supervision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            record = record_fixture("protocol-cases")
            identity.save_new(path, record)
            class Docker:
                pass
            module = SimpleNamespace(read_json=lambda path: {}, DockerCommands=Docker,
                                     validate_directory=lambda path: Path(path))
            calls = []
            def reserve(args):
                calls.append("budget")
                raise ValueError("Frozen budget missing or admission paused")
            module.reserve_batch = reserve
            module.supervise = lambda args: calls.append("supervise")
            with patch.object(identity, "load_launcher", return_value=module), patch.object(identity, "verify_installation", return_value=(record, {})):
                code = runner.main(["--installation-record", str(path), "--task", "P03", "--mode", "live", "--output-root", str(Path(directory) / "runs")])
            self.assertEqual(code, 40)
            self.assertEqual(calls, ["budget"])


if __name__ == "__main__":
    unittest.main()
