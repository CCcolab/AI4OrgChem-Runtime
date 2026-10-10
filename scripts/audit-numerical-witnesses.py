"""Read-only NumPy audit of saved matrices; never dispatch a scientific engine."""
from __future__ import annotations

import argparse
import builtins
import contextlib
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORTS = frozenset(('pyscf', 'ai4orgchem', 'rdkit', 'scipy'))


@contextlib.contextmanager
def numerical_only_imports():
    original = builtins.__import__

    class RefuseScientificImport:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in FORBIDDEN_IMPORTS:
                raise ImportError('Numerical witness audit forbids ' + fullname)
            return None

    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in FORBIDDEN_IMPORTS:
            raise ImportError('Numerical witness audit forbids ' + name)
        return original(name, *args, **kwargs)

    finder = RefuseScientificImport()
    builtins.__import__ = guarded
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        builtins.__import__ = original


with numerical_only_imports():
    import numpy as np


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError('Duplicate JSON key: ' + key)
            output[key] = value
        return output
    def nonfinite(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    record = json.loads(Path(path).read_text(encoding='utf-8-sig'),
                        object_pairs_hook=unique, parse_constant=nonfinite)
    def check_numbers(value):
        if isinstance(value, float):
            require(math.isfinite(value), 'Nonfinite JSON number')
        elif isinstance(value, dict):
            for child in value.values():
                check_numbers(child)
        elif isinstance(value, list):
            for child in value:
                check_numbers(child)
    check_numbers(record)
    return record


def require(condition, message):
    if not condition:
        raise ValueError(message)


def member_sha256(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes(order='C')).hexdigest()


def density_id(array):
    canonical = np.ascontiguousarray(array, dtype='<f8')
    header = b'AI4OrgChem-density-v1\0' + struct.pack('<QQ', *canonical.shape)
    return hashlib.sha256(header + canonical.tobytes(order='C')).hexdigest()


def decode_arrays(value, archive):
    """Recursively validate descriptor/member shape, dtype and C-byte identity."""
    if isinstance(value, dict) and 'npz_member' in value:
        array = archive[value['npz_member']]
        require(not array.dtype.hasobject, 'Object array forbidden')
        require(list(array.shape) == value['shape'], 'Array shape mismatch')
        require(array.dtype.str == value['dtype'], 'Array dtype mismatch')
        require(member_sha256(array) == value['sha256'], 'Array member SHA-256 mismatch')
        require(array.dtype.kind in 'fb' and np.isfinite(array).all(), 'Nonfinite/non-numeric array')
        return array
    if isinstance(value, dict):
        return {key: decode_arrays(item, archive) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_arrays(item, archive) for item in value]
    return value


def payload_path(root, entry):
    path = (root / entry['path']).resolve()
    require(path.is_relative_to(root.resolve()), 'Payload path escapes package')
    require(path.is_file() and not (root / entry['path']).is_symlink(), 'Missing/symlink payload')
    require(path.stat().st_size == entry['size_bytes'], 'Payload size mismatch: ' + entry['path'])
    require(sha256(path) == entry['sha256'], 'Payload SHA-256 mismatch: ' + entry['path'])
    return path


def matching_records(value, key, expected):
    if isinstance(value, dict):
        matches = [value] if value.get(key) == expected else []
        return matches + [item for child in value.values() for item in matching_records(child, key, expected)]
    if isinstance(value, list):
        return [item for child in value for item in matching_records(child, key, expected)]
    return []


def close(actual, expected, tolerance, name):
    require(math.isfinite(float(actual)) and math.isfinite(float(expected)), name + ': nonfinite')
    residual = abs(float(actual) - float(expected))
    require(residual <= tolerance, name + ': mismatch ' + str(residual))
    return residual


def trace_product(left, right):
    return float(np.sum(left * right.T))


def matrix_geometry(overlap):
    values, vectors = np.linalg.eigh(overlap)
    require(values[0] > 0, 'Overlap must be positive definite without repair')
    return values, (vectors * np.sqrt(values)) @ vectors.T, (vectors / np.sqrt(values)) @ vectors.T


def check_matrices(arrays, dimension):
    for name, array in arrays.items():
        if array.ndim == 2:
            require(array.shape == (dimension, dimension), 'Matrix dimension mismatch: ' + name)
            symmetry = np.array_equal(array, array.T) if array.dtype.kind == 'b' else float(np.max(np.abs(array-array.T))) <= 1e-10
            require(symmetry, 'Matrix symmetry mismatch: ' + name)


def audit_ordinary(record, arrays):
    s, d, c, f, h, v = [arrays[name] for name in
                        ('overlap', 'density', 'canonical_coefficients', 'fock', 'hcore', 'veff')]
    occupations, energies = arrays['occupations'], arrays['orbital_energies_hartree']
    n = record['basis_function_count']
    electrons = record['molecule']['electron_count']
    check_matrices({key: value for key, value in arrays.items() if key != 'canonical_coefficients'}, n)
    require(c.shape == (n, n) and occupations.shape == energies.shape == (n,), 'Orbital dimension mismatch')
    require(np.array_equal(occupations, record['occupations']), 'Saved occupations differ')
    require(np.array_equal(energies, record['orbital_energies_hartree']), 'Saved MO energies differ')
    require(np.isin(occupations, (0., 2.)).all() and sum(occupations) == electrons, 'Closed-shell occupancy mismatch')
    occupied = occupations == 2
    eigenvalues, half, inverse = matrix_geometry(s)
    reconstructed = (c * occupations) @ c.T
    p, fw = half @ d @ half / 2, inverse @ f @ inverse
    tolerances = record['tolerances']
    ledger = record['diagnostics']['energy_ledger']
    one, two = trace_product(d, h), .5 * trace_product(d, v)
    total = one + two + ledger['nuclear_repulsion']
    count = trace_product(d, s)
    residuals = {
        'electron_number_absolute': abs(count-electrons),
        'density_reconstruction_relative_frobenius': float(np.linalg.norm(d-reconstructed) / max(np.linalg.norm(d), 1.)),
        'occupied_orthonormality_frobenius': float(np.linalg.norm(c[:, occupied].T @ s @ c[:, occupied]-np.eye(sum(occupied)))),
        'whitened_projector_idempotency_frobenius': float(np.linalg.norm(p @ p-p)),
        'whitened_fock_projector_commutator_frobenius_hartree': float(np.linalg.norm(fw @ p-p @ fw)),
        'energy_ledger_closure_hartree': abs(total-record['total_energy_hartree']),
        'ordinary_fock_closure_max_absolute_hartree': float(np.max(np.abs(f-h-v))),
        'generalized_mo_eigen_equation_frobenius_hartree': float(np.linalg.norm(f @ c-(s @ c)*energies)),
    }
    for name in ('electron_number_absolute', 'density_reconstruction_relative_frobenius',
                 'occupied_orthonormality_frobenius', 'whitened_projector_idempotency_frobenius',
                 'whitened_fock_projector_commutator_frobenius_hartree'):
        require(residuals[name] <= tolerances[name], 'Ordinary numerical check failed: ' + name)
    require(residuals['ordinary_fock_closure_max_absolute_hartree'] <= tolerances['matrix_symmetry_absolute'], 'Ordinary F assembly failed')
    require(residuals['energy_ledger_closure_hartree'] <= tolerances['energy_ledger_closure_hartree'], 'Ordinary energy closure failed')
    require(eigenvalues[0] >= tolerances['minimum_overlap_eigenvalue'], 'Ordinary overlap minimum failed')
    require(eigenvalues[-1]/eigenvalues[0] <= tolerances['maximum_overlap_condition_number'], 'Ordinary overlap conditioning failed')
    for field, calculated in [('one_electron', one), ('two_electron_coulomb_exchange', two),
                              ('electronic', one+two), ('reconstructed_total', total), ('scf_total', total)]:
        close(calculated, ledger[field], tolerances['energy_ledger_closure_hartree'], 'Ordinary ledger ' + field)
    close(count, record['diagnostics']['electron_number'], tolerances['electron_number_absolute'], 'Ordinary saved electron count')
    require(record['scf']['converged'] and record['numerically_qualified'], 'Ordinary original qualification mismatch')
    gap = float(energies[sum(occupied)]-energies[sum(occupied)-1])
    close(gap, record['diagnostics']['orbital_summary']['homo_lumo_gap_hartree'], 1e-10, 'Ordinary saved gap')
    return {'audit_status': 'PASS_SAVED_ARRAY_WITNESS', 'saved_numerical_status': record['status'],
            'electron_number': count, 'reconstructed_total_energy_hartree': total,
            'homo_lumo_gap_hartree': gap, 'gap_role': 'DIAGNOSTIC_NOT_ORDINARY_ACCEPTANCE_GATE',
            'residuals': residuals, 'stability': record['stability_status'],
            'interpretation': 'Specified-geometry RHF witness; stable minimum and general method validity not established'}


def audit_conditional(record, arrays):
    d, s, h, f, g, j, k, v, mask, physical_s, physical_h = [arrays[name] for name in
        ('density', 'overlap_masked', 'hcore_masked', 'fock_masked', 'raw_fock', 'coulomb',
         'exchange', 'xc_potential', 'matrix_delete_mask', 'overlap_physical', 'hcore_physical')]
    check_matrices(arrays, 14)
    require(mask.dtype.kind == 'b', 'Deletion mask must be boolean')
    identity = density_id(d)
    binding = record['returned_density_binding']
    require(member_sha256(d) == binding['result_density_member_sha256']
            == binding['evaluation_requested_density_member_sha256'], 'Returned density member evidence mismatch')
    require(all(identity == binding[name] for name in
                ('solver_final_density_id', 'returned_density_id', 'requested_density_id', 'value_density_id')),
            'Returned density / true evaluation identity mismatch')
    require(record['operator_source'] == 'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY', 'True returned-density operator required')
    limits, saved, energy = record['saved_endpoint_gate']['thresholds'], record['saved_endpoint_gate'], record['energy_ledger']
    coefficient = record['exact_exchange_fraction']
    for name, observed in [('raw_G_assembly', g-(h+j-.5*coefficient*k+v)),
                           ('projected_F_assembly', f-np.where(mask, 0., g)),
                           ('masked_S_assembly', s-np.where(mask, 0., physical_s)),
                           ('masked_h_assembly', h-np.where(mask, 0., physical_h))]:
        require(float(np.max(np.abs(observed))) <= limits['mask_max_abs'], 'Conditional operator mismatch: ' + name)
    one, coulomb, exchange = trace_product(d, h), .5*trace_product(d, j), -.25*coefficient*trace_product(d, k)
    for name, actual in [('one_electron_energy', one), ('coulomb_energy', coulomb), ('exact_exchange_energy', exchange)]:
        close(actual, energy[name], limits['energy_closure_hartree'], 'Conditional ledger ' + name)
    total = one+coulomb+exchange+energy['semilocal_xc_energy']+energy['nuclear_repulsion']
    closure = close(total, energy['total_energy'], limits['energy_closure_hartree'], 'Conditional total ledger')
    close(total-energy['nuclear_repulsion'], energy['electronic_energy'], limits['energy_closure_hartree'], 'Conditional electronic ledger')
    count, physical_count = trace_product(d, s), trace_product(d, physical_s)
    close(count, record['electron_counts']['masked_metric'], 1e-10, 'Conditional masked count')
    close(physical_count, record['electron_counts']['physical_metric'], 1e-10, 'Conditional physical count')
    _, _, inverse = matrix_geometry(s)
    # Symmetric whitening uses NumPy only. Near-degenerate occupied subspaces
    # can differ from the original SciPy generalized eigenvectors.
    eigenvalues, white_coefficients = np.linalg.eigh(inverse @ f @ inverse)
    coefficients = inverse @ white_coefficients
    electrons, occupied = record['expected_electrons'], record['expected_electrons']//2
    mapped = 2*coefficients[:, :occupied] @ coefficients[:, :occupied].T
    mapped = .5*(mapped+mapped.T)
    commutator = float(np.linalg.norm(f @ d @ s-s @ d @ f))
    idempotency = float(np.linalg.norm(d @ s @ d-2*d)/max(np.linalg.norm(d), 1.))
    map_residual = float(np.linalg.norm(mapped-d)/max(np.linalg.norm(mapped), 1.))
    gap = float(eigenvalues[occupied]-eigenvalues[occupied-1])
    checks = {'commutator': commutator <= limits['commutator_frobenius'],
              'electron_count': abs(count-electrons) <= limits['electron_count_abs'],
              'idempotency': idempotency <= limits['idempotency_relative'],
              'energy_closure': closure <= limits['energy_closure_hartree'],
              'mapped_density_numpy': map_residual <= limits['mapped_density_relative'],
              'raw_gap_numpy': gap >= limits['final_non_diis_gap_minimum_hartree']}
    require(all(checks[name] for name in ('commutator', 'electron_count', 'idempotency', 'energy_closure')),
            'Conditional saved density has inconsistent basic numerical checks')
    require(saved['qualified'] is False and saved['checks']['mapped_density'] is False
            and saved['checks']['raw_gap'] is False, 'Saved endpoint rejection mismatch')
    require(saved['mapped_density_relative_residual'] > limits['mapped_density_relative']
            and saved['final_non_diis_gap_hartree'] < limits['final_non_diis_gap_minimum_hartree'], 'Saved gate/scalar mismatch')
    require(checks['raw_gap_numpy'] is False, 'NumPy did not reproduce the raw-gap rejection')
    require(record['comparison_available'] is False and record['production_activation'] is False,
            'Conditional witness must retain refusal to activate/compare')
    return {'audit_status': 'PASS_SAVED_ARRAY_WITNESS', 'endpoint_qualification': 'REJECTED',
            'returned_density_id': identity, 'electron_counts': {'masked_metric_recomputed': count,
            'physical_metric_recomputed': physical_count, 'grid_saved_scalar': record['electron_counts']['grid'],
            'grid_status': 'NOT_RECOMPUTED_NO_GRID_PAYLOAD'}, 'reconstructed_total_energy_hartree': total,
            'energy_closure_hartree': closure, 'commutator_frobenius': commutator,
            'idempotency_relative': idempotency,
            'saved_scipy_endpoint': {'raw_gap_hartree': saved['final_non_diis_gap_hartree'],
                                     'mapped_density_relative': saved['mapped_density_relative_residual']},
            'numpy_array_diagnostic': {'raw_gap_hartree': gap, 'mapped_density_relative': map_residual,
                 'checks': checks, 'exact_scipy_subspace_reproduction_claimed': False},
            'semilocal_xc_energy_status': 'SAVED_SCALAR_NOT_REINTEGRATED',
            'interpretation': 'Rejected saved endpoint; no claim about nonexistence of roots, physical bond energy, stationarity or stability'}


def audit_package(package, repository=REPOSITORY):
    with numerical_only_imports():
        package = Path(package).resolve()
        manifest = strict_json(package / 'manifest.json')
        require(manifest['schema'] == 'numerical-witness-package-v1', 'Unknown witness package schema')
        parents = {}
        for entry in manifest['public_parent_records']:
            path = payload_path(Path(repository), entry)
            parent = strict_json(path)
            require(entry.get('kind') == 'PUBLIC_METADATA_PROJECTION_NOT_ORIGINAL_BYTES',
                    'Explicit public parent byte policy required')
            projection = parent.get('_public_projection', {})
            require(projection.get('original_sha256') == entry.get('original_sha256')
                    and projection.get('original_size_bytes') == entry.get('original_size_bytes')
                    and projection.get('scientific_numeric_values_changed') is False
                    and projection.get('acceptance_transferred_to_current_code') is False,
                    'Original/public parent identity binding mismatch')
            parents[entry['path']] = parent
        rows = {}
        for name, witness in manifest['witnesses'].items():
            files = {key: payload_path(package, entry) for key, entry in witness['files'].items()}
            record = strict_json(files['record'])
            with np.load(files['arrays'], allow_pickle=False) as archive:
                require(set(archive.files) == set(witness['array_members']), 'NPZ member inventory mismatch')
                arrays = decode_arrays(witness['array_members'], archive)
            if witness['kind'] == 'ordinary-rhf':
                deployment = parents['validation/molecular-service/deployment-20261008.public.json']
                require(deployment['cases']['water']['result_sha256'] == sha256(files['record']), 'Public ordinary result binding mismatch')
                require(deployment['cases']['water']['host_manifest_sha256'] == sha256(files['host_manifest']), 'Public ordinary host binding mismatch')
                host = strict_json(files['host_manifest'])
                image = strict_json(files['image_identity'])
                require(host['output_sha256']['image-inspect.json'] == sha256(files['image_identity']), 'Original host/image binding mismatch')
                require(image['Id'] == deployment['image']['image_id'] == witness['provenance']['image_id'], 'Ordinary image identity mismatch')
                require(host['output_sha256']['output/calculation/orbitals-density.npz'] == sha256(files['arrays']), 'Original host/NPZ binding mismatch')
                require(record['array_artifact_sha256'] == sha256(files['arrays']), 'Original result/NPZ binding mismatch')
                require(record['structure_sha256'] == sha256(files['geometry']) and record['request_sha256'] == sha256(files['request']), 'Ordinary input binding mismatch')
                rows[name] = audit_ordinary(record, arrays)
            elif witness['kind'] == 'conditional-rejected-endpoint':
                require(record['arrays'] == witness['array_members'], 'Conditional descriptor binding mismatch')
                provenance = witness['provenance']
                published = parents['validation/user-molecule/seed-v2-20261007.public.json']
                matches = matching_records(published, 'raw_result_sha256', provenance['original_result_sha256'])
                require(len(matches) == 1 and matches[0]['endpoint_gate'] == record['saved_endpoint_gate'],
                        'Public conditional result/gate binding mismatch')
                framework = parents['validation/local-runtime-framework-20261007.public.json']
                sealed = matching_records(framework, 'directory', provenance['sealed_delivery_directory'])
                require(len(sealed) == 1 and sealed[0]['manifest_sha256'] == provenance['sealed_manifest_sha256'],
                        'Public conditional sealed-manifest binding mismatch')
                for member, original in [('overlap_physical', 'physical_overlap'), ('hcore_physical', 'physical_hcore')]:
                    require(witness['array_members'][member]['sha256'] == provenance['operator_array_identities'][original]['sha256'],
                            'Conditional physical array identity mismatch')
                rows[name] = audit_conditional(record, arrays)
            else:
                raise ValueError('Unknown witness kind')
        require(set(rows) == {'ordinary-water', 'conditional-ethene-v2'}, 'Witness scope mismatch')
        return {'schema': 'numerical-witness-audit-v1', 'audit_status': 'PASS_READ_ONLY_NUMPY_AUDIT',
                'numpy_version': np.__version__, 'witnesses': rows,
                'new_scientific_calls': {'scf': 0, 'integrals': 0, 'grids': 0, 'fock_evaluations': 0},
                'forbidden_imports': sorted(FORBIDDEN_IMPORTS),
                'provenance_limit': 'Hashes bind bytes to declared evidence; they do not authenticate a scientific engine or establish method validity'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=REPOSITORY/'evidence/numerical-witnesses')
    args = parser.parse_args()
    try:
        result = audit_package(args.package)
    except (ValueError, OSError, KeyError, TypeError, ImportError) as error:
        print(json.dumps({'audit_status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
