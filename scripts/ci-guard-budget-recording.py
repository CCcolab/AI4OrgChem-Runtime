"""Targeted budget-recording engineering; molecular operations stay forbidden.

Run in the pinned Linux candidate with tmpfs /tmp and a fresh /output.
This runner executes synthetic arrays/test doubles, never a molecular job.
"""
from __future__ import annotations

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
PATTERNS = (
    'test_reference_residual_budgeted_candidate.py',
    'test_reference_budgeted_seed.py',
    'test_reference_residual_candidate.py',
    'test_reference_residual_seed_v2.py',
    'test_reference_residual_molecule.py',
    'test_reference_seed_v2.py',
    'test_user_molecule_residual_budget.py',
    'test_user_molecule_residual_seed_execution_contract.py',
)
FAKE_COUNT_MODULES = (
    ('test_reference_residual_budgeted_candidate', 'ENGINEERING_FAKE_CALLBACK_COUNTS', 'FAKE_EVALUATOR'),
    ('test_reference_budgeted_seed', 'ENGINEERING_FAKE_XC_COUNTS', 'FAKE_PREPARED_XC'),
)

# Import helpers without invoking the older runner or changing its test scope.
_spec = importlib.util.spec_from_file_location(
    'ai4orgchem_seed_guard_helpers', ROOT/'scripts/ci-guard-seed-v2.py')
if _spec is None or _spec.loader is None:
    raise RuntimeError('Seed engineering helper loader unavailable')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
RecordedResult, test_ids = _shared.RecordedResult, _shared.test_ids
tmpfs_mount, save = _shared.tmpfs_mount, _shared.save


def install_guards(attempted):
    """Retain all bindings through discovery, tests and evidence collection."""
    from pyscf import dft, gto, scf
    from pyscf.dft import gen_grid, numint
    bindings = []
    for owner, attribute, label in (
        (scf.hf.SCF, 'kernel', 'SCF.kernel'),
        (scf.hf, 'kernel', 'hf.kernel'),
        (scf.hf.RHF, 'kernel', 'RHF.kernel'),
        (scf.uhf.UHF, 'kernel', 'UHF.kernel'),
        (scf.rohf.ROHF, 'kernel', 'ROHF.kernel'),
        (dft.rks.RKS, 'kernel', 'RKS.kernel'),
        (dft.uks.UKS, 'kernel', 'UKS.kernel'),
        (dft.roks.ROKS, 'kernel', 'ROKS.kernel'),
        (gen_grid.Grids, 'build', 'Grids.build'),
        (gto.Mole, 'intor', 'Mole.intor'),
        (gto.Mole, 'intor_by_shell', 'Mole.intor_by_shell'),
        (numint.NumInt, 'nr_rks', 'NumInt.nr_rks'),
        (numint, 'nr_rks', 'numint.nr_rks')):
        if not hasattr(owner, attribute):
            raise RuntimeError('Required molecular guard API unavailable: '+label)
        def forbidden(*_args, _label=label, **_kwargs):
            attempted.append(_label)
            raise AssertionError('Molecular operation forbidden in budget engineering: '+_label)
        setattr(owner, attribute, forbidden)
        bindings.append((owner, attribute, forbidden, label))
    return bindings


