"""Acceptance-only numerical worker. Production profiles/source remain immutable."""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.user_molecule.records import load, save, file_hash
from runtime.user_molecule.acceptance_resources import collect_cgroup
from runtime.user_molecule.acceptance_metrics import finite_scalar


class GateFailure(ValueError):
    pass


def import_audit():
    results = []
    for name in ('reference/user_molecule.py', 'reference/ordinary_molecule.py'):
        text = (ROOT/name).read_text()
        imports = []
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imports += [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or '')
        forbidden = [name for name in imports if name.startswith('ai4orgchem')]
        if forbidden or any(token in text for token in ('run_p09_conditional_rks', '_evaluate_density')):
            raise ValueError('Independent reference import/call audit failed')
        results.append({'path': name, 'sha256': file_hash(ROOT/name), 'imports': imports, 'status': 'PASS_STATIC_IMPORT_AND_DIRECT_NAME_AUDIT'})
    return results


def unit_tests(output):
    audit = import_audit()
    save(output/'resource-observation.json',collect_cgroup())
    # Fail immediately if any test starts scientific work, including indirectly.
    from pyscf import scf, dft, gto
    def forbidden(*args, **kwargs):
        raise AssertionError('Scientific operation forbidden in engineering unit tests')
    scf.hf.SCF.kernel = forbidden
    scf.hf.kernel = forbidden
    dft.gen_grid.Grids.build = forbidden
    gto.Mole.intor = forbidden
    gto.Mole.intor_by_shell = forbidden
    suite = unittest.TestSuite()
    for pattern in ('test_user_molecule_*.py', 'test_reference_user_molecule.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
    ids = []
    def flatten(value):
        for item in value:
            if isinstance(item, unittest.TestSuite):
                flatten(item)
            else:
                ids.append(item.id())
    flatten(suite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    save(output/'resource-observation-final.json',collect_cgroup())
    save(output/'unit-tests.json', {'status': 'PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
        'executions': result.testsRun, 'ids': ids, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'import_audit': audit, 'scientific_work': 'FORBIDDEN'})
    return 0 if result.wasSuccessful() and not result.skipped else 1


def scientific(args):
    import numpy as np
    from scipy.linalg import eigh
    from runtime.user_molecule.input import read_request
    from runtime.user_molecule.preflight import verify_source
    from reference import user_molecule as ref
    from reference import ordinary_molecule as ordinary_ref
    from ai4orgchem.qm import user_molecule_adapter as tested
    from ai4orgchem.qm.p09_conditional_scf import run_p09_conditional_rks, _evaluate_density
    from ai4orgchem.qm.p09_ao_classification import apply_interfragment_pi_matrix_mask
    from ai4orgchem.qm.p09_energy_assembly import apply_eri_tensor_mask
    contract_path = ROOT/'validation/user-molecule/w05-w06/acceptance-contract-v3.json'
    contract = load(contract_path)
    fixture = next(f for f in contract['fixtures'] if f['id'] == args.fixture)
    source = Path('/opt/ai4orgchem')
    source_lock = verify_source(ROOT, source)
    bundle = read_request(ROOT/fixture['request'], load(ROOT/'schemas/user-molecule-request-v1.json'))
    request, atoms = bundle['request'], bundle['atoms']
    profile_path = ROOT/'profiles/user-molecule'/ (request['calculation_profile']+'.json')
    profile = load(profile_path)
    if profile['compute_enabled'] is not False:
        raise ValueError('Acceptance driver requires blocked production profile')
    # A new acceptance request identity, never an in-place production profile edit.
    request = dict(request, resources={'threads': 1, 'memory_limit_mib': contract['budget']['memory_mib'], 'wall_time_limit_seconds': contract['budget']['process_seconds']})
    for name, expected in profile['expected_dependencies'].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError('Pinned dependency mismatch: '+name)
    output = args.output
    save(output/'request.acceptance.json', request)
    (output/'molecule.xyz').write_bytes(bundle['xyz_bytes'])
    save(output/'profile.unchanged.json', profile)
    identity = {'geometry_sha256': bundle['xyz_sha256'], 'source_request_sha256': bundle['request_sha256'],
        'acceptance_request_sha256': file_hash(output/'request.acceptance.json'), 'profile_sha256': file_hash(profile_path),
        'rules_sha256': source_lock['condition_rules_sha256'], 'science_commit': source_lock['source_commit'],
        'runtime_test_commit': os.environ['AI4ORGCHEM_RUNTIME_TEST_COMMIT'],
        'image_id': os.environ['AI4ORGCHEM_IMAGE_ID'], 'contract_sha256': file_hash(contract_path),
        'dependencies': profile['expected_dependencies'], 'mode': 'SEQUENTIAL_ACCEPTANCE_BUNDLE_V1'}
    result = {'fixture': fixture, 'identities': identity, 'import_audit': import_audit(),
        'purpose': contract['purpose'], 'method_review_status': 'PENDING_REAL_REVIEW',
        'research_status': 'NOT_REVIEWED', 'production_activation': False, 'stability_status': 'NOT_EXECUTED',
        'variational_status': 'NOT_ESTABLISHED', 'comparison_available': False, 'delta_hartree': None,
        'checks': [], 'phases': [], 'status': 'RUNNING'}
    save(output/'result.json', result)
    started = time.monotonic()
    stop = threading.Event()
    def sample():
        with (output/'cgroup-samples.jsonl').open('a', encoding='utf-8') as stream:
            while not stop.is_set():
                stream.write(json.dumps({'elapsed_seconds': time.monotonic()-started, 'cgroup': collect_cgroup()}, allow_nan=False)+'\n')
                stream.flush()
                stop.wait(.2)
    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    def phase(name):
        result['phases'].append({'name': name, 'elapsed_seconds': time.monotonic()-started, 'cgroup': collect_cgroup()})
        save(output/'result.json', result)
        print(name, flush=True)
    def clean(value):
        if isinstance(value, np.ndarray):
            raise TypeError('Arrays require separate NPZ')
        if isinstance(value, (np.integer, np.bool_)):
            return value.item()
        if isinstance(value, (float, np.floating)):
            return float(value) if np.isfinite(value) else None
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [clean(item) for item in value]
        return value
    def split(name, raw):
        arrays = {key: value for key, value in raw.items() if isinstance(value, np.ndarray)}
        np.savez(output/(name+'.npz'), **arrays)
        record = clean({key: value for key, value in raw.items() if key not in arrays})
        record['undefined_diagnostics'] = [{'field': f'history[{i}].energy_change_hartree',
            'reason': 'NO_PREVIOUS_CYCLE_ENERGY'} for i, row in enumerate(raw.get('history', []))
            if row.get('energy_change_hartree') is not None and not np.isfinite(row['energy_change_hartree'])]
        if name.startswith('conditional-'):
            record['gap_operator_source']='LAST_DIAGONALIZATION_POSSIBLY_DIIS'
            record['final_operator_source']='RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS'
        save(output/(name+'.json'), record)
        return record
    def gate(name, value, threshold, units, formula, operator='NOT_APPLICABLE', exact=False):
        number = finite_scalar(value)
        valid = number is not None
        result['checks'].append({'metric_id': name, 'value': number,
            'threshold': threshold, 'threshold_version': contract['version'], 'formula_version': formula,
            'units': units, 'required': True, 'operator_source': operator,
            'pass': bool(valid and (number == threshold if exact else number <= threshold))})
    def truth(name, condition):
        gate(name, 0 if condition else 1, 0, 'boolean_failure_count', 'EXACT_BOOLEAN_V1', exact=True)
    def matrices(prefix, left, right, names, maxabs, fro=None):
        for name in names:
            residual = np.asarray(left[name])-np.asarray(right[name])
            gate(prefix+'.'+name+'.maxabs', float(np.max(np.abs(residual), initial=0)), maxabs, 'native_AO', 'MAXABS_DIFFERENCE_V1')
            if fro is not None:
                gate(prefix+'.'+name+'.fro', float(np.linalg.norm(residual)), fro, 'native_AO', 'FROBENIUS_DIFFERENCE_V1')
    component_keys = {'one_electron': 'one_electron_energy_hartree', 'coulomb': 'coulomb_energy_hartree',
        'exact_exchange': 'exact_exchange_energy_hartree', 'semilocal_xc': 'semilocal_xc_energy_hartree',
        'nuclear_repulsion': 'nuclear_repulsion_hartree'}
    def components(prefix, ref_components, production, threshold):
        for key, pkey in component_keys.items():
            gate(prefix+'.'+key, abs(ref_components[key]-production[pkey]), threshold, 'Eh', 'ABS_COMPONENT_DIFFERENCE_V1')
    def qualification(prefix, record, conditional):
        tests = tested.metrics_qualified(record, mol.nelectron, profile, conditional)
        for key, passed in tests.items():
            truth(prefix+'.'+key, passed)
        return all(tests.values())
    def final_gap(prefix, fock, overlap):
        values = eigh(fock, overlap, eigvals_only=True)
        gap = float(values[mol.nelectron//2]-values[mol.nelectron//2-1])
        gate(prefix+'.final_non_diis_gap', -gap, -contract['engineering_gates']['final_non_diis_gap_minimum_hartree'],
            'Eh', 'NEGATED_OCC_VIRTUAL_GAP_V1', 'RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS')
        return gap
    try:
        memory_fields = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        vm_available = int(memory_fields['MemAvailable'].strip().split()[0])*1024
        result['vm_available_memory_bytes_before_scf'] = vm_available
        if vm_available < (contract['budget']['memory_mib']+contract['budget']['available_headroom_mib'])*1024**2:
            raise GateFailure('VM observed available memory below frozen process budget plus headroom')
        coordinates = np.array([atom[1] for atom in atoms])
        minimum_distance = min(float(np.linalg.norm(a-b)) for i,a in enumerate(coordinates) for b in coordinates[i+1:])
        gate('T01.minimum_distance', -minimum_distance, -contract['engineering_gates']['minimum_pair_distance_angstrom'], 'angstrom', 'NEGATED_PAIR_MINIMUM_V1')
        if minimum_distance < contract['engineering_gates']['minimum_pair_distance_angstrom']:
            raise GateFailure('Acceptance collision guard failed before scientific work')
        independent = ordinary_ref.run_ordinary(request, atoms, profile, progress=phase)
        np.savez(output/'ordinary-reference.npz', **independent.arrays)
        save(output/'ordinary-reference.json', independent.record)
        phase('TESTED_ORDINARY_SCF')
        mol, mf, descriptors = tested.build(request, atoms, profile)
        result['nao'] = int(mol.nao_nr())
        truth('nao.reference_limit', mol.nao_nr() <= contract['engineering_gates']['maximum_reference_nao'])
        energy = float(mf.kernel())
        result['grid_points'] = len(mf.grids.weights)
        d = np.asarray(mf.make_rdm1())
        s, h = mf.get_ovlp(), mf.get_hcore()
        j, k = mf.get_jk(mol, d, hermi=1)
        ne, exc, vxc = mf._numint.nr_rks(mol, mf.grids, mf.xc, d, hermi=1, max_memory=mf.max_memory)
        hybrid = float(mf._numint.rsh_and_hybrid_coeff(mf.xc, spin=0)[2])
        f = np.asarray(mf.get_fock(dm=d, cycle=-1, diis=None))
        trace = lambda matrix: float(np.sum(matrix*d.T))
        ordinary = {'converged': bool(mf.converged), 'total_energy_hartree': energy,
            'one_electron_energy_hartree': trace(h), 'coulomb_energy_hartree': .5*trace(j),
            'exact_exchange_energy_hartree': -.25*hybrid*trace(k), 'semilocal_xc_energy_hartree': float(exc),
            'nuclear_repulsion_hartree': float(mol.energy_nuc()), 'physical_metric_electron_count': trace(s),
            'grid_electron_count': float(ne), 'final_commutator_frobenius_norm': float(np.linalg.norm(f@d@s-s@d@f)),
            'closed_shell_idempotency_relative_residual': float(np.linalg.norm(d@s@d-2*d)/max(np.linalg.norm(d),1))}
        ordinary['energy_component_closure_residual_hartree'] = abs(sum(ordinary[key] for key in component_keys.values())-energy)
        save(output/'ordinary-tested.json', ordinary)
        np.savez(output/'ordinary-tested.npz', density=d, Fraw=f, overlap=s, hcore=h, grid_coords=mf.grids.coords, grid_weights=mf.grids.weights)
        gate('T04.energy', abs(energy-independent.record['total_energy_hartree']), contract['T04']['total_energy_hartree'], 'Eh', 'ABS_TOTAL_ENERGY_DIFFERENCE_V1')
        components('T04.components', independent.record['components_hartree'], ordinary, contract['T04']['component_hartree'])
        gate('T04.density', float(np.linalg.norm(d-independent.arrays['density'])), contract['T04']['density_frobenius'], 'density_AO', 'FROBENIUS_DIFFERENCE_V1')
        gate('T04.fock', float(np.linalg.norm(f-independent.arrays['Fraw'])), contract['T04']['fock_frobenius'], 'Eh_AO', 'FROBENIUS_DIFFERENCE_V1')
        gate('T04.electrons', abs(trace(s)-independent.record['physical_metric_electron_count']), contract['T04']['electron_count_abs'], 'electrons', 'ABS_ELECTRON_DIFFERENCE_V1')
        truth('T04.grid_coords_exact', np.array_equal(mf.grids.coords, independent.arrays['grid_coords']))
        truth('T04.grid_weights_exact', np.array_equal(mf.grids.weights, independent.arrays['grid_weights']))
        truth('T04.AO_labels_exact', mol.ao_labels(fmt=False) == independent.context.mol.ao_labels(fmt=False))
        truth('T04.AO_descriptors_exact', [(a.kind,a.group) for a in independent.context.aos] == [(a.kind,a.fragment) for a in descriptors])
        if not qualification('ordinary.tested', ordinary, False):
            raise GateFailure('Ordinary qualification failed; conditional work blocked')
        # Independent ordinary metrics use the same frozen thresholds, not a self-generated tolerance.
        if not qualification('ordinary.reference', independent.record, False):
            raise GateFailure('Independent ordinary qualification failed; conditional work blocked')
        if not all(item['pass'] for item in result['checks']):
            raise GateFailure('Ordinary comparison/identity gate failed; conditional work blocked')
        d0 = independent.arrays['density'].copy()
        np.save(output/'common-D0.npy', d0, allow_pickle=False)
        result['common_density_sha256'] = file_hash(output/'common-D0.npy')
        entries = ref.load_rules(source/'configs/qm/p09_exchange_integral_classes_v0.1.yaml', source_lock['condition_rules_sha256'])
        aos = independent.context.aos
        raw = independent.arrays['eri']
        masked, deleted = ref.mask_integrals(raw, aos, entries)
        ptensor, pmask = apply_eri_tensor_mask(raw, descriptors, entries)
        st, ht = ref.project(s,aos), ref.project(h,aos)
        gate('T02.kappa', float(np.linalg.cond(st)), contract['engineering_gates']['masked_overlap_condition_number_max'], 'dimensionless', 'KAPPA2_MASKED_OVERLAP_V1')
        truth('P11.positive_overlap', float(np.linalg.eigvalsh(st).min()) > 0)
        if float(np.linalg.eigvalsh(st).min()) <= 0 or np.linalg.cond(st) > contract['engineering_gates']['masked_overlap_condition_number_max']:
            raise GateFailure('Masked overlap guard failed; conditional work blocked')
        phase('SAME_D_OPERATOR_LEDGER')
        callback, _ = ref.original_grid_xc(independent.context.mean_field)
        same_ref = ref.evaluate(d0, ht, st, s, masked, aos, hybrid, mol.energy_nuc(), callback)
        same_prod = _evaluate_density(mean_field=mf, density=d0, masked_hcore=apply_interfragment_pi_matrix_mask(h,descriptors),
            masked_overlap=apply_interfragment_pi_matrix_mask(s,descriptors), physical_overlap=s, masked_eri=ptensor,
            descriptors=descriptors, exact_exchange_fraction=hybrid)
        split('same-D-reference', same_ref); split('same-D-tested', same_prod)
        matrices('T05.mask', {'eri':masked,'h':ht,'s':st}, {'eri':ptensor,'h':apply_interfragment_pi_matrix_mask(h,descriptors),'s':apply_interfragment_pi_matrix_mask(s,descriptors)}, ('eri','h','s'), 0.)
        truth('T05.deleted_count', deleted == int(np.count_nonzero(pmask)))
        mapped = {'J':same_prod['coulomb_matrix'],'K':same_prod['exchange_matrix'],'Vxc':same_prod['xc_potential'],'Fraw':same_prod['raw_fock'],'Fcond':same_prod['fock']}
        matrices('T05.operator',same_ref,mapped,tuple(mapped),contract['T05']['matrix_max_abs'],contract['T05']['matrix_frobenius'])
        for rkey,pkey in component_keys.items():
            key = pkey.removesuffix('_hartree')
            if rkey == 'nuclear_repulsion':
                value = mol.energy_nuc()
            else:
                value = same_prod[key]
            gate('T05.component.'+rkey, abs(same_ref['components_hartree'][rkey]-value),contract['T05']['component_hartree'],'Eh','ABS_COMPONENT_DIFFERENCE_V1')
        gate('T05.total',abs(same_ref['total_energy_hartree']-same_prod['total_energy']),contract['T05']['total_energy_hartree'],'Eh','ABS_TOTAL_ENERGY_DIFFERENCE_V1')
        gate('T05.grid_electrons',abs(same_ref['grid_electron_count']-same_prod['grid_electron_count']),contract['T05']['grid_electron_count_abs'],'electrons','ABS_ELECTRON_DIFFERENCE_V1')
        if not all(item['pass'] for item in result['checks']):
            raise GateFailure('Same-D operator/ledger gate failed; conditional SCF blocked')
        del pmask, ptensor, masked, same_ref, same_prod, mapped
        production = {}
        for mode, controlled in (('single',True),('copy',False)):
            phase('PRODUCTION_CONDITIONAL_'+mode.upper())
            settings = dict(profile['conditional'],memory_controlled_eri=controlled)
            value = run_p09_conditional_rks(mf,descriptors,entries,initial_density=d0,**settings)
            production[mode] = value
            record = split('conditional-'+mode,value)
            qualification('conditional.'+mode, record, True)
            # Reconstruct final operator for explicit no-DIIS spectrum diagnostics.
            tensor,_ = apply_eri_tensor_mask(raw,descriptors,entries)
            final = _evaluate_density(mean_field=mf,density=value['density'],masked_hcore=ht,masked_overlap=st,
                physical_overlap=s,masked_eri=tensor,descriptors=descriptors,exact_exchange_fraction=hybrid,
                optimize_eri_contractions=not controlled)
            production[mode]['acceptance_final_F'] = final['fock']
            split('conditional-'+mode+'-final-operator',final)
            result[mode+'_final_non_diis_gap_hartree'] = final_gap(mode,final['fock'],st)
            del tensor,final
        gate('P12.storage_energy',abs(production['single']['total_energy_hartree']-production['copy']['total_energy_hartree']),contract['P12']['energy_difference_hartree'],'Eh','ABS_TOTAL_ENERGY_DIFFERENCE_V1')
        gate('P13.storage_density',float(np.linalg.norm(production['single']['density']-production['copy']['density'])),contract['P13']['density_difference_frobenius'],'density_AO','FROBENIUS_DIFFERENCE_V1')
        truth('storage.deleted_count', production['single']['deleted_eri_count'] == production['copy']['deleted_eri_count'])
        independent_conditional = ordinary_ref.run_conditional(independent,source/'configs/qm/p09_exchange_integral_classes_v0.1.yaml',source_lock['condition_rules_sha256'],settings=profile['conditional'],progress=phase)
        save(output/'conditional-reference.json',independent_conditional.record)
        np.savez(output/'conditional-reference.npz',**independent_conditional.arrays)
        crecord,carrays = independent_conditional.record,independent_conditional.arrays
        # Convert only named independently computed metric fields for common qualification.
        qualification('conditional.reference',crecord,True)
        gate('T06.energy',abs(crecord['total_energy_hartree']-production['single']['total_energy_hartree']),contract['T06']['total_energy_hartree'],'Eh','ABS_TOTAL_ENERGY_DIFFERENCE_V1')
        components('T06.components',crecord['components_hartree'],production['single'],contract['T06']['component_hartree'])
        gate('T06.density',float(np.linalg.norm(carrays['density']-production['single']['density'])),contract['T06']['density_frobenius'],'density_AO','FROBENIUS_DIFFERENCE_V1')
        gate('T06.fock',float(np.linalg.norm(carrays['Fcond']-production['single']['acceptance_final_F'])),contract['T06']['fock_frobenius'],'Eh_AO','FROBENIUS_DIFFERENCE_V1')
        for mode,value in [('reference',carrays),('single',production['single']),('copy',production['copy'])]:
            occ = value['mo_occupations']
            truth(mode+'.global_closed_shell_occupations', np.all((occ==0)|(occ==2)) and np.sum(occ)==mol.nelectron)
        result['reference_final_non_diis_gap_hartree'] = final_gap('reference',carrays['Fcond'],st)
        result['nao'] = int(mol.nao_nr())
        result['grid_points'] = len(mf.grids.weights)
        result['numerical_evidence_pass'] = all(item['pass'] for item in result['checks'])
        result['status'] = 'PASS_ACCEPTANCE_ONLY' if result['numerical_evidence_pass'] else 'FAIL_NUMERICAL_GATES'
        result['failed_metric_ids'] = [item['metric_id'] for item in result['checks'] if not item['pass']]
        result['diagnostic_delta_hartree'] = energy-production['single']['total_energy_hartree']
        result['endpoint_classification'] = 'COMPARABLE_WITHIN_FROZEN_ENGINEERING_THRESHOLDS' if result['numerical_evidence_pass'] else 'ROOT_OR_NUMERICAL_GATES_NOT_QUALIFIED'
    except Exception as exc:
        result.update(status='FAIL_NUMERICAL_GATES' if isinstance(exc,GateFailure) else 'FAIL_EXECUTION', error=type(exc).__name__+': '+str(exc),
            failed_metric_ids=[item['metric_id'] for item in result['checks'] if not item['pass']])
        (output/'exception.log').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        result['research_status']='NOT_REVIEWED' if result['status']=='PASS_ACCEPTANCE_ONLY' else 'NOT_QUALIFIED'
        phase('FINAL_RECORD')
        stop.set(); monitor.join(timeout=2)
        result['elapsed_seconds'] = time.monotonic()-started
        result['cgroup_final'] = collect_cgroup()
        save(output/'result.json',result)
    return 0 if result['status']=='PASS_ACCEPTANCE_ONLY' else 30


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fixture')
    parser.add_argument('--tests-only',action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.tests_only:
        return unit_tests(args.output)
    import fcntl
    with Path('/locks/quantum.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return scientific(args)


if __name__=='__main__':
    sys.exit(main())
