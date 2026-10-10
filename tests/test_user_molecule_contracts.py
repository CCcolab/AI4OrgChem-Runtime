"""Portable integrity/safety checks for the W05 preparation contract, no QM imports."""
import hashlib
import json
from pathlib import Path
import unittest

from runtime.user_molecule.input import read_request
from runtime.historical_materials import (
    HistoricalMaterialError, MATERIALS, load_historical_source_materials,
)

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'validation/user-molecule/w05'


def load(path):
    def reject(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class W05PreparationContractTests(unittest.TestCase):
    def test_geometry_and_request_bytes_match_review_receipts(self):
        schema = load(ROOT / 'schemas/user-molecule-request-v1.json')
        for fixture in load(RECORDS / 'candidate-fixtures.json')['fixtures']:
            with self.subTest(fixture=fixture['id']):
                self.assertEqual(digest(ROOT / fixture['xyz_path']), fixture['xyz_sha256'])
                self.assertIsNone(fixture['expected_energies'])
                for request in fixture['requests']:
                    path = ROOT / request['path']
                    self.assertEqual(digest(path), request['sha256'])
                    bundle = read_request(path, schema)
                    self.assertEqual(bundle['xyz_sha256'], fixture['xyz_sha256'])
                    self.assertEqual(bundle['normalized_sha256'], request['normalized_request_sha256'])
                    self.assertEqual(len(bundle['atoms']), fixture['atom_count'])

    def test_groups_cover_carbon_exactly_and_electron_count_is_consistent(self):
        schema = load(ROOT / 'schemas/user-molecule-request-v1.json')
        for fixture in load(RECORDS / 'candidate-fixtures.json')['fixtures']:
            bundle = read_request(ROOT / fixture['requests'][0]['path'], schema)
            atoms = bundle['atoms']
            groups = fixture['fragments_1based']
            self.assertFalse(set(groups['A']) & set(groups['B']))
            self.assertEqual(set(groups['A'] + groups['B']),
                             {i + 1 for i, atom in enumerate(atoms) if atom[0] == 'C'})
            self.assertEqual(sum({'C': 6, 'H': 1}[atom[0]] for atom in atoms), fixture['electron_count'])

    def test_raw_snapshots_and_actual_image_profile_identity_remain_distinct(self):
        for entry in load(RECORDS / 'profile-register.json')['profiles']:
            snapshot = ROOT / entry['snapshot_path']
            self.assertEqual(digest(snapshot), entry['host_snapshot_sha256'])
            lf = snapshot.read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(lf).hexdigest(), entry['image_profile_sha256'])
            self.assertEqual(load(ROOT / entry['path']), load(snapshot))
            self.assertFalse(load(snapshot)['compute_enabled'])

    def test_missing_acceptance_decisions_do_not_become_compute_permission(self):
        decisions = load(RECORDS / 'pending-decisions.json')
        self.assertIsNone(decisions['approver'])
        self.assertIsNone(decisions['approved_at'])
        self.assertFalse(decisions['scientific_scf_budget_authorized'])
        state = load(ROOT / 'validation/user-molecule/implementation-state.public.json')
        self.assertFalse(state['compute_enabled'])
        self.assertFalse(state['work_packages']['W05']['ready_to_execute_scf'])
        # Preparation files remain historical; actual failed runs must not be
        # relabelled NOT_EXECUTED merely to satisfy a preparation-era test.
        self.assertIn(state['work_packages']['W05']['numerical_acceptance'],
                      ('NOT_EXECUTED', 'EXECUTED_FAILED_FROZEN_GATES'))
        self.assertFalse(state['work_packages']['W06']['production_activation'])
        w07 = state['work_packages']['W07']
        self.assertTrue(w07['validation'].startswith('PASS_SCOPED_'))
        self.assertIn('BLOCKED_FOR_RESEARCH', w07['validation'])
        self.assertEqual(w07['real_user_feedback'],
                         'DEFERRED_BY_USER_NOT_CURRENT_ENGINEERING_BLOCKER')
        self.assertTrue(state['scientific_pending'])
        for criterion in load(RECORDS / 'criteria-register.json')['criteria']:
            self.assertEqual(criterion['scientific_acceptance'], 'NOT_EXECUTED')
            if criterion['value'] is None:
                self.assertEqual(criterion['status'], 'TBD_REQUIRES_REVIEW')

    def test_no_process_peak_or_compute_size_is_inferred_from_eri_lower_bounds(self):
        budget = load(RECORDS / 'resource-budget-proposal.json')
        self.assertIsNone(budget['resource_model'])
        self.assertIsNone(budget['approved_maximum_compute_nao'])
        for row in budget['scale_observations']:
            n = row['nao']
            self.assertEqual(row['single_float64_eri_lower_bound_bytes'], 8 * n ** 4)
            self.assertEqual(row['reference_two_float64_plus_one_bool_tensor_floor_bytes'], 17 * n ** 4)
            self.assertIsNone(row['process_peak_bytes'])
            self.assertEqual(row['peak_calibration'], 'NOT_EXECUTED')

    def test_proposed_batch_fits_registered_cumulative_ceiling(self):
        budget = load(RECORDS / 'resource-budget-proposal.json')
        caps, batch = budget['future_candidate_ceilings'], budget['first_science_batch_proposal']
        count = sum(batch[key] for key in (
            'ordinary_independent_driver_processes_max', 'two_state_single_tensor_processes_max',
            'two_state_reference_copy_processes_max'))
        maximum = count * caps['per_scientific_process_wall_seconds_max']
        maximum += batch['fixed_density_reference_processes_max'] * batch['fixed_density_reference_per_process_wall_seconds_max']
        self.assertEqual(maximum, batch['worst_case_reserved_child_wall_seconds'])
        self.assertEqual(maximum + batch['remaining_within_7200_seconds'],
                         caps['per_science_batch_sum_child_wall_seconds_max'])
        self.assertEqual(budget['status'], 'PROPOSED_FOR_REVIEW_NOT_SCF_AUTHORIZATION')

    def test_frozen_source_materials_and_rule_identity_match(self):
        # Old design documents are retained only in an explicit local archive.
        # Their original SHA bindings remain in the source index; current
        # descriptions must never be passed off as those old reviewed bytes.
        with self.assertRaisesRegex(HistoricalMaterialError,
                                    '^HISTORICAL_MATERIALS_LOCAL_ARCHIVE_ONLY$'):
            load_historical_source_materials()
        archived = {item['original_path']: item for item in MATERIALS}
        archived_seen = set()
        for source in load(RECORDS / 'source-index.json')['local_sources']:
            if source['owner'] == 'runtime':
                if source['path'] in archived:
                    expected = archived[source['path']]
                    self.assertEqual(source, {'owner': expected['owner'],
                        'path': expected['original_path'], 'commit': expected['source_commit'],
                        'sha256': expected['sha256']})
                    archived_seen.add(source['path'])
                    continue  # Binding only; no original-document byte acceptance here.
                # The index records the reviewed Windows working bytes. A Linux
                # checkout may use LF. Verify this particular historical hash
                # by an exact EOL transformation; any other change still fails.
                raw = (ROOT / source['path']).read_bytes()
                lf = raw.replace(b'\r\n', b'\n')
                with self.subTest(source=source['path']):
                    self.assertIn(source['sha256'],
                        {hashlib.sha256(data).hexdigest() for data in (raw, lf, lf.replace(b'\n', b'\r\n'))})
        self.assertEqual(archived_seen, set(archived))
        lock = load(ROOT / 'locks/source.user-molecule.lock.json')
        state = load(RECORDS / 'preparation-status.public.json')
        self.assertEqual(state['science_commit'], lock['source_commit'])
        for check in load(RECORDS / 'inspect-review.json')['candidate_checks']:
            self.assertEqual(check['identities']['condition_rules_sha256'], lock['condition_rules_sha256'])
            self.assertEqual(check['identities']['science_commit'], lock['source_commit'])
            self.assertFalse(check['compute_eligible'])


if __name__ == '__main__':
    unittest.main()
