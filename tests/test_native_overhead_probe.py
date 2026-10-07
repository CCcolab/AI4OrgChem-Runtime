"""Engineering probe boundaries; synthetic factory test needs outer native guards."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_overhead_probe', ROOT / 'scripts/probe-user-molecule-native-overhead.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class NativeOverheadProbeTests(unittest.TestCase):
    def inactive(self):
        return {**{field: False for field in ('scientific_execution_authorized', 'local_cli_execute_requested',
            'scientific_budget_reserved', 'production_activation', 'scientific_approval', 'method_approval', 'Compute')},
            'execution_grant': None, 'budget_reservation': None, 'research_delta_hartree': None}

    def test_active_previous_scientific_contract_and_grants_are_refused(self):
        for key, value in [('scientific_execution_authorized', True), ('local_cli_execute_requested', True),
                           ('execution_grant', {'direct_user_message': 'anything'}), ('budget_reservation', {})]:
            item = self.inactive(); item[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.require_inactive(item)

    def test_truthy_or_numeric_false_cannot_substitute_exact_false(self):
        for value in (0, 1, None, 'false'):
            item = self.inactive(); item['Compute'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.require_inactive(item)
        probe.require_inactive(self.inactive())

    def test_source_count_is_contract_derived_and_actual_bytes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'one.py').write_bytes(b'one')
            (root / 'two.py').write_bytes(b'two')
            values = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ('one.py', 'two.py')}
            self.assertEqual(probe.source_map_admission(root, values), {'expected_count': 2, 'actual_count': 2,
                'total_source_bytes': 6, 'all_bytes_sha256_matched': True})

    def test_tampered_source_bytes_cannot_be_timed_as_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'one.py').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                probe.source_map_admission(root, {'one.py': hashlib.sha256(b'original').hexdigest()})

    def test_invalid_relative_paths_and_sha_formats_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, digest in [('../other.py', 'a' * 64), ('/other.py', 'a' * 64),
                                 ('path\\file.py', 'a' * 64), ('one.py', 'A' * 64), ('one.py', 'short')]:
                with self.subTest(name=name, digest=digest), self.assertRaises(ValueError):
                    probe.source_map_admission(Path(directory), {name: digest})

    def test_source_link_refused_even_for_matching_target_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'one.py').write_bytes(b'one')
            original = Path.is_symlink
            with patch.object(Path, 'is_symlink', lambda path: path.name == 'one.py' or original(path)):
                with self.assertRaises(ValueError):
                    probe.source_map_admission(root, {'one.py': hashlib.sha256(b'one').hexdigest()})

    def test_measure_uses_monotonic_duration_and_exactly_one_operation(self):
        ticks = iter([100, 135]); calls = []
        row, value = probe.measure('FIXED_TEST_ONLY', lambda: calls.append(1) or 'done', clock=lambda: next(ticks))
        self.assertEqual(calls, [1]); self.assertEqual(value, 'done')
        self.assertEqual(row['elapsed_ns'], 35); self.assertTrue(row['completed'])

    def test_operation_failure_is_propagated_and_has_no_success_measurement(self):
        def fail():
            raise OSError('write failure')
        with self.assertRaisesRegex(OSError, 'write failure'):
            probe.measure('FIXED_FAILURE', fail)

    def test_backwards_or_noninteger_clock_refuses_success(self):
        for ticks in ([20, 19], [1.0, 2.0]):
            iterator = iter(ticks)
            with self.subTest(ticks=ticks), self.assertRaises(ValueError):
                probe.measure('BAD_CLOCK', lambda: None, clock=lambda: next(iterator))

    def test_only_three_finite_complete_measurements_form_summary(self):
        samples = [{'completed': True, 'elapsed_seconds': value} for value in (1., 2., 3.)]
        self.assertEqual(probe.summarized(samples)['median_seconds'], 2.)
        for invalid in (samples[:2], samples + samples[:1],
                        [{'completed': True, 'elapsed_seconds': float('nan')}] * 3,
                        [{'completed': False, 'elapsed_seconds': 0.}] * 3):
            with self.assertRaises(ValueError):
                probe.summarized(invalid)

    def test_synthetic_resource_identity_has_actual_valid_hashes_without_old_scientific_identity(self):
        from runtime.user_molecule.acceptance_resources import identity_digest
        versions = {'numpy': 'fixture-only-version', 'scipy': 'fixture-only-version'}
        identity = probe.synthetic_probe_identity(versions, 'a' * 64)
        self.assertEqual(len(identity_digest(identity)), 64)
        for key in ('geometry_sha256', 'profile_sha256', 'dependencies_sha256'):
            self.assertRegex(identity[key], r'^[0-9a-f]{64}$')
        self.assertIn('SYNTHETIC14X14', identity['geometry_identity_scope'])
        self.assertFalse(identity['scientific_execution_authorized'])
        changed = probe.synthetic_probe_identity({'numpy': 'changed-version', 'scipy': 'fixture-only-version'}, 'a' * 64)
        self.assertNotEqual(identity['dependencies_sha256'], changed['dependencies_sha256'])
        self.assertEqual(identity['geometry_sha256'], changed['geometry_sha256'])
        for invalid in ({}, {'numpy': False}, {'numpy': ''}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                probe.synthetic_probe_identity(invalid, 'a' * 64)

    def test_fresh_output_never_overwrites_existing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base / 'source'; source.mkdir()
            inputs = base / 'inputs'; inputs.mkdir(); contract = inputs / 'contract.json'; contract.write_text('{}')
            output = base / 'evidence'; output.mkdir(); prior = output / 'prior.json'; prior.write_bytes(b'preserve')
            with self.assertRaises(ValueError):
                probe.fresh_output(output, source, contract)
            self.assertEqual(prior.read_bytes(), b'preserve')

    def test_output_inside_source_or_input_records_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base / 'source'; source.mkdir()
            inputs = base / 'inputs'; inputs.mkdir(); contract = inputs / 'contract.json'; contract.write_text('{}')
            for target in (source / 'new', inputs / 'new'):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    probe.fresh_output(target, source, contract)
                self.assertFalse(target.exists())

    def test_existing_empty_external_mount_is_valid_but_remains_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base / 'source'; source.mkdir()
            inputs = base / 'inputs'; inputs.mkdir(); contract = inputs / 'contract.json'; contract.write_text('{}')
            output = base / 'output'; output.mkdir()
            self.assertEqual(probe.fresh_output(output, source, contract), output.resolve())
            self.assertEqual(list(output.iterdir()), [])

    def test_filesystem_reports_actual_longest_mount_and_rw_flags(self):
        mountinfo = ('1 0 0:1 / / ro - overlay overlay ro\n'
                     '2 1 0:2 / /output rw,noatime - 9p shared rw\n'
                     '3 1 0:3 / /tmp rw,nosuid - tmpfs tmpfs rw\n')
        self.assertEqual(probe.filesystem('/output/new', mountinfo)['filesystem'], '9p')
        self.assertFalse(probe.filesystem('/output/new', mountinfo)['read_only'])
        self.assertTrue(probe.filesystem('/workspace', mountinfo)['read_only'])
        self.assertEqual(probe.filesystem('/tmp/new', mountinfo)['filesystem'], 'tmpfs')

    def test_unknown_or_ambiguous_filesystem_refuses(self):
        with self.assertRaises(ValueError):
            probe.filesystem('/output', '')
        text = '1 0 0:1 / /output ro - 9p shared ro\n2 0 0:1 / /output rw - 9p shared rw\n'
        with self.assertRaises(ValueError):
            probe.filesystem('/output/new', text)

    def fake_bindings(self):
        owner = SimpleNamespace()
        rows = []
        for index, label in enumerate(sorted(probe.GUARD_NAMES)):
            name = 'guard_' + str(index); callback = object(); setattr(owner, name, callback)
            rows.append((owner, name, callback, label))
        return rows

    def test_exact_14_guards_and_energy_nuclear_are_mandatory(self):
        bindings = self.fake_bindings()
        self.assertEqual(probe.held_guards(bindings, [])['actual_native_F_NR_SCF_grid_integral_nuclear_calls'], 0)
        for invalid in (bindings[:-1], bindings + bindings[:1],
                        [row for row in bindings if row[3] != 'Mole.energy_nuc']):
            with self.assertRaises(RuntimeError):
                probe.held_guards(invalid, [])

    def test_changed_guard_or_forbidden_attempt_refuses_success(self):
        bindings = self.fake_bindings()
        with self.assertRaises(RuntimeError):
            probe.held_guards(bindings, ['NumInt.nr_rks'])
        owner, name, _callback, _label = bindings[0]; setattr(owner, name, object())
        with self.assertRaises(RuntimeError):
            probe.held_guards(bindings, [])

    def test_active_contract_main_records_honest_failure_before_engine_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); inputs = base / 'input'; inputs.mkdir()
            contract = inputs / 'active.json'; item = self.inactive(); item['scientific_execution_authorized'] = True
            contract.write_text(json.dumps(item), encoding='utf-8'); output = base / 'probe-output'
            with patch.object(probe, 'load_helper', side_effect=AssertionError('must not reach platform/native setup')):
                self.assertEqual(probe.main(['--source-contract', str(contract), '--output-dir', str(output)]), 2)
            record = json.loads((output / 'probe-summary.json').read_text(encoding='utf-8'))
            self.assertEqual(record['status'], 'FAIL_ZERO_NATIVE_ENGINEERING_PROBE')
            self.assertIsNone(record['actual_native_calls']); self.assertIsNone(record['scientific_budget'])
            self.assertFalse((output / 'SIMULATED_CALLBACKS.json').exists())

    def test_fixed_synthetic_factory_three_durable_slots_never_claims_source_nr(self):
        # Run in the pinned guarded engineering suite; no molecule/program callbacks.
        import numpy as np
        from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
        from runtime.user_molecule.root_native_accounting import RootNativeAccounting
        from reference.occupied_space_root_native_candidate import SyntheticRootEvaluator, FrozenRecord, density_id
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); density = np.diag([2.] * 8 + [0.] * 6); identity_id = density_id(density)
            versions = {name: importlib.metadata.version(name) for name in ('numpy', 'scipy')}
            identity = probe.synthetic_probe_identity(versions, identity_id)
            journal = ConditionalCallbackBudget(path=output / 'simulation.json', batch_id='overhead-unit-simulation',
                identity=identity, path_limits={'independent_reference': 201}, total_limit=201)
            book = RootNativeAccounting(output / 'accounting', journal)
            evaluator = SyntheticRootEvaluator('diagonal', expected_initial_density_id=identity_id, accounting=book)
            for index in range(1, 4):
                phase = 'CURRENT_INITIAL' if index == 1 else 'OPTIMIZER_BASE'
                evaluator.bind_candidate_callback(FrozenRecord({'evaluation_count': index, 'density_id': identity_id,
                    'phase': phase, 'admission_group_id': None, 'chart': None, 'fd_sample': None,
                    'base_snapshot_id': None, 'base_density_id': None, 'base_operator_id': None}))
                evaluator(density.copy(), phase)
            result = book.close('ENGINEERING_ONLY_THREE_SLOT_PROBE_TEST')
            self.assertEqual(result['callback_slots'], {'charged': 3, 'pending': 0, 'succeeded': 3, 'failed': 0, 'limit': 201})
            self.assertEqual(result['engineering_simulated_native_counts'], {'entered': 3, 'completed': 3, 'failed': 0})
            self.assertIsNone(result['source_native_dispatch_counts']['entered'])
            self.assertFalse(result['scientific_execution_authorized'])


if __name__ == '__main__':
    unittest.main()
