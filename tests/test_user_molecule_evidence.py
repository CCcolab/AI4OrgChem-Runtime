"""Local JSON evidence tests; never import or execute scientific engines."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.user_molecule.evidence import read_run_report
from runtime.user_molecule.input import InputError


STAGE = Path(r'D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-report-engineering\evidence-tests')


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        STAGE.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='json-', dir=STAGE)
        self.root = Path(self.temporary.name)
        self.request = {'research_question': '本地合成证据测试',
                        'calculation_profile': 'pilot-b3lypg-sto3g-grid2-v1',
                        'fragments': [{'id': 'A', 'carbon_atom_indices_1based': [1]}]}

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')

    def manifest(self, name='run-manifest.json', **fields):
        files = {path.relative_to(self.root).as_posix():
                 {'size_bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                 for path in self.root.rglob('*') if path.is_file() and path.name not in ('manifest.json', 'run-manifest.json')}
        self.write(name, {'files': files, **fields})

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def preflight(self):
        self.write('preflight.json', {'input_status': 'VALID', 'compute_eligible': False,
                   'method_status': 'NOT_REVIEWED', 'reasons': ['FROZEN_GATE'],
                   'identities': {'image_id': 'synthetic-image', 'runtime_build_commit': 'synthetic-build'}})
        self.write('input/request.normalized.json', self.request)

    def qualified(self):
        self.write('result.json', {'input_status': 'VALID', 'execution_status': 'COMPLETED',
                   'numerical_status': 'NUMERICALLY_QUALIFIED', 'research_status': 'NOT_REVIEWED',
                   'comparison_available': True, 'delta_hartree': -.5,
                   'delta_kcal_mol': -313.75473703155,
                   'ordinary': {'converged': True, 'total_energy_hartree': -2.},
                   'conditional': {'converged': True, 'total_energy_hartree': -1.5},
                   'ordinary_tests': {'synthetic': True}, 'conditional_tests': {'synthetic': True},
                   'identities': {'runtime_test_commit': 'synthetic-test'}, 'reasons': []})
        self.write('input/request.normalized.json', self.request)

    def test_check_is_completed_but_science_not_executed_and_read_is_immutable(self):
        self.preflight()
        self.manifest(action='check', execution_status='COMPLETED', numerical_status='NOT_EXECUTED')
        before = self.snapshot()
        value = read_run_report(self.root)
        summary = value['summary']
        self.assertEqual(summary['record_integrity'], 'MATCHED')
        self.assertEqual(summary['execution_status'], 'COMPLETED')
        self.assertEqual(summary['numerical_status'], 'NOT_EXECUTED')
        self.assertEqual(summary['research_status'], 'NOT_REVIEWED')
        self.assertFalse(summary['compute_eligible'])
        self.assertIn('Compute 资格：False', value['markdown'])
        self.assertNotIn('NUMERICAL_COMPARISON_NOT_QUALIFIED', value['markdown'])
        self.assertIn('gap 来源（记录字段）：', value['markdown'])
        self.assertNotIn('LAST_DIAGONALIZATION_POSSIBLY_DIIS', value['markdown'])
        self.assertEqual(summary['report_exit_code'], 0)
        self.assertEqual(self.snapshot(), before)

    def test_error_record_overrides_cached_preflight_and_preserves_original_exit(self):
        self.preflight()
        self.write('error.json', {'error_type': 'InputError', 'message': 'failed check', 'exit_code': 11})
        self.write('runtime-progress.json', {'stage': 'INPUT_CHECK_COMPLETED', 'scf_executed': False})
        self.manifest(execution_status='FAILED', numerical_status='NOT_EXECUTED', exit_code=11)
        value = read_run_report(self.root)
        summary = value['summary']
        self.assertEqual(value['record_kind'], 'service-error')
        self.assertEqual(summary['execution_status'], 'FAILED')
        self.assertEqual(summary['numerical_status'], 'NOT_EXECUTED')
        self.assertEqual(summary['research_status'], 'NOT_QUALIFIED')
        self.assertEqual(summary['original_exit_code'], 11)
        self.assertEqual(summary['original_exit_code_source'], 'error.json.exit_code')
        self.assertEqual(summary['report_exit_code'], 0)
        self.assertIn('failed check', value['markdown'])

    def test_host_timeout_overrides_even_a_cached_qualified_result(self):
        self.qualified()
        self.write('host-execution.json', {'status': 'PASS', 'observation':
                   {'reason': 'TIMEOUT', 'container_exit_code': 137, 'oom_killed': False}})
        self.manifest()
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['execution_status'], 'FAILED')
        self.assertEqual(summary['termination_reason'], 'TIMEOUT')
        self.assertEqual(summary['original_exit_code'], 137)
        self.assertEqual(summary['research_status'], 'NOT_QUALIFIED')
        self.assertFalse(summary['comparison_available'])
        self.assertIsNone(summary['delta_hartree'])
        self.assertIsNone(summary['delta_kcal_mol'])

    def test_acceptance_failure_labels_are_diagnostic_and_do_not_promote_comparison(self):
        self.write('result.json', {'status': 'FAIL_NUMERICAL_GATES', 'research_status': 'NOT_REVIEWED',
                   'comparison_available': True, 'delta_hartree': 999., 'diagnostic_delta_hartree': 1.,
                   'checks': [{'metric_id': 'recorded-gate', 'required': True, 'pass': False}],
                   'identities': {'image_id': 'synthetic-image', 'runtime_test_commit': 'synthetic-test'}})
        self.write('request.acceptance.json', self.request)
        self.write('execution.json', {'container_exit_code': 30, 'status': 'FAIL_NUMERICAL_GATES'})
        self.write('ordinary-tested.json', {'converged': True, 'total_energy_hartree': -2.})
        self.write('conditional-single.json', {'converged': True, 'total_energy_hartree': -1.,
                   'gap_operator_source': 'SYNTHETIC_STORED_SOURCE', 'molecular_acceptance': 'NOT_EXECUTED'})
        self.write('conditional-copy.json', {'converged': False, 'total_energy_hartree': -1.2})
        self.write('conditional-reference.json', {'converged': False, 'total_energy_hartree': -1.3,
                   'state_comparability': 'COMPARABLE_CANDIDATE'})
        self.write('resource-candidate.json', {'scientific_qualification': 'NOT_REVIEWED'})
        self.manifest('manifest.json')
        before = self.snapshot()
        value = read_run_report(self.root)
        summary = value['summary']
        self.assertEqual(value['record_kind'], 'acceptance')
        self.assertEqual(summary['scientific_execution_status'], 'EXECUTED')
        self.assertEqual(summary['numerical_status'], 'NOT_QUALIFIED')
        self.assertEqual(summary['research_status'], 'NOT_QUALIFIED')
        self.assertFalse(summary['comparison_available'])
        self.assertIsNone(summary['delta_hartree'])
        self.assertEqual(summary['raw_statuses']['research_status'], 'NOT_REVIEWED')
        self.assertEqual(summary['raw_statuses']['resource_scientific_qualification'], 'NOT_REVIEWED')
        self.assertEqual(summary['failed_metric_ids'], ['recorded-gate'])
        self.assertEqual(summary['original_exit_code'], 30)
        self.assertIn('synthetic-test', value['markdown'])
        self.assertIn('镜像构建 runtime：UNKNOWN', value['markdown'])
        self.assertIn('SYNTHETIC_STORED_SOURCE', value['markdown'])
        self.assertIn('pilot-b3lypg-sto3g-grid2-v1', value['markdown'])
        self.assertIn('conditional-copy', value['markdown'])
        self.assertIn('conditional-reference', value['markdown'])
        self.assertEqual(summary['raw_state_labels']['conditional-single']['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertEqual(summary['raw_state_labels']['conditional-reference']['state_comparability'], 'COMPARABLE_CANDIDATE')
        self.assertEqual(self.snapshot(), before)

    def test_missing_manifest_or_unlisted_read_file_is_unverified_and_suppresses_delta(self):
        self.qualified()
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['record_integrity'], 'UNVERIFIED')
        self.assertEqual(summary['report_exit_code'], 40)
        self.assertEqual(summary['numerical_status'], 'UNKNOWN')
        self.assertFalse(summary['comparison_available'])
        self.assertIsNone(summary['delta_hartree'])
        self.manifest()
        self.write('runtime-progress.json', {'scf_executed': False})
        value = read_run_report(self.root)
        self.assertIn('FILE_NOT_MANIFESTED: runtime-progress.json', value['summary']['evidence_issues'])
        self.assertEqual(value['source_files']['runtime-progress.json']['integrity'], 'UNVERIFIED')
        self.assertFalse(value['summary']['comparison_available'])

    def test_missing_listed_file_is_reported_and_does_not_become_zero_or_success(self):
        self.preflight()
        self.manifest()
        manifest = json.loads((self.root / 'run-manifest.json').read_text())
        manifest['files']['absent.json'] = {'size_bytes': 2, 'sha256': '0' * 64}
        self.write('run-manifest.json', manifest)
        value = read_run_report(self.root)
        self.assertIn('absent.json', value['summary']['missing_files'])
        self.assertEqual(value['summary']['report_exit_code'], 40)
        self.assertIsNone(value['summary']['original_exit_code'])
        self.assertIsNone(value['summary']['delta_hartree'])

    def test_every_manifest_file_is_verified_without_loading_binary_arrays(self):
        self.preflight()
        (self.root / 'stored-array.npz').write_bytes(b'synthetic binary evidence')
        self.manifest(execution_status='COMPLETED')
        original = Path.read_bytes
        def guarded(path):
            if path.suffix == '.npz':
                raise AssertionError('Binary arrays must be streamed, never loaded')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded):
            self.assertEqual(read_run_report(self.root)['summary']['record_integrity'], 'MATCHED')
        (self.root / 'stored-array.npz').write_bytes(b'tampered binary evidence')
        with self.assertRaises(InputError) as caught:
            read_run_report(self.root)
        self.assertEqual(caught.exception.code, 40)

    def test_escaping_paths_duplicate_json_nonfinite_json_and_size_mismatch_are_rejected(self):
        for mode in ('escape', 'duplicate', 'nonfinite', 'size'):
            with self.subTest(mode=mode):
                self.preflight()
                self.manifest()
                if mode == 'escape':
                    manifest = json.loads((self.root / 'run-manifest.json').read_text())
                    manifest['files']['../outside.json'] = {'size_bytes': 0, 'sha256': '0' * 64}
                    self.write('run-manifest.json', manifest)
                elif mode == 'duplicate':
                    (self.root / 'preflight.json').write_text('{"compute_eligible":false,"compute_eligible":true}')
                    self.manifest()
                elif mode == 'nonfinite':
                    (self.root / 'preflight.json').write_text('{"compute_eligible":false,"x":1e999}')
                    self.manifest()
                else:
                    manifest = json.loads((self.root / 'run-manifest.json').read_text())
                    manifest['files']['preflight.json']['size_bytes'] += 1
                    self.write('run-manifest.json', manifest)
                with self.assertRaises(InputError) as caught:
                    read_run_report(self.root)
                self.assertEqual(caught.exception.code, 40)

    def test_conflicting_run_identities_and_request_binding_are_rejected(self):
        self.preflight()
        self.write('host-execution.json', {'status': 'FAILED', 'image_id': 'different-image'})
        self.manifest()
        with self.assertRaises(InputError):
            read_run_report(self.root)
        self.write('host-execution.json', {'status': 'FAILED', 'image_id': 'synthetic-image'})
        preflight = json.loads((self.root / 'preflight.json').read_text())
        preflight['identities']['normalized_sha256'] = '0' * 64
        self.write('preflight.json', preflight)
        self.manifest()
        with self.assertRaises(InputError):
            read_run_report(self.root)

    def test_local_manifest_cannot_grant_method_or_research_approval(self):
        self.qualified()
        record = json.loads((self.root / 'result.json').read_text())
        record['method_status'] = 'APPROVED_WITHIN_SCOPE'
        record['research_status'] = 'QUALIFIED_WITHIN_SCOPE'
        self.write('result.json', record)
        self.manifest(method_status='APPROVED_WITHIN_SCOPE')
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['method_status'], 'NOT_REVIEWED')
        self.assertEqual(summary['research_status'], 'TECHNICAL_ONLY')
        self.assertEqual(summary['record_integrity_scope'], 'LOCAL_MANIFEST_BYTES_ONLY')

    def test_failed_saved_gate_cannot_keep_a_bare_numerically_qualified_label(self):
        self.qualified()
        record = json.loads((self.root / 'result.json').read_text())
        record['conditional']['converged'] = False
        self.write('result.json', record)
        self.manifest()
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['numerical_status'], 'NOT_QUALIFIED')
        self.assertEqual(summary['raw_statuses']['numerical_status'], 'NUMERICALLY_QUALIFIED')
        self.assertFalse(summary['comparison_available'])
        self.assertIsNone(summary['delta_hartree'])

    def test_early_error_without_input_snapshot_can_be_complete_diagnostic_evidence(self):
        self.write('error.json', {'error_type': 'InputError', 'message': 'input parsing failed', 'exit_code': 10})
        self.write('runtime-progress.json', {'stage': 'INPUT_CHECK', 'scf_executed': False})
        self.manifest(execution_status='FAILED', numerical_status='NOT_EXECUTED', exit_code=10)
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['record_integrity'], 'MATCHED')
        self.assertEqual(summary['report_exit_code'], 0)
        self.assertTrue(summary['expected_absence'])
        self.assertEqual(summary['input_status'], 'UNKNOWN')
        self.assertEqual(summary['scientific_execution_status'], 'NOT_EXECUTED')
        self.assertIsNone(summary['delta_hartree'])

    def test_host_blocked_exit20_is_separate_from_infrastructure_failure(self):
        self.write('result.json', {'input_status': 'VALID', 'execution_status': 'BLOCKED',
                   'numerical_status': 'NOT_EXECUTED', 'research_status': 'NOT_REVIEWED',
                   'comparison_available': False, 'delta_hartree': None, 'delta_kcal_mol': None,
                   'reasons': ['FROZEN_GATE'], 'identities': {}})
        self.write('input/request.normalized.json', self.request)
        self.write('host-execution.json', {'status': 'BLOCKED', 'service_exit_code': 20, 'container_exit_code': 20})
        self.manifest()
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['execution_status'], 'BLOCKED')
        self.assertEqual(summary['host_service_exit_code'], 20)
        self.assertEqual(summary['container_exit_code'], 20)
        self.assertEqual(summary['original_exit_code'], 20)
        self.assertEqual(summary['report_exit_code'], 0)

    def test_completed_host_check_survives_manifest_host_only_envelope(self):
        self.preflight()
        host = {'status': 'COMPLETED', 'service_exit_code': 0, 'container_exit_code': 0}
        self.write('host-execution.json', host)
        self.manifest(host=host)
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['execution_status'], 'COMPLETED')
        self.assertEqual(summary['scientific_execution_status'], 'NOT_EXECUTED')
        self.assertEqual(summary['research_status'], 'NOT_REVIEWED')

    def test_collection_failure_overrides_old_completed_label_and_separates_codes(self):
        self.preflight()
        self.write('host-execution.json', {'status': 'COMPLETED', 'service_exit_code': 40,
                   'container_exit_code': 0, 'collection_error': 'host collection failed',
                   'termination_reason': 'UNKNOWN'})
        self.manifest()
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['execution_status'], 'FAILED')
        self.assertEqual(summary['scientific_execution_status'], 'UNKNOWN')
        self.assertEqual(summary['numerical_status'], 'UNKNOWN')
        self.assertEqual(summary['original_exit_code'], 40)
        self.assertEqual(summary['host_service_exit_code'], 40)
        self.assertEqual(summary['container_exit_code'], 0)
        self.assertEqual(summary['report_exit_code'], 0)

    def test_unknown_host_terminal_state_is_not_a_completed_check(self):
        self.preflight()
        self.write('host-execution.json', {'status': 'UNKNOWN', 'service_exit_code': None,
                   'container_exit_code': None})
        self.manifest(execution_status='COMPLETED')
        summary = read_run_report(self.root)['summary']
        self.assertEqual(summary['execution_status'], 'UNKNOWN')
        self.assertEqual(summary['record_integrity'], 'UNVERIFIED')
        self.assertEqual(summary['report_exit_code'], 40)
        self.assertIsNone(summary['original_exit_code'])
        self.assertIsNone(summary['compute_eligible'])

    def test_failure_science_execution_follows_progress_instead_of_cached_preflight(self):
        self.preflight()
        self.write('error.json', {'error_type': 'RuntimeError', 'message': 'science failed', 'exit_code': 40})
        for executed, expected in ((True, 'EXECUTED'), (False, 'NOT_EXECUTED'), (None, 'UNKNOWN')):
            with self.subTest(executed=executed):
                self.write('runtime-progress.json', {'scf_executed': executed})
                self.manifest()
                summary = read_run_report(self.root)['summary']
                self.assertEqual(summary['scientific_execution_status'], expected)
                self.assertEqual(summary['execution_status'], 'FAILED')
                self.assertFalse(summary['checked_only'])

    def test_host_manifest_copy_and_top_level_source_identities_must_match(self):
        self.preflight()
        host = {'status': 'COMPLETED', 'service_exit_code': 0, 'container_exit_code': 0,
                'runtime_build_commit': 'different-build'}
        self.write('host-execution.json', host)
        self.manifest(host=host)
        with self.assertRaises(InputError):
            read_run_report(self.root)
        host['runtime_build_commit'] = 'synthetic-build'
        self.write('host-execution.json', host)
        self.manifest(host={**host, 'status': 'FAILED'})
        with self.assertRaises(InputError):
            read_run_report(self.root)

    def test_manifest_case_collisions_reparse_components_and_metadata_bounds_are_rejected(self):
        self.preflight()
        self.manifest()
        manifest = json.loads((self.root / 'run-manifest.json').read_text())
        manifest['files']['PREFLIGHT.JSON'] = manifest['files']['preflight.json']
        self.write('run-manifest.json', manifest)
        with self.assertRaises(InputError):
            read_run_report(self.root)
        self.manifest()
        observed_lstat = Path.lstat
        def flagged_lstat(path):
            observed = observed_lstat(path)
            if path == self.root / 'preflight.json':
                return SimpleNamespace(st_mode=observed.st_mode, st_file_attributes=0x400)
            return observed
        with patch.object(Path, 'lstat', flagged_lstat), self.assertRaises(InputError):
            read_run_report(self.root)
        (self.root / 'preflight.json').write_bytes(b' ' * (4 * 1024 * 1024 + 1))
        self.manifest()
        with self.assertRaises(InputError) as caught:
            read_run_report(self.root)
        self.assertEqual(caught.exception.code, 40)
        self.preflight()
        self.write('run-manifest.json', {'files': {f'f{index}': {'size_bytes': 0, 'sha256': '0' * 64}
                                                for index in range(10001)}})
        with self.assertRaises(InputError):
            read_run_report(self.root)


if __name__ == '__main__':
    unittest.main()
