"""Register a locally rebuilt fixed-service image; never import historical acceptance.

Docker molecular, registered, protocol and high-cost services are supported. Registration inspects
the immutable image, declared base layers, frozen critical source bytes and
installed package versions. It performs no SCF, optimisation or memory probe.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
import installation_source_bindings as source_bindings

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ai4orgchem-runtime-installation-v2"
SHA = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
TAG = re.compile(r"[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")
HOST_FILES = ("scripts/register-installation.py", "scripts/run-installed-runtime.py",
              "scripts/installation_source_bindings.py", "scripts/runtime_host_safety.py")
SERVICES = {
    "molecular-service": {
        "launcher": "scripts/run-molecular-service.py", "module": "runtime.molecular_service",
        "source": "locks/molecular-service-source.json", "dependency": "locks/molecular-service-dependencies.json",
        "profile": "profiles/molecular-service/rhf-631gd-small-v1.json", "prefix": "molecular",
        "source_sha": "0f1370a8ef1c5e1a8c7b58f310dc6ad2faa0c08e568e19b01cf8e02d7eff29ab",
        "dependency_sha": "954b8d84d7d393388990303665b6d7416bd760e92fbed21d1148f7574144dbdd",
        "profile_sha": "40d9c5c16f35b7c90fad86ea771a4379a27b31856bd21785b1f75e313f703dfb",
        "tasks": ["single-point"], "modes": ["live"],
        "env": ["AI4ORGCHEM_RUNTIME_COMMIT", "AI4ORGCHEM_MOLECULAR_SOURCE_SHA256", "AI4ORGCHEM_MOLECULAR_DEPENDENCY_SHA256"],
    },
    "registered-cases": {
        "launcher": "scripts/run-registered-case.py", "module": "runtime.registered_cases",
        "source": "locks/registered-cases-source.json", "dependency": "locks/registered-cases-dependencies.json",
        "profile": "configs/registered-cases-v1.json", "prefix": "registered",
        "source_sha": "1bc64c322920671b9fe2335b13ea639619e960648422e7eb984c4001f2a481ca",
        "dependency_sha": "511711d709508ff77fa995b120d5aeed3a9058984868a3a17f1d0604b788d393",
        "profile_sha": "660602b00f4e38441e6397d3d4720d4d4727cd12dcdc91e6406e279ab7a4080b",
        "tasks": ["p02-statistics", "p13-graph-ledger", "p01-orbital-density"], "modes": ["live"],
        "env": ["AI4ORGCHEM_RUNTIME_COMMIT", "AI4ORGCHEM_REGISTERED_SOURCE_SHA256", "AI4ORGCHEM_REGISTERED_DEPENDENCY_SHA256"],
    },
    "protocol-cases": {
        "launcher": "scripts/run-protocol-case.py", "module": "runtime.protocol_cases",
        "source": "locks/protocol-cases-source.json", "dependency": "locks/protocol-cases-dependencies.json",
        "profile": "configs/protocol-cases-v1.json", "prefix": "protocol",
        "source_sha": "20708a08ecfa4d74327dd9d5689b20e4faecbbcdb271d962e798616dfc5baa6d",
        "dependency_sha": "954b8d84d7d393388990303665b6d7416bd760e92fbed21d1148f7574144dbdd",
        "profile_sha": "64abfaa9090e72b893458f1fc261b9f0cc4efce9d95458997b9077a95da0d4a4",
        "tasks": ["P03", "P04", "P05", "P06", "P07", "P08", "P09", "P10"],
        "modes": ["ledger", "preflight", "live"],
        "env": ["AI4ORGCHEM_PROTOCOL_RUNTIME_COMMIT", "AI4ORGCHEM_PROTOCOL_SOURCE_SHA256", "AI4ORGCHEM_PROTOCOL_DEPENDENCY_SHA256"],
    },
    "high-cost-cases": {
        "launcher": "scripts/run-high-cost-case.py", "module": "runtime.high_cost_cases",
        "source": "locks/high-cost-source.json", "dependency": "locks/high-cost-dependencies.json",
        "profile": "configs/high-cost-cases-v1.json", "prefix": "high-cost",
        "source_sha": "d8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322",
        "dependency_sha": "ca5f5e8b6de0e95364383bb7481e091bb37595cc7e2668dd489eadb9e0b3bb3c",
        "profile_sha": "0fa3a9205eaec088f704bfc4139c15a01ec5a3b684300f37015b7aa464282308",
        "tasks": ["P11", "P12"], "modes": ["ledger", "preflight", "live"],
        "env": ["AI4ORGCHEM_HIGH_COST_COMMIT", "AI4ORGCHEM_HIGH_COST_SOURCE_SHA256", "AI4ORGCHEM_HIGH_COST_DEPENDENCY_SHA256"],
    },
}
HIGH_COST_BASELINE = "locks/high-cost-source.installation-baseline.json"
HIGH_COST_HOST_OVERRIDES = {
    "scripts/run-high-cost-case.py": {
        "base_sha256": "76fa7c77f9d4ef61fc60c95b809fcd30ee16b70d9639445461f78694432eca55",
        "sha256": "55c5306ba2ee493e521e533c05d39f5be8870de40dff7da6040680fedaeda607"},
    "tests/test_high_cost_supervisor.py": {
        "base_sha256": "923a6d61569ca76f600246d8e230149812c78c8ecc4bfc8a9d053ab43595c229",
        "sha256": "0a478092ac794c5979cde71772b353a06dc4498fcc41fc253cec3f71e4132b66"},
}
FIELDS = {"schema", "backend", "service", "tasks", "modes", "platform", "status",
          "scientific_acceptance", "capabilities", "image_id", "local_tag",
          "base_image_id", "image_build_runtime_commit", "source_snapshot_sha256",
          "dependency_lock_sha256", "profile_sha256", "dependency_lock_base_image_id",
          "host_files", "evidence", "source_catalog_binding", "registered_utc"}
EVIDENCE_FILES = ("image-inspect.json", "base-image-inspect.json", "inventory.json")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    path = checked_file(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Oversized installation evidence")
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("Nonfinite JSON: " + value)
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=nonfinite)
    json.dumps(value, allow_nan=False)
    return value


def checked_file(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                raise ValueError("Linked or reparse installation path forbidden")
    if not path.is_file():
        raise ValueError("Missing installation file: " + str(path))
    return path


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                                allow_nan=False) + "\n")


def service_spec(service):
    if not isinstance(service, str) or service not in SERVICES:
        raise ValueError("Only explicitly supported installation services are allowed")
    return SERVICES[service]


def capabilities(service):
    return {"single-point": "PROFILE_BOUND_NUMERICAL_GATES_REQUIRED" if service == "molecular-service" else "NOT_REGISTERED_FOR_THIS_INSTALLATION",
            "conditional_user_compute": "BLOCKED", "native_compute": "BLOCKED",
            "registered_protocol_tasks": "NOT_REGISTERED_FOR_THIS_INSTALLATION" if service == "molecular-service" else "FIXED_SERVICE_TASKS_ONLY"}


def load_launcher(service="molecular-service"):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("_installed_frozen_launcher_" + service.replace("-", "_"), ROOT / service_spec(service)["launcher"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_host_identity(service="molecular-service"):
    import importlib
    spec = service_spec(service)
    for name in ("source", "dependency", "profile"):
        if name == "source":
            continue
        if digest(checked_file(ROOT / spec[name])) != spec[name + "_sha"]:
            raise ValueError("Installation cannot replace the approved frozen lock/profile: " + name)
    if (ROOT / source_bindings.baseline_path(service)).is_file():
        source, binding = source_bindings.bind(ROOT, service)
    else:
        # A historical catalog is accepted only if every original byte still
        # matches. New launchers cannot register themselves as an old image.
        if digest(checked_file(ROOT / spec['source'])) != spec['source_sha']:
            raise ValueError('Installation cannot replace the frozen source catalog')
        source = importlib.import_module(spec["module"]).verify_source()
        binding = {"kind": "FROZEN_SOURCE_CATALOG", "baseline_sha256": spec["source_sha"],
                   "source_sha256": spec["source_sha"], "file_count": len(source["files"]), "host_overrides": {}}
    dependency = read_json(ROOT / spec["dependency"])
    if not IMAGE_SHA.fullmatch(str(dependency.get("base_image_id"))):
        raise ValueError("Frozen dependency lock identity differs")
    if not isinstance(dependency.get("packages"), dict) or not dependency["packages"] or any(not isinstance(k, str) or not isinstance(v, str) for k, v in dependency["packages"].items()):
        raise ValueError("Frozen dependency package versions required")
    files = dict(source["files"]) if isinstance(source["files"], dict) else {row["path"]: row["sha256"] for row in source["files"]}
    files[spec["source"]] = digest(ROOT / spec["source"])
    if binding['kind'] == source_bindings.KIND:
        files[source_bindings.baseline_path(service)] = spec["source_sha"]
    for name in HOST_FILES:
        files[name] = digest(checked_file(ROOT / name))
    # Each critical path is also checked against linked/reparse ancestry.
    for name in files:
        checked_file(ROOT / name)
    return {
        "source_snapshot_sha256": digest(ROOT / spec["source"]),
        "dependency_lock_sha256": digest(ROOT / spec["dependency"]),
        "profile_sha256": digest(ROOT / spec["profile"]),
        "dependency_lock_base_image_id": dependency["base_image_id"],
        "host_files": {name: digest(checked_file(ROOT / name)) for name in HOST_FILES},
        "source_catalog_binding": binding,
        "inventory": {"schema": "molecular-installation-inventory-v1", "files": files,
                      "python_version": dependency["python_version"], "packages": dependency["packages"]},
    }


def high_cost_source_binding():
    """Allow exactly two already reviewed host changes; freeze all other 105 rows."""
    spec = SERVICES["high-cost-cases"]
    baseline_path = checked_file(ROOT / HIGH_COST_BASELINE)
    if digest(baseline_path) != spec["source_sha"]:
        raise ValueError("Original 107-file source catalog byte identity required")
    baseline = read_json(baseline_path)
    source = read_json(ROOT / spec["source"])
    if not isinstance(source, dict) or set(source) != set(baseline) or {k: v for k, v in source.items() if k != "files"} != {k: v for k, v in baseline.items() if k != "files"}:
        raise ValueError("High-cost catalog schema/scope cannot be changed")
    base_rows, rows = baseline.get("files"), source.get("files")
    if not isinstance(base_rows, list) or not isinstance(rows, list) or len(rows) != 107 or len(base_rows) != 107:
        raise ValueError("Exactly 107 original high-cost paths required")
    overrides = {}
    for original, actual in zip(base_rows, rows):
        if not isinstance(actual, dict) or set(actual) != {"path", "sha256", "size"} or actual["path"] != original["path"]:
            raise ValueError("High-cost catalog paths/order/fields differ")
        name = actual["path"]
        if name in HIGH_COST_HOST_OVERRIDES:
            allowed = HIGH_COST_HOST_OVERRIDES[name]
            if original["sha256"] != allowed["base_sha256"] or actual["sha256"] != allowed["sha256"] or type(actual["size"]) is not int or actual["size"] < 0:
                raise ValueError("Only the two approved final-evidence host byte changes are allowed")
            overrides[name] = {**allowed, "size": actual["size"]}
        elif actual != original:
            raise ValueError("High-cost scientific/source catalog row changed: " + name)
        file = checked_file(ROOT / name)
        if digest(file) != actual["sha256"] or file.stat().st_size != actual["size"]:
            raise ValueError("High-cost installed source bytes differ: " + name)
    if set(overrides) != set(HIGH_COST_HOST_OVERRIDES):
        raise ValueError("Exactly both approved host paths must be rebound")
    return source, {"kind": "EXACT_TWO_HOST_PATH_REBIND", "baseline_sha256": spec["source_sha"],
                    "source_sha256": digest(ROOT / spec["source"]), "file_count": 107,
                    "unchanged_rows": 105, "host_overrides": overrides}


def validate_record(record, *, expected=None):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("Closed installation record fields required")
    spec = service_spec(record.get("service"))
    fixed = {"schema": SCHEMA, "backend": "docker", "tasks": spec["tasks"], "modes": spec["modes"], "platform": "linux/amd64",
             "status": "ENGINEERING_VALIDATED", "scientific_acceptance": "UNKNOWN",
             "capabilities": capabilities(record["service"])}
    if any(type(record.get(k)) is not type(v) or record[k] != v for k, v in fixed.items()):
        raise ValueError("Installation scope/status cannot authorize historical science or other tasks")
    for key in ("image_id", "base_image_id", "dependency_lock_base_image_id"):
        if not isinstance(record[key], str) or not IMAGE_SHA.fullmatch(record[key]):
            raise ValueError("Complete immutable image/base identity required")
    if not isinstance(record["image_build_runtime_commit"], str) or not COMMIT.fullmatch(record["image_build_runtime_commit"]):
        raise ValueError("Complete build commit required")
    for key in ("source_snapshot_sha256", "dependency_lock_sha256", "profile_sha256"):
        if not isinstance(record[key], str) or not SHA.fullmatch(record[key]):
            raise ValueError("Complete source/dependency/profile digest required")
    if not isinstance(record["local_tag"], str) or not TAG.fullmatch(record["local_tag"]):
        raise ValueError("Explicit local image tag required")
    for key, names in (("host_files", HOST_FILES), ("evidence", EVIDENCE_FILES)):
        value = record[key]
        if not isinstance(value, dict) or set(value) != set(names) or any(not isinstance(v, str) or not SHA.fullmatch(v) for v in value.values()):
            raise ValueError("Complete closed installation " + key + " required")
    try:
        stamp = datetime.fromisoformat(record["registered_utc"])
    except (TypeError, ValueError):
        raise ValueError("UTC registration timestamp required") from None
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("UTC registration timestamp required")
    binding = record["source_catalog_binding"]
    common = {"kind", "baseline_sha256", "source_sha256", "file_count", "host_overrides"}
    required_binding = common | ({"unchanged_rows"} if binding.get('kind') in ('EXACT_TWO_HOST_PATH_REBIND', source_bindings.KIND) else set()) if isinstance(binding, dict) else common
    if not isinstance(binding, dict) or set(binding) != required_binding or binding.get("baseline_sha256") != spec["source_sha"] or binding.get("source_sha256") != record["source_snapshot_sha256"]:
        raise ValueError("Closed source catalog baseline binding required")
    if type(binding.get("file_count")) is not int or binding["file_count"] < 1:
        raise ValueError("Exact source catalog file count required")
    if binding['kind'] == source_bindings.KIND:
        source_bindings.validate_binding(record['service'], binding, record['source_snapshot_sha256'])
    elif record["service"] == "high-cost-cases":
        if binding["kind"] != "EXACT_TWO_HOST_PATH_REBIND" or binding["file_count"] != 107 or type(binding["unchanged_rows"]) is not int or binding["unchanged_rows"] != 105 or not isinstance(binding["host_overrides"], dict) or set(binding["host_overrides"]) != set(HIGH_COST_HOST_OVERRIDES):
            raise ValueError("Only the exact approved two-host-path installation scope is allowed")
        for name, row in binding["host_overrides"].items():
            if not isinstance(row, dict) or set(row) != {"base_sha256", "sha256", "size"} or {k: row[k] for k in ("base_sha256", "sha256")} != HIGH_COST_HOST_OVERRIDES[name] or type(row["size"]) is not int or row["size"] < 0:
                raise ValueError("Approved host override identity required")
    elif binding["kind"] != "FROZEN_SOURCE_CATALOG" or binding["host_overrides"] != {} or record["source_snapshot_sha256"] != spec["source_sha"]:
        raise ValueError("Frozen service source catalog cannot be rebound")
    if expected is not None:
        for key in ("source_snapshot_sha256", "dependency_lock_sha256", "profile_sha256", "dependency_lock_base_image_id", "host_files", "source_catalog_binding"):
            if record[key] != expected[key]:
                raise ValueError("Current frozen source/dependency/profile/host differs: " + key)
    return record


def legacy_record(record):
    value = {key: record[key] for key in ("image_id", "image_build_runtime_commit",
            "source_snapshot_sha256", "dependency_lock_sha256", "base_image_id", "profile_sha256")}
    if record["service"] == "protocol-cases":
        value["source_lock_sha256"] = value.pop("source_snapshot_sha256")
    if record["service"] == "high-cost-cases":
        value["source_sha256"] = value.pop("source_snapshot_sha256")
        value["dependencies_sha256"] = value.pop("dependency_lock_sha256")
        value["runtime_build_commit"] = value.pop("image_build_runtime_commit")
    return value


def verify_inspections(image, base, record):
    spec = service_spec(record["service"])
    launcher = load_launcher(record["service"])
    if record["service"] == "high-cost-cases":
        launcher.image_check(image, legacy_record(record))
    else:
        launcher.verify_image_inspection(image, legacy_record(record))
    if base.get("Id") != record["base_image_id"] or base.get("Os") != "linux" or base.get("Architecture") != "amd64":
        raise ValueError("Immediate base image identity/platform differs")
    layers = image.get("RootFS", {}).get("Layers")
    base_layers = base.get("RootFS", {}).get("Layers")
    if not isinstance(layers, list) or not isinstance(base_layers, list) or not base_layers or len(layers) <= len(base_layers) or layers[:len(base_layers)] != base_layers:
        raise ValueError("Image layers do not extend the recorded immediate base")
    if image.get("Config", {}).get("User") != "10001:10001":
        raise ValueError("Installed worker image must retain the non-root user")
    if record["local_tag"] not in (image.get("RepoTags") or []):
        raise ValueError("Local tag does not identify the immutable image")
    env = dict(row.split("=", 1) for row in image.get("Config", {}).get("Env", []) if "=" in row)
    expected = dict(zip(spec["env"], (record["image_build_runtime_commit"], record["source_snapshot_sha256"], record["dependency_lock_sha256"])))
    if any(env.get(key) != value for key, value in expected.items()):
        raise ValueError("Worker environment build identity differs")


def inspect_one(executable, reference):
    process = subprocess.run([executable, "image", "inspect", reference], capture_output=True, timeout=30, check=True)
    result = json.loads(process.stdout)
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise ValueError("One actual image inspection required")
    return result[0]


def image_inventory(executable, image_id, expected):
    # Fixed stdlib-only inventory: no scientific imports, kernels or capacity probe.
    names = sorted(expected["files"])
    packages = sorted(expected["packages"])
    program = ("import hashlib,json,platform,pathlib,importlib.metadata as m;"
               "r=pathlib.Path('/opt/runtime');"
               "n=" + repr(names) + ";p=" + repr(packages) + ";"
               "assert all((r/x).is_file() and not (r/x).is_symlink() for x in n);"
               "print(json.dumps({'schema':'molecular-installation-inventory-v1',"
               "'files':{x:hashlib.sha256((r/x).read_bytes()).hexdigest() for x in n},"
               "'python_version':platform.python_version(),'packages':{x:m.version(x) for x in p}},sort_keys=True))")
    name = "molecular-installation-check-" + uuid.uuid4().hex
    label = "ai4orgchem.installation.check-id=" + name
    command = [executable, "create", "--name", name, "--label", label, "--network", "none",
               "--read-only", "--user", "10001:10001", "--memory", "134217728", "--memory-swap", "134217728",
               "--cpus", "1", "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--entrypoint", "/opt/venv/bin/python", image_id, "-B", "-c", program]
    cid = None
    try:
        cid = subprocess.run(command, capture_output=True, timeout=30, check=True).stdout.decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise ValueError("Complete inventory container ID required")
        process = subprocess.run([executable, "start", "--attach", cid], capture_output=True, timeout=45, check=True)
        inventory = json.loads(process.stdout)
        if inventory != expected:
            raise ValueError("Actual immutable image critical bytes or installed dependencies differ")
        return inventory
    finally:
        # An interrupted create is found by its unique name. Never remove another container.
        inspected = subprocess.run([executable, "inspect", cid or name], capture_output=True, timeout=15)
        if inspected.returncode == 0:
            rows = json.loads(inspected.stdout)
            if len(rows) != 1 or rows[0].get("Image") != image_id or (rows[0].get("Config", {}).get("Labels") or {}).get("ai4orgchem.installation.check-id") != name:
                raise ValueError("Inventory cleanup ownership differs")
            owned = rows[0]["Id"]
            subprocess.run([executable, "rm", "--force", owned], capture_output=True, timeout=15, check=True)
            absent = subprocess.run([executable, "inspect", owned], capture_output=True, timeout=15)
            if absent.returncode != 1 or not any(s in absent.stderr.decode("utf-8", "replace").lower() for s in ("no such object", "no such container")):
                raise ValueError("Inventory container removal unconfirmed")
        elif inspected.returncode != 1 or not any(s in inspected.stderr.decode("utf-8", "replace").lower() for s in ("no such object", "no such container")):
            raise ValueError("Inventory container absence unknown")


def verify_installation(path, executable="docker", *, inspect=inspect_one, inventory=image_inventory):
    path = checked_file(path)
    record = read_json(path)
    expected = expected_host_identity(record.get("service"))
    validate_record(record, expected=expected)
    evidence = {}
    for name, sha in record["evidence"].items():
        file = checked_file(path.parent / name)
        if digest(file) != sha:
            raise ValueError("Installation evidence bytes differ: " + name)
        evidence[name] = read_json(file)
    verify_inspections(evidence["image-inspect.json"], evidence["base-image-inspect.json"], record)
    if evidence["inventory.json"] != expected["inventory"]:
        raise ValueError("Recorded inventory differs from frozen source/dependency identities")
    actual = inspect(executable, record["image_id"])
    base = inspect(executable, record["base_image_id"])
    tagged = inspect(executable, record["local_tag"])
    if tagged.get("Id") != record["image_id"]:
        raise ValueError("Local tag was retargeted")
    verify_inspections(actual, base, record)
    current_inventory = inventory(executable, record["image_id"], expected["inventory"])
    return record, {"schema": "molecular-installation-preflight-v1", "status": "PASS_ENGINEERING_IDENTITY",
                    "installation_record_sha256": digest(path), "image_id": record["image_id"],
                    "installation_record_canonical_sha256": hashlib.sha256((json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")).hexdigest(),
                    "scientific_acceptance": "UNKNOWN", "inventory": current_inventory}


def register(args):
    launcher = load_launcher(args.service)
    output = launcher.validate_directory(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    expected = expected_host_identity(args.service)
    spec = service_spec(args.service)
    image = inspect_one(args.docker_executable, args.image)
    labels = image.get("Config", {}).get("Labels") or {}
    base_id = labels.get("ai4orgchem." + spec["prefix"] + ".base-image-id")
    if not IMAGE_SHA.fullmatch(str(base_id)):
        raise ValueError("Image label must bind its immutable immediate base")
    base = inspect_one(args.docker_executable, base_id)
    record = {"schema": SCHEMA, "backend": "docker", "service": args.service, "tasks": list(spec["tasks"]), "modes": list(spec["modes"]),
              "platform": "linux/amd64", "status": "ENGINEERING_VALIDATED", "scientific_acceptance": "UNKNOWN",
              "capabilities": capabilities(args.service), "image_id": image["Id"], "local_tag": args.image,
              "base_image_id": base_id, "image_build_runtime_commit": labels.get("ai4orgchem." + spec["prefix"] + ".runtime-commit"),
              **{key: expected[key] for key in ("source_snapshot_sha256", "dependency_lock_sha256", "profile_sha256",
                                               "dependency_lock_base_image_id", "host_files", "source_catalog_binding")},
              "evidence": {name: "0" * 64 for name in EVIDENCE_FILES},
              "registered_utc": datetime.now(timezone.utc).isoformat()}
    validate_record(record, expected=expected)
    verify_inspections(image, base, record)
    actual_inventory = image_inventory(args.docker_executable, record["image_id"], expected["inventory"])
    for name, value in zip(EVIDENCE_FILES, (image, base, actual_inventory)):
        save_new(output / name, value)
        record["evidence"][name] = digest(output / name)
    save_new(output / "installation-record.json", record)
    return output / "installation-record.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", choices=tuple(SERVICES), default="molecular-service")
    parser.add_argument("--image", required=True, help="Explicit local service image tag; no pulls are performed")
    parser.add_argument("--output-dir", type=Path, required=True, help="New independent installation record directory")
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        record = register(args)
    except Exception as error:
        print(json.dumps({"status": "REFUSED_INSTALLATION_REGISTRATION", "error": str(error)}))
        return 40
    print(json.dumps({"status": "ENGINEERING_VALIDATED", "scientific_acceptance": "UNKNOWN", "installation_record": str(record)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
