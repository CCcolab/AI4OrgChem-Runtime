"""Fixed-geometry experimental adapter; frozen P09 core is not modified.

Runtime must enforce the versioned profile, resource model and validation gates.
This adapter alone does not approve a molecule or a scientific interpretation.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import math
import numpy as np
from .p09_ao_classification import classify_planar_pyscf_aos
from .p09_conditional_scf import run_p09_conditional_rks, generalized_commutator, closed_shell_idempotency_residual


def build(request, atoms, profile):
    from pyscf import gto, dft, lib
    from pyscf.dft import gen_grid, radi
    lib.num_threads(request['resources']['threads'])
    mol = gto.M(atom=atoms, basis=profile['basis'], unit='Angstrom', charge=0,
                spin=0, cart=False, symmetry=False, ecp={}, verbose=0,
                max_memory=profile['ordinary']['max_memory_mb'])
    mf = dft.RKS(mol)
    mf.verbose = 0
    mf.xc = profile['xc']
    for key, value in profile['ordinary'].items():
        if key == 'max_memory_mb':
            mf.max_memory = value
        else:
            setattr(mf, key, value)
    mf.grids.level = profile['grid']['level']
    mf.grids.atom_grid = {}
    mf.grids.prune = gen_grid.nwchem_prune
    mf.grids.radi_method = radi.treutler
    mf.grids.radii_adjust = radi.treutler_atomic_radii_adjust
    mf.grids.atomic_radii = radi.BRAGG_RADII
    mf.grids.becke_scheme = gen_grid.original_becke
    mf.grids.alignment = 8
    mf.small_rho_cutoff = 0
    mf.nlc = ''
    mapping = {index-1: group['id'] for group in request['fragments'] for index in group['carbon_atom_indices_1based']}
    descriptors = classify_planar_pyscf_aos(mol, mapping)
    return mol, mf, descriptors


def inspect(request, atoms, profile):
    mol, mf, descriptors = build(request, atoms, profile)
    omega, alpha, hybrid = mf._numint.rsh_and_hybrid_coeff(mf.xc, spin=0)
    basis_bytes = repr(mol._basis).encode('utf-8')
    return {'nao': int(mol.nao_nr()), 'electron_count': int(mol.nelectron),
        'ao_labels': [[int(label[0]), *label[1:]] for label in mol.ao_labels(fmt=False)],
        'ao_descriptors': [{'kind': d.kind, 'fragment': d.fragment} for d in descriptors],
        'basis_expansion_sha256': hashlib.sha256(basis_bytes).hexdigest(),
        'xc_effective': {'xc': mf.xc, 'omega': float(omega), 'alpha': float(alpha), 'hybrid': float(hybrid)},
        'ordinary_effective': {key: getattr(mf, 'max_memory' if key == 'max_memory_mb' else key) for key in profile['ordinary']},
        'grid_effective': {'level': mf.grids.level, 'prune': 'pyscf.dft.gen_grid.nwchem_prune',
            'radi_method': 'pyscf.dft.radi.treutler', 'radii_adjust': 'pyscf.dft.radi.treutler_atomic_radii_adjust',
            'atomic_radii': 'pyscf.dft.radi.BRAGG_RADII', 'becke_scheme': 'pyscf.dft.gen_grid.original_becke',
            'alignment': mf.grids.alignment, 'small_rho_cutoff': mf.small_rho_cutoff, 'nlc': mf.nlc,
            'atom_grid': mf.grids.atom_grid},
        'dependencies': {n: importlib.metadata.version(n) for n in ('pyscf', 'numpy', 'scipy')},
        'scf_executed': False, 'grid_built': False, 'full_eri_allocated': False}


def strict_value(value, reasons, path='conditional'):
    if isinstance(value, np.ndarray):
        raise TypeError('Large arrays must be stored separately, not implicitly exported')
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            reasons.append({'field': path, 'reason': 'UNDEFINED_OR_NONFINITE'})
            return None
        return float(value)
    if isinstance(value, dict):
        return {key: strict_value(child, reasons, path+'.'+key) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_value(child, reasons, path+f'[{i}]') for i, child in enumerate(value)]
    return value


def metrics_qualified(record, electrons, profile, conditional):
    threshold = profile['thresholds']
    electron_key = 'masked_metric_electron_count' if conditional else 'physical_metric_electron_count'
    tests = {
        'converged': record.get('converged') is True,
        'energy_finite': isinstance(record.get('total_energy_hartree'), (float, int)) and math.isfinite(record['total_energy_hartree']),
        'electron_count': abs(record.get(electron_key, math.inf)-electrons) <= threshold['electron_count_abs'],
        'commutator': record.get('final_commutator_frobenius_norm', math.inf) <= threshold['commutator_frobenius'],
        'idempotency': record.get('closed_shell_idempotency_relative_residual', math.inf) <= threshold['idempotency_relative'],
        'energy_closure': abs(record.get('energy_component_closure_residual_hartree', math.inf)) <= threshold['energy_closure_hartree'],
    }
    if conditional:
        tests.update({'masked_overlap_positive': record.get('masked_overlap_minimum_eigenvalue', -math.inf) > 0,
            'overlap_mask': record.get('masked_overlap_cross_pi_max_abs', math.inf) <= threshold['mask_max_abs'],
            'fock_mask': record.get('conditional_fock_cross_pi_max_abs', math.inf) <= threshold['mask_max_abs']})
    return tests


def compute(request, atoms, profile, progress=lambda value: None):
    if not profile.get('compute_enabled'):
        raise RuntimeError('Profile blocked until W05 resource and numerical acceptance')
    mol, mf, descriptors = build(request, atoms, profile)
    progress({'stage': 'ORDINARY_RUNNING'})
    energy = float(mf.kernel())
    density = np.asarray(mf.make_rdm1(), dtype=float)
    overlap = np.asarray(mf.get_ovlp(), dtype=float)
    fock = np.asarray(mf.get_fock(dm=density, cycle=-1, diis=None), dtype=float)
    j, k = mf.get_jk(mol, density, hermi=1)
    grid_electrons, xc_energy, _ = mf._numint.nr_rks(mol, mf.grids, mf.xc, density, hermi=1, max_memory=mf.max_memory)
    omega, _, hybrid = mf._numint.rsh_and_hybrid_coeff(mf.xc, spin=0)
    if abs(omega) > 0:
        raise RuntimeError('Range-separated functional is outside profile')
    h = np.asarray(mf.get_hcore(), dtype=float)
    components = {'one_electron_energy_hartree': float(np.einsum('pq,qp->', h, density)),
        'coulomb_energy_hartree': .5*float(np.einsum('pq,qp->', j, density)),
        'exact_exchange_energy_hartree': -.25*float(hybrid)*float(np.einsum('pq,qp->', k, density)),
        'semilocal_xc_energy_hartree': float(xc_energy), 'nuclear_repulsion_hartree': float(mol.energy_nuc())}
    ordinary = {'converged': bool(mf.converged), 'total_energy_hartree': energy, **components,
        'physical_metric_electron_count': float(np.einsum('pq,qp->', overlap, density)),
        'grid_electron_count': float(grid_electrons),
        'final_commutator_frobenius_norm': float(np.linalg.norm(generalized_commutator(fock, density, overlap))),
        'closed_shell_idempotency_relative_residual': closed_shell_idempotency_residual(density, overlap),
        'energy_component_closure_residual_hartree': float(sum(components.values())-energy)}
    ordinary_tests = metrics_qualified(ordinary, mol.nelectron, profile, False)
    progress({'stage': 'ORDINARY_COMPLETED', 'ordinary': ordinary, 'qualification_tests': ordinary_tests})
    result = {'ordinary': ordinary, 'ordinary_tests': ordinary_tests, 'conditional': None,
              'conditional_tests': None, 'comparison_available': False, 'delta_hartree': None,
              'delta_kcal_mol': None, 'research_status': 'NOT_QUALIFIED',
              'variational_status': 'NOT_ESTABLISHED', 'stability_analysis': 'NOT_EXECUTED'}
    if not all(ordinary_tests.values()):
        result['reasons'] = ['ORDINARY_NUMERICAL_GATE_FAILED']
        return result
    import yaml
    source = Path(__file__).resolve().parents[4]
    classes = yaml.safe_load((source / 'configs/qm/p09_exchange_integral_classes_v0.1.yaml').read_text(encoding='utf-8'))
    progress({'stage': 'CONDITIONAL_RUNNING'})
    raw = run_p09_conditional_rks(mf, descriptors, classes['exchange_integral_classes'],
                                  initial_density=density, **profile['conditional'])
    tests = metrics_qualified(raw, mol.nelectron, profile, True)
    reasons = []
    conditional = strict_value({key: value for key, value in raw.items()
        if key not in ('density', 'mo_coefficients', 'mo_energies_hartree', 'mo_occupations')}, reasons)
    result.update({'conditional': conditional, 'conditional_tests': tests, 'undefined_diagnostics': reasons})
    if all(tests.values()):
        delta = energy-float(raw['total_energy_hartree'])
        result.update({'comparison_available': True, 'delta_hartree': delta,
            'delta_kcal_mol': delta*profile['hartree_to_kcal_mol'], 'research_status': 'TECHNICAL_ONLY',
            'reasons': ['W05_W06_ACCEPTANCE_NOT_COMPLETED']})
    else:
        result['reasons'] = ['CONDITIONAL_NUMERICAL_GATE_FAILED']
    progress({'stage': 'CONDITIONAL_COMPLETED', 'conditional': conditional, 'qualification_tests': tests})
    return strict_value(result, reasons, 'result')
