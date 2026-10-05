"""Bounded strict input parsing. No quantum-chemistry imports or coordinate edits."""
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath

MAX_REQUEST_BYTES = 256 * 1024
MAX_XYZ_BYTES = 4 * 1024 * 1024
MAX_ATOMS = 128
PLANE_TOLERANCE_ANGSTROM = 1e-8


class InputError(ValueError):
    def __init__(self, message, code=10):
        super().__init__(message)
        self.code = code


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def strict_json(data):
    def invalid(value):
        raise InputError(f'non-finite JSON constant: {value}')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f'invalid UTF-8 JSON: {exc}') from exc
    def finite(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise InputError('non-finite JSON number')
        if isinstance(item, dict):
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)
    try:
        finite(value)
    except RecursionError as exc:
        raise InputError('JSON nesting too deep') from exc
    return value


def bounded_read(path, maximum):
    with Path(path).open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise InputError(f'file exceeds {maximum} bytes: {Path(path).name}')
    return data


def geometry_path(request_path, name):
    if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name):
        raise InputError('geometry_file must be a nonempty relative path')
    win = PureWindowsPath(name)
    normalized = name.replace('\\', '/')
    parts = normalized.split('/')
    if win.drive or win.root or ':' in name or any(p in ('', '.', '..') for p in parts):
        raise InputError('geometry_file absolute/URI/traversal path rejected')
    root = Path(request_path).resolve().parent
    candidate = root.joinpath(*parts)
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink() or getattr(cursor.lstat(), 'st_file_attributes', 0) & 0x400:
            raise InputError('geometry_file symlink/reparse point rejected')
    if not candidate.resolve().is_relative_to(root) or not candidate.is_file():
        raise InputError('geometry_file must be a file inside the input directory')
    return candidate


def parse_xyz(data):
    try:
        lines = data.decode('utf-8').splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise InputError('XYZ requires integer count, comment line and atoms')
        count = int(lines[0].strip())
        if not 1 <= count <= MAX_ATOMS:
            raise InputError(f'XYZ atom count must be 1..{MAX_ATOMS}', 11)
        if len(lines) < count + 2 or any(line.strip() for line in lines[count + 2:]):
            raise InputError('XYZ count mismatch/trailing structure')
        atoms = []
        seen = set()
        for number, line in enumerate(lines[2:count + 2], 1):
            fields = line.split()
            if len(fields) != 4:
                raise InputError(f'XYZ atom {number}: expected element x y z')
            if fields[0] not in ('C', 'H'):
                raise InputError(f'XYZ atom {number}: only C/H supported', 11)
            coordinates = tuple(float(x) for x in fields[1:])
            if not all(math.isfinite(x) for x in coordinates):
                raise InputError(f'XYZ atom {number}: non-finite coordinate')
            if abs(coordinates[2]) > PLANE_TOLERANCE_ANGSTROM:
                raise InputError(f'XYZ atom {number}: outside fixed xy plane', 11)
            if coordinates in seen:
                raise InputError(f'XYZ atom {number}: coincident nuclei')
            seen.add(coordinates)
            atoms.append([fields[0], list(coordinates)])
        if sum(6 if a[0] == 'C' else 1 for a in atoms) % 2:
            raise InputError('odd electron count incompatible with closed-shell singlet', 11)
        return atoms
    except (UnicodeError, ValueError, OverflowError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f'invalid XYZ: {exc}') from exc


def read_request(request_path, schema):
    path = Path(request_path)
    if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
        raise InputError('request symlink/reparse point rejected')
    raw = bounded_read(path, MAX_REQUEST_BYTES)
    request = strict_json(raw)
    from jsonschema import Draft202012Validator
    failures = sorted(Draft202012Validator(schema).iter_errors(request), key=lambda e: str(list(e.path)))
    if failures:
        error = failures[0]
        field = '.'.join(str(p) for p in error.path) or 'request'
        raise InputError(f'{field}: {error.message}')
    try:
        geom = geometry_path(path, request['geometry_file'])
        xyz = bounded_read(geom, MAX_XYZ_BYTES)
    except OSError as exc:
        raise InputError('geometry_file unavailable or unreadable') from exc
    atoms = parse_xyz(xyz)
    carbon = {i for i, a in enumerate(atoms, 1) if a[0] == 'C'}
    groups = [g['carbon_atom_indices_1based'] for g in request['fragments']]
    flat = [i for group in groups for i in group]
    if len(set(flat)) != len(flat) or set(flat) != carbon:
        raise InputError('fragments must assign every carbon exactly once and no hydrogen/out-of-range atom')
    if [g['id'] for g in request['fragments']] != ['A', 'B']:
        raise InputError('fragments must be ordered A, B')
    normalized = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return {'request': request, 'atoms': atoms, 'request_bytes': raw, 'xyz_bytes': xyz,
            'request_sha256': digest(raw), 'normalized_sha256': digest(normalized),
            'xyz_sha256': digest(xyz), 'normalized_bytes': normalized,
            'atom_mapping': [{'index_1based': i, 'index_0based': i-1, 'element': a[0],
                              'coordinates_angstrom': a[1],
                              'pi_group': next((g['id'] for g in request['fragments'] if i in g['carbon_atom_indices_1based']), None)}
                             for i, a in enumerate(atoms, 1)]}
