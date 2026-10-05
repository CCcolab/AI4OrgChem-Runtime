"""Independent conditional reference with truthful endpoint stopping, candidate v2.

This candidate is NOT_ACCEPTED for molecular or research use. It retains the
frozen conditional equation, global closed-shell Aufbau occupation and v1
array-level reference evaluation. It changes only the stopping/reset strategy:
an apparent DIIS plateau must pass an independently evaluated real-F endpoint;
an unqualified plateau clears Pulay and uses two subsequent raw-F cycles.
V2.1 also rejects an arithmetically unusable Pulay extrapolation, clears its
history and uses raw F for this cycle and the following two cycles. Invalid
inputs and nonfinite functional/residual values remain hard errors.
There is no production import, MOM, level shift, fractional/fragment occupation,
scientific-rule change or relaxed numerical threshold in this module.
"""
import numpy as np
from scipy.linalg import eigh

from reference import user_molecule as original


STRATEGY = 'INDEPENDENT_REAL_F_ENDPOINT_PLATEAU_AND_DIIS_FAILURE_RESET_V2_1_CANDIDATE'
FINAL_OPERATOR = 'RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS'
THRESHOLDS = {
    'commutator_frobenius': 1e-5,
    'electron_count_absolute': 1e-7,
    'idempotency_relative': 1e-7,
    'energy_closure_absolute_hartree': 1e-9,
    'mask_absolute': 1e-12,
    'final_gap_minimum_hartree': 1e-6,
}


def _settings(settings):
    keys = {'maximum_cycles', 'density_tolerance', 'energy_tolerance',
            'diis_start_cycle', 'diis_space', 'damping_cycles', 'damping',
            'memory_controlled_eri'}
    if set(settings) != keys:
        raise ValueError('Supply the complete frozen conditional settings')
    for name in ('maximum_cycles', 'diis_start_cycle', 'diis_space'):
        if type(settings[name]) is not int or settings[name] < 1:
            raise ValueError('Invalid cycle setting')
    if settings['maximum_cycles'] > 100:
        raise ValueError('Maximum cycles must not exceed the frozen 100-cycle ceiling')
    if type(settings['damping_cycles']) is not int or settings['damping_cycles'] < 0:
        raise ValueError('Invalid damping cycle count')
    if not np.isfinite(settings['damping']) or not 0 <= settings['damping'] < 1:
        raise ValueError('Invalid damping')
    for name in ('density_tolerance', 'energy_tolerance'):
        if not np.isfinite(settings[name]) or settings[name] <= 0:
            raise ValueError('Invalid stopping threshold')
    for name, ceiling in (('density_tolerance', 2e-8), ('energy_tolerance', 1e-9)):
        if settings[name] > ceiling:
            raise ValueError(f'{name} must not relax the frozen stopping threshold')


