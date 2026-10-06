"""Minimal-dependency engineering CI; array and adapter tests are separate groups."""
import argparse
import importlib.abc
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MINIMAL_PATTERNS = (
    'test_user_molecule_input.py',
    'test_user_molecule_preflight.py',
    'test_user_molecule_contracts.py',
    'test_user_molecule_acceptance_resources.py',
    'test_user_molecule_solver_contract.py',
    'test_user_molecule_research.py',
    'test_user_molecule_run_preservation.py',
    'test_user_molecule_evidence.py',
    'test_user_molecule_report_export.py',
    'test_user_molecule_residual_budget.py',
)
ARRAY_PATTERNS = (
    'test_user_molecule_acceptance_metrics.py',
    'test_user_molecule_ordinary_reference.py',
    'test_user_molecule_solver_candidate.py',
    'test_user_molecule_residual_candidate.py',
    'test_user_molecule_residual_bridge.py',
    'test_user_molecule_residual_preparation.py',
    'test_user_molecule_residual_integration.py',
    'test_user_molecule_basis_representation.py',
)


def test_ids(suite):
    if isinstance(suite, unittest.TestSuite):
        return [identity for child in suite for identity in test_ids(child)]
    return [suite.id()]


class RejectScientificImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'pyscf', 'scipy', 'ai4orgchem', 'rdkit'):
            raise AssertionError('Scientific import forbidden in minimal CI: ' + fullname)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        raise ValueError('Use a new evidence directory outside the source checkout')
    declared = set(MINIMAL_PATTERNS + ARRAY_PATTERNS)
    actual = {path.name for path in (ROOT / 'tests').glob('test_user_molecule_*.py')}
    if actual != declared:
        raise ValueError('Unclassified CI test files: ' + repr(sorted(actual ^ declared)))
    output.mkdir(parents=True)
    for variable, leaf in (
        ('AI4ORGCHEM_EVIDENCE_TEST_STAGE', 'evidence'),
        ('AI4ORGCHEM_REPORT_TEST_STAGE', 'report-export'),
        ('AI4ORGCHEM_PRESERVATION_TEST_STAGE', 'run-preservation')):
        os.environ[variable] = str(Path(tempfile.gettempdir()) /
                                'ai4orgchem-minimal-tests' / leaf)
    sys.path.insert(0, str(ROOT))
    guard = RejectScientificImports()
    sys.meta_path.insert(0, guard)
    groups = []
    try:
        for pattern in MINIMAL_PATTERNS:
            suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=pattern)
            identities = test_ids(suite)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            groups.append({'pattern': pattern, 'tests': result.testsRun,
                           'failures': len(result.failures), 'errors': len(result.errors),
                           'skipped': len(result.skipped), 'test_ids': identities})
            good = (bool(result.testsRun) and result.wasSuccessful() and not result.skipped
                    and len(identities) == len(set(identities)) == result.testsRun)
            record = {
                'status': 'RUNNING' if good else 'FAIL',
                'groups': groups, 'unit_test_total': sum(row['tests'] for row in groups),
                'unit_test_ids': [identity for row in groups for identity in row['test_ids']],
                'array_groups': list(ARRAY_PATTERNS),
                'array_execution': 'SEPARATE_LOCAL_GUARDED_GROUP; NOT_EXECUTED_HERE',
                'reference_v1_v2': 'SEPARATE_LOCAL_GUARDED_GROUP; NOT_EXECUTED_HERE',
                'scientific_adapter': 'UNPUBLISHED_SOURCE; SEPARATE_LOCAL_GROUP',
                'scientific_scf_grid_full_eri': 'NOT_EXECUTED',
                'production_compute_enabled': False,
                'scope': 'Synthetic input/resource/receipt/report engineering only',
            }
            (output / 'summary.json').write_text(
                json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                encoding='utf-8')
            if not good:
                raise RuntimeError('Minimal unit group failed, was skipped or empty: ' + pattern)
        record['status'] = 'PASS_ENGINEERING_ONLY'
        (output / 'summary.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
            encoding='utf-8')
        print(json.dumps({'status': record['status'],
                          'unit_test_total': record['unit_test_total']}, ensure_ascii=False))
    finally:
        sys.meta_path.remove(guard)


if __name__ == '__main__':
    main()
