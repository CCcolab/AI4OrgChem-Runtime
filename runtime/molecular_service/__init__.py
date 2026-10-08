"""User-molecule ordinary calculation contracts, separate from conditional SCF."""
from __future__ import annotations
import hashlib,json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE_LOCK=ROOT/'locks/molecular-service-source.json'
DEPENDENCY_LOCK=ROOT/'locks/molecular-service-dependencies.json'
PROFILE_PATH=ROOT/'profiles/molecular-service/rhf-631gd-small-v1.json'
TASK='single-point'
PROFILE_ID='rhf-631gd-small-v1'
PROTOCOL_ID='ORDINARY_MOLECULAR_SINGLE_POINT_V0.1'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def strict_load(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    def constant(value):raise ValueError('Nonfinite JSON: '+value)
    value=json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    json.dumps(value,allow_nan=False)
    return value
def source_snapshot_sha256():return digest(SOURCE_LOCK)
def verify_source():
    lock=strict_load(SOURCE_LOCK)
    if lock.get('schema')!='molecular-service-source-v1' or not isinstance(lock.get('files'),dict) or not lock['files']:
        raise ValueError('Unknown or empty source closure')
    for name,expected in lock['files'].items():
        path=ROOT/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not re.fullmatch('[0-9a-f]{64}',expected):
            raise ValueError('Unsafe source identity')
        if digest(path)!=expected:raise ValueError('Source bytes differ: '+name)
    return lock
def validate_contract(contract):
    if not isinstance(contract,dict):raise ValueError('Execution contract must be an object')
    allowed={'schema','task','profile_id','protocol_id','scientific_execution_authorized','runtime_commit',
       'source_snapshot_sha256','dependency_lock_sha256','profile_sha256','request_sha256','structure_sha256',
       'input_manifest_sha256','execution_id','memory_limit_bytes','threads','maximum_processes',
       'wall_time_limit_seconds','stop_after_seconds','started_epoch','stop_deadline_epoch','hard_deadline_epoch',
       'scf_kernel_call_limit','boys_kernel_call_limit','pipek_mezey_kernel_call_limit'}
    if set(contract)!=allowed:raise ValueError('Execution fields differ from the closed contract')
    fixed={'schema':'molecular-service-execution-v1','task':TASK,'profile_id':PROFILE_ID,'protocol_id':PROTOCOL_ID,
      'scientific_execution_authorized':True,'memory_limit_bytes':1073741824,'threads':1,'maximum_processes':1,
      'wall_time_limit_seconds':120,'stop_after_seconds':100,'scf_kernel_call_limit':1,
      'boys_kernel_call_limit':0,'pipek_mezey_kernel_call_limit':0}
    for key,value in fixed.items():
        if type(contract.get(key)) is not type(value) or contract[key]!=value:raise ValueError('Contract mismatch: '+key)
    for key,length in (('runtime_commit',40),('execution_id',32),*[(key,64) for key in ('source_snapshot_sha256',
       'dependency_lock_sha256','profile_sha256','request_sha256','structure_sha256','input_manifest_sha256')]):
        if not isinstance(contract.get(key),str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',contract[key]):
            raise ValueError('Invalid execution identity: '+key)
    for key in ('started_epoch','stop_deadline_epoch','hard_deadline_epoch'):
        if type(contract[key]) not in (float,int) or not math.isfinite(contract[key]):raise ValueError('Finite epoch required')
    if abs(contract['stop_deadline_epoch']-contract['started_epoch']-100)>1e-6 or abs(contract['hard_deadline_epoch']-contract['started_epoch']-120)>1e-6:
        raise ValueError('Wall deadlines cannot be extended')
    if contract['profile_sha256']!=digest(PROFILE_PATH):raise ValueError('Actual profile differs')
    return strict_load(PROFILE_PATH)
def validate_case_result(result,contract):
    if not isinstance(result,dict):raise ValueError('Calculation result must be an object')
    if result.get('schema')!='molecular-single-point-result-v1':raise ValueError('Result schema differs')
    for key in ('task','profile_id','protocol_id','execution_id','request_sha256','structure_sha256','profile_sha256'):
        if result.get(key)!=contract[key]:raise ValueError('Result identity mismatch: '+key)
    if result.get('status')!='NUMERICALLY_QUALIFIED_ORDINARY_RHF' or result.get('scientific_qualified') is not True:
        raise ValueError('Ordinary calculation did not qualify')
    if result.get('stability_status')!='NOT_EXECUTED' or result.get('stability')!='NOT_EXECUTED':raise ValueError('Uncontracted stability claim')
    if result.get('execution_identity')!=contract:raise ValueError('Result execution contract differs')
    validate_contract(result['execution_identity'])
    if result.get('execution_kind')!='PINNED_PYSCF_ORDINARY_RHF' or result.get('method')!='RHF' or result.get('basis')!='6-31G(d)':
        raise ValueError('Uncontracted method or engineering fixture result')
    for key,expected in (('numerically_qualified',True),('operations_closed',True),('conditional_scf_executed',False)):
        if type(result.get(key)) is not bool or result[key] is not expected:raise ValueError('Result gate differs: '+key)
    diagnostics=result.get('diagnostics',{})
    if not isinstance(diagnostics,dict):raise ValueError('Numerical diagnostics must be an object')
    checks=diagnostics.get('checks',{})
    required={'scf_converged','closed_shell_occupations','electron_number','occupied_orthonormality',
        'whitened_projector_idempotency','density_reconstruction','energy_ledger_closure',
        'whitened_fock_projector_commutator','finite_arrays_and_energy','symmetric_ao_matrices',
        'ordinary_fock_equals_hcore_plus_veff','package_energy_ledger_closure'}
    if diagnostics.get('numerically_qualified') is not True or not isinstance(checks,dict) or set(checks)!=required or any(value is not True for value in checks.values()):
        raise ValueError('Independent ordinary numerical checks are incomplete or failed')
    return result

def verify_calculation_artifacts(directory,result):
    directory=Path(directory)
    if strict_load(directory/'result.json')!=result:raise ValueError('Saved result differs from the qualified calculation')
    if digest(directory/'orbitals-density.npz')!=result.get('array_artifact_sha256'):
        raise ValueError('Array artifact differs from result identity')
    ledger=strict_load(directory/'operation-ledger.json')
    if ledger!=result.get('operation_ledger') or ledger.get('status')!='CLOSED' or ledger.get('execution_id')!=result['execution_id'] or ledger.get('task')!=TASK:
        raise ValueError('Operation ledger did not close consistently')
    operation=ledger.get('operations',{}).get('scf_kernel',{})
    for key,expected in (('limit',1),('charged',1),('entered',1),('returned',1),('failed',0)):
        if type(operation.get(key)) is not int or operation[key]!=expected:raise ValueError('Actual SCF operation ledger differs')
    if operation.get('status')!='SUCCEEDED':raise ValueError('SCF operation did not return successfully')
    return {'status':'PASS_BOUND_CALCULATION_ARTIFACTS','array_sha256':digest(directory/'orbitals-density.npz'),
            'ledger_sha256':digest(directory/'operation-ledger.json')}
