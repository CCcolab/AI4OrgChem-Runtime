"""Deterministic occupied--virtual seed rotations using saved arrays only.

This is a new initialization diagnostic candidate, not a new final occupation
rule.  No F, energy, solver, SCF, integral, grid, seed-V2 operation, callback,
MOM, fractional occupation, fragment quota, random direction, or metric repair
is performed.  D is never projected or replaced by its admission reconstruction.
"""
from __future__ import annotations

import hashlib
import math
from numbers import Real
import re

import numpy as np

from .occupation_response import density_id, _admit_density, _freeze, _matrix


POLICY_ID = 'MASKED_GLOBAL_OCCUPIED_VIRTUAL_ANCHOR_ROTATION_DIAGNOSTIC_V1'
MAXIMUM_ANGLES = 4
MAXIMUM_ABSOLUTE_ANGLE_RAD = .25
MANIFOLD_TOLERANCE = 1e-10
DIRECTION_MINIMUM_PROJECTION_FRACTION = 1e-12


def array_identity(value):
    """Existing bridge array format, implemented without importing SciPy."""
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or not raw.size:
        raise ValueError('Array identity requires a nonempty real nonboolean array')
    array = np.ascontiguousarray(raw, dtype='<f8')
    if not np.isfinite(array).all():
        raise ValueError('Array identity requires finite entries')
    return {'shape': list(array.shape), 'dtype': '<f8', 'order': 'C',
        'sha256': hashlib.sha256(array.tobytes(order='C')).hexdigest()}


def _fingerprint(value):
    array = np.asarray(value)
    return (array.shape, array.dtype.str, hashlib.sha256(array.tobytes(order='C')).hexdigest())


def _anchor(value, name, size):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or raw.shape != (size,):
        raise ValueError(name+' must be a real nonboolean length-n AO vector')
    array = np.asarray(raw, dtype=np.float64).copy()
    if not np.isfinite(array).all():
        raise ValueError(name+' must be finite')
    return array


def _unit(value, name, *, anchor_norm=None):
    norm = float(np.linalg.norm(value))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError(name+' projection must have a finite nonzero norm')
    if anchor_norm is not None and norm/anchor_norm <= DIRECTION_MINIMUM_PROJECTION_FRACTION:
        raise ValueError(name+' projection fraction must exceed the numerical direction admission threshold1e-12')
    unit = value/norm
    if not np.isfinite(unit).all():
        raise ValueError(name+' normalization must be finite')
    return unit, norm


def _angles(value):
    if not isinstance(value, (list, tuple, np.ndarray)):
        raise ValueError('Angles require an explicit ordered list/tuple/one-dimensional array')
    if isinstance(value, np.ndarray) and value.ndim != 1:
        raise ValueError('Angles require a one-dimensional array')
    if not 1 <= len(value) <= MAXIMUM_ANGLES:
        raise ValueError('Require one to four explicit diagnostic angles')
    result = []
    for angle in value:
        if (isinstance(angle, (bool, np.bool_)) or not isinstance(angle, Real)
                or not math.isfinite(angle) or angle == 0 or abs(angle) > MAXIMUM_ABSOLUTE_ANGLE_RAD):
            raise ValueError('Each angle must be finite, nonboolean, nonzero and |theta|<=0.25 rad')
        result.append(float(angle))
    if len(set(result)) != len(result):
        raise ValueError('Duplicate explicit angles are not allowed')
    return tuple(result)


