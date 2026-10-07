"""Closed registry for three fixed local cases; no arbitrary molecule dispatch."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE_LOCK = ROOT / 'locks/registered-cases-source.json'
DEPENDENCY_LOCK = ROOT / 'locks/registered-cases-dependencies.json'
REGISTRY = ROOT / 'configs/registered-cases-v1.json'
TASKS = ('p02-statistics', 'p13-graph-ledger', 'p01-orbital-density')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value): raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)

def source_snapshot_sha256():
    return digest(SOURCE_LOCK)

def verify_source():
    lock = strict_load(SOURCE_LOCK)
    if lock.get('schema') != 'registered-case-source-v1': raise ValueError('Unknown source lock')
    if not isinstance(lock.get('files'), dict) or not lock['files']: raise ValueError('Empty source closure')
    for name, expected in lock['files'].items():
        path = ROOT / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            raise ValueError('Unsafe source path: ' + name)
        if not re.fullmatch('[0-9a-f]{64}', expected) or digest(path) != expected:
            raise ValueError('Source bytes differ: ' + name)
    return lock

def validate_contract(contract):
    if not isinstance(contract, dict): raise ValueError('Execution contract must be an object')
    allowed = {'schema','task','protocol_id','scientific_execution_authorized','runtime_commit',
        'source_snapshot_sha256','dependency_lock_sha256','execution_id','memory_limit_bytes',
        'threads','maximum_processes','wall_time_limit_seconds','stop_after_seconds','started_epoch',
        'stop_deadline_epoch','hard_deadline_epoch','scf_kernel_call_limit','boys_kernel_call_limit',
        'pipek_mezey_kernel_call_limit','p01_protocol_sha256'}
    if set(contract) - allowed: raise ValueError('Unrecognized execution fields')
    if contract.get('task') not in TASKS: raise ValueError('Only registered fixed tasks are supported')
    spec = strict_load(REGISTRY)['tasks'][contract['task']]
    quantum = contract['task'] == 'p01-orbital-density'
    fixed = {'schema':'registered-case-execution-v1','protocol_id':spec['protocol_id'],
        'scientific_execution_authorized':quantum,'memory_limit_bytes':1073741824,'threads':1,
        'maximum_processes':1,'wall_time_limit_seconds':120,'stop_after_seconds':100,
        'scf_kernel_call_limit':int(quantum),'boys_kernel_call_limit':int(quantum),
        'pipek_mezey_kernel_call_limit':int(quantum)}
    for key, value in fixed.items():
        if type(contract.get(key)) is not type(value) or contract[key] != value:
            raise ValueError('Fixed contract mismatch: ' + key)
    for key, length in (('runtime_commit',40),('source_snapshot_sha256',64),('dependency_lock_sha256',64),('execution_id',32)):
        if not isinstance(contract.get(key),str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',contract[key]):
            raise ValueError('Invalid execution identity: ' + key)
    for key in ('started_epoch','stop_deadline_epoch','hard_deadline_epoch'):
        if type(contract.get(key)) not in (int,float) or not math.isfinite(contract[key]):
            raise ValueError('Finite execution epoch required: ' + key)
    if abs(contract['stop_deadline_epoch']-contract['started_epoch']-100)>1e-6 or abs(contract['hard_deadline_epoch']-contract['started_epoch']-120)>1e-6:
        raise ValueError('The original wall clock deadlines cannot be extended')
    if quantum:
        if contract.get('p01_protocol_sha256') != spec['protocol_sha256']: raise ValueError('P01 protocol differs')
    elif 'p01_protocol_sha256' in contract:
        raise ValueError('P01 scientific authorization is not applicable to a pure task')
    return spec

def validate_case_result(result, contract):
    if not isinstance(result,dict) or result.get('protocol_id')!=contract['protocol_id']:
        raise ValueError('Case result protocol differs from its execution contract')
    task=contract['task']
    if task=='p01-orbital-density':
        if result.get('task')!=task:raise ValueError('P01 fixed result task differs')
    else:
        case={'p02-statistics':'P02','p13-graph-ledger':'P13'}[task]
        if result.get('case_id')!=case or result.get('proposition_id')!=case:
            raise ValueError('Pure case result identity differs from the requested task')
    return result
