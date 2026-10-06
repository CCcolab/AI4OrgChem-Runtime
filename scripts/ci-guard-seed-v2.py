"""Targeted V2 engineering groups; all molecular evaluation APIs forbidden.

Run in the pinned Linux candidate with a tmpfs /tmp and a fresh /output.
This runner has no Docker, Compute, publication or scientific budget action.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    'test_user_molecule_seed_v2.py',
    'test_reference_seed_v2.py',
    'test_user_molecule_residual_seed_v2.py',
    'test_reference_residual_seed_v2.py',
    'test_user_molecule_residual_seed_execution_contract.py',
    'test_user_molecule_residual_bridge.py',
    'test_user_molecule_residual_preparation.py',
    'test_user_molecule_residual_integration.py',
    'test_user_molecule_solver_candidate.py',
    'test_user_molecule_residual_candidate.py',
    'test_reference_residual_candidate.py',
    'test_reference_residual_molecule.py',
    'test_user_molecule_residual_budget.py',
    'test_user_molecule_residual_execution_contract.py',
)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8')


def test_ids(suite):
    if isinstance(suite, unittest.TestSuite):
        return [identity for child in suite for identity in test_ids(child)]
    return [suite.id()]


def tmpfs_mount(path):
    """Return the actual nearest Linux mount, not a directory-name claim."""
    candidates = []
    for row in Path('/proc/self/mountinfo').read_text(encoding='utf-8').splitlines():
        before, after = row.split(' - ', 1)
        mount = Path(before.split()[4].replace('\\040', ' ').replace('\\134', '\\'))
        if path.is_relative_to(mount):
            candidates.append((len(mount.parts), str(mount), after.split()[0]))
    if not candidates:
        raise RuntimeError('No actual fixture mount information')
    _, mount, kind = max(candidates)
    if kind != 'tmpfs':
        raise RuntimeError('Synthetic fixture directory is not on tmpfs: '+mount+' ('+kind+')')
    return {'mount_point': mount, 'filesystem': kind}


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_test_ids = []

    def startTest(self, test):
        self.executed_test_ids.append(test.id())
        super().startTest(test)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('/output'))
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Engineering evidence must be outside the source checkout')
    output.mkdir(parents=True, exist_ok=True)
    targets = [output/'test-progress.json', output/'seed-v2-engineering-tests.json']
    if any(path.exists() for path in targets):
        raise ValueError('Do not overwrite a previous engineering execution')
    sys.path.insert(0, str(ROOT))
    rows, seen, attempted = [], set(), []
    record = {'schema_version': 'seed-v2-engineering-tests-v1', 'status': 'RUNNING',
              'scope': 'TARGETED_ARRAY_AND_TEST_DOUBLE_REGRESSIONS_ONLY',
              'planned_groups': list(PATTERNS), 'groups': rows,
              'test_ids': [], 'unit_test_total': 0, 'unique_test_total': 0,
              'molecular_scf_grid_integrals_xc': 'NOT_EXECUTED',
              'new_real_scientific_calls': 0, 'production_compute_enabled': False,
              'scientific_method_approval': False, 'forbidden_operation_attempts': attempted,
              'numeric_acceptance': 'NOT_EXECUTED_ARRAY_TESTS_DO_NOT_QUALIFY_MOLECULES'}
    started = time.monotonic()
    try:
        scratch = Path(tempfile.gettempdir()).resolve()
        record['synthetic_fixture_mount'] = tmpfs_mount(scratch)
        fixture_root = Path(tempfile.mkdtemp(prefix='ai4orgchem-seed-v2-', dir=scratch))
        record['synthetic_fixture_root'] = str(fixture_root)
        for variable, leaf in (
            ('AI4ORGCHEM_EVIDENCE_TEST_STAGE', 'evidence'),
            ('AI4ORGCHEM_REPORT_TEST_STAGE', 'report-export'),
            ('AI4ORGCHEM_PRESERVATION_TEST_STAGE', 'run-preservation')):
            os.environ[variable] = str(fixture_root/leaf)
        from pyscf import dft, gto, scf
        from pyscf.dft import gen_grid, numint
        guarded, guard_bindings = [], []
        def install(owner, attribute, label):
            if not hasattr(owner, attribute):
                raise RuntimeError('Required molecular guard API unavailable: '+label)
            def forbidden(*_args, **_kwargs):
                attempted.append(label)
                raise AssertionError('Molecular operation forbidden in V2 engineering: '+label)
            setattr(owner, attribute, forbidden)
            guarded.append(label)
            guard_bindings.append((owner, attribute, forbidden, label))
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
            install(owner, attribute, label)
        record['guarded_operations'] = guarded
        save(targets[0], record)
        for pattern in PATTERNS:
            suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern)
            planned_ids = test_ids(suite)
            runner = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult)
            result = runner.run(suite)
            executed = list(result.executed_test_ids)
            changed_guards = [label for owner, attribute, callback, label in guard_bindings
                              if getattr(owner, attribute) is not callback]
            duplicate = sorted({identity for identity in executed
                                if executed.count(identity) > 1 or identity in seen})
            good = (bool(result.testsRun) and result.wasSuccessful() and not result.skipped
                    and planned_ids == executed and len(planned_ids) == result.testsRun
                    and not duplicate and not attempted and not changed_guards)
            row = {'pattern': pattern, 'status': 'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                   'tests': result.testsRun, 'test_ids': executed, 'planned_test_ids': planned_ids,
                   'duplicate_test_ids': duplicate,
                   'changed_guard_bindings': changed_guards,
                   'failures': [{'test_id': test.id(), 'traceback': detail}
                                for test, detail in result.failures],
                   'errors': [{'test_id': test.id(), 'traceback': detail}
                              for test, detail in result.errors],
                   'skips': [{'test_id': test.id(), 'reason': reason}
                             for test, reason in result.skipped]}
            rows.append(row); seen.update(executed)
            record.update(test_ids=[identity for item in rows for identity in item['test_ids']],
                          unit_test_total=sum(item['tests'] for item in rows), unique_test_total=len(seen),
                          elapsed_seconds=time.monotonic()-started)
            save(targets[0], record)
            if not good:
                raise RuntimeError('Targeted unit group failed, skipped, empty, duplicate or guard violation: '+pattern)
        record['status'] = 'PASS_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        record.update(elapsed_seconds=time.monotonic()-started,
                      not_executed_groups=list(PATTERNS[len(rows):]))
        save(targets[0], record)
        save(targets[1], record)
    print(json.dumps({'status': record['status'], 'unit_test_total': record['unit_test_total'],
                      'unique_test_total': record['unique_test_total'],
                      'new_real_scientific_calls': 0}, allow_nan=False))


if __name__ == '__main__':
    main()