def prepare_occupied_space_seeds(*, density, masked_overlap, occupied_anchor,
                                virtual_anchor, angles, electrons,
                                expected_density_id, expected_overlap_identity=None):
    """Prepare at most four deterministic global masked-2/0 density rotations.

    Anchors are caller-selected AO vectors, not selected by F eigenvalues.
    Project them into the existing whitened occupied and virtual spaces;
    remove only <=1e-10 normalized orthogonality roundoff from the already
    selected virtual direction.  Larger corrections are refused.  Base and
    outputs must independently pass the unchanged strict density admission.
    Expected overlap identity, when supplied, uses the bridge array format.
    No callback parameter is accepted; all new F/E/operator fields are null.
    """
    chosen_angles = _angles(angles)
    d, s = _matrix(density, 'Saved base density'), _matrix(masked_overlap, 'Masked overlap')
    if d.shape != s.shape:
        raise ValueError('Base D and masked overlap must have identical dimensions')
    size = len(d)
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*size:
        raise ValueError('Explicit global integer closed-shell electron count with a virtual orbital required')
    if not isinstance(expected_density_id, str) or re.fullmatch('[0-9a-f]{64}', expected_density_id) is None:
        raise ValueError('An explicit lowercase density-v1 SHA-256 is required')
    base_id, overlap_identity = density_id(d), array_identity(s)
    if base_id != expected_density_id:
        raise ValueError('Saved base density identity differs from the explicit expected identity')
    if expected_overlap_identity is not None and expected_overlap_identity != overlap_identity:
        raise ValueError('Masked overlap identity differs from the explicit expected identity')
    ao_occ = _anchor(occupied_anchor, 'Occupied anchor', size)
    ao_vir = _anchor(virtual_anchor, 'Virtual anchor', size)
    callers = {'density': density, 'masked_overlap': masked_overlap,
        'occupied_anchor': occupied_anchor, 'virtual_anchor': virtual_anchor, 'angles': angles}
    fingerprints = {name: _fingerprint(value) for name, value in callers.items()}
    sw, sv = np.linalg.eigh(s)
    if sw.min() <= 0:
        raise ValueError('Masked overlap must be positive definite; no metric repair allowed')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        half, inverse = (sv*np.sqrt(sw))@sv.T, (sv/np.sqrt(sw))@sv.T
        projector = .5*half @ d @ half
    if not all(np.isfinite(value).all() for value in (half, inverse, projector)):
        raise ValueError('Masked whitening must be finite')
    base_admission = _admit_density(d, s, electrons, half, inverse)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        occ_white_anchor, vir_white_anchor = half@ao_occ, half@ao_vir
        _, occ_anchor_norm = _unit(occ_white_anchor, 'Whitened occupied anchor')
        _, vir_anchor_norm = _unit(vir_white_anchor, 'Whitened virtual anchor')
        u, occ_projection_norm = _unit(projector@occ_white_anchor, 'Occupied anchor', anchor_norm=occ_anchor_norm)
        virtual_projection = (np.eye(size)-projector)@vir_white_anchor
        virtual_before, vir_projection_norm = _unit(virtual_projection, 'Virtual anchor', anchor_norm=vir_anchor_norm)
        cross_before = float(u@virtual_before)
        if not math.isfinite(cross_before) or abs(cross_before) > MANIFOLD_TOLERANCE:
            raise ValueError('Selected directions require more than allowed orthogonality roundoff removal')
        # This changes only the selected virtual direction.  P/D are preserved.
        correction = u*float(u@virtual_projection)
        v, vir_corrected_norm = _unit(virtual_projection-correction, 'Roundoff-cleaned virtual anchor')
        u_norm_error = abs(float(u@u)-1)
        v_norm_error = abs(float(v@v)-1)
        cross_after = abs(float(u@v))
        occupied_membership = float(np.linalg.norm(projector@u-u))
        virtual_membership = float(np.linalg.norm(projector@v))
    direction_measures = (u_norm_error, v_norm_error, cross_after, occupied_membership, virtual_membership)
    if not np.isfinite(direction_measures).all() or max(direction_measures) > MANIFOLD_TOLERANCE:
        raise ValueError('Selected directions fail normalization, orthogonality or occupied/virtual membership')
    seeds = []
    for index, angle in enumerate(chosen_angles, 1):
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            rotated_direction = math.cos(angle)*u+math.sin(angle)*v
            rotated_projector = projector-np.outer(u, u)+np.outer(rotated_direction, rotated_direction)
            rotated_density = 2*inverse @ rotated_projector @ inverse
        # No symmetrization/projection/repair is applied to Ptheta or Dtheta.
        rotated_density = _matrix(rotated_density, 'Rotated diagnostic density', d.shape)
        admission = _admit_density(rotated_density, s, electrons, half, inverse)
        actual_projector = .5*half @ rotated_density @ half
        projector_difference = actual_projector-projector
        density_difference = rotated_density-d
        projector_frobenius = float(np.linalg.norm(projector_difference))
        principal_sine = float(np.linalg.norm(projector_difference, ord=2))
        density_frobenius = float(np.linalg.norm(density_difference))
        if not np.isfinite((projector_frobenius, principal_sine, density_frobenius)).all():
            raise ValueError('Rotated density/column-space comparison must be finite')
        seeds.append({'seed_index': index, 'angle_rad': angle,
            'density': rotated_density, 'density_id': density_id(rotated_density),
            'density_identity': array_identity(rotated_density), 'admission': admission,
            'base_density_difference_frobenius': density_frobenius,
            'base_density_difference_relative': density_frobenius/max(float(np.linalg.norm(d)), 1.0),
            'column_space_change': {'whitened_projector_difference_frobenius': projector_frobenius,
                'largest_projector_difference_singular_value': principal_sine,
                'observed_changed': projector_frobenius > 0,
                'base_occupied_column_space_preserved': projector_frobenius == 0,
                'occupied_direction_weight': float(u@actual_projector@u),
                'occupied_virtual_cross_weight': float(u@actual_projector@v),
                'meaning': 'MEASURED_BASE_OCCUPIED_PROJECTOR_CHANGE_NOT_ORDINARY_MO_SPACE_PRESERVATION'},
            'F_at_new_density': None, 'energy': None, 'operator_id': None,
            'molecular_evaluation': 'NOT_EXECUTED', 'endpoint_acceptance': 'NOT_EXECUTED',
            'engine_qualified': False, 'research_qualified': False})
    if any(_fingerprint(value) != fingerprints[name] for name, value in callers.items()):
        raise ValueError('Caller-owned source D/S/anchor/angle bytes changed during preparation')
    if expected_overlap_identity is not None and expected_overlap_identity != overlap_identity:
        raise ValueError('Caller changed expected overlap identity during preparation')
    return _freeze({'policy_id': POLICY_ID,
        'status': 'PREPARED_PURE_ARRAY_NEW_INITIALIZATION_DIAGNOSTIC_CANDIDATE',
        'source_density': d, 'source_masked_overlap': s,
        'source_occupied_anchor': ao_occ, 'source_virtual_anchor': ao_vir,
        'source': {'density_id': base_id, 'expected_density_id': expected_density_id,
            'density_identity': array_identity(d), 'masked_overlap_identity': overlap_identity,
            'expected_overlap_identity_supplied': expected_overlap_identity is not None,
            'occupied_anchor_identity': array_identity(ao_occ), 'virtual_anchor_identity': array_identity(ao_vir),
            'electrons': electrons, 'occupied_rank': electrons//2},
        'base_admission': base_admission,
        'directions': {'occupied_white_direction': u, 'virtual_white_direction': v,
            'occupied_anchor_masked_metric_norm': occ_anchor_norm,
            'virtual_anchor_masked_metric_norm': vir_anchor_norm,
            'occupied_projection_norm': occ_projection_norm,
            'virtual_projection_norm_before_roundoff_removal': vir_projection_norm,
            'virtual_projection_norm_after_roundoff_removal': vir_corrected_norm,
            'occupied_projection_fraction_of_metric_anchor': occ_projection_norm/occ_anchor_norm,
            'virtual_projection_fraction_of_metric_anchor': vir_projection_norm/vir_anchor_norm,
            'minimum_projection_fraction_exclusive': DIRECTION_MINIMUM_PROJECTION_FRACTION,
            'projection_fraction_role': 'NUMERICAL_DIRECTION_ADMISSION_NOT_SCIENTIFIC_FINAL_GATE',
            'normalized_cross_before_roundoff_removal': cross_before,
            'roundoff_correction_relative_norm': float(np.linalg.norm(correction))/vir_projection_norm,
            'occupied_norm_error': u_norm_error, 'virtual_norm_error': v_norm_error,
            'normalized_cross_after_roundoff_removal': cross_after,
            'occupied_membership_residual': occupied_membership,
            'virtual_membership_residual': virtual_membership,
            'density_or_projector_repaired': False},
        'angles_rad': chosen_angles, 'seeds': tuple(seeds),
        'array_admission_thresholds': {'symmetry_absolute': 1e-12,
            'whitened_trace_absolute': 1e-10, 'whitened_idempotency_absolute': 1e-10,
            'masked_electron_count_absolute': 1e-7,
            'production_density_reconstruction_relative': 1e-10,
            'selected_direction_manifold_roundoff': MANIFOLD_TOLERANCE,
            'selected_direction_projection_fraction_minimum_exclusive': DIRECTION_MINIMUM_PROJECTION_FRACTION},
        'angle_admission': {'maximum_count': 4, 'maximum_absolute_rad': .25,
            'minimum_absolute_rad': None, 'nonzero_required': True, 'duplicates_allowed': False},
        'source_preserved': True, 'repairs_performed': False,
        'new_final_occupation_rule': False, 'ordinary_occupied_space_preservation_claim': False,
        'functional_calls': 0, 'solver_iterations': 0,
        'F_at_new_density': None, 'energy': None, 'operator_id': None,
        'molecular_evaluation': 'NOT_EXECUTED', 'endpoint_acceptance': 'NOT_EXECUTED',
        'scientific_execution_authorized': False, 'scientific_approval': False,
        'production_activation': False, 'compute_enabled': False,
        'engine_qualified': False, 'research_qualified': False,
        'research_acceptance': 'NOT_ACCEPTED', 'delta_hartree': None,
        'comparison_status': {'UM-P12': 'NOT_EXECUTED', 'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'}})
