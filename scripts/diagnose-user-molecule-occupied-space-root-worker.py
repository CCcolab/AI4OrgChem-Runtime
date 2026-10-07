"""Prepare one explicit root-search initial density; this version never solves.

The current contract is engineering/readiness only.  There is no live dispatch,
callback journal, NR allowance or scientific root budget in this worker.  All
four saved seeds are verified before selecting index2, theta=-0.10.  Historical
F evidence is read only as provenance and never becomes a current evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback


SELECTED_DENSITY_ID = '6b0d501aba96ac5c53ca633491e105d7c5dab13836350bd6d7350437f91bd7c0'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))
        stream.flush(); os.fsync(stream.fileno())


def response_helper_definitions(root):
    """Reuse saved-array/platform helpers without either retained worker main."""
    spec = importlib.util.spec_from_file_location('retained_occupied_response_helpers',
        root/'scripts/diagnose-user-molecule-occupied-space-response-worker.py')
    if spec is None or spec.loader is None:
        raise ValueError('Retained response helper definitions unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_saved_initial(family, declared):
    """Bind the actual saved second D; never construct or replace a seed here."""
    import numpy as np
    from runtime.user_molecule.occupation_response import density_id
    from runtime.user_molecule.occupied_space_seeds import array_identity
    if (not isinstance(declared, dict) or declared.get('seed_index') != 2 or
            declared.get('angle_rad') != -.1 or declared.get('density_id') != SELECTED_DENSITY_ID):
        raise ValueError('Only the separately declared second seed at theta=-0.10 is admitted')
    rows = family.get('seeds', ())
    if len(rows) != 4:
        raise ValueError('The complete four-seed family is required before selection')
    selected = rows[1]
    if selected.get('seed_index') != 2 or selected.get('angle_rad') != -.1:
        raise ValueError('Saved source seed index/angle differs')
    array = np.asarray(selected.get('density'))
    actual_id = density_id(array)
    if actual_id != SELECTED_DENSITY_ID or actual_id != selected.get('density_id'):
        raise ValueError('Selected actual saved D bytes differ from the fixed density-v1 identity')
    actual_array = array_identity(array)
    for key in ('shape', 'dtype', 'sha256'):
        expected = declared.get('array_identity', {}).get(key)
        value = actual_array[key]
        if (list(expected) if key == 'shape' and expected is not None else expected) != value:
            raise ValueError('Selected actual array identity differs from the candidate contract: '+key)
    result = array.copy(); result.setflags(write=False)
    return result


def preparation_worker(args, output, contract, contract_sha, helpers):
    import numpy as np
    from pyscf import dft, gto, scf
    from pyscf.dft import numint
    from reference.ordinary_molecule import ReferenceResult
    from reference.residual_molecule import PreparedResidualReference
    from runtime.user_molecule.residual_bridge import PreparedResidualBridge, array_identity
    from runtime.user_molecule.residual_candidate import density_id
    from runtime.user_molecule.residual_seed_preparation import prepare_cached_context
    from runtime.user_molecule.residual_preparation import create_bridge_contract
    from runtime.user_molecule.occupied_space_response import preflight_occupied_space_response
    from runtime.user_molecule.occupied_space_root_contract import validate_input_binding
    from runtime.user_molecule import residual_candidate, solver_candidate
    from reference import residual_candidate as reference_solver, residual_budgeted_candidate as old_budgeted
    from reference import user_molecule as reference_equations, user_molecule_v2 as reference_equations_v2
    from ai4orgchem.qm import p09_conditional_scf as source_equations
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    from runtime.user_molecule.input import strict_json
    import scipy.optimize
    import scipy.optimize._numdiff

    started, forbidden, bindings = time.monotonic(), [], []
    def install(owner, name, label):
        if not hasattr(owner, name): raise ValueError('Required forbidden API unavailable: '+label)
        def refuse(*_args, **_kwargs):
            forbidden.append(label); raise RuntimeError('Root readiness forbids '+label)
        setattr(owner, name, refuse); bindings.append((owner, name, refuse, label))
    for owner, name, label in (
        (scf.hf.SCF, 'kernel', 'SCF.kernel'), (scf.hf.SCF, 'scf', 'SCF.scf'),
        (scf.hf, 'kernel', 'hf.kernel'), (scf.hf.RHF, 'kernel', 'RHF.kernel'),
        (scf.uhf.UHF, 'kernel', 'UHF.kernel'), (scf.rohf.ROHF, 'kernel', 'ROHF.kernel'),
        (dft.rks.RKS, 'kernel', 'RKS.kernel'), (dft.uks.UKS, 'kernel', 'UKS.kernel'),
        (dft.roks.ROKS, 'kernel', 'ROKS.kernel'), (dft.gen_grid.Grids, 'build', 'Grids.build'),
        (gto.Mole, 'intor', 'Mole.intor'), (gto.Mole, 'intor_by_shell', 'Mole.intor_by_shell'),
        (gto.Mole, 'energy_nuc', 'Mole.energy_nuc'),
        (numint.NumInt, 'nr_rks', 'NumInt.nr_rks'), (numint, 'nr_rks', 'numint.nr_rks'),
        (residual_candidate, 'solve_residual_candidate', 'old production residual solve'),
        (solver_candidate, 'iterate_candidate', 'old production iterate'),
        (solver_candidate, 'run_candidate_conditional_rks', 'old production SCF driver'),
        (reference_solver, 'solve', 'old reference solve'),
        (reference_solver, 'least_squares', 'old reference SciPy shortcut'),
        (old_budgeted, 'solve_budgeted_candidate', 'old ENGINEERING_ONLY budgeted solve'),
        (old_budgeted, 'least_squares', 'old budgeted SciPy shortcut'),
        (old_budgeted, 'approx_derivative', 'old budgeted private Jacobian shortcut'),
        (reference_equations, 'fixed_point', 'reference fixed_point'),
        (reference_equations_v2, 'fixed_point', 'reference v2 fixed_point'),
        (source_equations, 'run_p09_conditional_rks', 'source SCF driver'),
        (source_equations, '_evaluate_density', 'source single-F evaluation'),
        (scipy.optimize, 'least_squares', 'SciPy TRF'),
        (scipy.optimize._numdiff, 'approx_derivative', 'SciPy private Jacobian'),
        (PreparedResidualBridge, 'run', 'old production bridge.run'),
        (PreparedResidualBridge, 'evaluate', 'old production bridge.evaluate'),
        (PreparedResidualReference, 'run', 'old reference bridge.run'),
        (PreparedResidualReference, 'evaluate', 'prepared reference.evaluate')):
        install(owner, name, label)
    # Import only after the mature optimizer/FD APIs have been disabled.  This
    # metadata-only worker grants no exception to the new candidate's aliases.
    from reference import occupied_space_root_candidate as candidate
    install(candidate, 'solve_occupied_space_root_candidate', 'new root candidate solve')
    resource_helpers = helpers.shared_helpers(args.runtime_root)
    def changed():
        return [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
    def observe(phase):
        value = {'phase': phase, 'elapsed_seconds': time.monotonic()-started,
            'cgroup': collect_cgroup(phase=phase), 'vm_memory': resource_helpers.vm_memory()}
        with (output/'resources.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(value, allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
        if resource_helpers.resource_reasons(value['cgroup']): raise RuntimeError('Actual cgroup readiness refused')
        available = value['vm_memory']['available_bytes']
        if available is None or available < 2147483648: raise RuntimeError('At least 2GiB VM MemAvailable required')
        if forbidden or changed(): raise RuntimeError('Changed preparation guard or forbidden scientific attempt')
        return value
    versions = {name: importlib.metadata.version(name) for name in contract['expected_dependencies']}
    loaded = {name: getattr(importlib.import_module(name), '__version__', None) for name in versions}
    save(output/'dependency-identity.json', {'expected': contract['expected_dependencies'],
        'actual_distributions': versions, 'loaded_module_versions': loaded})
    if versions != contract['expected_dependencies'] or loaded != contract['expected_dependencies']:
        raise ValueError('Actual dependencies differ from the candidate contract')
    for name, digest in contract['source_file_sha256'].items():
        if sha((args.runtime_root/name).read_bytes()) != digest: raise ValueError('Source bytes changed: '+name)
    observe('BEFORE_PREPARATION')
    cached = prepare_cached_context(runtime_root=args.runtime_root, science_root=args.science_root,
        ordinary_dir=args.ordinary_dir, identity=contract)
    save(output/'legacy-basis-representation.json', cached['basis_receipt'])
    source_raw = (args.seed_input_dir/'SOURCE.json').read_bytes()
    source_arrays_raw = (args.seed_input_dir/'source-arrays.npz').read_bytes()
    seed_record_raw = (args.seed_input_dir/'prepared-seed-family.json').read_bytes()
    seed_arrays_raw = (args.seed_input_dir/'prepared-seed-family.npz').read_bytes()
    history_raw = (args.seed_input_dir/'parent-response-result.json').read_bytes()
    mdr_raw = (args.seed_input_dir/'MDR-007.json').read_bytes()
    binding = validate_input_binding(contract, source_raw, seed_record_raw, seed_arrays_raw,
        source_arrays_bytes=source_arrays_raw, history_record_bytes=history_raw, mdr_bytes=mdr_raw)
    save(output/'input-byte-binding.json', binding)
    source, family = strict_json(source_raw), helpers.load_saved_family(strict_json(seed_record_raw), seed_arrays_raw)
    context = cached['context']
    mapping = source['source_mapping']
    if mapping['ao_labels'] != context.metadata['ao_labels'] or mapping['ao_descriptors'] != context.metadata['ao_descriptors']:
        raise ValueError('Actual cached AO labels/fragments differ from saved recipe')
    import io
    source_arrays = {}
    with np.load(io.BytesIO(source_arrays_raw), allow_pickle=False) as archive:
        for name, metadata in source['arrays'].items():
            array = archive[name].copy()
            if (list(array.shape) != metadata['shape'] or array.dtype.str != metadata['dtype'] or
                    not np.isfinite(array).all() or sha(array.tobytes()) != metadata['sha256']):
                raise ValueError('Actual saved source array bytes differ: '+name)
            array.setflags(write=False); source_arrays[name] = array
    for name, field in (('base_density', 'source_density'), ('masked_overlap', 'source_masked_overlap'),
                         ('occupied_anchor', 'source_occupied_anchor'), ('virtual_anchor', 'source_virtual_anchor')):
        if not np.array_equal(source_arrays[name], family[field]): raise ValueError('Source/family array mismatch: '+name)
    if not np.array_equal(source_arrays['physical_overlap'], cached['arrays']['overlap']):
        raise ValueError('Saved physical S differs from actual original cache')
    prepared = create_bridge_contract(runtime_root=args.runtime_root, science_root=args.science_root,
        prepared_input=cached['prepared_input'], context=context, arrays=cached['arrays'], ordinary_record=cached['record'],
        runtime_test_commit=contract['runtime_test_commit'], image_id=contract['image_id'],
        image_build_commit=contract['image_build_runtime_commit'], execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC',
        initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR', ordinary_record_path=cached['record_path'],
        ordinary_arrays_path=cached['arrays_path'], maximum_evaluations=201)
    save(output/'preparation-contract.json', prepared['contract']); save(output/'prepared-mapping.json', prepared['mapping_receipt'])
    if (mapping['atom_mapping'] != prepared['mapping_receipt']['atom_mapping'] or
            mapping['profile_sha256'] != contract['profile_canonical_sha256'] or
            prepared['mapping_receipt']['profile_canonical_sha256'] != contract['profile_canonical_sha256']):
        raise ValueError('Actual original geometry/profile mapping differs from saved source')
    reference = PreparedResidualReference(ordinary=ReferenceResult(record=cached['record'], arrays=cached['arrays'], context=context),
        rule_path=args.science_root/'configs/qm/p09_exchange_integral_classes_v0.1.yaml',
        expected_sha256=prepared['contract']['condition_rules_sha256'], initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
        maximum_evaluations=201, execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC')
    if not np.array_equal(reference.overlap, source_arrays['masked_overlap']) or not np.array_equal(reference.mask, source_arrays['matrix_delete_mask']):
        raise ValueError('Actual reference metric/mask differs from the saved source')
    ready = preflight_occupied_space_response(prepared_seeds=family, overlap=reference.overlap,
        electrons=16, matrix_delete_mask=reference.mask)
    selected = select_saved_initial(family, contract['initial_density'])
    if list(ready['density_ids']) != [row['density_id'] for row in family['seeds']]:
        raise ValueError('Whole-family verification changes a saved density identity')
    resource_helpers.pack_record(output, 'actual-family-admissions', ready)
    resource_helpers.pack_record(output, 'selected-initial-density', {'density': selected,
        'density_id': density_id(selected), 'array_identity': array_identity(selected), 'seed_index': 2, 'angle_rad': -.1,
        'historical_F_not_current': True, 'F_at_selected_density': None, 'energy': None, 'operator_id': None})
    resource_helpers.pack_record(output, 'prepared-reference-masks', {'masked_overlap': reference.overlap.copy(),
        'masked_hcore': reference.hcore.copy(), 'masked_eri': reference.masked_eri.copy(), 'matrix_mask': reference.mask.copy()})
    if reference.ledger or forbidden or changed(): raise RuntimeError('Preparation invoked scientific evaluation or changed guards')
    reference._used = reference._settled = True
    final = observe('PREPARATION_END')
    save(output/'root-readiness.json', {'status': 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_ROOT_PREPARATION_ONLY',
        'runtime_test_commit': contract['runtime_test_commit'], 'contract_sha256': contract_sha,
        'source_file_sha256': contract['source_file_sha256'], 'seed_input_source_sha256': sha(source_raw),
        'seed_input_record_sha256': sha(seed_record_raw), 'seed_input_archive_sha256': sha(seed_arrays_raw),
        'history_record_sha256': sha(history_raw), 'mdr_record_sha256': sha(mdr_raw),
        'ordered_seed_density_ids': list(ready['density_ids']), 'selected_seed_index': 2, 'selected_angle_rad': -.1,
        'selected_density_id': density_id(selected), 'selected_array_identity': array_identity(selected),
        'source_metric_matches_reference': True, 'all_four_recipe_verified': True,
        'source_bindings': {'source_record_sha256': sha(source_raw), 'source_arrays_sha256': sha(source_arrays_raw),
            'seed_record_sha256': sha(seed_record_raw), 'seed_arrays_sha256': sha(seed_arrays_raw),
            'history_record_sha256': sha(history_raw), 'mdr_record_sha256': sha(mdr_raw)},
        'guarded_operations': [row[3] for row in bindings], 'forbidden_attempts': forbidden, 'changed_guard_bindings': changed(),
        'real_F_NR_SCF_grid_integral_calls': 0, 'nuclear_repulsion_calls': 0, 'prepared_callback_ledger_entries': 0,
        'new_true_F_NR_calls': 0, 'solver_evaluated': False, 'native_budget': None,
        'scientific_budget': None, 'scientific_callback_reservation_created': False,
        'scientific_execution_authorized': False, 'root_solve': 'NOT_EXECUTED', 'CURRENT_F': 'NOT_EXECUTED',
        'actual_live_root_runner': 'NOT_IMPLEMENTED_IN_THIS_PREPARE_ONLY_VERSION',
        'scientific_execution': 'NOT_EXECUTED', 'resource_end': final, 'Compute': False, 'method_approval': False})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=Path('/candidate-contract.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('/output'))
    parser.add_argument('--ordinary-dir', type=Path, default=Path('/saved-ordinary'))
    parser.add_argument('--seed-input-dir', type=Path, default=Path('/seed-input'))
    parser.add_argument('--runtime-root', type=Path, default=Path('/workspace'))
    parser.add_argument('--science-root', type=Path, default=Path('/opt/ai4orgchem'))
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not args.prepare_only:
        raise ValueError('This worker version admits only --prepare-only; real root execution is not implemented')
    args.runtime_root, args.science_root = args.runtime_root.resolve(), args.science_root.resolve()
    sys.path[:0] = [str(args.runtime_root), str(args.science_root/'software/src')]
    from runtime.user_molecule.occupied_space_root_contract import load_execution_contract
    contract = load_execution_contract(args.contract)
    if contract['scientific_execution_authorized'] is not False:
        raise ValueError('This preparation version cannot grant scientific execution')
    for key, name in (('runtime_test_commit', 'AI4ORGCHEM_RUNTIME_TEST_COMMIT'),
                     ('image_id', 'AI4ORGCHEM_IMAGE_ID'), ('image_build_runtime_commit', 'AI4ORGCHEM_IMAGE_BUILD_COMMIT')):
        if contract[key] != os.environ.get(name): raise ValueError('Actual environment identity differs: '+key)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()): raise ValueError('Fresh preparation output required; no overwrite')
    contract_sha = sha(args.contract.read_bytes())
    save(output/'WORKER_STARTED.json', {'pid': os.getpid(), 'runtime_test_commit': contract['runtime_test_commit'],
        'contract_sha256': contract_sha, 'mode': 'ZERO_F_ROOT_PREPARATION_ONLY', 'scientific_execution_authorized': False})
    try:
        helpers = response_helper_definitions(args.runtime_root)
        platform = helpers.platform_preflight(roots={'root_filesystem': '/', 'runtime_source': args.runtime_root,
            'science_source': args.science_root, 'ordinary_cache': args.ordinary_dir.resolve(),
            'seed_input': args.seed_input_dir.resolve(), 'execution_contract': args.contract.resolve()})
        save(output/'platform-preflight.json', platform)
        if platform['status'] != 'PASS_ACTUAL_PLATFORM_PREFLIGHT':
            save(output/'root-readiness.json', {'status': 'BLOCKED_PLATFORM_PREFLIGHT', 'reasons': platform['reasons'],
                'scientific_execution': 'NOT_EXECUTED', 'scientific_budget': None, 'scientific_callback_reservation_created': False,
                'real_F_NR_SCF_grid_integral_calls': 0, 'Compute': False})
            return 20
        return preparation_worker(args, output, contract, contract_sha, helpers)
    except BaseException as error:
        save(output/'worker-fatal-error.json', {'status': 'FATAL_ROOT_PREPARATION_NOT_QUALIFIED',
            'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc(),
            'scientific_budget': None, 'Compute': False, 'automatic_retry': False})
        traceback.print_exc(); return 2


if __name__ == '__main__':
    raise SystemExit(main())