def _aufbau(fock, metric, electrons):
    energies, coefficients = eigh(fock, metric, check_finite=True)
    occupations = np.zeros(len(metric))
    occupations[:electrons // 2] = 2.0
    density = (coefficients * occupations) @ coefficients.T
    return energies, coefficients, occupations, (density + density.T) / 2


def _endpoint(evaluated, metric, hcore, aos, electrons, density_tolerance):
    """Independent qualification and raw Aufbau map; no production gate reuse."""
    d, f = evaluated['density'], evaluated['Fcond']
    energies, coefficients, occupations, mapped = _aufbau(f, metric, electrons)
    occupied = electrons // 2
    gap = float(energies[occupied] - energies[occupied - 1]) if occupied < len(energies) else None
    metrics = {
        'final_commutator_frobenius_norm': float(np.linalg.norm(f @ d @ metric - metric @ d @ f)),
        'masked_metric_electron_count_absolute_residual': abs(float(np.sum(metric * d.T)) - electrons),
        'closed_shell_idempotency_relative_residual': float(np.linalg.norm(d @ metric @ d - 2 * d)
                                                           / max(np.linalg.norm(d), 1.0)),
        'energy_component_closure_residual_hartree': abs(sum(evaluated['components_hartree'].values())
                                                       - evaluated['total_energy_hartree']),
        'mask_absolute_residual': max(float(np.max(np.abs(value - original.project(value, aos)), initial=0))
                                      for value in (metric, hcore, f)),
        'final_raw_aufbau_density_relative_residual': float(np.linalg.norm(mapped - d)
                                                          / max(np.linalg.norm(mapped), 1.0)),
        'final_non_diis_gap_hartree': gap,
    }
    if not np.isfinite([value for value in metrics.values() if value is not None]).all():
        raise ValueError('Nonfinite final qualification metric')
    tests = {
        'commutator': metrics['final_commutator_frobenius_norm'] <= THRESHOLDS['commutator_frobenius'],
        'electron_count': metrics['masked_metric_electron_count_absolute_residual'] <= THRESHOLDS['electron_count_absolute'],
        'idempotency': metrics['closed_shell_idempotency_relative_residual'] <= THRESHOLDS['idempotency_relative'],
        'energy_closure': metrics['energy_component_closure_residual_hartree'] <= THRESHOLDS['energy_closure_absolute_hartree'],
        'mask': metrics['mask_absolute_residual'] <= THRESHOLDS['mask_absolute'],
        'raw_aufbau_density': metrics['final_raw_aufbau_density_relative_residual'] <= density_tolerance,
        'final_non_diis_gap': gap is not None and gap >= THRESHOLDS['final_gap_minimum_hartree'],
    }
    return metrics, tests, energies, coefficients, occupations, mapped


def _gram_diagnostics(pulay):
    if not pulay.errors:
        return {'vectors': 0, 'rank': 0, 'condition_number': None,
                'condition_number_reason': 'NO_DIIS_VECTORS'}
    gram = np.array([[np.dot(a, b) for b in pulay.errors] for a in pulay.errors])
    rank = int(np.linalg.matrix_rank(gram))
    condition = float(np.linalg.cond(gram))
    finite = np.isfinite(condition)
    return {'vectors': len(pulay.errors), 'rank': rank,
            'condition_number': condition if finite else None,
            'condition_number_reason': None if finite else 'SINGULAR_OR_NONFINITE_CONDITION_NUMBER'}


def fixed_point(*, density, h, overlap, eri, aos, entries, electrons, hybrid,
                nuclear, xc, settings, progress=None):
    """V1-compatible array input plus optional progress(phase_string).

    Molecular callers must separately freeze the unchanged 100-cycle / start-2
    space-8 / first-two-cycle-0.2 / 1e-9-Eh / 2e-8-density contract. Allowing
    explicit smaller settings here enables bounded analytical regression tests;
    it does not approve a new molecular contract. At most 2*N+1 evaluations are
    made. Qualification is not variationality, stability or method acceptance.
    """
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons > 2 * len(aos):
        raise ValueError('Closed-shell electron count unsupported')
    _settings(settings)
    if progress is not None and not callable(progress):
        raise ValueError('Progress callback must be callable')
    if not np.isfinite(hybrid) or not 0 <= hybrid <= 1:
        raise ValueError('Only finite global-hybrid fractions supported')
    st, ht = original.project(overlap, aos), original.project(h, aos)
    minimum = float(np.linalg.eigvalsh(st).min())
    if minimum <= 0:
        raise ValueError('Masked metric is not positive definite; no repair allowed')
    masked, deleted = original.mask_integrals(eri, aos, entries)
    d = np.asarray(density, dtype=float).copy()
    if d.shape != ht.shape or not np.isfinite(d).all():
        raise ValueError('Invalid initial density')
    d = (d + d.T) / 2
    pulay = original.Pulay(settings['diis_space'])
    history, previous_energy, previous_candidate = [], None, None
    converged, raw_cycles, resets, fallbacks, evaluations = False, 0, 0, 0, 0
    plateau_resets, arithmetic_resets = 0, 0
    raw_reason = None
    coefficients = eigenvalues = occupations = None
    for cycle in range(1, settings['maximum_cycles'] + 1):
        if progress:
            progress(f'reference_v2.cycle_{cycle}.current_density')
        evaluated = original.evaluate(d, ht, st, overlap, masked, aos, hybrid, nuclear, xc)
        evaluations += 1
        f = evaluated['Fcond']
        error = f @ d @ st - st @ d @ f
        if not np.isfinite(f).all() or not np.isfinite(error).all():
            raise ValueError('Nonfinite real-F residual before DIIS')
        update_failure, arithmetic_reset = None, False
        if raw_cycles:
            diagonalized = f.copy()
            raw_cycles -= 1
            operator = raw_reason
        elif cycle >= settings['diis_start_cycle']:
            before = pulay.fallbacks
            try:
                diagonalized = pulay.update(f, error)
            except (np.linalg.LinAlgError, ValueError) as error_value:
                if (isinstance(error_value, ValueError)
                        and str(error_value) != 'Unusable affine DIIS coefficients'):
                    raise
                fallbacks += pulay.fallbacks - before
                update_failure = {'exception_type': type(error_value).__name__,
                                  'message': str(error_value),
                                  'action': 'REJECT_EXTRAPOLATION_CLEAR_PULAY_USE_CURRENT_PLUS_TWO_RAW_F_CYCLES'}
                pulay = original.Pulay(settings['diis_space'])
                raw_cycles, resets, arithmetic_reset = 2, resets + 1, True
                arithmetic_resets += 1
                raw_reason = 'RAW_F_AFTER_UNUSABLE_DIIS_EXTRAPOLATION_RESET'
                diagonalized = f.copy()
                operator = 'RAW_F_AFTER_UNUSABLE_DIIS_EXTRAPOLATION'
            else:
                fallbacks += pulay.fallbacks - before
                operator = 'INDEPENDENT_AFFINE_DIIS'
        else:
            diagonalized = f.copy()
            operator = 'RAW_F_BEFORE_DIIS_START'
        eigenvalues, coefficients, occupations, candidate = _aufbau(diagonalized, st, electrons)
        residual = float(np.linalg.norm(candidate - d) / max(np.linalg.norm(candidate), 1.0))
        change = None if previous_energy is None else abs(evaluated['total_energy_hartree'] - previous_energy)
        if progress:
            progress(f'reference_v2.cycle_{cycle}.candidate_real_f')
        candidate_evaluation = original.evaluate(candidate, ht, st, overlap, masked, aos, hybrid, nuclear, xc)
        evaluations += 1
        candidate_metrics, candidate_tests, *_ = _endpoint(candidate_evaluation, st, ht, aos, electrons,
                                                          settings['density_tolerance'])
        candidate_energy_change = abs(candidate_evaluation['total_energy_hartree']
                                      - evaluated['total_energy_hartree'])
        plateau = (change is not None and residual <= settings['density_tolerance']
                   and change <= settings['energy_tolerance'])
        candidate_tests['candidate_energy_change'] = candidate_energy_change <= settings['energy_tolerance']
        qualified = all(candidate_tests.values())
        row = {
            'cycle': cycle, 'total_energy_hartree': evaluated['total_energy_hartree'],
            'density_residual': residual, 'energy_change_hartree': change,
            'commutator_frobenius': float(np.linalg.norm(error)),
            'diagonalized_operator_source': operator,
            'candidate_total_energy_hartree': candidate_evaluation['total_energy_hartree'],
            'candidate_energy_change_hartree': candidate_energy_change,
            'candidate_real_f_metrics': candidate_metrics,
            'candidate_qualification_tests': candidate_tests,
            'legacy_small_step_plateau': bool(plateau),
            'candidate_endpoint_qualified': bool(qualified),
            'diis_gram': _gram_diagnostics(pulay),
            'diis_update_failure': update_failure,
            'diis_arithmetic_reset': arithmetic_reset,
            'occupied_subspace_overlap_with_previous_candidate':
                None if previous_candidate is None else float(np.trace(0.5 * candidate @ st @ (0.5 * previous_candidate) @ st)),
            'plateau_reset': False,
        }
        history.append(row)
        if plateau and qualified:
            d, converged = candidate, True
            break
        if plateau:
            plateau_resets += 1
            pulay = original.Pulay(settings['diis_space'])
            raw_cycles = 2
            raw_reason = 'RAW_F_AFTER_UNQUALIFIED_PLATEAU'
            if not arithmetic_reset:
                resets += 1
            row['plateau_reset'] = True
            row['scheduled_raw_f_cycles'] = 2
        previous_energy, previous_candidate = evaluated['total_energy_hartree'], candidate.copy()
        damping = settings['damping'] if cycle <= settings['damping_cycles'] else 0
        d = (1 - damping) * candidate + damping * d
        d = (d + d.T) / 2
    if progress:
        progress('reference_v2.final_returned_density')
    final = original.evaluate(d, ht, st, overlap, masked, aos, hybrid, nuclear, xc)
    evaluations += 1
    metrics, tests, raw_energies, raw_coefficients, raw_occupations, mapped = _endpoint(
        final, st, ht, aos, electrons, settings['density_tolerance'])
    # Repeated final evaluation is checked again: a stateful/non-reproducible XC
    # callback cannot preserve a candidate's earlier qualification claim.
    preliminary_converged = converged
    final_energy_recheck = abs(final['total_energy_hartree']
                              - candidate_evaluation['total_energy_hartree'])
    tests['final_energy_recheck'] = final_energy_recheck <= settings['energy_tolerance']
    converged = bool(converged and all(tests.values()))
    tests['converged'] = converged
    mapped_matches = bool(tests['raw_aufbau_density'])
    final.update(metrics)
    final.update({
        'converged': converged, 'cycles': len(history), 'history': history,
        'qualification_tests': tests,
        'stopping_reason': ('QUALIFIED_REAL_F_FIXED_POINT' if converged else
                            'FINAL_RECHECK_FAILED' if preliminary_converged else 'MAXIMUM_CYCLES'),
        'final_energy_recheck_change_hartree': final_energy_recheck,
        'state_comparability': 'COMPARABLE_CANDIDATE' if tests['final_non_diis_gap'] else 'ROOT_AMBIGUOUS',
        'mo_coefficients': raw_coefficients, 'mo_energies_hartree': raw_energies,
        'mo_occupations': raw_occupations,
        'mo_operator_source': FINAL_OPERATOR,
        'mo_density_role': 'FINAL_RAW_AUFBAU_MAP_DIAGNOSTIC',
        'mo_density_matches_returned': mapped_matches,
        'mo_density_failure_reason': None if mapped_matches else 'FINAL_RAW_AUFBAU_MAP_DIFFERS_FROM_RETURNED_DENSITY',
        'final_raw_mo_coefficients': raw_coefficients,
        'final_non_diis_eigenvalues_hartree': raw_energies,
        'raw_aufbau_density': mapped,
        'last_diagonalization_mo_coefficients': coefficients,
        'last_diagonalization_mo_energies_hartree': eigenvalues,
        'last_diagonalization_mo_occupations': occupations,
        'last_diagonalization_operator_source': history[-1]['diagonalized_operator_source'],
        'occupied_virtual_gap_hartree': metrics['final_non_diis_gap_hartree'],
        'gap_operator_source': FINAL_OPERATOR,
        'final_non_diis_gap_operator_source': FINAL_OPERATOR,
        'undefined_diagnostics': [] if metrics['final_non_diis_gap_hartree'] is not None else [
            {'field': 'final_non_diis_gap_hartree', 'reason': 'NO_VIRTUAL_ORBITALS'}],
        'masked_overlap': st, 'masked_hcore': ht, 'masked_eri': masked,
        'deleted_eri_count': deleted, 'total_eri_count': len(aos) ** 4,
        'masked_overlap_minimum_eigenvalue': minimum,
        'masked_overlap_condition_number': float(np.linalg.cond(st)),
        'final_operator_source': FINAL_OPERATOR,
        'diis_implementation': 'INDEPENDENT_AFFINE_GRAM_SOLVE_V1',
        'diis_least_squares_fallbacks': fallbacks,
        'plateau_reset_count': plateau_resets,
        'diis_arithmetic_reset_count': arithmetic_resets,
        'solver_reset_count': resets,
        'pending_raw_f_cycles': raw_cycles,
        'functional_evaluation_count': evaluations,
        'functional_evaluation_maximum': 2 * settings['maximum_cycles'] + 1,
        'solver_strategy': STRATEGY,
        'solver_candidate_status': 'NOT_ACCEPTED',
        'qualification_thresholds': dict(THRESHOLDS, raw_aufbau_density_relative=settings['density_tolerance']),
        'reference_storage': 'COPY_PLUS_CATEGORY_DECISIONS',
        'variational_status': 'NOT_ESTABLISHED', 'stability_status': 'NOT_EXECUTED',
        'molecular_acceptance': 'NOT_EXECUTED', 'research_acceptance': 'NOT_ACCEPTED',
    })
    return final
