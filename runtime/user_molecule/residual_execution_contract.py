"""Exact single diagnostic contract and live admission checks, standard library.

An execution receipt records the user's bounded diagnostic instruction. It does
not grant method approval, scientific interpretation or production Compute.
Historical engineering proposals and budgets are never rewritten here.
"""
import hashlib
import json
import math
import re
from pathlib import Path

from .input import strict_json


SCIENCE='cc7437901119e71ef7945a12813c021c383e7648'
BASELINE='28511f3d84fa65707a107cde1e8121a7b4334ecb'
IMAGE='sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d'
IMAGE_BUILD='5098775c9cf40468ab92712447a3e5c7b1361a63'
DEPENDENCIES={'pyscf':'2.14.0','numpy':'2.5.1','scipy':'1.18.0'}
NUMERICAL_COMPARISONS={
    'T05_same_density':{'mask_max_abs':0.0,'matrix_max_abs':1e-10,'matrix_frobenius':1e-9,
        'component_hartree':1e-9,'total_energy_hartree':1e-9,'grid_electron_count_abs':1e-9},
    'P12_energy_difference_hartree':1e-10,'P13_density_difference_frobenius':1e-9,
    'T06_total_energy_hartree':1e-8,'T06_component_hartree':1e-6,
    'T06_density_frobenius':1e-6,'T06_fock_frobenius':1e-6}
PATHS=(('production_copy','COPY_MASK',True),('production_owned','INPLACE_OWNED',False),
       ('independent_reference',None,None))


class ExecutionContractError(ValueError):pass


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def _sha(value,name,length=64,prefix=''):
    if not isinstance(value,str) or re.fullmatch(re.escape(prefix)+'[0-9a-f]{'+str(length)+'}',value) is None:
        raise ExecutionContractError(name+' must be a complete immutable identity')


