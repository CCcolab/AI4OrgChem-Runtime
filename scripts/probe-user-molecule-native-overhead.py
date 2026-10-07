# SPDX-License-Identifier: Apache-2.0
"""Fixed three-repeat zero-native measurements of local evidence overhead.

Run only in retained r3 with source/contract read-only, UID10001, network none,
1CPU/1GiB/zero swap and tmpfs /tmp. This is an engineering timing probe. It
accepts an inactive source contract, never an active scientific contract, an
engine, an evaluator callback, a density replay or an old callback journal.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
REPEATS = 3
GUARD_NAMES = frozenset(('SCF.kernel', 'hf.kernel', 'RHF.kernel', 'UHF.kernel',
    'ROHF.kernel', 'RKS.kernel', 'UKS.kernel', 'ROKS.kernel', 'Grids.build',
    'Mole.intor', 'Mole.intor_by_shell', 'NumInt.nr_rks', 'numint.nr_rks',
    'Mole.energy_nuc'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2,
                                allow_nan=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())


def load_helper(root, relative, name):
    spec = importlib.util.spec_from_file_location(name, root / relative)
    if spec is None or spec.loader is None:
        raise ValueError('Unavailable retained helper: ' + relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fresh_output(path, source_root, contract_path):
    path = Path(path).absolute()
    root = Path(source_root).resolve(strict=True)
    contract = Path(contract_path).resolve(strict=True)
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('Output cannot be a link')
    resolved = path.resolve()
    protected_input_directory = contract.parent != Path(contract.anchor)
    if (resolved.is_relative_to(root) or resolved == contract.parent
            or (protected_input_directory and resolved.is_relative_to(contract.parent))):
        raise ValueError('Output must be external to source and input')
    cursor = path
    while cursor != cursor.parent:
        if cursor.is_symlink() or (hasattr(cursor, 'is_junction') and cursor.is_junction()):
            raise ValueError('Output ancestors cannot be links')
        cursor = cursor.parent
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError('Fresh empty external output; no overwrite or resume')
    else:
        path.mkdir(parents=True, exist_ok=False)
    return path.resolve(strict=True)


def require_inactive(contract):
    for field in ('scientific_execution_authorized', 'local_cli_execute_requested',
                  'scientific_budget_reserved', 'production_activation',
                  'scientific_approval', 'method_approval', 'Compute'):
        if contract.get(field) is not False:
            raise ValueError('Only an inactive false source contract is allowed: ' + field)
    for field in ('execution_grant', 'budget_reservation', 'research_delta_hartree'):
        if contract.get(field) is not None:
            raise ValueError('An engineering probe cannot carry grant/budget/scientific delta')


def source_map_admission(root, values):
    """Strict paths/count metadata, before the retained byte-verifier timing."""
    root = Path(root).resolve(strict=True)
    if not isinstance(values, dict) or not values:
        raise ValueError('Verified nonempty source map required')
    total = 0
    for name, expected in values.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError('Source path/hash must be strings')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or str(relative) != name or '\\' in name:
            raise ValueError('Strict relative source path required')
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Exact lowercase SHA256 required')
        path = root.joinpath(*relative.parts)
        cursor = path
        while cursor != root:
            if cursor.is_symlink() or (hasattr(cursor, 'is_junction') and cursor.is_junction()):
                raise ValueError('Source links are refused')
            cursor = cursor.parent
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError('Source bytes differ: ' + name)
        total += path.stat().st_size
    return {'expected_count': len(values), 'actual_count': len(values),
            'total_source_bytes': total, 'all_bytes_sha256_matched': True}


def filesystem(path, mountinfo):
    """Report actual covering filesystem; directory labels are insufficient."""
    path = PurePosixPath(os.fspath(path))
    candidates = []
    for line in mountinfo.splitlines():
        before, after = line.split(' - ', 1)
        fields, extra = before.split(), after.split()
        point = PurePosixPath(fields[4].replace('\\040', ' ').replace('\\134', '\\'))
        if path.is_relative_to(point):
            candidates.append((len(point.parts), str(point), fields[5].split(','), extra[0]))
    if not candidates:
        raise ValueError('Actual filesystem unknown')
    depth = max(item[0] for item in candidates)
    covering = [item for item in candidates if item[0] == depth]
    if len({(item[1], tuple(item[2]), item[3]) for item in covering}) != 1:
        raise ValueError('Ambiguous actual filesystem')
    _, point, flags, kind = covering[-1]
    return {'path': str(path), 'mount_point': point, 'filesystem': kind,
            'mount_options': flags, 'read_only': 'ro' in flags and 'rw' not in flags}


def measure(label, operation, clock=time.monotonic_ns):
    """Internal timed operation; exceptions always propagate, never yield PASS."""
    started = clock()
    value = operation()
    finished = clock()
    if type(started) is not int or type(finished) is not int or finished < started:
        raise ValueError('Invalid monotonic timing')
    return {'operation': label, 'elapsed_ns': finished - started,
            'elapsed_seconds': (finished - started) / 1_000_000_000,
            'completed': True}, value


def summarized(samples):
    if len(samples) != REPEATS or any(row.get('completed') is not True for row in samples):
        raise ValueError('Exactly three complete engineering measurements required')
    durations = [row['elapsed_seconds'] for row in samples]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in durations):
        raise ValueError('Finite nonnegative timing required')
    return {'repeat_count': REPEATS, 'samples': samples, 'minimum_seconds': min(durations),
            'median_seconds': statistics.median(durations), 'maximum_seconds': max(durations),
            'sum_seconds': sum(durations)}


def synthetic_probe_identity(dependency_versions, initial_density_id):
    """Required resource hashes describe the fixed array fixture, not old science."""
    if (not isinstance(dependency_versions, dict) or not dependency_versions
            or any(type(key) is not str or type(value) is not str or not value
                   for key, value in dependency_versions.items())):
        raise ValueError('Explicit verified dependency-version strings required')
    if (not isinstance(initial_density_id, str) or len(initial_density_id) != 64
            or any(char not in '0123456789abcdef' for char in initial_density_id)):
        raise ValueError('Exact fixed synthetic density ID required')
    canonical = lambda value: digest(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8'))
    geometry = {'kind': 'PURE_ARRAY_FIXTURE_NO_MOLECULE', 'shape': [14, 14],
                'density_diagonal': [2.] * 8 + [0.] * 6}
    profile = {'kind': 'ENGINEERING_OVERHEAD_ONLY_NO_QUANTUM_CHEMISTRY_PROFILE',
               'factory': 'SyntheticRootEvaluator', 'scenario': 'diagonal',
               'fixed_simulated_slots': REPEATS, 'actual_engine': 'NOT_USED'}
    return {'mode': 'ENGINEERING_SIMULATED_NATIVE', 'execution_kind': 'ENGINEERING_SIMULATED_NATIVE',
        'scientific_execution_authorized': False, 'scientific_budget_reserved': False,
        'budget_reservation': None, 'execution_grant': None, 'Compute': False,
        'initial_density_id': initial_density_id,
        'geometry_sha256': canonical(geometry), 'profile_sha256': canonical(profile),
        'dependencies_sha256': canonical(dependency_versions),
        'geometry_identity_scope': 'SYNTHETIC14X14_ARRAY_NOT_ORIGINAL139_MOLECULE',
        'profile_identity_scope': 'FIXED_THREE_SLOT_ZERO_NATIVE_PROBE_NOT_SCIENTIFIC_PROFILE',
        'scope': 'FIXED_THREE_SLOT_ZERO_NATIVE_OVERHEAD_PROBE_NOT_ROOT_SEARCH'}


def held_guards(bindings, attempts):
    changed = [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
    labels = [item[3] for item in bindings]
    if attempts or changed or len(labels) != 14 or set(labels) != GUARD_NAMES or len(set(labels)) != 14:
        raise RuntimeError('Native guard evidence refused; attempts=' + repr(attempts) + '; changed=' + repr(changed))
    return {'guard_operations': labels, 'forbidden_attempts': [], 'changed_guards': [],
            'status': 'PASS_HELD_14_NATIVE_GUARDS_ONLY_NOT_OS_SANDBOX_AUTHENTICATION',
            'actual_native_F_NR_SCF_grid_integral_nuclear_calls': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--source-contract', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.runtime_root.resolve(strict=True)
    if root != ROOT:
        raise ValueError('Probe must be loaded from its actual read-only source root')
    output = fresh_output(args.output_dir, root, args.source_contract)
    started = time.monotonic_ns()
    attempts, bindings, journal, accounting = [], [], None, None
    record = {'schema': 'zero-native-overhead-probe-v1', 'status': 'RUNNING_ENGINEERING_ONLY',
        'execution_kind': 'ENGINEERING_SIMULATED_NATIVE', 'scientific_execution_authorized': False,
        'scientific_budget': None, 'Compute': False, 'fixed_repeats_per_segment': REPEATS,
        'scientific_performance_extrapolation_allowed': False, 'old_records_written': False,
        'actual_native_calls': None, 'segments': {}, 'time_source': 'time.monotonic_ns',
        'run_scope': 'THREE_SOURCE_VERIFICATIONS_THREE_SIMULATED_SLOTS_THREE_ATOMIC_WRITES_THREE_ARRAY_EXPORTS_ONLY'}
    save(output / 'PROBE_STARTED.json', record)
    code = 2
    try:
        sys.path.insert(0, str(root))
        from runtime.user_molecule.input import strict_json
        from runtime.user_molecule.occupied_space_root_native_contract import validate_execution_contract
        raw_contract = args.source_contract.read_bytes()
        contract = strict_json(raw_contract)
        require_inactive(contract)
        validate_execution_contract(contract)
        admission = source_map_admission(root, contract['source_file_sha256'])
        record['source_identity'] = {'inactive_contract_sha256': digest(raw_contract),
            'runtime_commit_declaration': contract['runtime_test_commit'],
            'probe_script_sha256': digest(Path(__file__).read_bytes()),
            'probe_loaded_path': str(Path(__file__).resolve()), 'source_map': admission}
        platform_helper = load_helper(root, 'scripts/diagnose-user-molecule-occupied-space-response-worker.py', 'probe_platform')
        platform = platform_helper.platform_preflight(roots={'root_filesystem': '/', 'runtime_source': root,
            'science_source': '/opt/ai4orgchem', 'source_contract': args.source_contract.resolve()})
        save(output / 'platform-preflight.json', platform)
        if platform['status'] != 'PASS_ACTUAL_PLATFORM_PREFLIGHT':
            raise RuntimeError('Actual non-root/offline/read-only platform refused')
        guard_helper = load_helper(root, 'scripts/ci-guard-budget-recording.py', 'probe_native_guards')
        record['tmpfs'] = guard_helper.tmpfs_mount(Path(tempfile.gettempdir()).resolve())
        bindings = guard_helper.install_guards(attempts)
        from pyscf import gto
        def no_nuclear(*_args, **_kwargs):
            attempts.append('Mole.energy_nuc')
            raise AssertionError('Native nuclear call forbidden in zero-native probe')
        gto.Mole.energy_nuc = no_nuclear
        bindings.append((gto.Mole, 'energy_nuc', no_nuclear, 'Mole.energy_nuc'))
        held_guards(bindings, attempts)
        versions = {key: importlib.metadata.version(key) for key in contract['parent_preparation_contract']['expected_dependencies']}
        if versions != contract['parent_preparation_contract']['expected_dependencies']:
            raise ValueError('Retained r3 dependency versions differ')
        record['dependency_versions'] = versions
        import numpy as np
        from runtime.user_molecule.acceptance_resources import collect_cgroup, _atomic_write
        from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
        from runtime.user_molecule.root_native_accounting import RootNativeAccounting
        from runtime.user_molecule.root_native_binding import _source_bytes
        from reference.occupied_space_root_native_candidate import SyntheticRootEvaluator, FrozenRecord, density_id
        array_helper = platform_helper.shared_helpers(root)
        def resources(phase):
            observation = collect_cgroup(phase=phase)
            reasons = array_helper.resource_reasons(observation)
            if observation.get('cpu_quota_us') != observation.get('cpu_period_us'):
                reasons.append('EXACT_ONE_CPU_NOT_CONFIRMED')
            if reasons:
                raise RuntimeError('Actual probe resources refused: ' + repr(reasons))
            held_guards(bindings, attempts)
            return observation
        record['resources_before'] = resources('BEFORE_FIXED_PROBE')
        mountinfo = Path('/proc/self/mountinfo').read_text(encoding='ascii')
        record['filesystems'] = {'source': filesystem(root, mountinfo),
            'output': filesystem(output, mountinfo), 'tmp': filesystem(Path(tempfile.gettempdir()).resolve(), mountinfo)}
        if record['filesystems']['output']['read_only'] or record['filesystems']['tmp']['filesystem'] != 'tmpfs':
            raise ValueError('Writable external output and tmpfs required')
        samples = []
        for _index in range(REPEATS):
            sample, _value = measure('RETAINED_SOURCE_BYTES_VERIFICATION', lambda: _source_bytes(root, contract))
            samples.append(sample)
        record['segments']['source_byte_verification'] = summarized(samples)
        identity = synthetic_probe_identity(versions, density_id(np.diag([2.] * 8 + [0.] * 6)))
        record['simulated_resource_identity'] = identity
        journal = ConditionalCallbackBudget(path=output / 'SIMULATED_CALLBACKS.json',
            batch_id='zero-native-overhead-probe', identity=identity,
            path_limits={'independent_reference': 201}, total_limit=201)
        accounting = RootNativeAccounting(output / 'SIMULATED_ACCOUNTING', journal,
            execution_kind='ENGINEERING_SIMULATED_NATIVE', scientific_execution_authorized=False)
        evaluator = SyntheticRootEvaluator('diagonal', expected_initial_density_id=identity['initial_density_id'], accounting=accounting)
        density = np.diag([2.] * 8 + [0.] * 6)
        density.setflags(write=False)
        samples = []
        for index in range(1, REPEATS + 1):
            phase = 'CURRENT_INITIAL' if index == 1 else 'OPTIMIZER_BASE'
            evaluator.bind_candidate_callback(FrozenRecord({'evaluation_count': index, 'density_id': identity['initial_density_id'],
                'phase': phase, 'admission_group_id': None, 'chart': None, 'fd_sample': None,
                'base_snapshot_id': None, 'base_density_id': None, 'base_operator_id': None}))
            sample, _wire = measure('PURE_SYNTHETIC_CHARGE_DELEGATE_FINISH_WITH_DURABLE_WRITES', lambda: evaluator(density.copy(), phase))
            samples.append(sample)
            resources('AFTER_SIMULATED_SLOT_' + str(index))
        book = accounting.close('FIXED_THREE_SLOT_ENGINEERING_PROBE_COMPLETE_NO_SCIENCE')
        accounting = None
        if book['callback_slots'] != {'charged': 3, 'pending': 0, 'succeeded': 3, 'failed': 0, 'limit': 201}:
            raise RuntimeError('Exactly three completed simulated slots required')
        if any(book['source_native_dispatch_counts'][key] is not None for key in ('entered', 'completed', 'failed')):
            raise RuntimeError('Simulation cannot report observed source-native NR counts')
        record['simulated_accounting_final'] = book
        record['segments']['simulated_accounting_cycle'] = summarized(samples)
        samples = []
        for index in range(REPEATS):
            target = output / ('ATOMIC_FIXTURE_' + str(index + 1) + '.json')
            sample, _value = measure('RETAINED_ATOMIC_JSON_FSYNC_REPLACE', lambda: _atomic_write(target,
                {'execution_kind': 'ENGINEERING_SIMULATED_NATIVE', 'scientific_execution_authorized': False,
                 'shape': [14, 14], 'fixed_index': index + 1, 'Compute': False}))
            if json.loads(target.read_text(encoding='utf-8'))['fixed_index'] != index + 1:
                raise RuntimeError('Atomic fixture readback differs')
            samples.append(sample)
        record['segments']['atomic_json_write'] = summarized(samples)
        samples, exports = [], []
        fixture_dir = output / 'ARRAY_EXPORT_FIXTURES'
        fixture_dir.mkdir()
        for index in range(REPEATS):
            name = 'pure-array-' + str(index + 1)
            sample, _value = measure('RETAINED_NPZ_AND_JSON_CAPTURE_WRITE', lambda: array_helper.pack_record(fixture_dir, name,
                {'execution_kind': 'ENGINEERING_SIMULATED_NATIVE', 'scientific_execution_authorized': False,
                 'fixture_density': density.copy(), 'fixture_matrix': np.eye(14), 'Compute': False}))
            item = json.loads((fixture_dir / (name + '.json')).read_text(encoding='utf-8'))
            archive = fixture_dir / item['raw_array_archive']['file']
            if digest(archive.read_bytes()) != item['raw_array_archive']['sha256']:
                raise RuntimeError('Saved pure-array fixture bytes differ')
            with np.load(archive, allow_pickle=False) as loaded:
                if len(loaded.files) != 2 or any(loaded[key].shape != (14, 14) for key in loaded.files):
                    raise RuntimeError('Fixed two14x14 fixture matrices required')
            exports.append({'name': name, 'archive_sha256': item['raw_array_archive']['sha256'],
                            'size_bytes': archive.stat().st_size, 'array_count': 2, 'shape': [14, 14]})
            samples.append(sample)
        record['segments']['array_capture_write'] = summarized(samples)
        record['array_exports'] = exports
        record['capture_write_policy'] = 'Retained pack_record: NPZ close plus strict JSON flush/fsync; unchanged helper semantics, not an assertion of power-loss durability.'
        record['resources_after'] = resources('AFTER_FIXED_PROBE')
        source_map_admission(root, contract['source_file_sha256'])
        record['guard_evidence'] = held_guards(bindings, attempts)
        record['actual_native_calls'] = 0
        record['status'] = 'PASS_FIXED_ZERO_NATIVE_ENGINEERING_OVERHEAD_ONLY'
        code = 0
    except BaseException as error:
        record.update(status='FAIL_ZERO_NATIVE_ENGINEERING_PROBE', error_type=type(error).__name__, error=str(error))
        code = 2
    finally:
        if accounting is not None:
            try:
                record['simulated_accounting_failure_close'] = accounting.close('PROBE_FAILED_NO_RETRY_NO_SCIENCE')
            except BaseException as error:
                record['simulation_cleanup_error'] = type(error).__name__ + ': ' + str(error)
                code = 2
        elif journal is not None and 'simulated_accounting_final' not in record:
            try:
                state = journal.snapshot()
                if state['paths']['independent_reference']['state'] == 'OPEN':
                    journal.close_path('independent_reference', 'PROBE_INITIALIZATION_FAILED_NO_RETRY')
            except BaseException as error:
                record['simulation_cleanup_error'] = type(error).__name__ + ': ' + str(error)
                code = 2
        if code != 0:
            record['status'] = 'FAIL_ZERO_NATIVE_ENGINEERING_PROBE'
        if bindings:
            record['guard_operations'] = [row[3] for row in bindings]
            record['forbidden_attempts'] = attempts
            record['changed_guards'] = [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
        record['whole_probe_elapsed_seconds'] = (time.monotonic_ns() - started) / 1_000_000_000
        record['timing_interpretation'] = 'Only three observed engineering operations per segment on this filesystem. No native NR time, root wall forecast, larger-system resource claim or scientific acceptance.'
        save(output / 'probe-summary.json', record)
    print(json.dumps({'status': record['status'], 'actual_native_calls': record['actual_native_calls'],
                      'Compute': False, 'scientific_budget': None}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
