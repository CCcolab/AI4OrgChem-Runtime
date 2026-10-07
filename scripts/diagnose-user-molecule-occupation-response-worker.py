"""One fresh bounded single-F response process; never an SCF/solver entry.

Use three saved, explicitly identified density probes and the unchanged true
conditional operator.  No seed-V2 run, optimizer, Jacobian or endpoint recheck
is invoked.  A single-point gate is diagnostic and never activates Compute.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

PATHS = ('production_copy', 'production_owned', 'independent_reference')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())


def shared_helpers(root):
    """Load only definitions from the retained worker; never call its main."""
    spec = importlib.util.spec_from_file_location('retained_seed_worker_helpers',
        root / 'scripts/diagnose-user-molecule-seed-v2-worker.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scientific_worker(args, output, contract, contract_sha):
    import numpy as np
    from pyscf import dft, gto, scf
    from pyscf.dft import numint
    from reference.ordinary_molecule import ReferenceResult
    from reference.residual_molecule import PreparedResidualReference
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
    from runtime.user_molecule.residual_bridge import PreparedResidualBridge, array_identity
    from runtime.user_molecule.residual_candidate import density_id
    from runtime.user_molecule.residual_seed_preparation import prepare_cached_context
    from runtime.user_molecule.residual_preparation import create_bridge_contract
    from runtime.user_molecule.occupation_response import run_response_probe, preflight_response_probes
    from runtime.user_molecule.occupation_response_contract import execution_identity, validate_probe_binding
    from runtime.user_molecule import residual_candidate, solver_candidate
    from reference import residual_candidate as reference_solver, user_molecule as reference_equations
    from reference import user_molecule_v2 as reference_equations_v2
    from ai4orgchem.qm import p09_conditional_scf as source_equations
    import scipy.optimize
    import scipy.optimize._numdiff

    helpers = shared_helpers(args.runtime_root)
    started = time.monotonic()
    forbidden, bindings = [], []
    def install(owner, attribute, label):
        if not hasattr(owner, attribute):
            raise ValueError('Required forbidden API unavailable: ' + label)
        def refuse(*_args, **_kwargs):
            forbidden.append(label)
            raise RuntimeError('Forbidden in single-F response: ' + label)
        setattr(owner, attribute, refuse)
        bindings.append((owner, attribute, refuse, label))

    # Save the actual native function BEFORE metadata guards replace it.
    original_nr = numint.NumInt.nr_rks
    original_nuc = gto.Mole.energy_nuc
    for owner, attribute, label in (
        (scf.hf.SCF, 'kernel', 'SCF.kernel'), (scf.hf.SCF, 'scf', 'SCF.scf'),
        (scf.hf, 'kernel', 'hf.kernel'), (scf.hf.RHF, 'kernel', 'RHF.kernel'),
        (scf.uhf.UHF, 'kernel', 'UHF.kernel'), (scf.rohf.ROHF, 'kernel', 'ROHF.kernel'),
        (dft.rks.RKS, 'kernel', 'RKS.kernel'), (dft.uks.UKS, 'kernel', 'UKS.kernel'),
        (dft.roks.ROKS, 'kernel', 'ROKS.kernel'),
        (dft.gen_grid.Grids, 'build', 'Grids.build'),
        (gto.Mole, 'intor', 'Mole.intor'), (gto.Mole, 'intor_by_shell', 'Mole.intor_by_shell'),
        (numint.NumInt, 'nr_rks', 'NumInt.nr_rks outside charged instance'),
        (numint, 'nr_rks', 'numint.nr_rks outside charged instance'),
        (residual_candidate, 'solve_residual_candidate', 'production residual solve'),
        (solver_candidate, 'iterate_candidate', 'production candidate iterate'),
        (solver_candidate, 'run_candidate_conditional_rks', 'production candidate SCF driver'),
        (reference_solver, 'solve', 'reference solve'),
        (reference_equations, 'fixed_point', 'reference fixed_point'),
        (reference_equations_v2, 'fixed_point', 'reference v2 fixed_point'),
        (source_equations, 'run_p09_conditional_rks', 'frozen scientific SCF driver'),
        (scipy.optimize, 'least_squares', 'scipy least_squares'),
        (scipy.optimize._numdiff, 'approx_derivative', 'scipy numerical Jacobian'),
        (PreparedResidualBridge, 'run', 'production bridge.run'),
        (PreparedResidualReference, 'run', 'reference bridge.run'),
    ):
        install(owner, attribute, label)

    def observe(phase):
        value = {'phase': phase, 'elapsed_seconds': time.monotonic() - started,
                 'cgroup': collect_cgroup(phase=phase), 'vm_memory': helpers.vm_memory()}
        with (output / 'resources.jsonl').open('a', encoding='utf-8', newline='\n') as target:
            target.write(json.dumps(value, allow_nan=False) + '\n')
            target.flush()
            os.fsync(target.fileno())
        if helpers.resource_reasons(value['cgroup']):
            raise RuntimeError('Native scientific hard limits or resource observations refused')
        if value['vm_memory']['available_bytes'] is None or value['vm_memory']['available_bytes'] < 2147483648:
            raise RuntimeError('At least 2GiB VM available memory is required')
        return value

    for package, version in contract['expected_dependencies'].items():
        import importlib.metadata
        if importlib.metadata.version(package) != version:
            raise ValueError('Pinned dependency mismatch: ' + package)
    for name, digest in contract['source_file_sha256'].items():
        if sha((args.runtime_root / name).read_bytes()) != digest:
            raise ValueError('Tested runtime source bytes changed: ' + name)
    observe('BEFORE_PREPARATION')
    cached = prepare_cached_context(runtime_root=args.runtime_root, science_root=args.science_root,
                                   ordinary_dir=args.ordinary_dir, identity=contract)
    save(output / 'legacy-basis-representation.json', cached['basis_receipt'])
    context = cached['context']
    # prepare_cached_context restores the class nuclear function it observed;
    # nuclear energy is also prohibited outside the charged instance below.
    install(gto.Mole, 'energy_nuc', 'Mole.energy_nuc outside charged instance')
    probe_raw = (args.probe_input_dir / contract['probe_origin']['review_file']).read_bytes()
    arrays_raw = (args.probe_input_dir / contract['probe_origin']['arrays_file']).read_bytes()
    binding = validate_probe_binding(contract, probe_raw, arrays_raw)
    save(output / 'probe-byte-binding.json', binding)
    from io import BytesIO
    probes = {}
    with np.load(BytesIO(arrays_raw), allow_pickle=False) as source:
        for item in contract['probe_origin']['probes']:
            density = source[item['member']].copy()
            if array_identity(density) != item['array_identity'] or density_id(density) != item['density_id']:
                raise ValueError('Actual probe member identity differs: ' + item['name'])
            density.setflags(write=False)
            probes[item['name']] = density

    journal_identity = execution_identity(contract, contract_sha)
    journal = None
    active = {'path': None, 'probe': None, 'density_id': None, 'slot_id': None}
    counts = {path: {'nr_rks_attempts': 0, 'nr_rks_completed': 0, 'nr_rks_failed': 0,
                     'energy_nuc_attempts': 0, 'energy_nuc_completed': 0, 'energy_nuc_failed': 0} for path in PATHS}
    slot_counts = {}
    def event(kind, detail=None):
        record = {'kind': kind, 'active': dict(active), 'elapsed_seconds': time.monotonic() - started,
                  'counts': copy.deepcopy(counts), 'detail': detail}
        with (output / 'native-callbacks.jsonl').open('a', encoding='utf-8', newline='\n') as target:
            target.write(json.dumps(record, allow_nan=False) + '\n')
            target.flush()
            os.fsync(target.fileno())
    def pending(kind):
        if journal is None:
            raise RuntimeError('No scientific callback budget is reserved during preparation')
        path = active['path']
        snapshot = journal.snapshot()
        rows = [row for row in snapshot['slots'] if row['slot_id'] == active['slot_id']]
        if len(rows) != 1 or path not in PATHS:
            raise RuntimeError('Native call outside an explicit precharged response slot')
        row = rows[0]
        if (row['status'] != 'PENDING' or row['path_id'] != path or row['density_id'] != active['density_id']
                or active['probe'] not in probes or row['density_id'] != density_id(probes[active['probe']])):
            raise RuntimeError('Native PENDING slot/path/probe/D binding differs')
        if snapshot['charged_slots'] > 9 or snapshot['path_charged_slots'][path] > 3:
            raise RuntimeError('Native callback budget exceeded')
        slot = slot_counts.setdefault(row['slot_id'], {'NR_RKS': 0, 'ENERGY_NUC': 0})
        if slot[kind] or (kind == 'ENERGY_NUC' and path == 'independent_reference'):
            raise RuntimeError('Additional native call within the same response slot refused')
        slot[kind] += 1
        return path
    def counted_nr(*values, **settings):
        path = pending('NR_RKS')
        # Verify the native requested D, rather than inferring it from a slot.
        native_d = settings.get('dms', values[3] if len(values) > 3 else None)
        if native_d is None or density_id(native_d) != active['density_id']:
            raise RuntimeError('Native XC density differs from the charged density')
        if sum(row['nr_rks_attempts'] for row in counts.values()) >= 9 or counts[path]['nr_rks_attempts'] >= 3:
            raise RuntimeError('Native NR hard ceiling exhausted')
        counts[path]['nr_rks_attempts'] += 1
        event('NR_RKS_ENTERED')
        try:
            value = original_nr(context.mean_field._numint, *values, **settings)
        except BaseException as error:
            counts[path]['nr_rks_failed'] += 1
            event('NR_RKS_FAILED', type(error).__name__ + ': ' + str(error))
            raise
        counts[path]['nr_rks_completed'] += 1
        event('NR_RKS_COMPLETED')
        return value
    def counted_nuc(*values, **settings):
        path = pending('ENERGY_NUC')
        counts[path]['energy_nuc_attempts'] += 1
        event('ENERGY_NUC_ENTERED')
        try:
            value = original_nuc(context.mol, *values, **settings)
        except BaseException as error:
            counts[path]['energy_nuc_failed'] += 1
            event('ENERGY_NUC_FAILED', type(error).__name__ + ': ' + str(error))
            raise
        counts[path]['energy_nuc_completed'] += 1
        event('ENERGY_NUC_COMPLETED')
        return value
    context.mean_field._numint.nr_rks = counted_nr
    context.mol.energy_nuc = counted_nuc
    def prohibited(*_args, **_kwargs):
        raise RuntimeError('Ordinary SCF/one-electron integral evaluation forbidden')
    context.mean_field.get_hcore = context.mean_field.get_ovlp = prohibited
    context.mean_field.kernel = context.mean_field.scf = prohibited
    prepared = create_bridge_contract(runtime_root=args.runtime_root, science_root=args.science_root,
        prepared_input=cached['prepared_input'], context=context, arrays=cached['arrays'],
        ordinary_record=cached['record'], runtime_test_commit=contract['runtime_test_commit'],
        image_id=contract['image_id'], image_build_commit=contract['image_build_runtime_commit'],
        execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC', initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
        ordinary_record_path=cached['record_path'], ordinary_arrays_path=cached['arrays_path'], maximum_evaluations=3)
    save(output / 'preparation-contract.json', prepared['contract'])
    save(output / 'prepared-mapping.json', prepared['mapping_receipt'])
    engines = {
        'production_copy': PreparedResidualBridge(**prepared['bridge_kwargs'], eri_mode='COPY_MASK', optimize_eri_contractions=True),
        'production_owned': PreparedResidualBridge(**prepared['bridge_kwargs'], eri_mode='INPLACE_OWNED', optimize_eri_contractions=False),
        'independent_reference': PreparedResidualReference(
            ordinary=ReferenceResult(record=cached['record'], arrays=cached['arrays'], context=context),
            rule_path=args.science_root / 'configs/qm/p09_exchange_integral_classes_v0.1.yaml',
            expected_sha256=prepared['contract']['condition_rules_sha256'],
            initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR', maximum_evaluations=3,
            execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC'),
    }
    expected_s = contract['probe_origin']['source_masked_overlap_identity']
    for path, engine in engines.items():
        actual_s = array_identity(engine.overlap)
        if any(actual_s[key] != expected_s[key] for key in ('shape', 'dtype', 'sha256')):
            raise ValueError('Probe construction metric differs from actual prepared metric: ' + path)
    admissions = preflight_response_probes(probes=probes, overlap=engines['production_copy'].overlap,
        electrons=16, matrix_delete_mask=engines['production_copy'].mask)
    helpers.pack_record(output, 'actual-probe-admissions', admissions)
    helpers.pack_record(output, 'prepared-masks', {
        path: {'masked_overlap': engine.overlap.copy(), 'masked_hcore': engine.hcore.copy(),
               'masked_eri': engine.masked_eri.copy(), 'matrix_mask': engine.mask.copy()} for path, engine in engines.items()})
    observe('PREPARED_BEFORE_F')
    if args.prepare_only:
        changed = [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
        if forbidden or changed or any(row['nr_rks_attempts'] or row['energy_nuc_attempts'] for row in counts.values()):
            raise RuntimeError('Zero-F preparation guard/counter integrity failed')
        for engine in engines.values():
            engine._used = engine._settled = True
        final = observe('PREPARATION_END')
        save(output / 'probe-readiness.json', {'status': 'PASS_ACTUAL_CACHED_RESPONSE_PREPARATION_ONLY',
            'runtime_test_commit': contract['runtime_test_commit'], 'contract_sha256': contract_sha,
            'probe_input_review_sha256': sha(probe_raw), 'probe_input_archive_sha256': sha(arrays_raw),
            'source_file_sha256': contract['source_file_sha256'], 'source_metric_matches_all_three_paths': True,
            'native_counts': counts, 'real_F_NR_SCF_grid_integral_calls': 0,
            'scientific_budget': None, 'scientific_callback_reservation_created': False,
            'guarded_operations': [row[3] for row in bindings], 'forbidden_attempts': forbidden,
            'changed_guard_bindings': changed, 'resource_end': final,
            'scientific_execution': 'NOT_EXECUTED', 'Compute': False, 'method_approval': False})
        return 0
    journal = ConditionalCallbackBudget(path=output / 'callbacks.json', batch_id=contract['batch_id'],
        identity=journal_identity, path_limits={path: 3 for path in PATHS}, total_limit=9)
    native_leaf = output / 'source-captures'
    native_leaf.mkdir()
    callbacks = {}
    for path in PATHS:
        engine = engines[path]
        def callback(density, phase, *, path=path, engine=engine):
            names = [name for name, value in probes.items() if density_id(value) == density_id(density)]
            rows = [row for row in journal.snapshot()['slots'] if row['status'] == 'PENDING']
            if len(names) != 1 or len(rows) != 1 or rows[0]['path_id'] != path:
                raise RuntimeError('Response callback requires one matched precharged slot')
            active.update(path=path, probe=names[0], density_id=density_id(density), slot_id=rows[0]['slot_id'])
            try:
                if path == 'independent_reference':
                    value = engine.evaluate(density)
                    raw = copy.deepcopy(engine.last_evaluation)
                    if density_id(raw['density']) != active['density_id']:
                        raise ValueError('Reference raw evaluation belongs to a different density')
                    value = dict(value, raw_fock=raw['Fraw'], coulomb_matrix=raw['J'], exchange_matrix=raw['K'],
                        xc_potential=raw['Vxc'], grid_electron_count=raw['grid_electron_count'],
                        masked_metric_electron_count=raw['masked_metric_electron_count'],
                        physical_metric_electron_count=raw['physical_metric_electron_count'],
                        electronic_energy=raw['total_energy_hartree'] - raw['components_hartree']['nuclear_repulsion'])
                else:
                    value = engine.evaluate(density, phase=phase)
                helpers.pack_record(native_leaf, f'slot-{active["slot_id"]:02d}',
                    {'requested_density': density.copy(), 'requested_density_id': active['density_id'],
                     'path': path, 'probe': names[0], 'phase': phase, 'value': copy.deepcopy(value),
                     'prepared_ledger_row': copy.deepcopy(engine.ledger[-1])})
                observe('AFTER_SLOT_' + str(active['slot_id']))
                return value
            finally:
                active.update(path=None, probe=None, density_id=None, slot_id=None)
        callbacks[path] = callback
    try:
        result = run_response_probe(probes=probes, callbacks=callbacks, overlap=engines['production_copy'].overlap,
            electrons=16, matrix_delete_mask=engines['production_copy'].mask, journal=journal,
            execution_kind='PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC')
    finally:
        for engine in engines.values():
            engine._used = engine._settled = True
    helpers.pack_record(output, 'response-result', result)
    changed = [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
    if context.mean_field._numint.nr_rks is not counted_nr or context.mol.energy_nuc is not counted_nuc:
        changed.append('Prepared charged native wrapper')
    final = observe('END')
    snapshot = journal.snapshot()
    save(output / 'native-counts.json', {'counts': counts, 'total_NR_attempts': sum(row['nr_rks_attempts'] for row in counts.values()),
        'total_NR_completed': sum(row['nr_rks_completed'] for row in counts.values()),
        'total_NR_failed': sum(row['nr_rks_failed'] for row in counts.values()),
        'per_slot_counts': slot_counts, 'native_counter_proof': 'INSTRUMENTED_WRAPPER_ENTRY_COMPLETION_FAILURE',
        'conservative_slots_are_not_native_calls': True})
    save(output / 'guard-status.json', {'guarded_operations': [row[3] for row in bindings],
        'forbidden_attempts': forbidden, 'changed_bindings': changed,
        'status': 'PASS' if not changed and not forbidden else 'FAIL',
        'solver_and_SCF_iterations': 0, 'new_grid_or_integral_builds': 0})
    good = (result['status'] == 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE' and not changed and not forbidden
            and snapshot['charged_slots'] == 9 and snapshot['pending_slots'] == snapshot['failed_slots'] == 0
            and all(counts[path]['nr_rks_attempts'] == counts[path]['nr_rks_completed'] == 3 for path in PATHS)
            and all(counts[path]['nr_rks_failed'] == counts[path]['energy_nuc_failed'] == 0 for path in PATHS)
            and all(counts[path]['energy_nuc_attempts'] == counts[path]['energy_nuc_completed'] == 3
                    for path in ('production_copy', 'production_owned'))
            and counts['independent_reference']['energy_nuc_attempts'] == counts['independent_reference']['energy_nuc_completed'] == 0)
    save(output / 'response-summary.json', {'status': 'EXECUTED_SINGLE_F_RESPONSE_ONLY' if good else 'FAILED_OR_REFUSED_SINGLE_F_RESPONSE',
        'source_identity': journal_identity, 'native_counts': counts, 'charged_slots': snapshot['charged_slots'],
        'resource_end': final, 'scientific_processes': 1, 'SCF_iterations': 0,
        'Compute': False, 'full_endpoint_qualification': 'NOT_EXECUTED',
        'UM_P12_UM_P13_T06': 'NOT_EXECUTED', 'research_delta_hartree': None,
        'production_activation': False, 'method_approval': False, 'automatic_retry': False})
    return 0 if good else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=Path('/execution-contract.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('/output'))
    parser.add_argument('--ordinary-dir', type=Path, default=Path('/saved-ordinary'))
    parser.add_argument('--probe-input-dir', type=Path, default=Path('/probe-input'))
    parser.add_argument('--runtime-root', type=Path, default=Path('/workspace'))
    parser.add_argument('--science-root', type=Path, default=Path('/opt/ai4orgchem'))
    parser.add_argument('--prepare-only', action='store_true', help='Verify actual cached mapping and all probes; no callback journal or F')
    args = parser.parse_args()
    args.runtime_root = args.runtime_root.resolve()
    args.science_root = args.science_root.resolve()
    sys.path.insert(0, str(args.runtime_root))
    sys.path.insert(0, str(args.science_root / 'software/src'))
    from runtime.user_molecule.occupation_response_contract import load_execution_contract
    contract = load_execution_contract(args.contract)
    if not args.prepare_only and contract['scientific_execution_authorized'] is not True:
        raise ValueError('This contract grants no scientific execution')
    for key, name in (('runtime_test_commit', 'AI4ORGCHEM_RUNTIME_TEST_COMMIT'),
                      ('image_id', 'AI4ORGCHEM_IMAGE_ID'), ('image_build_runtime_commit', 'AI4ORGCHEM_IMAGE_BUILD_COMMIT')):
        if contract[key] != os.environ.get(name):
            raise ValueError('Actual execution environment identity differs: ' + key)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Fresh worker output leaf required; no retry/overwrite')
    save(output / 'WORKER_STARTED.json', {'pid': os.getpid(), 'contract_sha256': sha(args.contract.read_bytes()),
        'runtime_test_commit': contract['runtime_test_commit'], 'mode': contract['execution_kind'],
        'authorization': contract['authorization_basis'], 'production_activation': False})
    try:
        return scientific_worker(args, output, contract, sha(args.contract.read_bytes()))
    except BaseException as error:
        save(output / 'worker-fatal-error.json', {'status': 'FATAL_NOT_QUALIFIED', 'type': type(error).__name__,
            'message': str(error), 'traceback': traceback.format_exc(), 'Compute': False, 'automatic_retry': False})
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
