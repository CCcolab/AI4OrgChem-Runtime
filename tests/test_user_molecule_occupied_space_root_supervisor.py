"""Root preparation CLI/receipt safeguards, stdlib only and no processes."""
from contextlib import redirect_stderr
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_user_molecule_occupied_space_root_contract import contract_fixture


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('root_preparation_supervisor',
    ROOT/'scripts/diagnose-user-molecule-occupied-space-root.py')
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)
PREPARATION_GUARDS = [
    'SCF.kernel', 'SCF.scf', 'hf.kernel', 'RHF.kernel', 'UHF.kernel', 'ROHF.kernel',
    'RKS.kernel', 'UKS.kernel', 'ROKS.kernel', 'Grids.build', 'Mole.intor', 'Mole.intor_by_shell',
    'Mole.energy_nuc', 'NumInt.nr_rks', 'numint.nr_rks', 'old production residual solve',
    'old production iterate', 'old production SCF driver', 'old reference solve',
    'old reference SciPy shortcut', 'old ENGINEERING_ONLY budgeted solve',
    'old budgeted SciPy shortcut', 'old budgeted private Jacobian shortcut',
    'reference fixed_point', 'reference v2 fixed_point', 'source SCF driver',
    'source single-F evaluation', 'SciPy TRF', 'SciPy private Jacobian',
    'old production bridge.run', 'old production bridge.evaluate', 'old reference bridge.run',
    'prepared reference.evaluate', 'new root candidate solve']


def readiness_fixture(contract, checksum):
    inputs, initial = contract['seed_binding'], contract['initial_density']
    return {'status': 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_ROOT_PREPARATION_ONLY',
        'runtime_test_commit': contract['runtime_test_commit'], 'contract_sha256': checksum,
        'source_file_sha256': copy.deepcopy(contract['source_file_sha256']),
        'seed_input_source_sha256': inputs['source_record']['sha256'],
        'seed_input_record_sha256': inputs['seed_record']['sha256'],
        'seed_input_archive_sha256': inputs['seed_arrays']['sha256'],
        'history_record_sha256': contract['parent_evidence']['history_record']['sha256'],
        'mdr_record_sha256': contract['parent_evidence']['mdr_record']['sha256'],
        'ordered_seed_density_ids': inputs['seed_density_ids'], 'selected_seed_index': 2,
        'selected_angle_rad': -.1, 'selected_density_id': initial['density_id'],
        'selected_array_identity': copy.deepcopy(initial['array_identity']),
        'source_metric_matches_reference': True, 'all_four_recipe_verified': True,
        'source_bindings': {'source_record_sha256': inputs['source_record']['sha256'],
            'source_arrays_sha256': inputs['source_arrays']['sha256'],
            'seed_record_sha256': inputs['seed_record']['sha256'], 'seed_arrays_sha256': inputs['seed_arrays']['sha256'],
            'history_record_sha256': contract['parent_evidence']['history_record']['sha256'],
            'mdr_record_sha256': contract['parent_evidence']['mdr_record']['sha256']},
        'guarded_operations': list(PREPARATION_GUARDS), 'forbidden_attempts': [], 'changed_guard_bindings': [],
        'real_F_NR_SCF_grid_integral_calls': 0, 'nuclear_repulsion_calls': 0,
        'prepared_callback_ledger_entries': 0, 'new_true_F_NR_calls': 0,
        'solver_evaluated': False, 'native_budget': None, 'scientific_budget': None,
        'scientific_callback_reservation_created': False, 'scientific_execution_authorized': False,
        'root_solve': 'NOT_EXECUTED', 'CURRENT_F': 'NOT_EXECUTED',
        'actual_live_root_runner': 'NOT_IMPLEMENTED_IN_THIS_PREPARE_ONLY_VERSION',
        'scientific_execution': 'NOT_EXECUTED', 'Compute': False, 'method_approval': False}


class OccupiedSpaceRootSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.contract = contract_fixture()
        self.checksum = hashlib.sha256(json.dumps(self.contract, sort_keys=True).encode()).hexdigest()
        self.receipt = readiness_fixture(self.contract, self.checksum)

    def verify(self, receipt):
        return supervisor.verify_root_readiness(receipt, self.contract, self.checksum)

    def refuse(self, mutation):
        receipt = copy.deepcopy(self.receipt); mutation(receipt)
        with self.assertRaises((ValueError, KeyError, TypeError)): self.verify(receipt)

    def test_cli_requires_explicit_prepare_only_and_parses_without_any_process(self):
        with patch.object(supervisor.subprocess, 'run', side_effect=AssertionError('Process forbidden')):
            args = supervisor.argument_parser().parse_args(['--output-root', 'candidate-out',
                '--seed-input-dir', 'candidate-in', '--prepare-only'])
        self.assertIs(args.prepare_only, True)
        self.assertFalse(hasattr(args, 'execute'))

    def test_cli_missing_prepare_only_or_any_execute_option_fails_before_docker(self):
        base = ['--output-root', 'candidate-out', '--seed-input-dir', 'candidate-in']
        with patch.object(supervisor.subprocess, 'run', side_effect=AssertionError('Process forbidden')):
            for arguments in (base, base+['--execute'], base+['--prepare-only', '--execute']):
                with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        supervisor.argument_parser().parse_args(arguments)
                    self.assertEqual(caught.exception.code, 2)

    def test_complete_worker_receipt_matches_real_contract_hash_without_granting_root_execution(self):
        before = copy.deepcopy(self.receipt)
        with patch.object(supervisor.subprocess, 'run', side_effect=AssertionError('Process forbidden')):
            self.assertIs(self.verify(self.receipt), True)
        self.assertEqual(self.receipt, before)
        self.assertIs(self.contract['scientific_execution_authorized'], False)
        self.assertIs(self.contract['scientific_budget_reserved'], False)

    def test_all_actual_operation_counts_require_integer_zero_and_scientific_flags_remain_false(self):
        for field in ('real_F_NR_SCF_grid_integral_calls', 'nuclear_repulsion_calls', 'prepared_callback_ledger_entries', 'new_true_F_NR_calls'):
            for bad in (False, 0., 1, None): self.refuse(lambda row: row.__setitem__(field, bad))
        for field in ('scientific_callback_reservation_created', 'scientific_execution_authorized', 'solver_evaluated', 'Compute', 'method_approval'):
            for bad in (True, 0): self.refuse(lambda row: row.__setitem__(field, bad))
        self.refuse(lambda row: row.__setitem__('scientific_budget', {}))
        self.refuse(lambda row: row.__setitem__('native_budget', {}))

    def test_source_input_history_current_contract_and_selected_seed_mismatches_refuse(self):
        for field in ('runtime_test_commit', 'contract_sha256', 'seed_input_source_sha256',
            'seed_input_record_sha256', 'seed_input_archive_sha256', 'history_record_sha256',
            'mdr_record_sha256', 'selected_density_id'):
            self.refuse(lambda row: row.__setitem__(field, 'ff'*32))
        self.refuse(lambda row: row.__setitem__('selected_seed_index', 1))
        self.refuse(lambda row: row.__setitem__('selected_angle_rad', .1))
        self.refuse(lambda row: row['selected_array_identity'].__setitem__('sha256', 'ff'*32))
        self.refuse(lambda row: row['ordered_seed_density_ids'].reverse())
        self.refuse(lambda row: row['source_file_sha256'].__setitem__('reference/residual_budgeted_candidate.py', 'ff'*32))
        self.refuse(lambda row: row['source_bindings'].__setitem__('source_arrays_sha256', 'ff'*32))

    def test_status_only_or_nonexecuted_scope_and_unverified_recipe_guard_faults_refuse(self):
        for receipt in ({}, {'status': self.receipt['status']}):
            with self.assertRaises((ValueError, KeyError, TypeError)): self.verify(receipt)
        for field, bad in (('status', 'NOT_EXECUTED'), ('root_solve', 'EXECUTED'),
            ('CURRENT_F', 'EVALUATED_FROM_OLD_HISTORY'), ('scientific_execution', 'EXECUTED'),
            ('all_four_recipe_verified', 1), ('source_metric_matches_reference', False),
            ('forbidden_attempts', ['NR']), ('changed_guard_bindings', ['SCF'])):
            self.refuse(lambda row: row.__setitem__(field, bad))
        self.refuse(lambda row: row['guarded_operations'].pop())
        self.refuse(lambda row: row['guarded_operations'].__setitem__(0, row['guarded_operations'][1]))
        self.refuse(lambda row: row['guarded_operations'].__setitem__(0, 'unknown_guard'))


if __name__ == '__main__': unittest.main()
