"""Strict, bounded user XYZ admission for ordinary single-point calculations.

Only standard-library modules are imported. This layer neither constructs a
quantum-chemistry object nor edits the supplied coordinates or atom order.
The real AO count is deliberately left to engine preflight before SCF.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "profiles/molecular-service/rhf-631gd-small-v1.json"
MAX_REQUEST_BYTES = 64 * 1024
MAX_XYZ_BYTES = 256 * 1024
MAX_JSON_DEPTH = 32
ATOMIC_NUMBERS = {"H": 1, "C": 6, "N": 7, "O": 8}
REQUEST_KEYS = frozenset({"schema", "task", "profile", "structure", "charge", "multiplicity", "method", "basis"})
STRUCTURE_KEYS = frozenset({"file", "format", "unit"})
FIXED_SCOPE = {"elements": ["H", "C", "N", "O"], "charge": 0, "multiplicity": 1,
               "max_atoms": 20, "coordinate_unit": "angstrom", "max_abs_coordinate_angstrom": 10000,
               "allow_three_dimensional_geometry": True, "min_nuclear_distance_angstrom": 0.5}
FIXED_ENGINE = {"program": "pyscf", "method": "RHF", "basis": "6-31G(d)", "symmetry": False,
                "conv_tol": 1e-12, "conv_tol_grad": 1e-8, "max_memory_mb": 768,
                "max_cycle": 100, "max_ao": 80, "scf_kernel_call_limit": 1, "automatic_retry": False}
FIXED_RESOURCES = {"cpus": 1, "threads": 1, "maximum_processes": 1,
                   "memory_limit_bytes": 1073741824, "wall_time_limit_seconds": 120,
                   "stop_after_seconds": 100}
FIXED_TOLERANCES = {"commutator_whitened_frobenius_max": 1e-7, "electron_count_abs_max": 1e-8,
                    "occupied_orthonormality_frobenius_max": 1e-8, "projector_idempotency_frobenius_max": 1e-8,
                    "density_reconstruction_relative_frobenius_max": 1e-9,
                    "energy_closure_abs_hartree_max": 1e-9, "overlap_eigenvalue_min": 1e-10,
                    "overlap_condition_number_max": 1e10, "matrix_symmetry_abs_max": 1e-10}
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_COUNT = re.compile(r"[1-9][0-9]*\Z")
_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class InputError(ValueError):
    """A deterministic refusal; no scientific result is implied."""

    def __init__(self, message: str, code: str = "INPUT_SCHEMA_REJECTED") -> None:
        super().__init__(message)
        self.code = code


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes) -> Any:
    """Parse UTF-8 JSON while rejecting duplicate keys and non-finite values."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise InputError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise InputError(f"non-finite JSON constant: {value}")

    def finite(value: Any, depth: int = 0) -> None:
        if depth > MAX_JSON_DEPTH:
            raise InputError("JSON nesting exceeds the fixed input limit")
        if isinstance(value, float) and not math.isfinite(value):
            raise InputError("non-finite JSON number")
        if isinstance(value, dict):
            for child in value.values():
                finite(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                finite(child, depth + 1)

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
        finite(result)
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"invalid UTF-8 JSON: {exc}") from exc


def _no_links(path: Path) -> None:
    """Check every existing component, including a supplied input root."""

    candidate = path.absolute()
    for component in (*reversed(candidate.parents), candidate):
        try:
            info = component.lstat()
        except OSError as exc:
            raise InputError(f"input path unavailable: {component.name}", "INPUT_PATH_REJECTED") from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InputError("input symlink or reparse point rejected", "INPUT_PATH_REJECTED")


