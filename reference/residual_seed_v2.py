"""Independent V2 seed adapter over the unchanged independent evaluator.

The old prepared ordinary density remains a parent.  Only the low-level
solver's initial density argument is replaced by an admitted, frozen seed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np

from reference import residual_candidate as solver
from reference.residual_molecule import PreparedResidualReference, array_identity
from reference.seed_v2 import POLICY_ID, prepare_seed_v2


LOWER_POLICY = 'REQUIRE_EXISTING_MASKED_PROJECTOR'
MO_KEYS = ('mo_coefficients', 'mo_occupations')


def _receipt_identity(receipt):
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


class PreparedResidualSeedReferenceV2(PreparedResidualReference):
    def __init__(self, *, ordinary, rule_path, expected_sha256,
                 initialization_policy=POLICY_ID, maximum_evaluations=201,
                 execution_kind='ENGINEERING_FAKE', shared_seed_density=None):
        if initialization_policy != POLICY_ID:
            raise ValueError('Explicit supported V2 seed policy required')
        super().__init__(ordinary=ordinary, rule_path=rule_path,
                         expected_sha256=expected_sha256, initialization_policy=LOWER_POLICY,
                         maximum_evaluations=maximum_evaluations, execution_kind=execution_kind)
        self.policy = POLICY_ID
        self._mo_inputs = {}
        for key in MO_KEYS:
            if key not in ordinary.arrays or key not in self.identities:
                raise ValueError('Verified ordinary MO array and identity required: ' + key)
            value = solver.real_array(ordinary.arrays[key], key).copy()
            if array_identity(value) != self.identities[key]:
                raise solver.ReferenceRefusal('FROZEN_CACHED_MO_MISMATCH', key)
            value.setflags(write=False)
            self._mo_inputs[key] = value
        independent = prepare_seed_v2(density=self.arrays['density'],
            physical_overlap=self.arrays['overlap'], masked_overlap=self.overlap,
            mo_coefficients=self._mo_inputs['mo_coefficients'],
            mo_occupations=self._mo_inputs['mo_occupations'], electrons=self.electrons)
        self.reference_seed_density = independent['density'].copy()
        self.seed_coefficients = independent['coefficients'].copy()
        self.seed_receipt = copy.deepcopy(independent['receipt'])
        self.seed_receipt.update(ordinary_density_identity=copy.deepcopy(self.identities['density']),
            ordinary_density_id=solver.density_id(self.arrays['density']),
            reference_seed_density_identity=array_identity(self.reference_seed_density),
            ordinary_mo_identities={key: copy.deepcopy(self.identities[key]) for key in MO_KEYS})
        self._shared_source = shared_seed_density
        self._shared_source_identity = None
        if shared_seed_density is None:
            self.seed_density = self.reference_seed_density.copy()
            self.seed_receipt['seed_used_source'] = 'INDEPENDENTLY_CONSTRUCTED_SEED'
            self.seed_receipt['shared_seed_admission'] = {'status': 'NOT_REQUESTED'}
        else:
            candidate = solver.real_array(shared_seed_density, 'Shared V2 seed').copy()
            self.seed_receipt['shared_seed_admission'] = {'status': 'REFUSED', 'checks': {},
                'provided_density_identity': array_identity(candidate),
                'independently_constructed_density_identity': array_identity(self.reference_seed_density),
                'production_density_reconstruction': 'NOT_IMPLEMENTED_IN_EXISTING_REFERENCE_ENTRY',
                'functional_calls': 0}
            if candidate.shape != self.overlap.shape:
                self._shared_refuse('SHARED_SEED_SHAPE_INVALID')
            self._shared_check('symmetry', float(np.max(np.abs(candidate-candidate.T))), 1e-12,
                               formula='max(abs(Dshared-Dshared.T))')
            denominator = max(float(np.linalg.norm(self.reference_seed_density, 'fro')), 1.)
            self._shared_check('independent_seed_agreement',
                float(np.linalg.norm(candidate-self.reference_seed_density, 'fro'))/denominator,
                1e-10, formula='norm(Dshared-Dreference,F)/max(norm(Dreference,F),1)',
                denominator=denominator)
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                values, vectors = np.linalg.eigh(self.overlap)
                half = (vectors*np.sqrt(values))@vectors.T
                projection = .5*half@candidate@half
                if not np.isfinite(projection).all():
                    self._shared_refuse('SHARED_SEED_WHITENING_NONFINITE')
                self._shared_check('white_projector_trace', abs(float(np.trace(projection))-self.electrons//2),
                    1e-10, formula='abs(trace(0.5*S_tilde_half@Dshared@S_tilde_half)-nocc)')
                self._shared_check('white_projector_idempotency',
                    float(np.linalg.norm(projection@projection-projection, 'fro')), 1e-10,
                    formula='norm(Pshared@Pshared-Pshared,F)')
            self.seed_density = candidate
            self._shared_source_identity = array_identity(candidate)
            self.seed_receipt['seed_used_source'] = 'SHARED_EXACT_DENSITY_AFTER_INDEPENDENT_SEED_COMPARISON'
            self.seed_receipt['shared_seed_admission']['status'] = 'PASS_ARRAY_REFERENCE_ENTRY_ONLY'
        self.seed_receipt.update(used_seed_density_identity=array_identity(self.seed_density),
                                used_seed_density_id=solver.density_id(self.seed_density),
                                lower_solver_policy=LOWER_POLICY,
                                actual_reference_entry_execution='NOT_EXECUTED_BEFORE_RUN')
        self._seed_frozen = {'density': array_identity(self.seed_density),
                            'reference_density': array_identity(self.reference_seed_density),
                            'coefficients': array_identity(self.seed_coefficients),
                            'receipt': _receipt_identity(self.seed_receipt)}
        for array in (self.seed_density, self.reference_seed_density, self.seed_coefficients):
            array.setflags(write=False)
        self._assert_frozen()

    def _shared_refuse(self, reason):
        self.seed_receipt['shared_seed_admission']['reason'] = reason
        error = solver.ReferenceRefusal(reason, 'Shared seed failed independent reference entrance')
        error.receipt = copy.deepcopy(self.seed_receipt)
        raise error

    def _shared_check(self, name, value, threshold, *, formula, denominator='NONE'):
        finite = math.isfinite(value)
        passed = finite and value <= threshold
        self.seed_receipt['shared_seed_admission']['checks'][name] = {
            'value': value if finite else None, 'threshold': threshold, 'comparison': '<=',
            'formula': formula, 'denominator': denominator, 'passed': bool(passed)}
        if not passed:
            self._shared_refuse('SHARED_SEED_'+name.upper()+'_FAILED')

    def _assert_frozen(self):
        super()._assert_frozen()
        # The parent invokes this method while its own constructor is running.
        if not hasattr(self, '_seed_frozen'):
            return
        if self.policy != POLICY_ID:
            raise solver.ReferenceRefusal('FROZEN_SEED_POLICY_CHANGED', 'V2 policy changed')
        for key in MO_KEYS:
            if (array_identity(self.ordinary.arrays[key]) != self.identities[key] or
                    array_identity(self._mo_inputs[key]) != self.identities[key]):
                raise solver.ReferenceRefusal('FROZEN_CACHED_MO_CHANGED', key)
        if self._shared_source is not None and array_identity(self._shared_source) != self._shared_source_identity:
            raise solver.ReferenceRefusal('FROZEN_SHARED_SEED_CHANGED', 'Caller shared seed changed')
        current = {'density': array_identity(self.seed_density),
                   'reference_density': array_identity(self.reference_seed_density),
                   'coefficients': array_identity(self.seed_coefficients),
                   'receipt': _receipt_identity(self.seed_receipt)}
        if current != self._seed_frozen:
            raise solver.ReferenceRefusal('FROZEN_V2_SEED_CHANGED', 'Owned seed or seed receipt changed')

    def run(self, **settings):
        if self._used:
            raise solver.ReferenceRefusal('REFERENCE_ALREADY_USED', 'No reference retry/budget reset')
        self._used = True
        offset = len(self.ledger)
        try:
            self._assert_frozen()
            remaining = self.limit-offset
            if remaining < 1:
                raise solver.ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED', 'No prepared budget remains')
            result = solver.solve(density=self.seed_density, overlap=self.overlap,
                electrons=self.electrons, evaluate=self.evaluate, initialization_policy=LOWER_POLICY,
                maximum_evaluations=remaining, matrix_delete_mask=self.mask, **settings)
            phase_mapping_complete = len(result['evaluation_ledger']) == len(self.ledger)-offset
            for own, row in zip(self.ledger[offset:], result['evaluation_ledger']):
                if own['density_id'] == row['density_id']:
                    own['phase'] = row['phase']
                    if 'local_rotation_coordinates' in row:
                        own['local_rotation_coordinates'] = row['local_rotation_coordinates']
                else:
                    phase_mapping_complete = False
        finally:
            self._settled = True
        initialized = result['initialization']
        reported_seed = copy.deepcopy(self.seed_receipt)
        entry_status = initialized.get('status')
        reported_seed['actual_reference_entry_execution'] = (
            'EXECUTED_UNCHANGED_LOW_LEVEL_FRAME_CHECKS'
            if entry_status == 'PREPARED_ENGINEERING_INITIALIZATION' else
            'REFUSED_LOW_LEVEL_FRAME_CHECKS' if entry_status == 'REFUSED' else
            'NOT_EXECUTED_LOW_LEVEL_FRAME_CHECKS')
        initialized['lower_solver_density_argument_id'] = initialized.pop('ordinary_density_id')
        initialized.update(policy=POLICY_ID, lower_solver_policy=LOWER_POLICY,
            ordinary_density_id=solver.density_id(self.arrays['density']),
            seed_density_id=solver.density_id(self.seed_density),
            seed_receipt=copy.deepcopy(reported_seed))
        result.update(reference_adapter_id='PREPARED_INDEPENDENT_SEED_V2',
            initialization_policy=POLICY_ID, lower_solver_policy=LOWER_POLICY,
            prepared_evaluation_ledger=copy.deepcopy(self.ledger), global_evaluation_count=len(self.ledger),
            global_evaluation_limit=self.limit, execution_kind=self.execution_kind,
            nuclear_source='FROZEN_ORDINARY_RECORD_COMPONENT_NOT_EXTRA_ENERGY_NUC_CALL',
            rules_sha256=self.rule_sha, ordinary_density_identity=copy.deepcopy(self.identities['density']),
            seed_receipt=copy.deepcopy(reported_seed), used_seed_density_identity=array_identity(self.seed_density),
            independently_constructed_seed_identity=array_identity(self.reference_seed_density),
            metadata=copy.deepcopy(self.metadata), last_evaluation=self.last_evaluation,
            last_snapshot=copy.deepcopy(self.last_snapshot), prepared_budget_settled=self._settled,
            phase_mapping_status='COMPLETE' if phase_mapping_complete else
                'PARTIAL_REFUSED_CALLBACK_WITHOUT_TRUE_FUNCTIONAL_ATTEMPT',
            real_functional_attempt_count=0 if self.execution_kind == 'ENGINEERING_FAKE' else len(self.ledger),
            engine_cache_scope=dict(self.engine_cache_scope),
            identity_evidence_kind='FROZEN_ORDINARY_AND_SEED_ARRAY_IDENTITIES_NOT_EXTERNAL_AUTHENTICATION',
            shared_dependencies=['RAW_INTEGRALS', 'ORIGINAL_GRID_XC', 'NUMPY', 'SCIPY'],
            method_review_status='EXTERNAL_REVIEW_CANCELLED_BY_USER_INTERNAL_METHOD_VALIDATION_PENDING',
            molecular_execution='NOT_EXECUTED_ENGINEERING_FAKE' if self.execution_kind == 'ENGINEERING_FAKE' else
                ('EXECUTED_DIAGNOSTIC_UNQUALIFIED' if self.ledger else 'NOT_EXECUTED'))
        return result
