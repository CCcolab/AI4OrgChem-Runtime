"""Default-gated single-start worker: prepare inputs or use a separate grant.

No ordinary SCF, integral/grid build or nuclear-energy call is permitted. An
explicit granted run uses one prepared independent reference and fresh slots.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback
import types


def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
        stream.flush();os.fsync(stream.fileno())
def load_module(root,path,name):
    spec=importlib.util.spec_from_file_location(name,root/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def close_active_initialization(output,*,journal,accounting,reference,reason):
    """Close already-created handles only; never create/resume/refund a budget.

    If accounting construction/settlement failed, retain its original files and
    settle the actual journal directly as FAILED. Unknown native counts are not
    replaced by zero. A persistence failure is retained and re-raised.
    """
    if reference is not None:reference._used=reference._settled=True
    errors=[];book=None
    if accounting is not None:
        try:book=accounting.close(reason)
        except BaseException as error:errors.append(type(error).__name__+': '+str(error))
    if journal is not None:
        try:
            state=journal.snapshot()
            for row in state['slots']:
                if row['status']=='PENDING':
                    journal.finish(row['slot_id'],status='FAILED',detail='Active initialization/worker failed; no refund or retry')
            for path,row in journal.snapshot()['paths'].items():
                if row['state']=='OPEN':journal.close_path(path,reason)
            save(output/'native-journal-final.json',journal.snapshot())
        except BaseException as error:errors.append(type(error).__name__+': '+str(error))
    if book is not None:save(output/'native-accounting-final.json',book)
    elif journal is not None:
        save(output/'native-accounting-unavailable.json',{'status':'ACCOUNTING_UNAVAILABLE_NO_RETRY',
            'native_counts':'UNKNOWN_NOT_REPLACED_BY_ZERO','errors':errors,'Compute':False,'automatic_retry':False})
    if errors:
        save(output/'active-cleanup-errors.json',{'status':'NOT_QUALIFIED','errors':errors,'automatic_retry':False,'Compute':False})
        raise RuntimeError('Active handles could not be completely settled: '+'; '.join(errors))
    return book


def run_worker(args,contract,parent_bytes,grant,output):
    import numpy as np
    from pyscf import dft,gto,scf
    from pyscf.dft import numint
    from reference.ordinary_molecule import ReferenceResult
    from reference.residual_molecule import PreparedResidualReference
    from runtime.user_molecule.residual_seed_preparation import prepare_cached_context
    from runtime.user_molecule.residual_preparation import create_bridge_contract
    from runtime.user_molecule.occupied_space_response import preflight_occupied_space_response
    from runtime.user_molecule.occupied_space_root_native_contract import validate_input_binding,execution_identity
    from runtime.user_molecule.input import strict_json
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    # Capture the trusted mature APIs before forbidding legacy shortcuts.
    original_nr=numint.NumInt.nr_rks
    from reference.occupied_space_root_native_candidate import solve_occupied_space_root_native_candidate
    from runtime.user_molecule import residual_candidate,solver_candidate
    from reference import residual_candidate as old_reference,residual_budgeted_candidate as old_budgeted
    from reference import occupied_space_root_candidate as old_root
    from ai4orgchem.qm import p09_conditional_scf as source_equations
    import scipy.optimize
    import scipy.optimize._numdiff
    helpers=load_module(args.runtime_root,'scripts/diagnose-user-molecule-occupied-space-response-worker.py','native_response_helpers')
    retained=load_module(args.runtime_root,'scripts/diagnose-user-molecule-occupied-space-root-worker.py','native_retained_seed_helpers')
    resource_helpers=helpers.shared_helpers(args.runtime_root)
    forbidden,guards=[],[]
    def install(owner,name,label):
        def refuse(*_args,**_kwargs):
            forbidden.append(label);raise RuntimeError('Root-native forbids '+label)
        setattr(owner,name,refuse);guards.append((owner,name,refuse,label))
    for owner,name,label in (
        (scf.hf.SCF,'kernel','SCF.kernel'),(scf.hf.SCF,'scf','SCF.scf'),(scf.hf,'kernel','hf.kernel'),
        (scf.hf.RHF,'kernel','RHF.kernel'),(scf.uhf.UHF,'kernel','UHF.kernel'),(scf.rohf.ROHF,'kernel','ROHF.kernel'),
        (dft.rks.RKS,'kernel','RKS.kernel'),(dft.uks.UKS,'kernel','UKS.kernel'),(dft.roks.ROKS,'kernel','ROKS.kernel'),
        (dft.gen_grid.Grids,'build','Grids.build'),(gto.Mole,'intor','Mole.intor'),
        (gto.Mole,'intor_by_shell','Mole.intor_by_shell'),(gto.Mole,'energy_nuc','Mole.energy_nuc'),
        (numint.NumInt,'nr_rks','unbound NumInt.nr_rks'),(numint,'nr_rks','module numint.nr_rks'),
        (residual_candidate,'solve_residual_candidate','old production solve'),
        (solver_candidate,'iterate_candidate','old production iterate'),
        (solver_candidate,'run_candidate_conditional_rks','old production SCF driver'),
        (old_reference,'solve','old reference solve'),(old_budgeted,'solve_budgeted_candidate','old budgeted solve'),
        (old_root,'solve_occupied_space_root_candidate','old fake-only root'),
        (source_equations,'run_p09_conditional_rks','source SCF driver'),
        (source_equations,'_evaluate_density','source direct F shortcut'),
        (scipy.optimize,'least_squares','public SciPy shortcut'),
        (scipy.optimize._numdiff,'approx_derivative','public Jacobian shortcut')):
        install(owner,name,label)
    if not args.execute:
        from reference import occupied_space_root_native_candidate as native_candidate
        for owner,name,label in (
            (native_candidate,'solve_occupied_space_root_native_candidate','new native root solve'),
            (native_candidate,'least_squares','new native TRF alias'),
            (native_candidate,'approx_derivative','new native Jacobian alias'),
            (PreparedResidualReference,'evaluate','prepared reference evaluate')):
            install(owner,name,label)
    def changed():return [label for owner,name,guard,label in guards if getattr(owner,name)is not guard]
    started=time.monotonic()
    def observe(phase):
        value={'phase':phase,'elapsed_worker_seconds':time.monotonic()-started,
            'cgroup':collect_cgroup(phase=phase),'vm_memory':resource_helpers.vm_memory()}
        with (output/'resources.jsonl').open('a',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        if resource_helpers.resource_reasons(value['cgroup']) or value['vm_memory']['available_bytes'] is None or value['vm_memory']['available_bytes']<2147483648:
            raise RuntimeError('Actual single-process resource admission refused')
        if forbidden or changed():raise RuntimeError('Forbidden operation or changed held guard')
        if args.execute and time.time()>=args.stop_deadline_epoch:raise RuntimeError('Host stop deadline reached; no callback or tail extension')
        return value
    parent=contract['parent_preparation_contract']
    versions={name:importlib.metadata.version(name) for name in parent['expected_dependencies']}
    if versions!=parent['expected_dependencies']:raise ValueError('Pinned dependency distributions differ')
    save(output/'dependency-identity.json',versions)
    for name,digest in contract['source_file_sha256'].items():
        if sha((args.runtime_root/name).read_bytes())!=digest:raise ValueError('Actual new source bytes differ: '+name)
    observe('BEFORE_PREPARATION')
    names=('SOURCE.json','source-arrays.npz','prepared-seed-family.json','prepared-seed-family.npz','parent-response-result.json','MDR-007.json')
    raw={name:(args.seed_input_dir/name).read_bytes() for name in names}
    opts={'explicit_grant':grant,'local_cli_execute_requested':args.execute}
    binding=validate_input_binding(contract,raw['SOURCE.json'],raw['prepared-seed-family.json'],raw['prepared-seed-family.npz'],
        parent_preparation_contract_bytes=parent_bytes,source_arrays_bytes=raw['source-arrays.npz'],
        history_record_bytes=raw['parent-response-result.json'],mdr_bytes=raw['MDR-007.json'],**opts)
    save(output/'input-byte-binding.json',binding)
    cached=prepare_cached_context(runtime_root=args.runtime_root,science_root=args.science_root,
        ordinary_dir=args.ordinary_dir,identity=parent)
    source=strict_json(raw['SOURCE.json'])
    family=helpers.load_saved_family(strict_json(raw['prepared-seed-family.json']),raw['prepared-seed-family.npz'])
    context=cached['context'];arrays={}
    with np.load(io.BytesIO(raw['source-arrays.npz']),allow_pickle=False) as archive:
        for name,meta in source['arrays'].items():
            array=archive[name].copy()
            if list(array.shape)!=meta['shape'] or array.dtype.str!=meta['dtype'] or not np.isfinite(array).all() or sha(array.tobytes())!=meta['sha256']:
                raise ValueError('Actual source array payload differs: '+name)
            array.setflags(write=False);arrays[name]=array
    for name,key in (('base_density','source_density'),('masked_overlap','source_masked_overlap'),
        ('occupied_anchor','source_occupied_anchor'),('virtual_anchor','source_virtual_anchor')):
        if not np.array_equal(arrays[name],family[key]):raise ValueError('Source/family array mismatch: '+name)
    mapping=source['source_mapping']
    if mapping['ao_labels']!=context.metadata['ao_labels'] or mapping['ao_descriptors']!=context.metadata['ao_descriptors']:
        raise ValueError('Actual AO labels/fragment metadata differ')
    if not np.array_equal(arrays['physical_overlap'],cached['arrays']['overlap']):raise ValueError('Original cached overlap differs')
    prepared=create_bridge_contract(runtime_root=args.runtime_root,science_root=args.science_root,
        prepared_input=cached['prepared_input'],context=context,arrays=cached['arrays'],ordinary_record=cached['record'],
        runtime_test_commit=contract['runtime_test_commit'],image_id=parent['image_id'],image_build_commit=parent['image_build_runtime_commit'],
        execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC',initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
        ordinary_record_path=cached['record_path'],ordinary_arrays_path=cached['arrays_path'],maximum_evaluations=201)
    save(output/'prepared-mapping.json',prepared['mapping_receipt'])
    if mapping['atom_mapping']!=prepared['mapping_receipt']['atom_mapping'] or prepared['mapping_receipt']['profile_canonical_sha256']!=parent['profile_canonical_sha256']:
        raise ValueError('Actual geometry/profile mapping differs')
    accounting=journal=nr_binding=reference=None
    result=book=None;active_error=None;active_stage='ACTIVE_HANDLE_INITIALIZATION'
    try:
        # No science allowance exists before complete identity/platform admission.
        if args.execute:
            from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
            from runtime.user_molecule.root_native_accounting import RootNativeAccounting
            from runtime.user_molecule.root_native_binding import NativeReferenceNRBinding
            identity=execution_identity(contract,sha(args.contract.read_bytes()),**opts)
            journal=ConditionalCallbackBudget(path=output/'callbacks.json',batch_id=contract['batch_id'],identity=identity,
                path_limits={'independent_reference':201},total_limit=201)
            active_stage='ACCOUNTING_CONSTRUCTION'
            accounting=RootNativeAccounting(output/'accounting',journal,execution_kind='SOURCE_NATIVE_DIAGNOSTIC',scientific_execution_authorized=True)
            active_stage='NR_BINDING_CONSTRUCTION'
            nr_binding=NativeReferenceNRBinding(context=context,accounting=accounting,contract=contract,runtime_root=args.runtime_root,
                original_nr=types.MethodType(original_nr,context.mean_field._numint),contract_sha256=sha(args.contract.read_bytes()),**opts)
            active_stage='NR_BINDING_INSTALL'
            nr_binding.install()
        active_stage='PREPARED_REFERENCE_CONSTRUCTION'
        reference=PreparedResidualReference(ordinary=ReferenceResult(record=cached['record'],arrays=cached['arrays'],context=context),
            rule_path=args.science_root/'configs/qm/p09_exchange_integral_classes_v0.1.yaml',
            expected_sha256=prepared['contract']['condition_rules_sha256'],initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
            maximum_evaluations=201,execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC')
        active_stage='REFERENCE_METRIC_CHECK'
        if not np.array_equal(reference.overlap,arrays['masked_overlap']) or not np.array_equal(reference.mask,arrays['matrix_delete_mask']):
            raise ValueError('Actual reference metric/mask differs from source')
        active_stage='SEED_RECIPE_ADMISSION'
        ready=preflight_occupied_space_response(prepared_seeds=family,overlap=reference.overlap,electrons=16,matrix_delete_mask=reference.mask)
        active_stage='INITIAL_SELECTION'
        selected=retained.select_saved_initial(family,contract['initial_density'])
        resource_helpers.pack_record(output,'selected-initial',{'density':selected,'density_id':contract['initial_density']['density_id'],
            'CURRENT_INITIAL_F':None,'energy':None,'historical_F_reused':False})
        resource_helpers.pack_record(output,'all-family-admissions',ready)
        observe('READY_BEFORE_NEW_F')
        if not args.execute:
            if journal is not None or reference.ledger or forbidden or changed():raise RuntimeError('Gated preparation attempted a native evaluation')
            reference._used=reference._settled=True
            save(output/'native-readiness.json',{'status':'PASS_GATED_SOURCE_NATIVE_INPUT_PREPARATION_ONLY',
                'contract_sha256':sha(args.contract.read_bytes()),'runtime_test_commit':contract['runtime_test_commit'],
                'parent_contract_sha256':sha(parent_bytes),'contract_family_sha256':contract['contract_family_sha256'],
                'selected_density_id':contract['initial_density']['density_id'],'selected_seed_index':2,'selected_angle_rad':-.1,
                'four_seed_recipe_verified':True,'source_file_sha256':contract['source_file_sha256'],
                'guarded_operations':[row[3] for row in guards],'changed_guards':changed(),'forbidden_attempts':forbidden,
                'actual_native_NR_calls':0,'new_scientific_budget':None,'root_solve':'NOT_EXECUTED','Compute':False})
            return 0
        from runtime.user_molecule.root_native_binding import SourceBoundRootEvaluator
        captures=output/'source-captures';captures.mkdir()
        def capture(value):resource_helpers.pack_record(captures,'slot-'+str(value['slot_id']).zfill(3),value)
        active_stage='SOURCE_EVALUATOR_CONSTRUCTION'
        evaluator=SourceBoundRootEvaluator(engine=reference,nr_binding=nr_binding,accounting=accounting,contract=contract,
            runtime_root=args.runtime_root,save_snapshot=capture,observe_resources=observe,**opts)
        active_stage='SOLVE_AND_RESULT_PUBLICATION'
        result=solve_occupied_space_root_native_candidate(density=selected,overlap=reference.overlap,electrons=16,
            matrix_delete_mask=reference.mask,evaluate=evaluator,execution_kind='SOURCE_NATIVE_DIAGNOSTIC',
            scientific_execution_authorized=True,expected_initial_density_id=contract['initial_density']['density_id'])
        resource_helpers.pack_record(output,'native-root-result',result)
    except BaseException as error:
        active_error=error
        if args.execute:
            save(output/'native-active-failure.json',{'status':'FAILED_INITIALIZATION_OR_SOLVE_NO_RETRY',
                'stage':active_stage,'type':type(error).__name__,'message':str(error),
                'journal_created':journal is not None,'accounting_created':accounting is not None,
                'reference_created':reference is not None,'Compute':False,'automatic_retry':False})
        raise
    finally:
        if args.execute:
            try:
                book=close_active_initialization(output,journal=journal,accounting=accounting,reference=reference,
                    reason='NORMAL_RETURN' if active_error is None else 'ACTIVE_INITIALIZATION_OR_SOLVE_FAILURE_NO_RETRY')
            finally:
                save(output/'guard-status.json',{'guarded_operations':[row[3] for row in guards],
                    'forbidden_attempts':forbidden,'changed_bindings':changed(),
                    'new_ordinary_SCF_grid_full_integrals':0,'nuclear_repulsion_calls':0})
    save(output/'native-summary.json',{'status':'EXECUTED_SINGLE_PATH_ROOT_DIAGNOSTIC_ONLY',
        'endpoint_qualified':bool(result['engine_qualified']),'stop_reason':result['stop_reason'],
        'source_NR_counts':book['source_native_dispatch_counts'],'callback_slots':book['callback_slots'],
        'Compute':False,'independent_production_equivalence':'NOT_EXECUTED','method_approval':False,
        'research_delta_hartree':None,'automatic_retry':False})
    return 0


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=Path('/native-contract.json'))
    parser.add_argument('--parent-contract',type=Path,default=Path('/parent-contract.json'))
    parser.add_argument('--grant-file',type=Path)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare-only',action='store_true');group.add_argument('--execute',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=Path('/output'))
    parser.add_argument('--ordinary-dir',type=Path,default=Path('/saved-ordinary'))
    parser.add_argument('--seed-input-dir',type=Path,default=Path('/seed-input'))
    parser.add_argument('--runtime-root',type=Path,default=Path('/workspace'))
    parser.add_argument('--science-root',type=Path,default=Path('/opt/ai4orgchem'))
    parser.add_argument('--stop-deadline-epoch',type=float)
    return parser


def main():
    args=argument_parser().parse_args()
    args.runtime_root=args.runtime_root.resolve();sys.path[:0]=[str(args.runtime_root),str(args.science_root/'software/src')]
    from runtime.user_molecule.input import strict_json
    from runtime.user_molecule.occupied_space_root_native_contract import load_execution_contract
    if args.execute and (args.grant_file is None or args.stop_deadline_epoch is None):raise ValueError('Explicit grant and host stop deadline required')
    if args.prepare_only and args.grant_file is not None:raise ValueError('Gated preparation cannot receive an execution grant')
    parent_bytes=args.parent_contract.read_bytes();grant=strict_json(args.grant_file.read_bytes()) if args.grant_file else None
    contract=load_execution_contract(args.contract,parent_preparation_contract_bytes=parent_bytes,
        explicit_grant=grant,local_cli_execute_requested=args.execute)
    if contract['runtime_test_commit']!=os.environ.get('AI4ORGCHEM_RUNTIME_TEST_COMMIT'):raise ValueError('Actual source commit differs')
    parent=contract['parent_preparation_contract']
    for key,env in (('image_id','AI4ORGCHEM_IMAGE_ID'),('image_build_runtime_commit','AI4ORGCHEM_IMAGE_BUILD_COMMIT')):
        if parent[key]!=os.environ.get(env):raise ValueError('Actual image identity differs: '+key)
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise ValueError('Fresh output; no resume or overwrite')
    save(output/'WORKER_STARTED.json',{'runtime_test_commit':contract['runtime_test_commit'],
        'contract_sha256':sha(args.contract.read_bytes()),'execute':args.execute,'grant_supplied':grant is not None})
    try:
        helpers=load_module(args.runtime_root,'scripts/diagnose-user-molecule-occupied-space-response-worker.py','native_platform')
        roots={'root_filesystem':'/','runtime_source':args.runtime_root,'science_source':args.science_root,
            'ordinary_cache':args.ordinary_dir,'seed_input':args.seed_input_dir,'execution_contract':args.contract,
            'parent_contract':args.parent_contract}
        if args.grant_file:roots['execution_grant']=args.grant_file
        platform=helpers.platform_preflight(roots=roots);save(output/'platform-preflight.json',platform)
        if platform['status']!='PASS_ACTUAL_PLATFORM_PREFLIGHT':return 20
        return run_worker(args,contract,parent_bytes,grant,output)
    except BaseException as error:
        save(output/'worker-fatal-error.json',{'status':'NOT_QUALIFIED','type':type(error).__name__,
            'message':str(error),'traceback':traceback.format_exc(),'Compute':False,'automatic_retry':False})
        traceback.print_exc();return 2


if __name__=='__main__':raise SystemExit(main())