def _bounded_read(path: Path, maximum: int) -> bytes:
    _no_links(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise InputError("input must be a regular file", "INPUT_PATH_REJECTED")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise InputError("input file changed while opening", "INPUT_PATH_REJECTED")
            data = stream.read(maximum + 1)
            after_fd = os.fstat(stream.fileno())
        _no_links(path)
        after = path.lstat()
    except OSError as exc:
        raise InputError(f"input file unavailable: {path.name}", "INPUT_PATH_REJECTED") from exc
    identities = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if identities(before) != identities(opened) or identities(opened) != identities(after_fd) or identities(after_fd) != identities(after):
        raise InputError("input file changed while reading", "INPUT_PATH_REJECTED")
    if len(data) > maximum:
        raise InputError(f"input exceeds {maximum} bytes: {path.name}", "INPUT_SIZE_REJECTED")
    return data


def _basename(name: Any) -> str:
    if not isinstance(name, str) or not 5 <= len(name) <= 180:
        raise InputError("structure.file must be a single XYZ filename", "INPUT_PATH_REJECTED")
    if any(ord(char) < 32 or char in '\\/:<>"|?*' for char in name):
        raise InputError("structure.file absolute, URI, separator or device path rejected", "INPUT_PATH_REJECTED")
    windows = PureWindowsPath(name)
    if windows.drive or windows.root or windows.name != name or name in {".", ".."} or name.endswith((" ", ".")):
        raise InputError("structure.file traversal or invalid filename rejected", "INPUT_PATH_REJECTED")
    if windows.suffix.lower() != ".xyz" or not windows.stem or windows.stem.split(".")[0].upper() in _DEVICE_NAMES:
        raise InputError("structure.file must be a regular XYZ basename", "INPUT_PATH_REJECTED")
    return name


def _exact_object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise InputError(f"{name}: missing={sorted(keys - actual)}, unknown={sorted(actual - keys)}")
    return value


def load_profile() -> tuple[dict[str, Any], bytes]:
    """Read the sole fixed profile. Source-lock verification belongs to worker."""
    data = _bounded_read(PROFILE_PATH, MAX_REQUEST_BYTES)
    profile = strict_json(data)
    if not isinstance(profile, dict) or profile.get("id") != "rhf-631gd-small-v1" or profile.get("schema") != "molecular-service-profile-v1":
        raise InputError("fixed service profile identity mismatch", "INPUT_PROFILE_REJECTED")
    _validate_profile(profile)
    return profile, data


def _validate_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict) or profile.get("protocol_id") != "ORDINARY_MOLECULAR_SINGLE_POINT_V0.1" or profile.get("task") != "single-point":
        raise InputError("fixed ordinary calculation protocol mismatch", "INPUT_PROFILE_REJECTED")
    for key, expected in (("scope", FIXED_SCOPE), ("engine", FIXED_ENGINE),
                          ("resources", FIXED_RESOURCES), ("tolerances", FIXED_TOLERANCES)):
        value = profile.get(key)
        if not isinstance(value, dict) or set(value) != set(expected):
            raise InputError(f"fixed profile {key} fields mismatch", "INPUT_PROFILE_REJECTED")
        # bool is an int subclass; retain the exact frozen JSON value types.
        if any(type(value[name]) is not type(wanted) or value[name] != wanted for name, wanted in expected.items()):
            raise InputError(f"fixed profile {key} values mismatch", "INPUT_PROFILE_REJECTED")


