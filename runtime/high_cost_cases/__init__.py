"""Fixed P11/P12 optimisation services; independent of the frozen batch2 lane."""
from pathlib import Path
import hashlib, importlib, json, math, os, re

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'reference/high_cost_cases/source_tree'
SOURCE_LOCK=ROOT/'locks/high-cost-source.json'
DEPENDENCY_LOCK=ROOT/'locks/high-cost-dependencies.json'
PROFILE=ROOT/'configs/high-cost-cases-v1.json'
CASE_MODULES={'P11':'p11','P12':'p12'}
MODES=('ledger','preflight','live')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>32*1024*1024:raise ValueError('Unsafe or missing JSON: '+str(p))
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('Duplicate key '+k)
            d[k]=v
        return d
    d=json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON '+v)))
    json.dumps(d,allow_nan=False);return d
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n'
    tmp=p.with_name(p.name+'.atomic.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def adapter(case):
    if case not in CASE_MODULES:raise ValueError('Unknown fixed high-cost case')
    return importlib.import_module('runtime.high_cost_cases.'+CASE_MODULES[case])
def units():
    rows=[]
    for case in CASE_MODULES:
        for raw in adapter(case).units():
            u=dict(raw)
            u['case']=case;u['unit_id']=u['id']
            furan=u.get('subcase')=='P11-A' or u['id'].startswith('P11A-')
            u['operator_id']='ordinary_rks' if u['state']=='G' else ('furan_p09' if furan else 'source2007' if case=='P11' else 'source2011')
            u['optimizer']='scipy_minimize' if furan else 'geometric'
            special_seed=(case=='P11' and not furan and u.get('system')=='cyanobenzene' and u['state'] in ['GE1','GE2','GE3','GE4','GE5','GE6','GE7'])
            u['caps']={'scf':1100 if furan else 200,'gradient':0 if furan else 200,'numint':250000 if furan else 60000,'grids':1100 if furan else 1000,'conditional':550 if furan else 1 if special_seed else 0}
            rows.append(u)
    if len(rows)!=78 or len({u['id'] for u in rows})!=78:raise ValueError('Fixed 17+61 unit registry differs')
    return rows
def unit(identifier):
    for u in units():
        if u['id']==identifier:return u
    raise ValueError('Unknown optimisation unit '+str(identifier))
def limits(case,mode):
    if case not in CASE_MODULES or mode not in MODES:raise ValueError('Unknown scope')
    if mode!='live':return {'memory_bytes':1073741824,'cpus':1,'threads':1,'hard_wall_seconds':180,'soft_wall_seconds':120,'scratch_bytes_required':1073741824}
    return {'memory_bytes':8589934592 if case=='P11' else 15032385536,'cpus':8 if case=='P11' else 16,'threads':8 if case=='P11' else 16,'hard_wall_seconds':43200,'soft_wall_seconds':43080,'scratch_bytes_required':21474836480}
def verify_source():
    d=read_json(SOURCE_LOCK)
    for row in d['files']:
        p=ROOT/row['path']
        if p.is_symlink() or not p.is_file() or digest(p)!=row['sha256']:raise ValueError('Source byte identity differs: '+row['path'])
    return d
def validate_contract(c):
    fields={'schema','case','mode','unit','execution_id','image_id','runtime_build_commit','source_sha256','dependencies_sha256','profile_sha256','resources','started_epoch','stop_deadline_epoch','hard_deadline_epoch','inputs'}
    if not isinstance(c,dict) or set(c)!=fields or c['schema']!='high-cost-state-execution-v1':raise ValueError('Closed high-cost execution fields required')
    if c['case'] not in CASE_MODULES or c['mode'] not in MODES:raise ValueError('Unknown case/mode')
    if c['unit'] is None:
        if c['mode']=='live':raise ValueError('Live requires one explicit optimisation unit')
    elif unit(c['unit'])['case']!=c['case']:raise ValueError('Unit/case differs')
    if c['resources']!=limits(c['case'],c['mode']) or any(type(v) is not int for v in c['resources'].values()):raise ValueError('Frozen resources differ')
    for k,n in [('execution_id',32),('runtime_build_commit',40),('source_sha256',64),('dependencies_sha256',64),('profile_sha256',64)]:
        if not re.fullmatch('[0-9a-f]{'+str(n)+'}',str(c[k])):raise ValueError('Full identity required '+k)
    if not re.fullmatch('sha256:[0-9a-f]{64}',str(c['image_id'])):raise ValueError('Immutable image required')
    for k in ['started_epoch','stop_deadline_epoch','hard_deadline_epoch']:
        if type(c[k]) not in (int,float) or not math.isfinite(c[k]):raise ValueError('Finite deadline required')
    if c['hard_deadline_epoch']-c['started_epoch']!=c['resources']['hard_wall_seconds'] or c['stop_deadline_epoch']-c['started_epoch']!=c['resources']['soft_wall_seconds']:raise ValueError('Deadline differs')
    if not isinstance(c['inputs'],dict):raise ValueError('Dependency receipts required')
    wanted=set(unit(c['unit']).get('dependencies',[])) if c['unit'] and c['mode']=='live' else set()
    if set(c['inputs'])!=wanted:raise ValueError('Exact current-run dependency list required')
    return c
