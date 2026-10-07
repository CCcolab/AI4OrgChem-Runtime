"""Targeted response engineering tests; every molecular operation forbidden."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ('test_user_molecule_occupation_response.py',
            'test_user_molecule_occupation_response_contract.py',
            'test_user_molecule_residual_bridge.py',
            'test_reference_residual_molecule.py',
            'test_user_molecule_residual_budget.py',
            'test_user_molecule_solver_candidate.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('/output'))
    output = parser.parse_args().output_root.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Outputs must be outside read-only committed source')
    output.mkdir(parents=True, exist_ok=True)
    final_path = output / 'occupation-response-engineering-tests.json'
    if final_path.exists():
        raise ValueError('Never overwrite an old engineering test execution')
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('retained_response_guard_helpers', ROOT / 'scripts/ci-guard-budget-recording.py')
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    scratch = Path(tempfile.gettempdir()).resolve()
    mount = helpers.tmpfs_mount(scratch)
    for variable, leaf in (('AI4ORGCHEM_EVIDENCE_TEST_STAGE', 'evidence'),
                            ('AI4ORGCHEM_REPORT_TEST_STAGE', 'reports'),
                            ('AI4ORGCHEM_PRESERVATION_TEST_STAGE', 'preservation')):
        os.environ[variable] = str(scratch / 'response-engineering-fixtures' / leaf)
    if os.environ.get('AI4ORGCHEM_OCCUPATION_PROBE_INPUT_DIR') != '/probe-input':
        raise ValueError('The sealed read-only probe input must be explicitly mounted for byte-binding tests')
    attempts, rows, seen = [], [], set()
    bindings = helpers.install_guards(attempts)
    started = time.monotonic()
    record = {'status': 'RUNNING', 'scope': 'TARGETED_FAKE_AND_CACHE_BYTE_BINDING_ENGINEERING_ONLY',
        'patterns': PATTERNS, 'groups': rows, 'synthetic_fixture_mount': mount,
        'guarded_operations': [row[3] for row in bindings], 'forbidden_operation_attempts': attempts,
        'new_real_F_SCF_NR_grid_integral_calls': 0, 'scientific_budget': None,
        'Compute': False, 'full_W01_W07_CI': 'NOT_EXECUTED', 'GitHub_Actions': 'NOT_EXECUTED'}
    try:
        suites = [(pattern, unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=pattern)) for pattern in PATTERNS]
        record['planned_test_ids'] = [name for _, suite in suites for name in helpers.test_ids(suite)]
        if len(record['planned_test_ids']) != len(set(record['planned_test_ids'])):
            raise ValueError('Duplicate planned IDs')
        for pattern, suite in suites:
            planned = helpers.test_ids(suite)
            result = unittest.TextTestRunner(verbosity=2, resultclass=helpers.RecordedResult).run(suite)
            executed = result.executed_test_ids
            changed = [label for owner, name, callback, label in bindings if getattr(owner, name) is not callback]
            good = (result.testsRun and result.wasSuccessful() and not result.skipped and planned == executed
                    and len(executed) == result.testsRun and not seen.intersection(executed) and not attempts and not changed)
            rows.append({'pattern': pattern, 'tests': result.testsRun, 'test_ids': executed,
                'status': 'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                'failures': [{'test_id': test.id(), 'detail': detail} for test, detail in result.failures],
                'errors': [{'test_id': test.id(), 'detail': detail} for test, detail in result.errors],
                'skips': [{'test_id': test.id(), 'reason': reason} for test, reason in result.skipped]})
            seen.update(executed)
            helpers.save(output / 'test-progress.json', record)
            if not good:
                raise RuntimeError('Response engineering test or guard failed: ' + pattern)
        from runtime.user_molecule.occupation_response import ENGINEERING_FAKE_CALLBACK_COUNTS
        fake = dict(ENGINEERING_FAKE_CALLBACK_COUNTS)
        if fake['entered'] != fake['completed'] + fake['failed'] or fake['entered'] < 9:
            raise RuntimeError('Explicit fake callback counters are missing or not settled')
        record['fake_callback_counts'] = {'kind': 'INSTRUMENTED_FAKE_WRAPPER_NOT_NATIVE_NR', **fake}
        record['status'] = 'PASS_SCOPED_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        record['executed_test_ids'] = [name for row in rows for name in row['test_ids']]
        record['unique_tests'] = len(seen)
        record['test_executions'] = sum(row['tests'] for row in rows)
        record['elapsed_seconds'] = time.monotonic() - started
        record['changed_guard_bindings'] = [label for owner, name, callback, label in bindings if getattr(owner, name) is not callback]
        record['guard_status'] = 'PASS' if len(bindings) == 13 and not attempts and not record['changed_guard_bindings'] else 'FAIL'
        helpers.save(final_path, record)
    print(json.dumps({'status': record['status'], 'unique_tests': record['unique_tests'], 'real_F': 0, 'Compute': False}))


if __name__ == '__main__':
    main()