def fake_callback_counts():
    """Read explicit test-double counters; do not infer calls from testsRun."""
    rows = {}
    for name, counter_key, layer in FAKE_COUNT_MODULES:
        module = sys.modules.get(name)
        value = getattr(module, counter_key, None)
        if not isinstance(value, dict) or set(value) != {'entered', 'completed', 'failed'}:
            raise RuntimeError('Explicit engineering callback counters unavailable: '+name)
        if any(type(count) is not int or count < 0 for count in value.values()):
            raise RuntimeError('Invalid engineering callback counters: '+name)
        if value['entered'] != value['completed']+value['failed']:
            raise RuntimeError('Unsettled engineering callback counters: '+name)
        if value['entered'] < 1:
            raise RuntimeError('No actual test-double callback was entered: '+name)
        rows[name] = {'layer': layer, 'counter_key': counter_key, **dict(value)}
    return {'kind': 'EXPLICIT_TEST_DOUBLE_COUNTERS_NOT_SCIENTIFIC_CALLS',
            'groups': rows, 'counts_are_not_additive_across_layers': True,
            'older_regression_groups': 'NOT_INSTRUMENTED_BY_THIS_COUNTER'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('/output'))
    output = parser.parse_args().output_root.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Engineering evidence must be outside the source checkout')
    output.mkdir(parents=True, exist_ok=True)
    targets = (output/'test-progress.json', output/'budget-recording-engineering-tests.json')
    if any(path.exists() for path in targets):
        raise ValueError('Do not overwrite a previous engineering execution')
    sys.path.insert(0, str(ROOT))
    rows, seen, attempted, bindings = [], set(), [], []
    record = {'schema_version': 'budget-recording-engineering-tests-v1', 'status': 'RUNNING',
        'scope': 'TARGETED_ARRAY_AND_TEST_DOUBLE_REGRESSIONS_ONLY',
        'planned_groups': list(PATTERNS), 'groups': rows,
        'planned_test_ids': [], 'executed_test_ids': [], 'test_ids': [],
        'unit_test_total': 0, 'unique_test_total': 0,
        'molecular_scf_grid_integrals_xc': 'NOT_EXECUTED',
        'new_real_scientific_calls': 0,
        'real_native_functional_counts': {'entered': 0, 'completed': 0, 'failed': 0},
        'production_compute_enabled': False, 'scientific_method_approval': False,
        'scientific_budget': None, 'forbidden_operation_attempts': attempted,
        'numeric_acceptance': 'NOT_EXECUTED_ARRAY_TESTS_DO_NOT_QUALIFY_MOLECULES'}
    started = time.monotonic()
    try:
        scratch = Path(tempfile.gettempdir()).resolve()
        record['synthetic_fixture_mount'] = tmpfs_mount(scratch)
        fixtures = Path(tempfile.mkdtemp(prefix='ai4orgchem-budget-recording-', dir=scratch))
        record['synthetic_fixture_root'] = str(fixtures)
        for variable, leaf in (
            ('AI4ORGCHEM_EVIDENCE_TEST_STAGE', 'evidence'),
            ('AI4ORGCHEM_REPORT_TEST_STAGE', 'report-export'),
            ('AI4ORGCHEM_PRESERVATION_TEST_STAGE', 'run-preservation')):
            os.environ[variable] = str(fixtures/leaf)
        bindings = install_guards(attempted)
        record['guarded_operations'] = [row[3] for row in bindings]
        groups = [(pattern, unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
                  for pattern in PATTERNS]
        record['planned_test_ids'] = [identity for _, suite in groups for identity in test_ids(suite)]
        if len(record['planned_test_ids']) != len(set(record['planned_test_ids'])):
            raise RuntimeError('Planned engineering test IDs are duplicated')
        save(targets[0], record)
        for pattern, suite in groups:
            planned = test_ids(suite)
            result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
            executed = list(result.executed_test_ids)
            changed = [label for owner, attribute, callback, label in bindings
                       if getattr(owner, attribute) is not callback]
            duplicates = sorted({identity for identity in executed
                                 if executed.count(identity) > 1 or identity in seen})
            good = (bool(result.testsRun) and result.wasSuccessful() and not result.skipped
                    and planned == executed and len(planned) == result.testsRun
                    and not duplicates and not attempted and not changed)
            rows.append({'pattern': pattern, 'status': 'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                'tests': result.testsRun, 'planned_test_ids': planned, 'test_ids': executed,
                'duplicate_test_ids': duplicates, 'changed_guard_bindings': changed,
                'failures': [{'test_id': test.id(), 'traceback': detail} for test, detail in result.failures],
                'errors': [{'test_id': test.id(), 'traceback': detail} for test, detail in result.errors],
                'skips': [{'test_id': test.id(), 'reason': reason} for test, reason in result.skipped]})
            seen.update(executed)
            record.update(executed_test_ids=[identity for row in rows for identity in row['test_ids']],
                test_ids=[identity for row in rows for identity in row['test_ids']],
                unit_test_total=sum(row['tests'] for row in rows), unique_test_total=len(seen),
                elapsed_seconds=time.monotonic()-started)
            save(targets[0], record)
            if not good:
                raise RuntimeError('Unit group failed, skipped, empty, duplicate or guard violation: '+pattern)
        record['fake_array_callback_counts'] = fake_callback_counts()
        if record['planned_test_ids'] != record['executed_test_ids']:
            raise RuntimeError('Planned engineering IDs differ from execution')
        record['status'] = 'PASS_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed = [label for owner, attribute, callback, label in bindings
                   if getattr(owner, attribute) is not callback]
        record.update(elapsed_seconds=time.monotonic()-started,
            changed_guard_bindings=changed, not_executed_groups=list(PATTERNS[len(rows):]))
        if changed or attempted:
            record.update(status='FAIL_ENGINEERING_ONLY', guard_integrity_status='FAIL')
        else:
            record['guard_integrity_status'] = 'PASS' if len(bindings) == 13 else 'NOT_FULLY_INSTALLED'
        save(targets[0], record)
        save(targets[1], record)
    if record['status'] != 'PASS_ENGINEERING_ONLY':
        raise RuntimeError('Budget-recording engineering execution did not pass')
    print(json.dumps({'status': record['status'], 'unit_test_total': record['unit_test_total'],
        'unique_test_total': record['unique_test_total'], 'new_real_scientific_calls': 0}, allow_nan=False))


if __name__ == '__main__':
    main()
