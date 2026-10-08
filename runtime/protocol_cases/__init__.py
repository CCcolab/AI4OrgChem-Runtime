"""Closed, protocol-specific local replay cases; no general conditional Compute."""
from __future__ import annotations
import hashlib
import importlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'reference/protocol_cases/source_tree'
SOURCE_LOCK = ROOT / 'locks/protocol-cases-source.json'
DEPENDENCY_LOCK = ROOT / 'locks/protocol-cases-dependencies.json'
CASE_MODULES = {**dict.fromkeys(('P03','P04','P05','P06'),'p03_p06'),
                **dict.fromkeys(('P07','P08'),'p07_p08'), **dict.fromkeys(('P09','P10'),'p09_p10')}
SCF_CAPS = {'P03':{'RKS':1}, 'P04':{'UHF':6,'UHF1e':8,'RHF':6}, 'P05':{'UHF':3,'UHF1e':4,'RHF':4},
            'P06':{'UHF':2,'UHF1e':2,'RHF':2}, 'P07':{},'P08':{'RKS':1},'P09':{'RKS':1},'P10':{'RKS':5}}
CUSTOM_CAPS = {'P04':{'run_projector_fixed_point_scf':2}, 'P05':{'run_projector_fixed_point_scf':2},
               'P06':{'run_projector_fixed_point_scf':2}, 'P08':{'run_gl2014_scf':1},
               'P09':{'run_p09_conditional_rks':1}}
MODES = ('ledger','preflight','live')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result: raise ValueError('Duplicate key: '+key)
            result[key]=value
        return result
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,
                     parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+v)))
    json.dumps(value,allow_nan=False)  # Also rejects overflow literals such as 1e999.
    return value

def save(path,value):
    path=Path(path)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def verify_source():
    lock=read_json(SOURCE_LOCK)
    for item in lock['files']:
        path=ROOT/item['path']
        if not path.is_file() or path.is_symlink() or digest(path)!=item['sha256']:
            raise ValueError('Source identity mismatch: '+item['path'])
    return lock

def adapter(case):
    if case not in CASE_MODULES: raise ValueError('Unknown fixed protocol case')
    return importlib.import_module('runtime.protocol_cases.'+CASE_MODULES[case])

def spec(case):
    return read_json(ROOT/'configs/protocol-cases-v1.json')['cases'][case]

def limits(mode):
    if mode not in MODES: raise ValueError('Unknown mode')
    return {'memory_bytes':4294967296 if mode=='live' else 1073741824,
            'cpus':2 if mode=='live' else 1, 'threads':2 if mode=='live' else 1,
            'hard_wall_seconds':900 if mode=='live' else 120,
            'soft_wall_seconds':840 if mode=='live' else 90}

def validate_contract(value):
    required={'schema','case','mode','execution_id','runtime_commit','source_lock_sha256',
              'dependency_lock_sha256','resources','started_epoch','stop_deadline_epoch','hard_deadline_epoch'}
    if not isinstance(value,dict) or set(value)!=required: raise ValueError('Closed execution contract fields required')
    if value['schema']!='protocol-case-execution-v1' or value['case'] not in CASE_MODULES or value['mode'] not in MODES:
        raise ValueError('Unknown execution scope')
    if value['case']=='P07' and value['mode']=='live': raise ValueError('P07 has no new QM mode')
    expected=limits(value['mode'])
    if not isinstance(value['resources'],dict) or value['resources']!=expected or any(type(value['resources'].get(k)) is not int for k in expected):
        raise ValueError('Resource contract differs or is not integer-typed')
    for key in ('started_epoch','stop_deadline_epoch','hard_deadline_epoch'):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]): raise ValueError('Finite deadline required')
    if value['stop_deadline_epoch']-value['started_epoch']!=value['resources']['soft_wall_seconds']:
        raise ValueError('Soft deadline differs')
    if value['hard_deadline_epoch']-value['started_epoch']!=value['resources']['hard_wall_seconds']:
        raise ValueError('Hard deadline differs')
    import re
    for key,size in (('execution_id',32),('runtime_commit',40),('source_lock_sha256',64),('dependency_lock_sha256',64)):
        if not isinstance(value[key],str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}',value[key]): raise ValueError('Full identity required: '+key)
    return value
