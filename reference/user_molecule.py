"""Independent array-level conditional fixed-point reference, candidate v1.

No imports from ai4orgchem. Raw integrals, semilocal XC and linear algebra
remain shared dependencies. Molecular execution/thresholds are NOT accepted.
This module supplies no public Compute command or permission to run molecules.
"""
from dataclasses import dataclass
import hashlib
import itertools
from pathlib import Path

import numpy as np
from scipy.linalg import eigh


@dataclass(frozen=True)
class AO:
    kind: str
    group: str | None = None

    def __post_init__(self):
        if self.kind not in ('sigma', 'pi'):
            raise ValueError('Unknown AO parity')
        if self.kind == 'pi' and (not isinstance(self.group, str) or not self.group):
            raise ValueError('Pi AO needs a nonempty group')
        if self.kind == 'sigma' and self.group is not None:
            raise ValueError('Sigma AO is not a pi fragment')


def classify(labels, coordinates_angstrom, groups_1based):
    """Audit xy orientation and spherical s/p/d labels without production helpers."""
    coords = np.asarray(coordinates_angstrom, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 3 or not np.isfinite(coords).all():
        raise ValueError('Invalid coordinates')
    if np.max(np.abs(coords[:, 2]), initial=0) > 1e-8:
        raise ValueError('Geometry is not in the fixed xy plane')
    mapping = {}
    for group, atoms in groups_1based.items():
        for index in atoms:
            if type(index) is not int or not 1 <= index <= len(coords) or index in mapping:
                raise ValueError('Invalid/duplicate atom mapping')
            mapping[index] = group
    result = []
    components = {'s': {'': False}, 'p': {'x': False, 'y': False, 'z': True},
                  'd': {'xy': False, 'yz': True, 'z^2': False, 'xz': True, 'x2-y2': False}}
    for atom, _element, radial, component in labels:
        if type(atom) is not int or not 0 <= atom < len(coords):
            raise ValueError('AO center outside geometry')
        angular, component = radial[-1:].lower(), component.lower().replace(' ', '')
        if angular not in components or component not in components[angular]:
            raise ValueError('Unsupported spherical AO component')
        if components[angular][component]:
            if atom + 1 not in mapping:
                raise ValueError('Unassigned odd-parity AO')
            result.append(AO('pi', mapping[atom + 1]))
        else:
            result.append(AO('sigma'))
    return tuple(result)


def load_rules(path, expected_sha256):
    """Read the locked scientific YAML as data, not as executable reference code."""
    import yaml
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Rule bytes differ from source lock')
    entries = yaml.safe_load(raw)['exchange_integral_classes']
    if sorted(e['id'] for e in entries) != [f'X{i:02d}' for i in range(1, 16)]:
        raise ValueError('Exactly fifteen distinct ordered source classes required')
    allowed = {'P_not_equal_Q', 'S_not_equal_T', 'S_in_P_or_Q', 'T_in_P_or_Q'}
    for entry in entries:
        predicate = entry['index_predicate']
        tokens = predicate['bra'] + predicate['ket']
        if len(predicate['bra']) != 2 or len(predicate['ket']) != 2:
            raise ValueError('Malformed ordered rule')
        if any(t not in ('sigma', 'pi_P', 'pi_Q', 'pi_S', 'pi_T') for t in tokens):
            raise ValueError('Unknown rule token')
        if not set(predicate.get('constraints', [])) <= allowed:
            raise ValueError('Unknown rule constraint')
    return tuple(entries)


def ordered_matches(quartet, predicate):
    """Bind token variables explicitly and test the frozen two-group relations."""
    variables = {}
    tokens = predicate['bra'] + predicate['ket']
    if len(quartet) != 4 or len(tokens) != 4:
        raise ValueError('Four AO indices required')
    for token, ao in zip(tokens, quartet):
        if token == 'sigma':
            if ao.kind != 'sigma':
                return False
        else:
            if ao.kind != 'pi':
                return False
            variable = token[3:]
            if variable in variables and variables[variable] != ao.group:
                return False
            variables[variable] = ao.group
    constraints = predicate.get('constraints', [])
    for constraint, left, right in (('P_not_equal_Q', 'P', 'Q'), ('S_not_equal_T', 'S', 'T')):
        if constraint in constraints and left in variables and right in variables:
            if variables[left] == variables[right]:
                return False
    if 'S_in_P_or_Q' in constraints or 'T_in_P_or_Q' in constraints:
        if 'S' not in variables or 'T' not in variables or variables['S'] == variables['T']:
            return False
        pair = {variables['S'], variables['T']}
        if any(variables[v] not in pair for v in ('P', 'Q') if v in variables):
            return False
        if 'P' in variables and 'Q' in variables and {variables['P'], variables['Q']} != pair:
            return False
    return True


def permutations(quartet):
    """Generate pair-internal swaps and pair exchange without a production table."""
    left, right = tuple(quartet[:2]), tuple(quartet[2:])
    return set(a + b for a in (left, left[::-1]) for b in (right, right[::-1])) | set(
        b + a for a in (left, left[::-1]) for b in (right, right[::-1]))


def deleted_classes(quartet, entries):
    return {entry['id'] for entry in entries
            if any(ordered_matches(q, entry['index_predicate']) for q in permutations(quartet))}


def project(matrix, aos):
    value = np.asarray(matrix, dtype=float).copy()
    if value.shape != (len(aos), len(aos)) or not np.isfinite(value).all():
        raise ValueError('Invalid AO matrix')
    for p, left in enumerate(aos):
        for q, right in enumerate(aos):
            if left.kind == right.kind == 'pi' and left.group != right.group:
                value[p, q] = 0
    return value


def mask_integrals(eri, aos, entries):
    """Evaluate scalar category decisions then apply them to all AO quartets."""
    size = len(aos)
    if not 1 <= size <= 40:
        raise ValueError('Acceptance reference is limited to 1..40 AO')
    raw = np.asarray(eri, dtype=float)
    if raw.shape != (size,) * 4 or not np.isfinite(raw).all():
        raise ValueError('Invalid real chemist ERI tensor')
    masked, removed = raw.copy(), 0
    # The vocabulary is bounded by the two public pi groups plus sigma. Internal
    # single-group controls are allowed; no extra fragments silently accepted.
    if len({a.group for a in aos if a.kind == 'pi'}) > 2:
        raise ValueError('More than two pi groups is outside this reference')
    categories = tuple(dict.fromkeys(aos))
    indices = {ao: np.array([i for i, a in enumerate(aos) if a == ao]) for ao in categories}
    for quartet in itertools.product(categories, repeat=4):
        if deleted_classes(quartet, entries):
            selected = tuple(indices[a] for a in quartet)
            masked[np.ix_(*selected)] = 0
            removed += int(np.prod([len(s) for s in selected]))
    return masked, removed


def scalar_jk(density, eri):
    """Small same-D witness with literal independent J/K index contractions."""
    d = np.asarray(density, dtype=float)
    if d.ndim != 2 or d.shape[0] != d.shape[1] or not 1 <= len(d) <= 8:
        raise ValueError('Scalar toy witness limited to 1..8 AO')
    if np.shape(eri) != (len(d),) * 4:
        raise ValueError('Tensor dimensions differ')
    j, k = np.zeros_like(d), np.zeros_like(d)
    for p, q, r, s in itertools.product(range(len(d)), repeat=4):
        j[p, q] += eri[p, q, r, s] * d[r, s]
        k[p, q] += eri[p, r, q, s] * d[r, s]
    return j, k


def evaluate(density, h, overlap, physical_overlap, eri, aos, hybrid, nuclear, xc):
    """Independent five-component functional and projected final operator."""
    d = np.asarray(density, dtype=float)
    if d.shape != h.shape or not np.isfinite(d).all():
        raise ValueError('Invalid finite density')
    grid_electrons, xc_energy, potential = xc(d.copy())
    potential = np.asarray(potential, dtype=float)
    if potential.shape != d.shape or not np.isfinite(potential).all():
        raise ValueError('Invalid XC potential')
    if not np.isfinite([grid_electrons, xc_energy, hybrid, nuclear]).all():
        raise ValueError('Nonfinite functional component')
    j = np.tensordot(eri, d, axes=([2, 3], [0, 1]))
    k = np.tensordot(eri, d, axes=([1, 3], [0, 1]))
    trace = lambda matrix: float(np.sum(matrix * d.T))
    components = {'one_electron': trace(h), 'coulomb': 0.5 * trace(j),
        'exact_exchange': -0.25 * hybrid * trace(k), 'semilocal_xc': float(xc_energy),
        'nuclear_repulsion': float(nuclear)}
    raw = h + j - 0.5 * hybrid * k + potential
    values = {'density': d.copy(), 'J': j, 'K': k, 'Vxc': potential,
        'Fraw': raw, 'Fcond': project(raw, aos), 'components_hartree': components,
        'total_energy_hartree': sum(components.values()), 'grid_electron_count': float(grid_electrons),
        'masked_metric_electron_count': trace(overlap), 'physical_metric_electron_count': trace(physical_overlap)}
    if not np.isfinite([values['total_energy_hartree'], *components.values()]).all():
        raise ValueError('Nonfinite energy')
    return values


class Pulay:
    """Independent affine residual minimization; no production/PySCF DIIS calls.

    Degenerate Gram matrices use a least-squares solution, explicitly recorded.
    This algorithmic choice needs molecular/state-selection review before T06.
    """
    def __init__(self, space):
        self.space, self.focks, self.errors, self.fallbacks = space, [], [], 0

    def update(self, fock, error):
        self.focks.append(fock.copy())
        self.errors.append(error.ravel().copy())
        self.focks, self.errors = self.focks[-self.space:], self.errors[-self.space:]
        if len(self.focks) == 1:
            return fock.copy()
        count = len(self.focks)
        system = np.empty((count + 1, count + 1))
        system[0, 0], system[0, 1:], system[1:, 0] = 0, 1, 1
        system[1:, 1:] = [[np.dot(a, b) for b in self.errors] for a in self.errors]
        rhs = np.zeros(count + 1)
        rhs[0] = 1
        try:
            coefficients = np.linalg.solve(system, rhs)[1:]
        except np.linalg.LinAlgError:
            self.fallbacks += 1
            coefficients = np.linalg.lstsq(system, rhs, rcond=None)[0][1:]
        total = float(coefficients.sum())
        if not np.isfinite(coefficients).all() or abs(total) < np.finfo(float).eps:
            raise ValueError('Unusable affine DIIS coefficients')
        coefficients /= total
        return sum(weight * matrix for weight, matrix in zip(coefficients, self.focks))


def fixed_point(*, density, h, overlap, eri, aos, entries, electrons, hybrid,
                nuclear, xc, settings):
    """Complete array-level conditional iteration from an explicitly supplied D.

    XC callback must evaluate the original AO/grid, not the masked metric.
    Convergence is not research qualification or a proof of variationality.
    """
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons > 2 * len(aos):
        raise ValueError('Closed-shell electron count unsupported')
    keys = {'maximum_cycles', 'density_tolerance', 'energy_tolerance', 'diis_start_cycle',
            'diis_space', 'damping_cycles', 'damping', 'memory_controlled_eri'}
    if set(settings) != keys:
        raise ValueError('Supply the complete frozen conditional settings')
    for key in ('maximum_cycles', 'diis_start_cycle', 'diis_space'):
        if type(settings[key]) is not int or settings[key] < 1:
            raise ValueError('Invalid cycle setting')
    if type(settings['damping_cycles']) is not int or settings['damping_cycles'] < 0:
        raise ValueError('Invalid damping cycle count')
    if not 0 <= settings['damping'] < 1:
        raise ValueError('Invalid damping')
    for key in ('density_tolerance', 'energy_tolerance'):
        if not np.isfinite(settings[key]) or settings[key] <= 0:
            raise ValueError('Invalid stopping threshold')
    if not np.isfinite(hybrid) or not 0 <= hybrid <= 1:
        raise ValueError('Only finite global-hybrid fractions supported')
    st, ht = project(overlap, aos), project(h, aos)
    minimum = float(np.linalg.eigvalsh(st).min())
    if minimum <= 0:
        raise ValueError('Masked metric is not positive definite; no repair allowed')
    masked, count = mask_integrals(eri, aos, entries)
    d = np.asarray(density, dtype=float).copy()
    if d.shape != ht.shape or not np.isfinite(d).all():
        raise ValueError('Invalid initial density')
    d = (d + d.T) / 2
    diis, history, previous, converged = Pulay(settings['diis_space']), [], None, False
    for cycle in range(1, settings['maximum_cycles'] + 1):
        evaluated = evaluate(d, ht, st, overlap, masked, aos, hybrid, nuclear, xc)
        f = evaluated['Fcond']
        error = f @ d @ st - st @ d @ f
        diagonalized = diis.update(f, error) if cycle >= settings['diis_start_cycle'] else f
        eigenvalues, coefficients = eigh(diagonalized, st, check_finite=True)
        # Global Aufbau; no per-fragment electron count, MOM or fractional occupancy.
        occupations = np.zeros(len(aos))
        occupations[:electrons // 2] = 2
        candidate = (coefficients * occupations) @ coefficients.T
        residual = float(np.linalg.norm(candidate - d) / max(np.linalg.norm(candidate), 1.0))
        change = None if previous is None else abs(evaluated['total_energy_hartree'] - previous)
        history.append({'cycle': cycle, 'total_energy_hartree': evaluated['total_energy_hartree'],
            'density_residual': residual, 'energy_change_hartree': change,
            'commutator_frobenius': float(np.linalg.norm(error))})
        if change is not None and residual <= settings['density_tolerance'] and change <= settings['energy_tolerance']:
            d, converged = candidate, True
            break
        previous = evaluated['total_energy_hartree']
        damping = settings['damping'] if cycle <= settings['damping_cycles'] else 0
        d = (1 - damping) * candidate + damping * d
        d = (d + d.T) / 2
    final = evaluate(d, ht, st, overlap, masked, aos, hybrid, nuclear, xc)
    final.update({'converged': converged, 'cycles': len(history), 'history': history,
        'mo_coefficients': coefficients, 'mo_energies_hartree': eigenvalues, 'mo_occupations': occupations,
        'masked_overlap': st, 'masked_hcore': ht, 'masked_eri': masked,
        'deleted_eri_count': count, 'total_eri_count': len(aos) ** 4,
        'masked_overlap_minimum_eigenvalue': minimum,
        'masked_overlap_condition_number': float(np.linalg.cond(st)),
        'final_commutator_frobenius_norm': float(np.linalg.norm(final['Fcond'] @ d @ st - st @ d @ final['Fcond'])),
        'closed_shell_idempotency_relative_residual': float(np.linalg.norm(d @ st @ d - 2 * d) / max(np.linalg.norm(d), 1.0)),
        'energy_component_closure_residual_hartree': abs(sum(final['components_hartree'].values()) - final['total_energy_hartree']),
        'occupied_virtual_gap_hartree': float(eigenvalues[electrons // 2] - eigenvalues[electrons // 2 - 1]) if electrons < 2 * len(aos) else None,
        'gap_operator_source': 'LAST_DIAGONALIZATION_POSSIBLY_DIIS',
        'final_operator_source': 'RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS',
        'diis_implementation': 'INDEPENDENT_AFFINE_GRAM_SOLVE_V1',
        'diis_least_squares_fallbacks': diis.fallbacks,
        'reference_storage': 'COPY_PLUS_CATEGORY_DECISIONS',
        'variational_status': 'NOT_ESTABLISHED', 'stability_status': 'NOT_EXECUTED',
        'molecular_acceptance': 'NOT_EXECUTED'})
    return final


def original_grid_xc(mean_field):
    """Bridge only raw pinned PySCF XC; grids must already be explicitly frozen.

    Does not build a molecule, run ordinary/conditional SCF, or approve a budget.
    Shared integral/XC errors remain outside this reference's independence.
    """
    if mean_field.mol.cart or mean_field.mol.spin != 0:
        raise ValueError('Spherical closed-shell source required')
    if getattr(mean_field.grids, 'coords', None) is None:
        raise ValueError('Caller must freeze/build original grids under accepted budget')
    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(mean_field.xc, spin=0)
    if abs(omega) > 1e-14 or abs(alpha - hybrid) > 1e-14:
        raise ValueError('Range-separated hybrid not supported')
    def xc(density):
        return mean_field._numint.nr_rks(mean_field.mol, mean_field.grids, mean_field.xc,
            density, hermi=1, max_memory=mean_field.max_memory)
    return xc, float(hybrid)
