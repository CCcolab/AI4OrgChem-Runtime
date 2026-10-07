"""Zero-F receipt/finished-container admission tests; no process launches."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_user_molecule_occupied_space_response_contract import contract_fixture


SCRIPT = Path(__file__).resolve().parents[1]/'scripts/diagnose-user-molecule-occupied-space-response.py'
spec = importlib.util.spec_from_file_location('occupied_space_supervisor_under_test', SCRIPT)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)
COUNTERS = ('nr_rks_attempts', 'nr_rks_completed', 'nr_rks_failed',
            'energy_nuc_attempts', 'energy_nuc_completed', 'energy_nuc_failed')


class OccupiedSpaceSupervisorReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sequence = 0

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')

    def fixture(self):
        """Persist real matching metadata bytes, not a status-only receipt."""
        self.sequence += 1
        parent = self.root/('attempt-'+str(self.sequence))
        directory = parent/'output'; directory.mkdir(parents=True)
        contract = contract_fixture(authorized=True)
        prior = copy.deepcopy(contract); prior['scientific_execution_authorized'] = False
        prior['batch_id'] = 'zero-f-prior-'+str(self.sequence)
        self.write(parent/'execution-contract.json', prior)
        checksum = hashlib.sha256((parent/'execution-contract.json').read_bytes()).hexdigest()
        cid = 'cd'*32
        execution = {'status': 'EXECUTED_WITHIN_DECLARED_SCOPE', 'mode': 'ZERO_F_PREPARATION',
            'container_removed': True, 'platform_flags_verified': True,
            'container_exit_code': 0, 'oom_killed': False, 'container_id': cid}
        inspect = {'Id': cid, 'Image': contract['image_id'], 'Config': {'User': '10001:10001'},
            'State': {'Running': False, 'ExitCode': 0, 'OOMKilled': False},
            'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Memory': 1073741824,
                'MemorySwap': 1073741824, 'NanoCpus': 1000000000},
            'Mounts': [{'Destination': path, 'RW': False} for path in
                ('/workspace', '/saved-ordinary', '/seed-input', '/execution-contract.json')]}
        binding = contract['seed_binding']
        receipt = {'status': 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_PREPARATION_ONLY',
            'runtime_test_commit': contract['runtime_test_commit'],
            'source_file_sha256': contract['source_file_sha256'],
            'seed_input_source_sha256': binding['source_record']['sha256'],
            'seed_input_record_sha256': binding['seed_record']['sha256'],
            'seed_input_archive_sha256': binding['seed_arrays']['sha256'],
            'ordered_seed_density_ids': binding['seed_density_ids'],
            'source_metric_matches_all_three_paths': True,
            'real_F_NR_SCF_grid_integral_calls': 0, 'scientific_budget': None,
            'scientific_callback_reservation_created': False, 'forbidden_attempts': [],
            'changed_guard_bindings': [], 'native_counts': {path: {key: 0 for key in COUNTERS} for path in contract['paths']},
            'contract_sha256': checksum, 'scientific_execution': 'NOT_EXECUTED', 'Compute': False,
            'method_approval': False}
        for name, value in (('EXECUTION.json', execution), ('container-inspect.json', inspect)):
            self.write(parent/name, value)
        self.write(directory/'seed-readiness.json', receipt)
        return directory, contract

    def edit(self, path, mutation):
        value = json.loads(path.read_bytes()); mutation(value); self.write(path, value)

    def refuse(self, *, target='receipt', mutation=None):
        directory, contract = self.fixture()
        paths = {'receipt': directory/'seed-readiness.json', 'prior': directory.parent/'execution-contract.json',
            'execution': directory.parent/'EXECUTION.json', 'inspect': directory.parent/'container-inspect.json'}
        self.edit(paths[target], mutation)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            supervisor.verify_readiness(directory, contract)

    def test_matching_actual_false_authorized_prior_contract_receipt_and_finished_removed_container_pass(self):
        directory, contract = self.fixture()
        with patch.object(supervisor.subprocess, 'run', side_effect=AssertionError('Process launch forbidden')):
            binding = supervisor.verify_readiness(directory, contract)
        self.assertEqual(binding['scope'], 'ACTUAL_CACHED_PREPARATION_ONLY_NOT_ENDPOINT_OR_AUTHENTICATION')
        self.assertEqual(binding['sha256'], hashlib.sha256((directory/'seed-readiness.json').read_bytes()).hexdigest())
        self.assertEqual(binding['preparation_contract_sha256'], hashlib.sha256((directory.parent/'execution-contract.json').read_bytes()).hexdigest())

    def test_native_aggregate_and_each_of_eighteen_counters_are_integer_zero_not_boolean(self):
        for bad in (False, 0., 1, None):
            self.refuse(mutation=lambda value: value.__setitem__('real_F_NR_SCF_grid_integral_calls', bad))
        for path in contract_fixture()['paths']:
            for field in COUNTERS:
                for bad in (False, 0., 1):
                    self.refuse(mutation=lambda value: value['native_counts'][path].__setitem__(field, bad))

    def test_native_rows_require_all_three_paths_and_exact_six_fields(self):
        self.refuse(mutation=lambda value: value['native_counts'].pop('independent_reference'))
        self.refuse(mutation=lambda value: value['native_counts']['production_copy'].pop('nr_rks_failed'))
        self.refuse(mutation=lambda value: value['native_counts']['production_copy'].__setitem__('extra_unobserved', 0))

    def test_runtime_source_input_seed_order_and_all_path_metric_mismatches_refuse(self):
        for key, bad in (('runtime_test_commit', 'ff'*20), ('seed_input_source_sha256', 'ff'*32),
            ('seed_input_record_sha256', 'ff'*32), ('seed_input_archive_sha256', 'ff'*32),
            ('source_metric_matches_all_three_paths', 1)):
            self.refuse(mutation=lambda value: value.__setitem__(key, bad))
        self.refuse(mutation=lambda value: value['ordered_seed_density_ids'].reverse())
        self.refuse(mutation=lambda value: value['source_file_sha256'].__setitem__('runtime/user_molecule/occupied_space_seeds.py', 'ff'*32))

    def test_prior_contract_cannot_authorize_science_or_substitute_source_or_seed_binding(self):
        self.refuse(target='prior', mutation=lambda value: value.__setitem__('scientific_execution_authorized', True))
        self.refuse(target='prior', mutation=lambda value: value['source_file_sha256'].__setitem__('runtime/user_molecule/occupied_space_seeds.py', 'ff'*32))
        self.refuse(target='prior', mutation=lambda value: value['seed_binding']['seed_arrays'].__setitem__('sha256', 'ff'*32))

    def test_recorded_execution_requires_actual_run_isolated_cleanup_and_zero_exit(self):
        for key, bad in (('status', 'NOT_EXECUTED'), ('mode', 'SCIENTIFIC_OCCUPIED_SPACE_SINGLE_RESPONSE'),
            ('container_removed', False), ('platform_flags_verified', False), ('container_exit_code', 1),
            ('oom_killed', True), ('container_id', 'ff'*32)):
            self.refuse(target='execution', mutation=lambda value: value.__setitem__(key, bad))

    def test_actual_inspect_state_and_identity_cannot_be_overridden_by_success_execution_text(self):
        for key, bad in (('Running', True), ('ExitCode', 1), ('OOMKilled', True)):
            self.refuse(target='inspect', mutation=lambda value: value['State'].__setitem__(key, bad))
        self.refuse(target='inspect', mutation=lambda value: value.__setitem__('Image', 'sha256:'+'ff'*32))
        self.refuse(target='inspect', mutation=lambda value: value['Config'].__setitem__('User', 'root'))
        self.refuse(target='inspect', mutation=lambda value: value['HostConfig'].__setitem__('NetworkMode', 'default'))
        self.refuse(target='inspect', mutation=lambda value: value['HostConfig'].__setitem__('MemorySwap', -1))
        self.refuse(target='inspect', mutation=lambda value: value['Mounts'][0].__setitem__('RW', True))

    def test_false_zero_f_scope_claims_budget_or_guard_faults_refuse(self):
        for key, bad in (('scientific_execution', 'EXECUTED'), ('Compute', True), ('method_approval', True),
            ('scientific_budget', {}), ('scientific_callback_reservation_created', True),
            ('forbidden_attempts', ['SCF']), ('changed_guard_bindings', ['NumInt.nr_rks'])):
            self.refuse(mutation=lambda value: value.__setitem__(key, bad))

    def test_status_only_receipt_or_prior_contract_byte_hash_tampering_refuse(self):
        directory, contract = self.fixture()
        self.write(directory/'seed-readiness.json', {'status': 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_PREPARATION_ONLY'})
        with self.assertRaises((ValueError, KeyError, TypeError)): supervisor.verify_readiness(directory, contract)
        directory, contract = self.fixture()
        prior = directory.parent/'execution-contract.json'
        prior.write_bytes(prior.read_bytes()+b'\n')
        with self.assertRaises(ValueError): supervisor.verify_readiness(directory, contract)


if __name__ == '__main__': unittest.main()