def parse_xyz(data: bytes, *, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return unchanged-order XYZ coordinates and explicit admission evidence."""
    if len(data) > MAX_XYZ_BYTES:
        raise InputError("XYZ exceeds the fixed byte limit", "INPUT_SIZE_REJECTED")
    if profile is None:
        profile, _ = load_profile()
    else:
        _validate_profile(profile)
    scope = profile["scope"]
    try:
        lines = data.decode("utf-8").splitlines()
        if len(lines) < 3 or not _COUNT.fullmatch(lines[0].strip()):
            raise InputError("XYZ requires a positive integer atom count and a comment line", "INPUT_GEOMETRY_REJECTED")
        count = int(lines[0].strip())
        if not 1 <= count <= scope["max_atoms"]:
            raise InputError(f"profile admits 1..{scope['max_atoms']} atoms", "INPUT_SCOPE_REJECTED")
        if len(lines) < count + 2 or any(line.strip() for line in lines[count + 2:]):
            raise InputError("XYZ atom count mismatch or extra structure", "INPUT_GEOMETRY_REJECTED")
        atoms: list[dict[str, Any]] = []
        for index, line in enumerate(lines[2:count + 2]):
            fields = line.split()
            if len(fields) != 4:
                raise InputError(f"XYZ atom {index + 1}: expected exactly element x y z", "INPUT_GEOMETRY_REJECTED")
            symbol = fields[0]
            if symbol not in scope["elements"] or symbol not in ATOMIC_NUMBERS:
                raise InputError(f"XYZ atom {index + 1}: profile supports only H/C/N/O", "INPUT_SCOPE_REJECTED")
            if not all(_NUMBER.fullmatch(value) for value in fields[1:]):
                raise InputError(f"XYZ atom {index + 1}: invalid decimal coordinate", "INPUT_GEOMETRY_REJECTED")
            coordinates = [float(value) for value in fields[1:]]
            if not all(math.isfinite(value) for value in coordinates):
                raise InputError(f"XYZ atom {index + 1}: non-finite coordinate", "INPUT_GEOMETRY_REJECTED")
            if any(abs(value) > scope["max_abs_coordinate_angstrom"] for value in coordinates):
                raise InputError(f"XYZ atom {index + 1}: coordinate absolute value exceeds 10000 angstrom engineering bound", "INPUT_GEOMETRY_REJECTED")
            atoms.append({"index_1based": index + 1, "index_0based": index, "symbol": symbol, "xyz_angstrom": coordinates})
        electron_count = sum(ATOMIC_NUMBERS[atom["symbol"]] for atom in atoms) - scope["charge"]
        if electron_count <= 0 or electron_count % 2:
            raise InputError("neutral singlet RHF profile requires a positive even electron count", "INPUT_SCOPE_REJECTED")
        minimum: float | None = None
        pair: list[int] | None = None
        for left in range(count):
            for right in range(left + 1, count):
                distance = math.dist(atoms[left]["xyz_angstrom"], atoms[right]["xyz_angstrom"])
                if not math.isfinite(distance):
                    raise InputError("XYZ coordinate separation is not numerically representable", "INPUT_GEOMETRY_REJECTED")
                if minimum is None or distance < minimum:
                    minimum, pair = distance, [left + 1, right + 1]
                if distance < scope["min_nuclear_distance_angstrom"]:
                    raise InputError(f"nuclei {left + 1}/{right + 1} are closer than 0.5 angstrom; no automatic geometry correction", "INPUT_GEOMETRY_REJECTED")
        return {"atoms": atoms, "atom_count": count, "electron_count": electron_count,
                "minimum_distance_angstrom": minimum, "minimum_distance_atom_indices_1based": pair,
                "ao_preflight_status": "NOT_EXECUTED", "ao_count": None}
    except (UnicodeError, ValueError, OverflowError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"invalid UTF-8 XYZ: {exc}", "INPUT_GEOMETRY_REJECTED") from exc


def parse_request(request_path: Path | str, *, input_root: Path | str | None = None) -> dict[str, Any]:
    """Read a request plus its adjacent XYZ once, returning bytes for RO snapshot.

    ``input_root`` must name a real directory, and the request must be its direct
    child. The XYZ is a single basename inside the same directory. The host can
    copy ``request_bytes`` and ``structure_bytes`` without re-reading user files.
    """
    path = Path(request_path).absolute()
    root = Path(input_root).absolute() if input_root is not None else path.parent
    _no_links(root)
    if not root.is_dir() or path.parent != root:
        raise InputError("request must be directly inside input_root", "INPUT_PATH_REJECTED")
    request_bytes = _bounded_read(path, MAX_REQUEST_BYTES)
    request = _exact_object(strict_json(request_bytes), REQUEST_KEYS, "request")
    structure = _exact_object(request["structure"], STRUCTURE_KEYS, "structure")
    required = {"schema": "molecular-single-point-v1", "task": "single-point", "profile": "rhf-631gd-small-v1", "method": "RHF", "basis": "6-31G(d)"}
    for key, value in required.items():
        if type(request[key]) is not str or request[key] != value:
            raise InputError(f"unsupported {key}; required {value}", "INPUT_SCOPE_REJECTED")
    for key, value in (("charge", 0), ("multiplicity", 1)):
        if type(request[key]) is not int or request[key] != value:
            raise InputError("profile admits only charge 0, multiplicity 1 (neutral singlet)", "INPUT_SCOPE_REJECTED")
    if structure["format"] != "xyz" or type(structure["format"]) is not str or structure["unit"] != "angstrom" or type(structure["unit"]) is not str:
        raise InputError("profile requires XYZ coordinates explicitly in angstrom", "INPUT_SCOPE_REJECTED")
    name = _basename(structure["file"])
    structure_path = root / name
    structure_bytes = _bounded_read(structure_path, MAX_XYZ_BYTES)
    profile, profile_bytes = load_profile()
    geometry = parse_xyz(structure_bytes, profile=profile)
    normalized_bytes = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {"request": request, "request_path": str(path.resolve()), "structure_path": str(structure_path.resolve()),
            "structure_file": name, "request_bytes": request_bytes, "structure_bytes": structure_bytes,
            "normalized_bytes": normalized_bytes, "request_sha256": digest(request_bytes),
            "structure_sha256": digest(structure_bytes), "normalized_sha256": digest(normalized_bytes),
            "profile": profile, "profile_sha256": digest(profile_bytes), **geometry,
            "molecule": {"symbols": [atom["symbol"] for atom in geometry["atoms"]],
                         "geometry_angstrom": [list(atom["xyz_angstrom"]) for atom in geometry["atoms"]],
                         "coordinate_unit": "angstrom", "charge": request["charge"],
                         "multiplicity": request["multiplicity"], "atom_count": geometry["atom_count"],
                         "electron_count": geometry["electron_count"]},
            "admission_status": "INPUT_ADMITTED_AO_PREFLIGHT_PENDING",
            "geometry_edits": [], "scientific_execution_performed": False}
