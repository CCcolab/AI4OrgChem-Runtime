"""Verified runtime source snapshots; no installation, engine or network actions.

Git object proofs bind a snapshot to its declared commit. They do not authenticate
its publisher: use an independently confirmed commit or manifest digest when
accepting an externally supplied archive. Prepared directories are snapshots,
never synthetic Git repositories.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile


MANIFEST_NAME = "RUNTIME_SOURCE_MANIFEST.json"
IDENTITY_NAME = "SOURCE_IDENTITY.json"
SCHEMA = "ai4orgchem-runtime-source-snapshot-v1"
MAX_FILES = 10000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_RESERVED = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
             *("LPT" + str(i) for i in range(1, 10))}


class SourcePreparationError(ValueError):
    """Source bytes or provenance do not satisfy the snapshot contract."""


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _git_oid(kind, raw, object_format):
    return hashlib.new(object_format, kind.encode("ascii") + b" " + str(len(raw)).encode("ascii")
                       + b"\0" + raw).hexdigest()


def _path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise SourcePreparationError("Unsafe source path")
    parts = name.split("/")
    if any(not p or p in (".", "..") or p.lower() == ".git" or p[-1:] in (".", " ")
           or any(ord(c) < 32 or c in '<>\"|?*' for c in p)
           or p.split(".")[0].upper() in _RESERVED for p in parts):
        raise SourcePreparationError("Unsafe or nonportable source path: " + name)
    if PurePosixPath(name).is_absolute():
        raise SourcePreparationError("Absolute source path")
    return name


def _unique_paths(names):
    seen = set(); directory_spelling = {}
    for name in names:
        _path(name)
        folded = name.casefold()
        if folded in seen:
            raise SourcePreparationError("Duplicate or case-colliding source path: " + name)
        seen.add(folded)
        parts = name.split("/")
        for i in range(1, len(parts)):
            directory = "/".join(parts[:i]); key = directory.casefold()
            if key in directory_spelling and directory_spelling[key] != directory:
                raise SourcePreparationError("Case-colliding source directory")
            directory_spelling[key] = directory
    values = {name.casefold() for name in names}
    for name in values:
        parts = name.split("/")
        if any("/".join(parts[:i]) in values for i in range(1, len(parts))):
            raise SourcePreparationError("File/directory path collision")


def _git(root, *args, input_bytes=None):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                             "-C", str(root), *args], input=input_bytes,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if result.returncode:
        raise SourcePreparationError("Read-only Git command failed: "
                                     + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _read_objects(root, object_ids):
    ordered = sorted(set(object_ids))
    raw = _git(root, "cat-file", "--batch", input_bytes=("\n".join(ordered) + "\n").encode("ascii"))
    result = {}
    offset = 0
    for expected in ordered:
        end = raw.find(b"\n", offset)
        if end < 0:
            raise SourcePreparationError("Incomplete Git object proof")
        header = raw[offset:end].decode("ascii").split()
        if len(header) != 3 or header[0] != expected or not header[2].isdigit():
            raise SourcePreparationError("Invalid Git object proof header")
        size = int(header[2]); start = end + 1; finish = start + size
        if finish >= len(raw) or raw[finish:finish + 1] != b"\n":
            raise SourcePreparationError("Truncated Git object proof")
        result[expected] = (header[1], raw[start:finish]); offset = finish + 1
    if offset != len(raw):
        raise SourcePreparationError("Unexpected Git object proof bytes")
    return result


def _decode_proof(value):
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise SourcePreparationError("Invalid base64 Git proof") from exc


def _tree_files(manifest):
    fmt = manifest.get("git_object_format")
    if fmt not in ("sha1", "sha256"):
        raise SourcePreparationError("Unsupported Git object format")
    width = hashlib.new(fmt).digest_size
    commit = manifest.get("runtime_commit")
    if not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{" + str(width * 2) + "}", commit):
        raise SourcePreparationError("Expected a full actual Git commit identity")
    commit_raw = _decode_proof(manifest.get("commit_object_base64"))
    if _git_oid("commit", commit_raw, fmt) != commit:
        raise SourcePreparationError("Commit object identity mismatch")
    first = commit_raw.split(b"\n", 1)[0]
    if not first.startswith(b"tree "):
        raise SourcePreparationError("Commit has no root tree")
    root_tree = first[5:].decode("ascii")
    if manifest.get("runtime_tree") != root_tree:
        raise SourcePreparationError("Commit/tree binding mismatch")
    trees = manifest.get("tree_objects_base64")
    if not isinstance(trees, dict) or len(trees) > MAX_FILES:
        raise SourcePreparationError("Invalid tree proof inventory")
    used = set(); active = set(); files = {}

    def visit(oid, prefix):
        if prefix.count("/") > 128 or len(files) > MAX_FILES:
            raise SourcePreparationError("Git source tree exceeds inventory/depth limits")
        if oid in active or oid not in trees:
            raise SourcePreparationError("Missing or cyclic tree proof")
        active.add(oid); used.add(oid)
        raw = _decode_proof(trees[oid])
        if _git_oid("tree", raw, fmt) != oid:
            raise SourcePreparationError("Tree object identity mismatch")
        position = 0
        while position < len(raw):
            space = raw.find(b" ", position); zero = raw.find(b"\0", space + 1)
            if space < 0 or zero < 0 or zero + 1 + width > len(raw):
                raise SourcePreparationError("Invalid Git tree entry")
            mode = raw[position:space].decode("ascii")
            try:
                name = raw[space + 1:zero].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SourcePreparationError("Non-UTF8 Git path") from exc
            if "/" in name:
                raise SourcePreparationError("Invalid Git tree path")
            path = _path(prefix + name)
            child = raw[zero + 1:zero + 1 + width].hex()
            position = zero + 1 + width
            if mode == "40000":
                visit(child, path + "/")
            elif mode in ("100644", "100755"):
                if path in files:
                    raise SourcePreparationError("Duplicate Git path")
                files[path] = {"git_blob_id": child, "git_mode": mode}
            else:
                raise SourcePreparationError("Symlinks/submodules are unsupported source inputs")
        active.remove(oid)

    visit(root_tree, "")
    if set(trees) != used:
        raise SourcePreparationError("Unreferenced tree proof")
    _unique_paths(files)
    return files


def _canonical_blob(path, raw, policy):
    if policy == "RAW_BYTES":
        return raw
    if policy == "PS1_CRLF_TO_LF" and path.lower().endswith(".ps1") and b"\r\n" in raw:
        return raw.replace(b"\r\n", b"\n")
    raise SourcePreparationError("Invalid or inapplicable checkout byte policy")


def _source_records(manifest):
    keys = {"schema", "runtime_commit", "runtime_tree", "git_object_format", "commit_object_base64",
            "tree_objects_base64", "publisher_authentication", "file_count", "files"}
    if not isinstance(manifest, dict) or set(manifest) != keys or manifest.get("schema") != SCHEMA:
        raise SourcePreparationError("Unsupported source manifest")
    records = manifest.get("files")
    if not isinstance(records, list) or not records or len(records) > MAX_FILES:
        raise SourcePreparationError("Invalid source inventory")
    row_keys = {"path", "size_bytes", "sha256", "git_blob_id", "git_mode", "checkout_byte_policy"}
    if any(not isinstance(row, dict) or set(row) != row_keys for row in records):
        raise SourcePreparationError("Invalid source file record")
    _unique_paths([row["path"] for row in records])
    return records


def _validate(manifest, contents, *, expected_commit=None):
    records = _source_records(manifest)
    if manifest.get("publisher_authentication") != "NOT_ESTABLISHED_BY_LOCAL_OBJECT_PROOFS":
        raise SourcePreparationError("Unsupported publisher authentication claim")
    git_files = _tree_files(manifest)
    names = [row.get("path") for row in records]
    _unique_paths(names)
    if MANIFEST_NAME.casefold() in {n.casefold() for n in names} or IDENTITY_NAME.casefold() in {n.casefold() for n in names}:
        raise SourcePreparationError("Reserved provenance filename in Git source")
    if names != sorted(names) or set(names) != set(git_files) or set(contents) != set(names):
        raise SourcePreparationError("Incomplete or extra source files")
    total = 0
    for row in records:
        path = row["path"]; raw = contents[path]; proof = git_files[path]
        if type(row.get("size_bytes")) is not int or row["size_bytes"] != len(raw):
            raise SourcePreparationError("Source size mismatch: " + path)
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise SourcePreparationError("Source snapshot exceeds declared safety limits")
        if row.get("sha256") != _digest(raw):
            raise SourcePreparationError("Source SHA-256 mismatch: " + path)
        if any(row.get(key) != proof[key] for key in ("git_blob_id", "git_mode")):
            raise SourcePreparationError("Commit/blob binding mismatch: " + path)
        canonical = _canonical_blob(path, raw, row.get("checkout_byte_policy"))
        if _git_oid("blob", canonical, manifest["git_object_format"]) != proof["git_blob_id"]:
            raise SourcePreparationError("Source bytes do not match declared Git blob: " + path)
    if manifest.get("file_count") != len(records) or type(manifest.get("file_count")) is not int:
        raise SourcePreparationError("Source inventory count mismatch")
    if expected_commit is not None and manifest["runtime_commit"] != expected_commit:
        raise SourcePreparationError("Independently expected commit differs")
    return manifest


def inspect_git_source(source_root):
    """Read a clean committed checkout and return its manifest plus owned bytes."""
    root = Path(source_root).resolve(strict=True)
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if root != top:
        raise SourcePreparationError("Source must be the Git worktree root")
    fmt = _git(root, "rev-parse", "--show-object-format").decode("ascii").strip()
    if fmt not in ("sha1", "sha256"):
        raise SourcePreparationError("Unsupported Git object format")
    commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    root_tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    entries = _git(root, "ls-tree", "-rz", "HEAD").split(b"\0")
    files = {}
    for entry in filter(None, entries):
        header, name = entry.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        path = _path(name.decode("utf-8"))
        if kind != "blob" or mode not in ("100644", "100755"):
            raise SourcePreparationError("Only regular committed source files are supported")
        files[path] = (mode, oid)
    _unique_paths(files)
    # Attribute lookup itself does not execute filters. Refuse any active filter
    # before asking status to clean/compare worktree bytes; no LFS or custom code.
    attrs = _git(root, "check-attr", "-z", "--stdin", "filter",
                 input_bytes=b"\0".join(path.encode("utf-8") for path in files) + b"\0").split(b"\0")
    if len(attrs) != len(files) * 3 + 1 or attrs[-1] != b"":
        raise SourcePreparationError("Invalid Git filter attribute response")
    if any(attrs[i] not in (b"unspecified", b"unset") for i in range(2, len(attrs) - 1, 3)):
        raise SourcePreparationError("Active Git clean/process filters are unsupported source inputs")
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise SourcePreparationError("Source Git checkout must be clean, including untracked files")
    tree_entries = _git(root, "ls-tree", "-rtz", "HEAD").split(b"\0")
    tree_ids = {root_tree}
    for entry in filter(None, tree_entries):
        header = entry.split(b"\t", 1)[0].decode("ascii").split()
        if header[1] == "tree":
            tree_ids.add(header[2])
    objects = _read_objects(root, {commit, *tree_ids, *(oid for _, oid in files.values())})
    if objects[commit][0] != "commit" or any(objects[oid][0] != "tree" for oid in tree_ids):
        raise SourcePreparationError("Git proof type mismatch")
    manifest = {"schema": SCHEMA, "runtime_commit": commit, "runtime_tree": root_tree,
                "git_object_format": fmt,
                "commit_object_base64": base64.b64encode(objects[commit][1]).decode("ascii"),
                "tree_objects_base64": {oid: base64.b64encode(objects[oid][1]).decode("ascii") for oid in sorted(tree_ids)},
                "publisher_authentication": "NOT_ESTABLISHED_BY_LOCAL_OBJECT_PROOFS",
                "file_count": len(files), "files": []}
    contents = {}
    for path in sorted(files):
        actual = root.joinpath(*path.split("/"))
        if actual.is_symlink() or not actual.is_file():
            raise SourcePreparationError("Source is not a regular file: " + path)
        if actual.stat().st_size > MAX_FILE_BYTES:
            raise SourcePreparationError("Source file exceeds snapshot safety limits")
        raw = actual.read_bytes(); mode, oid = files[path]
        if objects[oid][0] != "blob":
            raise SourcePreparationError("Git file proof type mismatch")
        policy = "RAW_BYTES"
        if raw != objects[oid][1]:
            if path.lower().endswith(".ps1") and raw.replace(b"\r\n", b"\n") == objects[oid][1] and b"\r\n" in raw:
                policy = "PS1_CRLF_TO_LF"
            else:
                raise SourcePreparationError("Checkout bytes differ from committed source: " + path)
        contents[path] = raw
        manifest["files"].append({"path": path, "size_bytes": len(raw), "sha256": _digest(raw),
                                  "git_blob_id": oid, "git_mode": mode, "checkout_byte_policy": policy})
    _validate(manifest, contents)
    if _git(root, "rev-parse", "HEAD").decode("ascii").strip() != commit or _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise SourcePreparationError("Git source changed during snapshot preparation")
    return {"manifest": manifest, "contents": contents}


def _load_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SourcePreparationError("Duplicate JSON manifest key")
            result[key] = value
        return result
    try:
        def invalid_constant(value):
            raise SourcePreparationError("Nonfinite JSON constant: " + value)
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourcePreparationError("Invalid UTF-8 source manifest") from exc


def _read_zip(path):
    contents = {}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES + 1:
                raise SourcePreparationError("Too many ZIP members")
            names = [info.filename for info in entries]; _unique_paths(names)
            total = 0
            for info in entries:
                mode = (info.external_attr >> 16) & 0xffff
                if info.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or info.flag_bits & 1:
                    raise SourcePreparationError("ZIP contains a directory, link or encrypted member")
                total += info.file_size
                if info.file_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise SourcePreparationError("ZIP exceeds source safety limits")
                contents[info.filename] = archive.read(info)  # Includes CRC verification.
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise SourcePreparationError("Invalid or corrupted source ZIP") from exc
    if MANIFEST_NAME not in contents:
        raise SourcePreparationError("ZIP has no RUNTIME_SOURCE_MANIFEST.json; an ordinary GitHub ZIP is view-only, not a verified build input")
    raw = contents.pop(MANIFEST_NAME)
    return _load_json(raw), raw, contents


def export_source_zip(source_root, destination_zip):
    """Export all committed source bytes and proofs to a new project ZIP."""
    snapshot = inspect_git_source(source_root)
    destination = Path(destination_zip).absolute()
    if destination.resolve().is_relative_to(Path(source_root).resolve()):
        raise SourcePreparationError("Archive output must be outside the source Git checkout")
    if destination.exists():
        raise SourcePreparationError("ZIP destination must be new")
    raw_manifest = _json_bytes(snapshot["manifest"])
    with destination.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted({**snapshot["contents"], MANIFEST_NAME: raw_manifest}.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3; info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
    return {"status": "SOURCE_ZIP_EXPORTED", "runtime_commit": snapshot["manifest"]["runtime_commit"],
            "source_manifest_sha256": _digest(raw_manifest), "archive_sha256": _digest(destination.read_bytes()),
            "file_count": snapshot["manifest"]["file_count"], "archive_path": str(destination)}


def _identity(manifest, raw_manifest, origin):
    return {"schema": "ai4orgchem-runtime-prepared-source-v1", "status": "VERIFIED_PREPARED_SOURCE",
            "runtime_commit": manifest["runtime_commit"], "runtime_tree": manifest["runtime_tree"],
            "git_object_format": manifest["git_object_format"], "source_manifest_sha256": _digest(raw_manifest),
            "file_count": manifest["file_count"], "source_kind": origin,
            "git_history_created": False, "publisher_authentication": manifest["publisher_authentication"],
            "scope": "RUNTIME_TRACKED_SOURCE_ONLY_NOT_SCIENCE_WHEELS_OR_IMAGE",
            "scientific_execution": "NOT_EXECUTED", "image_build": "NOT_EXECUTED"}


def prepare_runtime_source(source_root, target, *, expected_commit=None, expected_manifest_sha256=None):
    """Create a new, fully verified source directory from Git or a project ZIP."""
    source = Path(source_root)
    destination = Path(target).absolute()
    if destination.exists():
        raise SourcePreparationError("Prepared target must be new, not an existing directory")
    if source.is_dir():
        if destination.resolve().is_relative_to(source.resolve()):
            raise SourcePreparationError("Prepared target must be outside the source Git checkout")
        snapshot = inspect_git_source(source)
        manifest, contents = snapshot["manifest"], snapshot["contents"]
        raw_manifest = _json_bytes(manifest); origin = "CLEAN_GIT_CHECKOUT"
    else:
        manifest, raw_manifest, contents = _read_zip(source); origin = "PROJECT_SOURCE_ZIP"
    _validate(manifest, contents, expected_commit=expected_commit)
    if expected_manifest_sha256 is not None and _digest(raw_manifest) != expected_manifest_sha256:
        raise SourcePreparationError("Independently expected manifest digest differs")
    identity = _identity(manifest, raw_manifest, origin)
    destination.mkdir(parents=False, exist_ok=False)
    for row in manifest["files"]:
        path = destination.joinpath(*row["path"].split("/")); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(contents[row["path"]])
        if os.name != "nt" and row["git_mode"] == "100755":
            path.chmod(0o755)
    (destination / MANIFEST_NAME).write_bytes(raw_manifest)
    (destination / IDENTITY_NAME).write_bytes(_json_bytes(identity))
    return verify_prepared_source(destination, expected_commit=expected_commit,
                                  expected_manifest_sha256=expected_manifest_sha256)


def verify_prepared_source(root, *, expected_commit=None, expected_manifest_sha256=None):
    """Verify every snapshot byte and identity; never repair or initialize Git."""
    root = Path(root).resolve(strict=True)
    raw_manifest = (root / MANIFEST_NAME).read_bytes()
    manifest = _load_json(raw_manifest)
    identity = _load_json((root / IDENTITY_NAME).read_bytes())
    expected_names = {row["path"] for row in _source_records(manifest)}
    actual_names = set(); contents = {}; total = 0
    expected_directories = {"/".join(name.split("/")[:i]) for name in expected_names
                            for i in range(1, len(name.split("/")))}
    for path in root.rglob("*"):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise SourcePreparationError("Prepared source contains a symlink")
        name = path.relative_to(root).as_posix(); _path(name)
        if path.is_dir():
            if name not in expected_directories:
                raise SourcePreparationError("Unknown directory in prepared source")
        elif path.is_file():
            actual_names.add(name)
            if name not in (MANIFEST_NAME, IDENTITY_NAME):
                total += path.stat().st_size
                if path.stat().st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise SourcePreparationError("Prepared source exceeds snapshot safety limits")
                contents[name] = path.read_bytes()
        else:
            raise SourcePreparationError("Prepared source contains a nonregular entry")
    if actual_names != expected_names | {MANIFEST_NAME, IDENTITY_NAME}:
        raise SourcePreparationError("Missing or unknown file in prepared source")
    _validate(manifest, contents, expected_commit=expected_commit)
    if expected_manifest_sha256 is not None and _digest(raw_manifest) != expected_manifest_sha256:
        raise SourcePreparationError("Independently expected manifest digest differs")
    if not isinstance(identity, dict):
        raise SourcePreparationError("Invalid prepared source identity")
    origin = identity.get("source_kind")
    if origin not in ("CLEAN_GIT_CHECKOUT", "PROJECT_SOURCE_ZIP") or identity != _identity(manifest, raw_manifest, origin):
        raise SourcePreparationError("Prepared source identity mismatch")
    return dict(identity)