def validate_execution_contract(value):
    try:
        if value['schema_version']!='residual-live-execution-contract-v1':raise ExecutionContractError('Unknown execution contract')
        if (value['scientific_execution_authorized'] is not True or value['production_activation'] is not False
                or value['method_approval'] is not False):
            raise ExecutionContractError('Only an explicitly authorized candidate diagnostic with production/method approval disabled is admitted')
        authority=value['authorization_basis']
        if authority['source']!='DIRECT_USER_MESSAGE' or authority['message']!='请继续下一步实施准入和诊断':
            raise ExecutionContractError('Explicit current user diagnostic instruction required')
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',value['batch_id']):raise ExecutionContractError('Bounded fresh batch identity required')
        for key in ('runtime_test_commit','science_commit','science_baseline_commit','image_build_runtime_commit'):_sha(value[key],key,40)
        _sha(value['image_id'],'image_id',64,'sha256:')
        if (value['science_commit']!=SCIENCE or value['science_baseline_commit']!=BASELINE
                or value['image_id']!=IMAGE or value['image_build_runtime_commit']!=IMAGE_BUILD):
            raise ExecutionContractError('Frozen science/image identities differ')
        for key in ('prior_proposal_sha256','profile_sha256','source_manifest_sha256','dependencies_sha256'):_sha(value[key],key)
        if value['expected_dependencies']!=DEPENDENCIES or value['dependencies_sha256']!=canonical_sha(DEPENDENCIES):
            raise ExecutionContractError('Frozen dependency identity differs')
        expected={'memory_limit_mib':1024,'threads':1,'swap_allowed':False,'maximum_scientific_processes':1,
            'process_wall_seconds':900,'batch_wall_seconds':900,'candidate_callbacks_per_path':201,
            'conditional_callback_slots_total':603,'serial_paths':True,'automatic_retry':False}
        limits=value['process_contract']
        for key,required in expected.items():
            if type(limits[key]) is not type(required) or limits[key]!=required:
                raise ExecutionContractError('Frozen process limit differs: '+key)
        fixture=value['fixture']
        if (fixture['id']!='ethene-planar-technical-v1' or fixture['profile_id']!='pilot-b3lypg-sto3g-grid2-v1'
                or fixture['request_path']!='examples/user-molecule/w05-candidates/ethene-planar-technical-v1/request-pilot.json'
                or type(fixture['nao']) is not int or fixture['nao']!=14
                or type(fixture['electron_count']) is not int or fixture['electron_count']!=16):
            raise ExecutionContractError('Only the exact fixed pilot fixture is admitted')
        if fixture['normalized_request_sha256']!='46a9f72bcf346e3be353d98291d8873a957675329f907ffd8271ca72df61bbab' or fixture['xyz_sha256']!='69f55725834dfa8419dfc6019ae56dd564f9a0ae18ec28e706245b785bfac80d':
            raise ExecutionContractError('Fixed request/geometry identity differs')
        origin=value['ordinary_origin']
        for name,expected in (('record','b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663'),
                              ('arrays','2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051')):
            if origin[name]['sha256']!=expected:raise ExecutionContractError('Exact old full ordinary source required')
        if origin['record_file']!='ordinary-reference.json' or origin['arrays_file']!='ordinary-reference.npz' or origin['common_density_identity']['sha256']!='9dc813178f17be82f7c231c7b9d0a0494e8d4bcd2acea05ac2605bf3bf268f8a':
            raise ExecutionContractError('Common D0 may not be mixed with another run')
        initial=value['initialization']
        if initial['policy']!='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0' or type(initial['initial_gap_minimum_hartree']) not in (int,float) or initial['initial_gap_minimum_hartree']!=1e-6:
            raise ExecutionContractError('Explicit frozen initialization admission required')
        if len(value['paths'])!=3:raise ExecutionContractError('Three exact serial paths required')
        for actual,(name,mode,optimize) in zip(value['paths'],PATHS):
            if actual['id']!=name or type(actual['callback_slots']) is not int or actual['callback_slots']!=201:
                raise ExecutionContractError('Path identity or callback limit differs')
            if mode is not None and (actual['eri_mode']!=mode or actual['optimize_eri_contractions'] is not optimize):
                raise ExecutionContractError('Exact contraction/storage mode required')
        settings=value['solver_parameters']
        for key,expected in (('maximum_iterations',8),('maximum_backtracks',8)):
            if type(settings[key]) is not int or settings[key]!=expected:raise ExecutionContractError('Frozen solver integer required: '+key)
        for key,expected in (('finite_difference_step',1e-5),('trust_radius',.25)):
            if type(settings[key]) not in (int,float) or settings[key]!=expected:raise ExecutionContractError('Frozen solver parameter required: '+key)
        admission=value['admission']
        for key in ('minimum_host_free_bytes','minimum_vm_available_bytes'):
            if type(admission[key]) is not int or admission[key]!=2147483648:raise ExecutionContractError('Separate2GiB host/VM admission required')
        _sha(admission['host_receipt_sha256'],'host_receipt_sha256')
        for key,expected in NUMERICAL_COMPARISONS.items():
            actual=value['comparisons'][key]
            if isinstance(expected,dict):
                if not isinstance(actual,dict) or actual.keys()!=expected.keys():raise ExecutionContractError('Frozen T05 items differ')
                pairs=((actual[name],limit) for name,limit in expected.items())
            else:pairs=((actual,expected),)
            if any(type(number) not in (int,float) or number!=limit for number,limit in pairs):
                raise ExecutionContractError('Frozen comparison tolerance differs: '+key)
        json.dumps(value,allow_nan=False)
        return value
    except (KeyError,TypeError,ValueError) as error:
        if isinstance(error,ExecutionContractError):raise
        raise ExecutionContractError('Incomplete or invalid exact execution contract: '+str(error)) from error


def load_execution_contract(path):
    return validate_execution_contract(strict_json(Path(path).read_bytes()))


def validate_proposal_binding(contract,proposal_raw):
    """Preserve the old proposal; bind its exact bytes and scientific limits."""
    validate_execution_contract(contract)
    if hashlib.sha256(proposal_raw).hexdigest()!=contract['prior_proposal_sha256']:
        raise ExecutionContractError('Historical proposal bytes differ')
    proposal=strict_json(proposal_raw)
    for key in ('fixture','ordinary_origin','initialization','paths','comparisons','scope_limits'):
        if contract[key]!=proposal[key]:raise ExecutionContractError('Frozen proposal definition differs: '+key)
    return True


