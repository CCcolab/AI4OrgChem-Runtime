"""Stdlib-only metadata worker, sent to the selected Python through stdin."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys

PACKAGES = ("pyscf", "numpy", "scipy", "geometric", "PyYAML", "jsonschema", "Pillow")


def digest(path):
    with Path(path).open("rb") as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def memory_snapshot(proc=Path("/proc")):
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    result = {}
    for row in (proc / "meminfo").read_text().splitlines():
        key, _, rest = row.partition(":")
        if key in wanted:
            value, unit = rest.split()
            if unit != "kB":
                raise ValueError("Unexpected proc memory unit")
            result[key + "_bytes"] = int(value) * 1024
    return result


def cgroup_snapshot(proc=Path("/proc")):
    membership = (proc / "self/cgroup").read_text().splitlines()
    mounts = (proc / "self/mountinfo").read_text().splitlines()
    result = {"memberships": membership, "memory_hierarchy": [], "errors": [], "resource_profile": "NOT_IMPLEMENTED"}
    for row in membership:
        _, controllers, relative = row.split(":", 2)
        version = 2 if controllers == "" else 1
        if version == 1 and "memory" not in controllers.split(","):
            continue
        for mount in mounts:
            left, right = mount.split(" - ", 1)
            fields, fs = left.split(), right.split()
            if fs[0] != ("cgroup2" if version == 2 else "cgroup") or (version == 1 and "memory" not in fs[2].split(",")):
                continue
            mount_path = Path(fields[4].replace("\\040", " "))
            relative_path = PurePosixPath(relative)
            root = PurePosixPath(fields[3])
            leaf = mount_path / str(relative_path.relative_to(root)) if relative_path.is_relative_to(root) else mount_path
            names = ("memory.max", "memory.current", "memory.swap.max", "memory.swap.current") if version == 2 else ("memory.limit_in_bytes", "memory.usage_in_bytes", "memory.memsw.limit_in_bytes", "memory.memsw.usage_in_bytes")
            while True:
                counters = {}
                for name in names:
                    try:
                        counters[name] = (leaf / name).read_text().strip()
                    except OSError:
                        counters[name] = None
                result["memory_hierarchy"].append({"version": version, "path": str(leaf), "counters": counters})
                if leaf == mount_path:
                    break
                leaf = leaf.parent
            break
    if not result["memory_hierarchy"]:
        result["errors"].append("No mounted memory controller observed")
    return result


def observe(source_files):
    packages = {}
    for name in PACKAGES:
        try:
            distribution = importlib.metadata.distribution(name)
            metadata_bytes = (distribution.read_text("METADATA") or "").encode("utf-8")
            packages[name] = {"version": distribution.version,
                              "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                              "location": str(distribution.locate_file(""))}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"version": None}
    source_rows = [{"path": path, "resolved_path": str(Path(path).resolve(strict=True)), "sha256": digest(path)} for path in source_files]
    identity = {"backend": "native-wsl2", "image_id": None, "python_executable": sys.executable,
                "python_prefix": sys.prefix, "python_version": platform.python_version(),
                "kernel_release": platform.release(), "machine": platform.machine(),
                "packages": packages, "source_files": source_rows,
                "identity_scope": "Metadata and explicit source hashes; not an immutable environment snapshot"}
    return {"schema_version": "native-wsl2-observation-v1", "compute_enabled": False, "qm_calls": 0,
            "environment_identity": identity, "uid": os.getuid(), "memory": memory_snapshot(),
            "cgroup": cgroup_snapshot(), "logical_cpus": os.cpu_count(),
            "affinity_cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "pid1_name": Path("/proc/1/comm").read_text().strip(),
            "available_tools": {name: shutil.which(name) for name in ("systemd-run", "prlimit", "unshare", "timeout", "taskset", "flock")},
            "python_isolated": bool(sys.flags.isolated), "bytecode_disabled": bool(sys.dont_write_bytecode),
            "user_site_disabled": bool(sys.flags.no_user_site),
            "resource_observation_grants_compute": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(observe(args.source_file), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
