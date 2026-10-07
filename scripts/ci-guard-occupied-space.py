"""Targeted occupied-space engineering tests and one mandatory fake example.

Run in the pinned Linux candidate with tmpfs /tmp, fresh /output, old sealed
occupation witnesses mounted read-only, and an explicit read-only example
script.  Thirteen molecular API guards remain installed during discovery,
tests, the example and evidence collection.  No real diagnostic is authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    'test_user_molecule_occupied_space_seeds.py',
    'test_user_molecule_occupied_space_admission.py',
    'test_user_molecule_occupation_response.py',
    'test_user_molecule_occupation_response_contract.py',
    'test_user_molecule_residual_budget.py',
    'test_user_molecule_solver_candidate.py',
)

_spec = importlib.util.spec_from_file_location(
    'ai4orgchem_occupied_space_guard_helpers', ROOT/'scripts/ci-guard-budget-recording.py')
if _spec is None or _spec.loader is None:
    raise RuntimeError('Budget engineering guard helpers unavailable')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
install_guards = _shared.install_guards
RecordedResult, test_ids = _shared.RecordedResult, _shared.test_ids
tmpfs_mount, save = _shared.tmpfs_mount, _shared.save


def _counts(module):
    value = getattr(module, 'ENGINEERING_FAKE_CALLBACK_COUNTS', None)
    if (not isinstance(value, dict) or set(value) != {'entered', 'completed', 'failed'}
            or any(type(count) is not int or count < 0 for count in value.values())
            or value['entered'] != value['completed']+value['failed']):
        raise RuntimeError('Invalid or unsettled explicit fake-admission counters')
    return dict(value)


def _delta(before, after):
    difference = {name: after[name]-before[name] for name in before}
    if any(value < 0 for value in difference.values()) or difference['entered'] != difference['completed']+difference['failed']:
        raise RuntimeError('Fake-admission counter reset or unsettled delta')
    return difference


def _changes(bindings):
    return [label for owner, attribute, callback, label in bindings
            if getattr(owner, attribute, None) is not callback]


def _readonly_mount(path):
    candidates = []
    for row in Path('/proc/self/mountinfo').read_text(encoding='utf-8').splitlines():
        before, after = row.split(' - ', 1)
        fields = before.split()
        mount = Path(fields[4].replace('\\040', ' ').replace('\\134', '\\'))
        if path.is_relative_to(mount):
            candidates.append((len(mount.parts), str(mount), fields[5].split(','), after.split()[0]))
    if not candidates:
        raise RuntimeError('No actual Linux mount information for read-only input')
    _, mount, options, kind = max(candidates)
    if 'ro' not in options:
        raise RuntimeError('Explicit input is not mounted read-only: '+str(path))
    return {'mount_point': mount, 'filesystem': kind, 'mount_options': options, 'read_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('/output'))
    output = parser.parse_args().output_root.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Engineering evidence must be outside the source checkout')
    output.mkdir(parents=True, exist_ok=True)
    targets = (output/'test-progress.json', output/'occupied-space-engineering-tests.json')
    if any(path.exists() for path in targets):
        raise ValueError('Do not overwrite a prior occupied-space engineering run')
    sys.path.insert(0, str(ROOT))
    rows, seen, attempted, bindings = [], set(), [], []
    record = {'schema_version': 'occupied-space-engineering-tests-v1', 'status': 'RUNNING',
        'scope': 'TARGETED_ARRAY_TESTS_AND_ONE_FIXED_FAKE_TWELVE_CALLBACK_EXAMPLE',
        'planned_groups': list(PATTERNS), 'groups': rows,
        'planned_test_ids': [], 'executed_test_ids': [], 'test_ids': [],
        'unit_test_total': 0, 'unique_test_total': 0,
        'forbidden_operation_attempts': attempted,
        'molecular_scf_grid_integrals_xc': 'NOT_EXECUTED',
        'new_real_scientific_calls': 0,
        'real_native_functional_counts': {'entered': 0, 'completed': 0, 'failed': 0},
        'guarded_native_observation_basis': 'THIRTEEN_HELD_API_BINDINGS_AND_FORBIDDEN_ENTRY_LOG',
        'scientific_budget': None, 'scientific_method_approval': False,
        'production_compute_enabled': False,
        'numeric_acceptance': 'NOT_EXECUTED_ARRAY_TESTS_AND_FAKE_EXAMPLE_DO_NOT_QUALIFY_MOLECULES',
        'guard_binding_checks': [],
        'mandatory_example': {'status': 'NOT_EXECUTED', 'required': True}}
    started, count_module = time.monotonic(), None
    try:
        scratch = Path(tempfile.gettempdir()).resolve()
        record['synthetic_fixture_mount'] = tmpfs_mount(scratch)
        fixtures = Path(tempfile.mkdtemp(prefix='ai4orgchem-occupied-space-', dir=scratch))
        record['synthetic_fixture_root'] = str(fixtures)
        for variable, leaf in (
            ('AI4ORGCHEM_EVIDENCE_TEST_STAGE', 'evidence'),
            ('AI4ORGCHEM_REPORT_TEST_STAGE', 'report-export'),
            ('AI4ORGCHEM_PRESERVATION_TEST_STAGE', 'run-preservation')):
            os.environ[variable] = str(fixtures/leaf)
        sealed = Path(os.environ.get('AI4ORGCHEM_OCCUPATION_PROBE_INPUT_DIR', '/probe-input')).resolve()
        if not sealed.is_dir():
            raise RuntimeError('The sealed old occupation-scope witness input directory is required')
        os.environ['AI4ORGCHEM_OCCUPATION_PROBE_INPUT_DIR'] = str(sealed)
        record['old_sealed_probe_input_directory'] = str(sealed)
        record['old_sealed_probe_input_mount'] = _readonly_mount(sealed)
        bindings = install_guards(attempted)
        if len(bindings) != 13:
            raise RuntimeError('All thirteen molecular guards must be installed')
        record['guarded_operations'] = [row[3] for row in bindings]
        from runtime.user_molecule import occupied_space_admission as count_module
        before_discovery = _counts(count_module)
        record['fake_admission_counters_before_discovery'] = before_discovery
        groups = [(pattern, unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
                  for pattern in PATTERNS]
        changed = _changes(bindings)
        record['guard_binding_checks'].append({'phase': 'AFTER_DISCOVERY', 'binding_count': len(bindings),
            'changed_bindings': changed, 'forbidden_attempt_count': len(attempted)})
        if changed or attempted:
            raise RuntimeError('Molecular guard binding or entry violation during discovery')
        record['planned_test_ids'] = [identity for _, suite in groups for identity in test_ids(suite)]
        if len(record['planned_test_ids']) != len(set(record['planned_test_ids'])):
            raise RuntimeError('Planned occupied-space engineering test IDs are duplicated')
        save(targets[0], record)
        for pattern, suite in groups:
            planned = test_ids(suite)
            result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
            executed, changed = list(result.executed_test_ids), _changes(bindings)
            duplicates = sorted({identity for identity in executed if executed.count(identity) > 1 or identity in seen})
            good = (bool(result.testsRun) and result.wasSuccessful() and not result.skipped
                and planned == executed and len(planned) == result.testsRun
                and not duplicates and not changed and not attempted)
            rows.append({'pattern': pattern, 'status': 'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                'tests': result.testsRun, 'planned_test_ids': planned, 'test_ids': executed,
                'duplicate_test_ids': duplicates, 'changed_guard_bindings': changed,
                'failures': [{'test_id': test.id(), 'traceback': detail} for test, detail in result.failures],
                'errors': [{'test_id': test.id(), 'traceback': detail} for test, detail in result.errors],
                'skips': [{'test_id': test.id(), 'reason': reason} for test, reason in result.skipped]})
            record['guard_binding_checks'].append({'phase': 'AFTER_GROUP_'+pattern, 'binding_count': len(bindings),
                'changed_bindings': changed, 'forbidden_attempt_count': len(attempted)})
            seen.update(executed)
            record.update(executed_test_ids=[identity for row in rows for identity in row['test_ids']],
                test_ids=[identity for row in rows for identity in row['test_ids']],
                unit_test_total=sum(row['tests'] for row in rows), unique_test_total=len(seen),
                elapsed_seconds=time.monotonic()-started)
            save(targets[0], record)
            if not good:
                raise RuntimeError('Unit group failed, skipped, empty, duplicate or guard violation: '+pattern)
        if record['planned_test_ids'] != record['executed_test_ids']:
            raise RuntimeError('Planned and executed engineering test IDs differ')
        after_tests = _counts(count_module)
        unit_delta = _delta(before_discovery, after_tests)
        if unit_delta['entered'] < 1:
            raise RuntimeError('No fake-admission callback was instrumented during tests')
        record['fake_admission_test_counts'] = {'before': before_discovery, 'after': after_tests, 'delta': unit_delta,
            'counter_kind': 'EXPLICIT_WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_CALLS',
            'subtests_and_callbacks_are_not_unit_test_counts': True}
        script_value = os.environ.get('AI4ORGCHEM_OCCUPIED_EXAMPLE_SCRIPT')
        if not isinstance(script_value, str) or not script_value.strip():
            raise RuntimeError('A mandatory AI4ORGCHEM_OCCUPIED_EXAMPLE_SCRIPT is required; tests alone cannot PASS this run')
        script = Path(script_value).resolve()
        if not script.is_file():
            raise RuntimeError('The explicit occupied-space example script does not exist')
        raw_script = script.read_bytes()
        record['mandatory_example'] = {'status': 'RUNNING', 'required': True,
            'script_path': str(script), 'script_size_bytes': len(raw_script),
            'script_sha256': hashlib.sha256(raw_script).hexdigest(),
            'script_mount': _readonly_mount(script)}
        save(targets[0], record)
        before_example = _counts(count_module)
        previous_argv = sys.argv
        try:
            sys.argv = [str(script)]
            namespace = runpy.run_path(str(script), run_name='__main__')
        finally:
            sys.argv = previous_argv
        after_example, changed = _counts(count_module), _changes(bindings)
        example_delta = _delta(before_example, after_example)
        summary = namespace.get('ENGINEERING_EXAMPLE_RECORD')
        if not isinstance(summary, dict) or summary.get('status') != 'PASS_ENGINEERING_ONLY':
            raise RuntimeError('Example must export an ENGINEERING_EXAMPLE_RECORD dict with PASS_ENGINEERING_ONLY status')
        json.dumps(summary, allow_nan=False)
        if example_delta != {'entered': 12, 'completed': 12, 'failed': 0}:
            raise RuntimeError('Mandatory example did not execute exactly twelve settled fake callbacks')
        if changed or attempted or script.read_bytes() != raw_script:
            raise RuntimeError('Example changed molecular guards/source script or attempted a forbidden native operation')
        record['guard_binding_checks'].append({'phase': 'AFTER_MANDATORY_EXAMPLE', 'binding_count': len(bindings),
            'changed_bindings': changed, 'forbidden_attempt_count': len(attempted)})
        record['mandatory_example'].update({'status': 'PASS_ENGINEERING_ONLY', 'summary': summary,
            'fake_admission_counters_before': before_example, 'fake_admission_counters_after': after_example,
            'fake_admission_counter_delta': example_delta,
            'counter_kind': 'EXPLICIT_WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_CALLS'})
        record['fake_admission_total_counts'] = {'before': before_discovery, 'after': after_example,
            'delta': _delta(before_discovery, after_example), 'counts_are_not_test_counts': True}
        record['status'] = 'PASS_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed = _changes(bindings)
        record.update(elapsed_seconds=time.monotonic()-started, changed_guard_bindings=changed,
            not_executed_groups=list(PATTERNS[len(rows):]))
        record['guard_binding_checks'].append({'phase': 'FINAL_EVIDENCE_COLLECTION', 'binding_count': len(bindings),
            'changed_bindings': changed, 'forbidden_attempt_count': len(attempted)})
        if changed or attempted or len(bindings) != 13:
            record.update(status='FAIL_ENGINEERING_ONLY', guard_integrity_status='FAIL')
        else:
            record['guard_integrity_status'] = 'PASS_ALL_THIRTEEN_BINDINGS_HELD'
        if count_module is not None:
            try:
                record['final_fake_admission_counters'] = _counts(count_module)
            except BaseException as error:
                record.update(status='FAIL_ENGINEERING_ONLY', final_counter_error_type=type(error).__name__,
                    final_counter_error=str(error))
        save(targets[0], record)
        save(targets[1], record)
    if record['status'] != 'PASS_ENGINEERING_ONLY':
        raise RuntimeError('Occupied-space engineering tests and mandatory example did not pass')
    print(json.dumps({'status': record['status'], 'unit_test_total': record['unit_test_total'],
        'unique_test_total': record['unique_test_total'], 'mandatory_example': record['mandatory_example']['status'],
        'new_real_scientific_calls': 0}, allow_nan=False))


if __name__ == '__main__': main()