def execution_identity(contract,contract_sha256):
    validate_execution_contract(contract);_sha(contract_sha256,'execution_contract_sha256')
    return {'geometry_sha256':contract['fixture']['xyz_sha256'],'profile_sha256':contract['profile_sha256'],
        'dependencies_sha256':contract['dependencies_sha256'],'mode':'LIVE_CONDITIONAL_DIAGNOSTIC',
        'execution_contract_sha256':contract_sha256,'runtime_test_commit':contract['runtime_test_commit'],
        'image_id':contract['image_id'],'image_build_runtime_commit':contract['image_build_runtime_commit'],
        'science_commit':contract['science_commit'],'science_baseline_commit':contract['science_baseline_commit'],
        'ordinary_record_sha256':contract['ordinary_origin']['record']['sha256'],
        'ordinary_arrays_sha256':contract['ordinary_origin']['arrays']['sha256']}


def pre_functional_admission(observation,vm_available_bytes,contract):
    """Startup gate; final resource qualification still needs completed inspect."""
    validate_execution_contract(contract);reasons=[]
    if (type(vm_available_bytes) is not int or vm_available_bytes<contract['admission']['minimum_vm_available_bytes']):
        reasons.append('VM_AVAILABLE_BELOW_REQUIRED_2GIB_OR_UNKNOWN')
    if observation.get('source') not in ('CGROUP_V1','CGROUP_V2'):reasons.append('UNKNOWN_CGROUP_SOURCE')
    if type(observation.get('memory_limit_bytes')) is not int or observation.get('memory_limit_bytes')!=1073741824 or observation.get('memory_limit_unbounded') is not False:
        reasons.append('ACTUAL_1GIB_MEMORY_LIMIT_NOT_CONFIRMED')
    if type(observation.get('memory_swap_limit_bytes')) is not int or observation.get('memory_swap_limit_bytes')!=0 or observation.get('memory_swap_limit_unbounded') is not False:
        reasons.append('ACTUAL_NO_SWAP_LIMIT_NOT_CONFIRMED')
    current=observation.get('memory_current_bytes')
    if type(current) is not int or not 0<=current<1073741824:reasons.append('CURRENT_MEMORY_NOT_WITHIN_LIMIT')
    if observation.get('errors'):reasons.append('NATIVE_CGROUP_READ_ERRORS')
    quota,period=observation.get('cpu_quota_us'),observation.get('cpu_period_us')
    if (observation.get('cpu_limit_unbounded') is not False or type(quota) is not int or
            type(period) is not int or not 0<quota<=period):reasons.append('ACTUAL_CPU_LIMIT_NOT_CONFIRMED')
    events=observation.get('memory_events')
    if not isinstance(events,dict):reasons.append('UNKNOWN_MEMORY_EVENTS')
    elif observation.get('source')=='CGROUP_V1':
        for key in ('limit_failures','under_oom'):
            if type(events.get(key)) is not int or events[key]!=0:reasons.append('V1_EVENT_NOT_CLEAR:'+key)
        if events.get('oom_kill') is not None and (type(events['oom_kill']) is not int or events['oom_kill']!=0):reasons.append('OOM_KILL_OBSERVED')
    else:
        for key in ('oom','oom_kill'):
            if type(events.get(key)) is not int or events[key]!=0:reasons.append('V2_EVENT_NOT_CLEAR:'+key)
    return {'status':'BLOCKED' if reasons else 'ADMITTED_FOR_BOUNDED_DIAGNOSTIC_START',
        'reasons':reasons,'vm_available_bytes':vm_available_bytes,
        'oom_kill_history': 'UNKNOWN_PENDING_COMPLETED_INSPECT' if observation.get('source')=='CGROUP_V1' and isinstance(events,dict) and events.get('oom_kill') is None else 'NATIVE_COUNTER_RECORDED',
        'resource_qualification':'NOT_YET_FINAL','production_activation':False,'method_approval':False}
