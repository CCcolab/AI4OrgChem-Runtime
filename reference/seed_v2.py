"""Independent occupied-space seed, using only supplied ordinary arrays.

This module constructs no molecule or operator.  It solves the occupied Gram
system directly and uses a Cholesky factor for a separate coefficient path.
Shared NumPy arithmetic is explicitly not an independent numerical library.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np


POLICY_ID = 'MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2'
RELATIVE_TOLERANCE = 1e-10
SYMMETRY_TOLERANCE = 1e-12
CONDITION_LIMIT = 1e6


class SeedV2Error(ValueError):
    """Refusal with the strict-JSON diagnostics measured before refusal."""
    def __init__(self, reason, receipt):
        self.reason, self.receipt = reason, receipt
        super().__init__(reason)


def _identity(array):
    encoded = np.ascontiguousarray(array, dtype='<f8')
    return {'shape': list(encoded.shape), 'dtype': '<f8', 'order': 'C',
            'sha256': hashlib.sha256(encoded.tobytes(order='C')).hexdigest()}


def prepare_seed_v2(*, density, physical_overlap, masked_overlap,
                    mo_coefficients, mo_occupations, electrons):
    """Return a separately constructed seed or fail before any F evaluation.

    The receipt separates definition checks from existing reference entrance
    checks.  File/cache identities and ordinary scientific qualification are
    the caller's responsibility; this API checks the supplied arrays only.
    """
    receipt = {'schema_version': 'independent-seed-v2-receipt-v1',
               'policy_id': POLICY_ID, 'implementation': 'INDEPENDENT_GRAM_SOLVE_CHOLESKY_V1',
               'status': 'REFUSED', 'reason': None, 'scientific_approval': False,
               'functional_calls': 0, 'final_endpoint_qualification': 'NOT_EXECUTED',
               'input_array_identities': {}, 'output_array_identities': {},
               'definition_checks': {}, 'solver_entry_checks': {},
               'production_density_reconstruction': 'NOT_IMPLEMENTED_IN_EXISTING_REFERENCE_ENTRY',
               'shared_dependencies': ['NumPy'], 'input_arrays_mutated': False}

    def refuse(reason):
        receipt['reason'] = reason
        raise SeedV2Error(reason, receipt)

    def check(group, name, actual, threshold, *, formula, denominator='NONE',
              positive=False):
        number = float(actual)
        finite = math.isfinite(number)
        passed = finite and (number > threshold if positive else number <= threshold)
        receipt[group][name] = {'value': number if finite else None,
                              'threshold': threshold,
                              'comparison': '>' if positive else '<=',
                              'formula': formula, 'denominator': denominator,
                              'passed': bool(passed)}
        if not passed:
            refuse(name.upper() + '_FAILED')

    def array(value, name):
        try:
            original = np.asarray(value)
            if original.dtype.kind not in 'iuf' or not original.size or not np.isfinite(original).all():
                refuse(name.upper() + '_NOT_FINITE_REAL_ARRAY')
            result = np.array(original, dtype=np.float64, copy=True, order='C')
            if not np.isfinite(result).all():
                refuse(name.upper() + '_FLOAT64_OVERFLOW')
        except (ValueError, TypeError, OverflowError) as error:
            if isinstance(error, SeedV2Error):
                raise
            refuse(name.upper() + '_NOT_REAL_ARRAY')
        receipt['input_array_identities'][name] = _identity(result)
        return result

    def symmetric(value, name):
        check('solver_entry_checks', name + '_symmetry',
              np.max(np.abs(value - value.T)), SYMMETRY_TOLERANCE,
              formula='max(abs(A-A.T))')

    def spd(value, name):
        spectrum = np.linalg.eigvalsh(value)
        check('definition_checks', name + '_minimum_eigenvalue', spectrum[0], 0.,
              formula='min(eigvalsh(A))', positive=True)
        check('definition_checks', name + '_condition_number', spectrum[-1] / spectrum[0],
              CONDITION_LIMIT, formula='max(eigvalsh(A))/min(eigvalsh(A))')

    def relative(name, actual, expected):
        divisor = max(float(np.linalg.norm(expected, 'fro')), 1.)
        check('definition_checks', name,
              np.linalg.norm(actual - expected, 'fro') / divisor, RELATIVE_TOLERANCE,
              formula='norm(actual-expected,F)/max(norm(expected,F),1)',
              denominator=divisor)

    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            d0 = array(density, 'density')
            s = array(physical_overlap, 'physical_overlap')
            metric = array(masked_overlap, 'masked_overlap')
            coefficients = array(mo_coefficients, 'mo_coefficients')
            occupations = array(mo_occupations, 'mo_occupations')
            if d0.ndim != 2 or d0.shape[0] != d0.shape[1]:
                refuse('DENSITY_SHAPE_INVALID')
            nao = d0.shape[0]
            if any(item.shape != (nao, nao) for item in (s, metric, coefficients)) or occupations.shape != (nao,):
                refuse('ORDINARY_ARRAY_SHAPES_MISMATCH')
            if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2 * nao:
                refuse('CLOSED_SHELL_OCCUPATION_UNSUPPORTED')
            occupied = electrons // 2
            variables = occupied * (nao - occupied)
            receipt.update(n_ao=nao, electrons=electrons, occupied_orbitals=occupied,
                           orbital_rotation_variables=variables)
            if variables > 64:
                refuse('ORBITAL_ROTATION_VARIABLES_EXCEED_64')
            if not np.all((occupations == 0.) | (occupations == 2.)) or np.count_nonzero(occupations == 2.) != occupied:
                refuse('ORDINARY_OCCUPATIONS_NOT_GLOBAL_2_0')
            for name, item in (('density', d0), ('physical_overlap', s), ('masked_overlap', metric)):
                symmetric(item, name)
            spd(s, 'physical_overlap')
            spd(metric, 'masked_overlap')
            c0 = coefficients[:, occupations == 2.].copy()
            unit = np.eye(occupied)
            relative('physical_occupied_orthogonality', c0.T @ s @ c0, unit)
            relative('ordinary_density_reconstruction', 2. * c0 @ c0.T, d0)
            gram = c0.T @ metric @ c0
            symmetric(gram, 'occupied_gram')
            spd(gram, 'occupied_gram')
            factor = np.linalg.cholesky(gram)
            cseed = np.linalg.solve(factor, c0.T).T
            seed = 2. * c0 @ np.linalg.solve(gram, c0.T)
            if not np.isfinite(seed).all() or not np.isfinite(cseed).all():
                refuse('SEED_NONFINITE')
            receipt['output_array_identities'] = {'density': _identity(seed),
                                                  'coefficients': _identity(cseed),
                                                  'occupied_gram': _identity(gram)}
            symmetric(seed, 'seed_density')
            relative('seed_coefficients_density_agreement', 2. * cseed @ cseed.T, seed)
            relative('seed_metric_orthogonality', cseed.T @ metric @ cseed, unit)
            relative('seed_closed_shell_idempotency', seed @ metric @ seed, 2. * seed)
            q0 = np.linalg.qr(c0, mode='reduced')[0]
            qseed = np.linalg.qr(cseed, mode='reduced')[0]
            relative('occupied_column_space', qseed @ qseed.T, q0 @ q0.T)
            count = float(np.trace(metric @ seed))
            receipt['masked_metric_electron_count'] = count
            receipt['original_metric_seed_electron_count'] = float(np.trace(s @ seed))
            check('definition_checks', 'seed_electron_count', abs(count - electrons), 1e-7,
                  formula='abs(trace(masked_overlap@Dseed)-electrons)')
            eigenvalues, eigenvectors = np.linalg.eigh(metric)
            half = (eigenvectors * np.sqrt(eigenvalues)) @ eigenvectors.T
            projection = .5 * half @ seed @ half
            if not np.isfinite(projection).all():
                refuse('WHITENED_PROJECTOR_NONFINITE')
            check('solver_entry_checks', 'white_projector_trace', abs(float(np.trace(projection)) - occupied),
                  1e-10, formula='abs(trace(0.5*S_tilde_half@Dseed@S_tilde_half)-nocc)')
            check('solver_entry_checks', 'white_projector_idempotency',
                  np.linalg.norm(projection @ projection - projection, 'fro'), 1e-10,
                  formula='norm(Pseed@Pseed-Pseed,F)')
    except SeedV2Error:
        raise
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, TypeError, OverflowError) as error:
        receipt['arithmetic_error_type'] = type(error).__name__
        refuse('INDEPENDENT_SEED_ARITHMETIC_FAILED')
    receipt.update(status='PASS_ARRAY_SEED_AND_REFERENCE_ENTRY_ONLY', reason=None,
                   actual_reference_entry_execution='NOT_EXECUTED_CHECKS_REPRODUCED_INDEPENDENTLY')
    return {'density': seed, 'coefficients': cseed, 'receipt': receipt}
