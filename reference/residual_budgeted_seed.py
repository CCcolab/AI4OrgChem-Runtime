"""Explicit engineering-only prepared-seed adapter for budget recording.

The scientific V2 adapter and live worker retain their original solver. This
class permits test-double execution only; it never registers production Compute
or grants a fresh scientific budget. Native NR counts require instrumented
engine evidence and are not inferred from the prepared callback ledger.
"""
from __future__ import annotations

import copy

from reference import residual_budgeted_candidate as candidate
from reference import residual_candidate as retained
from reference.residual_seed_v2 import PreparedResidualSeedReferenceV2, LOWER_POLICY, POLICY_ID
from reference.residual_molecule import array_identity


ADAPTER_ID = 'PREPARED_BUDGET_RECORDING_SEED_ENGINEERING_V1'


class PreparedBudgetedSeedReference(PreparedResidualSeedReferenceV2):
    def __init__(self, *, execution_kind='ENGINEERING_FAKE', **options):
        if execution_kind != 'ENGINEERING_FAKE':
            raise ValueError('Budget-recording candidate permits explicit test doubles only; no molecular diagnostic authorization')
        super().__init__(execution_kind=execution_kind, **options)

    def _assert_frozen(self):
        super()._assert_frozen()
        if self.execution_kind != 'ENGINEERING_FAKE':
            raise retained.ReferenceRefusal('ENGINEERING_EXECUTION_KIND_CHANGED', 'No molecular execution or changed execution-kind is admitted')

    def run(self, **settings):
        if self._used:
            raise retained.ReferenceRefusal('REFERENCE_ALREADY_USED', 'No retry or budget reset')
        self._used = True
        offset = len(self.ledger)
        try:
            self._assert_frozen()
            remaining = self.limit-offset
            if remaining < 1:
                raise retained.ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED', 'No remaining prepared engineering allowance')
            result = candidate.solve_budgeted_candidate(density=self.seed_density, overlap=self.overlap,
                electrons=self.electrons, evaluate=self.evaluate, initialization_policy=LOWER_POLICY,
                maximum_evaluations=remaining, matrix_delete_mask=self.mask, **settings)
            complete = len(result['evaluation_ledger']) == len(self.ledger)-offset
            mapping_reasons = [] if complete else ['CALLBACK_COUNT_MISMATCH']
            for own, row in zip(self.ledger[offset:], result['evaluation_ledger']):
                if own['density_id'] != row['density_id']:
                    complete = False
                    mapping_reasons.append('CALLBACK_DENSITY_ID_MISMATCH')
                    continue
                if row['status'] == own['status'] == 'VALIDATED' and own['fock_id'] != row['fock_id']:
                    complete = False
                    mapping_reasons.append('CALLBACK_FOCK_ID_MISMATCH')
                    continue
                own['phase'] = row['phase']
                own['solver_evaluation_count'] = row['evaluation_count']
                for key in ('local_rotation_coordinates', 'snapshot_id', 'role', 'jacobian_group', 'chart', 'fd_sample'):
                    if key in row:
                        own[key] = copy.deepcopy(row[key])
        finally:
            self._settled = True
        initialized = result['initialization']
        reported_seed = copy.deepcopy(self.seed_receipt)
        reported_seed['actual_reference_entry_execution'] = (
            'EXECUTED_UNCHANGED_LOW_LEVEL_FRAME_CHECKS'
            if initialized.get('status') == 'PREPARED_ENGINEERING_INITIALIZATION' else
            'REFUSED_LOW_LEVEL_FRAME_CHECKS' if initialized.get('status') == 'REFUSED' else
            'NOT_EXECUTED_LOW_LEVEL_FRAME_CHECKS')
        initialized['lower_solver_density_argument_id'] = initialized.pop('ordinary_density_id')
        initialized.update(policy=POLICY_ID, lower_solver_policy=LOWER_POLICY,
            ordinary_density_id=retained.density_id(self.arrays['density']),
            seed_density_id=retained.density_id(self.seed_density), seed_receipt=copy.deepcopy(reported_seed))
        lower_qualified = result['engine_qualified']
        lower_stop_reason = result['stop_reason']
        if not complete:
            result.update(engine_qualified=False, converged=False,
                stop_reason='ADAPTER_PHASE_ACCOUNTING_MAPPING_REFUSED',
                failure={'reason':'ADAPTER_PHASE_ACCOUNTING_MAPPING_REFUSED',
                    'detail':'Prepared and low-level callback accounting identities did not match',
                    'lower_failure':copy.deepcopy(result.get('failure'))})
        result.update(reference_adapter_id=ADAPTER_ID, initialization_policy=POLICY_ID,
            lower_solver_policy=LOWER_POLICY, seed_receipt=reported_seed,
            ordinary_density_identity=copy.deepcopy(self.identities['density']),
            used_seed_density_identity=array_identity(self.seed_density),
            independently_constructed_seed_identity=array_identity(self.reference_seed_density),
            prepared_evaluation_ledger=copy.deepcopy(self.ledger), global_evaluation_count=len(self.ledger),
            global_evaluation_limit=self.limit, execution_kind='ENGINEERING_FAKE',
            prepared_budget_settled=True,
            phase_mapping_status='COMPLETE' if complete else 'PARTIAL_CALLBACK_ACCOUNTING_MAPPING_REFUSED',
            phase_mapping_reasons=sorted(set(mapping_reasons)),
            lower_engine_qualified=lower_qualified, lower_stop_reason=lower_stop_reason,
            adapter_acceptance='PASS_ENGINEERING_MAPPING_ONLY' if complete else 'REFUSED_PHASE_ACCOUNTING_MAPPING',
            fake_solver_callback_attempts=result['evaluation_count'],
            fake_prepared_callback_attempts=len(self.ledger)-offset,
            native_nr_rks_counts='NOT_MEASURED_BY_ADAPTER; DO_NOT_INFER_FROM_PREPARED_LEDGER',
            molecular_execution='NOT_EXECUTED_ENGINEERING_FAKE',
            real_functional_attempt_count=0, new_scientific_budget=None,
            nuclear_source='FROZEN_ORDINARY_RECORD_NOT_EXTRA_ENERGY_NUC_CALL',
            identity_evidence_kind='LOCAL_CACHED_IDENTITIES_AND_TEST_DOUBLE_DECLARATION_NOT_ENGINE_AUTHENTICATION',
            production_activation=False, research_acceptance='NOT_ACCEPTED', molecular_acceptance='NOT_EXECUTED',
            comparison_available=False, deltas=None, delta_hartree=None, delta_kcal_mol=None)
        return result
