#!/usr/bin/env python3
"""Prepare public, hash-locked CPython 3.12 Linux/amd64 build inputs.

Only downloads artifacts. It never installs a package into the host interpreter,
imports a scientific library, starts Docker/WSL, or executes a calculation.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "locks" / "installation-dependencies.json"
DEFAULT_REQUIREMENTS = ROOT / "locks" / "requirements-installation-linux-amd64.txt"
HEX = re.compile(r"[0-9a-f]{64}\Z")


class InputError(ValueError):
    pass


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate_lock(lock: dict) -> list[dict]:
    if lock.get("schema") != "installation-dependencies-v1":
        raise InputError("Unsupported installation dependency schema")
    if lock.get("target_platform") != "linux/amd64" or lock.get("python_version") != "3.12.13":
        raise InputError("This installer only supports the frozen Linux/amd64 Python 3.12.13 target")
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 22 or lock.get("explicit_distribution_count") != 22:
        raise InputError("Expected exactly 22 explicitly locked distributions")
    names: set[str] = set()
    filenames: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise InputError("Artifact row is not an object")
        name, version = item.get("name"), item.get("version")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise InputError("Invalid distribution name")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version):
            raise InputError("Invalid fixed version")
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        if canonical in names:
            raise InputError("Duplicate distribution name")
        names.add(canonical)
        filename = item.get("filename")
        if not isinstance(filename, str) or "/" in filename or "\\" in filename or not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
            raise InputError("Unsafe artifact filename")
        if filename in filenames:
            raise InputError("Duplicate artifact filename")
        filenames.add(filename)
        url = urlparse(item.get("url", ""))
        if url.scheme != "https" or url.hostname != "files.pythonhosted.org" or url.query or url.fragment or url.username:
            raise InputError("Artifact must have a direct HTTPS official PyPI file URL")
        if Path(url.path).name != filename:
            raise InputError("Artifact URL and filename disagree")
        metadata = urlparse(item.get("metadata_url", ""))
        if metadata.scheme != "https" or metadata.hostname != "pypi.org" or metadata.path != f"/pypi/{name}/{version}/json":
            raise InputError("Artifact metadata URL does not identify the locked version")
        if not isinstance(item.get("sha256"), str) or not HEX.fullmatch(item["sha256"]):
            raise InputError("Invalid artifact SHA-256")
        if not isinstance(item.get("size"), int) or item["size"] <= 0:
            raise InputError("Invalid artifact size")
        if name == "geometric":
            if item.get("packagetype") != "sdist" or filename != "geometric-1.1.1.tar.gz" or version != "1.1.1":
                raise InputError("geometric must use the locked official 1.1.1 source archive")
        elif item.get("packagetype") != "bdist_wheel" or not filename.endswith(".whl"):
            raise InputError("All other distributions must use their locked wheels")
        if lock.get("packages", {}).get(name) != version:
            raise InputError("Package versions and artifact rows disagree")
    if len(lock.get("packages", {})) != 22 or "geometric" not in lock["packages"]:
        raise InputError("Package inventory is incomplete")
    return artifacts


def requirements_text(artifacts: list[dict], *, wheels_only: bool = False) -> str:
    return "".join(
        f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}\n"
        for item in artifacts if not wheels_only or item["packagetype"] == "bdist_wheel"
    )


def validate_requirements(path: Path, artifacts: list[dict]) -> None:
    actual = "\n".join(line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                       if line.strip() and not line.lstrip().startswith("#")) + "\n"
    if actual != requirements_text(artifacts):
        raise InputError("Requirements file and installation artifact lock disagree")


def download_artifact(item: dict, directory: Path, *, opener=urlopen) -> dict:
    target = directory / item["filename"]
    partial = directory / (item["filename"] + ".partial")
    result = hashlib.sha256()
    size = 0
    request = Request(item["url"], headers={"User-Agent": "AI4OrgChem-Runtime-public-install-inputs/1"})
    with opener(request, timeout=120) as response, partial.open("xb") as output:
        actual_url = urlparse(response.geturl())
        if actual_url.scheme != "https" or actual_url.hostname != "files.pythonhosted.org":
            raise InputError("Artifact redirected outside the official HTTPS file service")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            size += len(block)
            if size > item["size"]:
                raise InputError(f"Downloaded size exceeds locked size: {item['filename']}")
            result.update(block)
            output.write(block)
    if size != item["size"] or result.hexdigest() != item["sha256"]:
        raise InputError(f"Downloaded artifact identity mismatch: {item['filename']}")
    partial.rename(target)
    return {"name": item["name"], "version": item["version"], "filename": item["filename"],
            "url": item["url"], "metadata_url": item["metadata_url"], "sha256": result.hexdigest(),
            "size": size, "relative_path": f"{directory.name}/{target.name}", "status": "VERIFIED"}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def prepare(output: Path, lock_path: Path = DEFAULT_LOCK, requirements_path: Path = DEFAULT_REQUIREMENTS) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    artifacts = validate_lock(lock)
    validate_requirements(requirements_path, artifacts)
    output = output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise InputError("Output must be a new or empty directory; existing build inputs are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    (output / "wheels").mkdir()
    (output / "sources").mkdir()
    receipt = {"schema": "installation-dependency-preparation-v1", "status": "PREPARING",
               "started_utc": datetime.now(timezone.utc).isoformat(), "lock_sha256": digest(lock_path),
               "requirements_sha256": digest(requirements_path), "target_platform": lock["target_platform"],
               "python_version": lock["python_version"], "artifacts": [],
               "host_installation_performed": False, "scientific_calculation_performed": False,
               "historical_acceptance_inherited": False, "geometric_wheel_build": "NOT_EXECUTED_HERE"}
    write_json(output / "dependency-preparation.receipt.json", receipt)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = {pool.submit(download_artifact, item, output / ("sources" if item["packagetype"] == "sdist" else "wheels")): item
                       for item in artifacts}
            for future in as_completed(pending):
                row = future.result()
                receipt["artifacts"].append(row)
                print(json.dumps({"artifact": row["filename"], "status": "VERIFIED", "size": row["size"]}), flush=True)
        receipt["artifacts"].sort(key=lambda row: row["name"].lower())
        (output / "requirements.txt").write_text(requirements_text(artifacts), encoding="utf-8", newline="\n")
        (output / "requirements-wheels.txt").write_text(requirements_text(artifacts, wheels_only=True), encoding="utf-8", newline="\n")
        (output / "installation-dependencies.json").write_bytes(lock_path.read_bytes())
        receipt.update(status="VERIFIED", completed_utc=datetime.now(timezone.utc).isoformat(),
                       artifact_count=len(receipt["artifacts"]), wheel_count=21, source_archive_count=1,
                       downloaded_bytes=sum(row["size"] for row in receipt["artifacts"]))
    except Exception as error:
        receipt.update(status="FAILED", error=f"{type(error).__name__}: {error}",
                       completed_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "dependency-preparation.receipt.json", receipt)
        raise
    write_json(output / "dependency-preparation.receipt.json", receipt)
    return receipt


def verify(output: Path, lock_path: Path = DEFAULT_LOCK) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    artifacts = validate_lock(lock)
    receipt_path = output / "dependency-preparation.receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("status") != "VERIFIED" or receipt.get("lock_sha256") != digest(lock_path):
            raise InputError("Preparation receipt is incomplete or belongs to a different dependency lock")
    expected_paths = {("sources" if item["packagetype"] == "sdist" else "wheels") + "/" + item["filename"] for item in artifacts}
    actual_paths = {str(p.relative_to(output)).replace("\\", "/") for d in (output / "wheels", output / "sources") for p in d.iterdir()}
    if actual_paths != expected_paths:
        raise InputError("Prepared artifact inventory differs from the lock")
    for item in artifacts:
        path = output / ("sources" if item["packagetype"] == "sdist" else "wheels") / item["filename"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["size"] or digest(path) != item["sha256"]:
            raise InputError(f"Prepared artifact identity mismatch: {item['filename']}")
    if (output / "requirements.txt").exists():
        validate_requirements(output / "requirements.txt", artifacts)
    if (output / "requirements-wheels.txt").exists():
        if (output / "requirements-wheels.txt").read_text(encoding="utf-8") != requirements_text(artifacts, wheels_only=True):
            raise InputError("Prepared wheel-only requirements disagree")
    return {"status": "VERIFIED", "artifact_count": 22, "wheel_count": 21, "source_archive_count": 1,
            "lock_sha256": digest(lock_path), "receipt_status": "VERIFIED" if receipt_path.exists() else "NOT_PROVIDED",
            "historical_acceptance_inherited": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--output", "--input", dest="output", type=Path, required=True)
        sub.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
        if command == "prepare":
            sub.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    args = parser.parse_args()
    try:
        result = prepare(args.output, args.lock, args.requirements) if args.command == "prepare" else verify(args.output, args.lock)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "FAILED", "error": f"{type(error).__name__}: {error}"}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
