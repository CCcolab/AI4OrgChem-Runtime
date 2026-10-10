"""Reproduce the subset from local original evidence; no scientific execution."""
import argparse
import importlib.util
import json
import re
import shutil
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('witness_audit', REPOSITORY/'scripts/audit-numerical-witnesses.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
np = audit.np


def extract(water, seed, ordinary, package):
    final = audit.strict_json(seed/'FINAL_MANIFEST.json')
    assert audit.sha256(seed/'FINAL_MANIFEST.json') == '548e3ba94177eaa6e894623519b6c3abe9fa860686049242221bbf0174ebd797'
    final_rows = {row['path']: row for row in final['files']}
    originals = {}

    def source(bundle, path, root):
        originals[path] = audit.sha256(path)
        return {'bundle': bundle, 'relative_path': path.relative_to(root).as_posix(),
                'size_bytes': path.stat().st_size, 'sha256': originals[path]}

    def registered(path, kind, sources, transformations=None):
        entry = {'path': path.relative_to(package).as_posix(), 'size_bytes': path.stat().st_size,
                 'sha256': audit.sha256(path), 'byte_provenance': kind, 'source_files': sources}
        if transformations:
            entry['transformations'] = transformations
        return entry

    def copy_original(path, target, bundle, root):
        if path.suffix in ('.json', '.xyz'):
            assert not re.search(r'[A-Za-z]:\\|/Users/|/home/[^/]+/', path.read_text(encoding='utf-8-sig'))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        return registered(target, 'ORIGINAL_BYTES', [source(bundle, path, root)])

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

    def descriptor(array, member, origin):
        return {'npz_member': member, 'shape': list(array.shape), 'dtype': array.dtype.str,
                'sha256': audit.member_sha256(array), 'source': origin}

    manifest = {'schema': 'numerical-witness-package-v1', 'created_date': '2026-10-10',
        'scope': 'READ_ONLY_NUMPY_REVIEW_OF_EXISTING_SAVED_ARRAYS', 'scientific_reexecution': False,
        'public_parent_records': [], 'witnesses': {}, 'limitations': [
            'Selected witnesses do not establish all scientific services, roots, variational stationarity, wavefunction stability or physical bond energies.',
            'Derived subsets have their own hashes; omitted source file hashes are not the derived payload hashes.',
            'Saved semilocal XC energy and grid counts are not reintegrated; no ERI or grid payload is included.']}
    for rel in ('validation/molecular-service/deployment-20261008.public.json', 'validation/user-molecule/seed-v2-20261007.public.json',
                'validation/local-runtime-framework-20261007.public.json'):
        path = REPOSITORY/rel
        manifest['public_parent_records'].append({'path': rel, 'size_bytes': path.stat().st_size, 'sha256': audit.sha256(path)})
    result = audit.strict_json(water/'output/calculation/result.json')
    host = audit.strict_json(water/'host-run-manifest.json')
    execution = audit.strict_json(water/'host-execution.json')
    image = audit.strict_json(water/'image-inspect.json')
    deployment = audit.strict_json(REPOSITORY/'validation/molecular-service/deployment-20261008.public.json')
    assert audit.sha256(water/'output/calculation/result.json') == deployment['cases']['water']['result_sha256']
    assert audit.sha256(water/'host-run-manifest.json') == deployment['cases']['water']['host_manifest_sha256']
    files = {}
    for key, rel, name in [('record', 'output/calculation/result.json', 'result.json'),
            ('arrays', 'output/calculation/orbitals-density.npz', 'orbitals-density.npz'),
            ('geometry', 'input-snapshot/molecule.xyz', 'molecule.xyz'),
            ('request', 'input-snapshot/request.json', 'request.json'),
            ('host_manifest', 'host-run-manifest.json', 'host-run-manifest.json'),
            ('image_identity', 'image-inspect.json', 'image-inspect.json')]:
        path = water/rel
        if key != 'host_manifest':
            assert host['output_sha256'][rel] == audit.sha256(path)
        files[key] = copy_original(path, package/'ordinary-water'/name,
                                  '20261008-general-molecular-single-point/production-runs/'+water.name, water)
    with np.load(water/'output/calculation/orbitals-density.npz', allow_pickle=False) as archive:
        members = {key: descriptor(archive[key], key, {'source_file': 'output/calculation/orbitals-density.npz',
                     'source_npz_member': key, 'original_member_sha256': audit.member_sha256(archive[key])}) for key in archive.files}
    manifest['witnesses']['ordinary-water'] = {'kind': 'ordinary-rhf', 'files': files, 'array_members': members,
        'provenance': {'original_result_sha256': audit.sha256(water/'output/calculation/result.json'),
            'host_manifest_sha256': audit.sha256(water/'host-run-manifest.json'),
            'source_snapshot_sha256': result['execution_identity']['source_snapshot_sha256'],
            'image_id': image['Id'], 'image_build_runtime_commit': result['execution_identity']['runtime_commit'],
            'host_launcher_runtime_commit': execution['host_identity']['runtime_source_head'],
            'dependency_lock_sha256': result['execution_identity']['dependency_lock_sha256'],
            'software_at_original_execution': result['software'], 'original_host_status': execution['status'],
            'original_container_exit_code': execution['container_exit_code'], 'original_container_removed': execution['container_removed'],
            'host_execution_original': source('20261008-general-molecular-single-point/production-runs/'+water.name, water/'host-execution.json', water)},
        'missing_or_not_included': ['No independent-engine validation in this witness', 'Wavefunction stability/localization not executed',
             'Container logs, guard/resource receipts and additional worker output are omitted; original host manifest registers their hashes']}
    base = seed/'live-a1/output/production_copy'
    raw, evaluations = audit.strict_json(base/'result.json'), audit.strict_json(base/'evaluations.json')
    selected_sources = []
    for name in ('result.json', 'result.npz', 'evaluations.json', 'evaluations.npz'):
        path = base/name
        assert audit.sha256(path) == final_rows[path.relative_to(seed).as_posix()]['sha256']
        selected_sources.append(source(seed.name, path, seed))
    assert audit.sha256(base/'result.npz') == raw['raw_array_archive']['sha256']
    assert audit.sha256(base/'evaluations.npz') == evaluations['raw_array_archive']['sha256']
    operator = raw['operator_identity_contract']
    assert audit.sha256(ordinary/'ordinary-reference.npz') == operator['source_provenance']['ordinary_arrays']['sha256']
    true = evaluations['true_evaluation_at_returned_density']
    selected = {'returned_density': evaluations['returned_density'], 'true_evaluation_at_returned_density': true,
                'masked_overlap': evaluations['masked_overlap'], 'masked_hcore': evaluations['masked_hcore'], 'matrix_mask': evaluations['matrix_mask']}
    with np.load(base/'evaluations.npz', allow_pickle=False) as archive:
        decoded = audit.decode_arrays(selected, archive)
    with np.load(base/'result.npz', allow_pickle=False) as archive:
        density = audit.decode_arrays(raw['solver_result']['density'], archive)
    assert np.array_equal(density, decoded['returned_density'])
    assert np.array_equal(density, decoded['true_evaluation_at_returned_density']['requested_density'])
    identity, value = audit.density_id(density), true['value']
    assert all(identity == item for item in (raw['solver_result']['final_density_id'], evaluations['returned_density_id'],
                                            true['requested_density_id'], value['density_id']))
    arrays = {'density': density, 'overlap_masked': decoded['masked_overlap'], 'hcore_masked': decoded['masked_hcore'],
              'matrix_delete_mask': decoded['matrix_mask']}
    descriptors = {'density': raw['solver_result']['density'], 'overlap_masked': evaluations['masked_overlap'],
                   'hcore_masked': evaluations['masked_hcore'], 'matrix_delete_mask': evaluations['matrix_mask']}
    for member, name in [('fock_masked', 'fock'), ('raw_fock', 'raw_fock'), ('coulomb', 'coulomb_matrix'),
                         ('exchange', 'exchange_matrix'), ('xc_potential', 'xc_potential')]:
        arrays[member] = decoded['true_evaluation_at_returned_density']['value'][name]
        descriptors[member] = value[name]
    with np.load(ordinary/'ordinary-reference.npz', allow_pickle=False) as archive:
        for member, name, original in [('overlap_physical', 'overlap', 'physical_overlap'), ('hcore_physical', 'hcore', 'physical_hcore')]:
            array = archive[name]
            assert audit.member_sha256(array) == operator['array_identities'][original]['sha256']
            arrays[member] = array
    members = {}
    for member, array in arrays.items():
        if member in descriptors:
            desc = descriptors[member]
            origin = {'source_file': 'live-a1/output/production_copy/'+('result.npz' if member == 'density' else 'evaluations.npz'),
                      'source_record_path': desc['record_path'], 'source_npz_member': desc['npz_member'], 'original_member_sha256': desc['sha256']}
        else:
            origin = {'source_file': '20261005-user-molecule-solver-v2/numerical-a1/pilot-ethene/ordinary-reference.npz',
                      'source_npz_member': 'overlap' if member == 'overlap_physical' else 'hcore', 'original_member_sha256': audit.member_sha256(array)}
        members[member] = descriptor(array, member, origin)
    folder = package/'conditional-ethene-v2'
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(folder/'returned-endpoint.npz', **arrays)
    energy_names = ('one_electron_energy', 'coulomb_energy', 'exact_exchange_energy', 'semilocal_xc_energy',
                    'electronic_energy', 'total_energy', 'nuclear_repulsion')
    missing = ['Semilocal XC energy/grid count saved scalars; no reintegration', 'ERI contractions not repeated; saved J/K retained',
               'Original SciPy generalized eigenvectors/mapped density not retained; NumPy mapping is a distinct diagnostic',
               'No root search, new F(D), wavefunction stability or physical bond-energy claim']
    snapshot = {'schema': 'conditional-rejected-endpoint-witness-v1',
        'derivation': 'SELECTED_FIELDS_AND_ARRAY_MEMBERS_FROM_FROZEN_ORIGINALS_NOT_AN_ORIGINAL_RESULT',
        'method': {'basis': 'sto-3g', 'xc': 'B3LYPG', 'grid_level_at_original_execution': 2, 'condition': 'cross-fragment-pi-2011-v1'},
        'expected_electrons': 16, 'exact_exchange_fraction': .2,
        'returned_density_binding': {'solver_final_density_id': raw['solver_result']['final_density_id'],
            'returned_density_id': evaluations['returned_density_id'], 'requested_density_id': true['requested_density_id'],
            'value_density_id': value['density_id'], 'identity_method': 'SHA256(domain AI4OrgChem-density-v1 + NUL + little-endian uint64 shape + little-endian binary64 C bytes)',
            'result_density_member_sha256': raw['solver_result']['density']['sha256'],
            'evaluation_requested_density_member_sha256': true['requested_density']['sha256']},
        'operator_source': value['operator_source'], 'energy_ledger': {key: value[key] for key in energy_names},
        'electron_counts': {'masked_metric': value['masked_metric_electron_count'], 'physical_metric': value['physical_metric_electron_count'],
                           'grid': value['grid_electron_count'], 'grid_role': 'SAVED_SCALAR_NOT_REINTEGRATED_NO_GRID_PAYLOAD'},
        'saved_endpoint_gate': raw['solver_result']['endpoint_gate'], 'comparison_available': raw['comparison_available'],
        'production_activation': raw['production_activation'], 'research_acceptance': raw['research_acceptance'],
        'stability_status': raw['solver_result']['stability_status'], 'variational_status': raw['solver_result']['variational_status'],
        'stop_reason': raw['stop_reason'], 'arrays': members, 'missing_or_not_recomputed': missing}
    write(folder/'snapshot.json', snapshot)
    cached = source('20261005-user-molecule-solver-v2/numerical-a1/pilot-ethene', ordinary/'ordinary-reference.npz', ordinary)
    files = {'record': registered(folder/'snapshot.json', 'DERIVED_SELECTED_FIELDS', selected_sources,
                ['Keep matched returned-density evaluation/gate; omit callback history, grids, ERI and absolute local paths']),
             'arrays': registered(folder/'returned-endpoint.npz', 'DERIVED_SELECTED_MEMBERS', [selected_sources[1], selected_sources[3], cached],
                ['Copy selected stored array bytes without rounding/recomputation; rename NPZ members'])}
    manifest['witnesses']['conditional-ethene-v2'] = {'kind': 'conditional-rejected-endpoint', 'files': files, 'array_members': members,
        'provenance': {'sealed_delivery_directory': seed.name, 'sealed_manifest_sha256': audit.sha256(seed/'FINAL_MANIFEST.json'),
            'sealed_manifest_original': source(seed.name, seed/'FINAL_MANIFEST.json', seed),
            'original_result_sha256': audit.sha256(base/'result.json'), 'original_evaluations_sha256': audit.sha256(base/'evaluations.json'),
            'local_delivery_commit': final['local_delivery_commit'], 'scientific_execution_runtime_commit': final['scientific_execution_commit'],
            **{key: operator[key] for key in ('science_commit', 'science_baseline_commit', 'image_id', 'request_sha256',
                                               'profile_sha256', 'condition_rules_sha256', 'source_manifest_sha256')},
            'image_build_runtime_commit': operator['image_build_commit'],
            'operator_array_identities': {key: operator['array_identities'][key] for key in ('physical_overlap', 'physical_hcore')},
            'ordinary_cache_source': cached, 'evidence_kind': 'LOCAL_BYTES_AND_DECLARED_EXECUTION_IDENTITIES_NOT_ENGINE_AUTHENTICATION'},
        'missing_or_not_included': missing}
    assert all(audit.sha256(path) == expected for path, expected in originals.items()), 'Original evidence changed'
    manifest['extraction_original_readback'] = {'checked_original_file_count': len(originals), 'all_original_sha256_unchanged': True,
                                              'new_scientific_calls': 0}
    write(package/'manifest.json', manifest)
    return {'payloads': sum(len(row['files']) for row in manifest['witnesses'].values()),
            'original_files_readback': len(originals), 'originals_unchanged': True, 'new_scientific_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('water', 'seed', 'ordinary-cache'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    with audit.numerical_only_imports():
        result = extract(args.water.resolve(), args.seed.resolve(), args.ordinary_cache.resolve(), args.package.resolve())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
