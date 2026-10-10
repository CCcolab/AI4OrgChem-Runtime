"""Portable minimal-dependency CI with exhaustive, explicitly deferred coverage.

The existing twelve groups use the locked non-scientific CI environment,
including jsonschema; this runner does not install dependencies or skip failures.
"""
import argparse
import builtins
import hashlib
import importlib
import importlib.abc
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_PREFIXES = ('numpy', 'pyscf', 'scipy', 'ai4orgchem', 'rdkit')
MINIMAL_PATTERNS = (
    'test_user_molecule_input.py', 'test_user_molecule_preflight.py',
    'test_user_molecule_contracts.py', 'test_user_molecule_acceptance_resources.py',
    'test_user_molecule_solver_contract.py', 'test_user_molecule_research.py',
    'test_user_molecule_run_preservation.py', 'test_user_molecule_evidence.py',
    'test_user_molecule_report_export.py', 'test_user_molecule_residual_budget.py',
    'test_user_molecule_residual_execution_contract.py',
    'test_user_molecule_residual_seed_execution_contract.py',
)
# Historical field retained for older summary consumers; exhaustive coverage below.
ARRAY_PATTERNS = (
    'test_user_molecule_acceptance_metrics.py', 'test_user_molecule_ordinary_reference.py',
    'test_user_molecule_solver_candidate.py', 'test_user_molecule_residual_candidate.py',
    'test_user_molecule_residual_bridge.py', 'test_user_molecule_residual_preparation.py',
    'test_user_molecule_residual_integration.py', 'test_user_molecule_basis_representation.py',
    'test_user_molecule_seed_v2.py', 'test_user_molecule_residual_seed_v2.py',
)

def _entry(file, category, reason, runner, requirements=()):
    return {'file': file, 'category': category, 'reason': reason,
            'runner': runner, 'requirements': list(requirements)}

# Sequence preserves duplicate rows for validation rather than silently overwriting.
TEST_CLASSIFICATIONS = (
    *(_entry(name, 'MINIMAL',
       'Portable synthetic input/resource/record contract in the locked minimal CI environment; no scientific or sealed inputs.',
       'scripts/ci-unit-user-molecule.py') for name in MINIMAL_PATTERNS),
    _entry('test_user_molecule_acceptance_metrics.py', 'GUARDED',
       'NumPy scalar tests are outside the stdlib environment.',
       'scripts/ci-guard-w06.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_ordinary_reference.py', 'LOCAL_ONLY',
       'NumPy reference test doubles also require a locked scientific source rule file.',
       'scripts/ci-guard-w06.py', ('numpy', 'locked scientific source', 'held native-operation guards')),
    _entry('test_user_molecule_solver_candidate.py', 'GUARDED',
       'NumPy solver test doubles require held native APIs.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_residual_candidate.py', 'GUARDED',
       'NumPy residual candidate tests use the guarded array runner.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_residual_bridge.py', 'LOCAL_ONLY',
       'Bridge tests import numerical/source APIs and verify a locked unpublished source.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'pyscf', 'PyYAML', 'locked scientific source', 'held native-operation guards')),
    _entry('test_user_molecule_residual_preparation.py', 'LOCAL_ONLY',
       'Prepared-context tests import PySCF and require the pinned source adapter.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'pyscf', 'locked scientific source', 'held native-operation guards')),
    _entry('test_user_molecule_residual_integration.py', 'LOCAL_ONLY',
       'Array/reference integration imports source-bound preparation fixtures.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'pyscf', 'locked scientific source', 'held native-operation guards')),
    _entry('test_user_molecule_basis_representation.py', 'LOCAL_ONLY',
       'Basis tests import PySCF/source-bound preparation fixtures.',
       'scripts/ci-guard-w06.py', ('numpy', 'pyscf', 'locked scientific source', 'held native-operation guards')),
    _entry('test_user_molecule_seed_v2.py', 'GUARDED',
       'NumPy seed arrays use the dedicated native-guard runner.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_residual_seed_v2.py', 'GUARDED',
       'NumPy V2 preparation uses the dedicated native-guard runner.',
       'scripts/ci-guard-seed-v2.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_occupation_response.py', 'GUARDED',
       'NumPy single-response/quota test doubles require held native APIs.',
       'scripts/ci-guard-occupation-response.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_occupation_response_contract.py', 'LOCAL_ONLY',
       'Includes retained probe-byte integration; synthetic fallback is not sealed-byte acceptance.',
       'scripts/ci-guard-occupation-response.py', ('AI4ORGCHEM_OCCUPATION_PROBE_INPUT_DIR', 'sealed review JSON/NPZ', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_seeds.py', 'GUARDED',
       'NumPy rotation and admission tests retain no-native-operation guards.',
       'scripts/ci-guard-occupied-space.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_admission.py', 'GUARDED',
       'NumPy fake callbacks and persistent quota closure use a dedicated guard runner.',
       'scripts/ci-guard-occupied-space.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_response.py', 'LOCAL_ONLY',
       'NumPy LIVE-declaration test doubles require the retained four-input seed family.',
       'scripts/ci-guard-occupied-space-response.py', ('numpy', 'AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR', 'AI4ORGCHEM_OCCUPIED_SEED_INPUT_DIR', 'sealed seed inputs', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_response_contract.py', 'LOCAL_ONLY',
       'Positive JSON/NPZ binding tests require retained sealed seed files.',
       'scripts/ci-guard-occupied-space-response.py', ('AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR', 'sealed seed inputs', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_supervisor.py', 'GUARDED',
       'Stdlib readiness mocks are scheduled with their dedicated worker/guard suite.',
       'scripts/ci-guard-occupied-space-response.py', ('held native-operation guards',)),
    _entry('test_user_molecule_occupied_space_worker.py', 'GUARDED',
       'NumPy loader and platform mocks use the response worker guard suite.',
       'scripts/ci-guard-occupied-space-response.py', ('numpy', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_root_contract.py', 'LOCAL_ONLY',
       'Positive six-file historical/seed binding requires retained root inputs.',
       'scripts/ci-guard-occupied-space-root.py', ('AI4ORGCHEM_OCCUPIED_ROOT_INPUT_DIR', 'sealed six-file inputs', 'held native-operation guards')),
    _entry('test_user_molecule_occupied_space_root_supervisor.py', 'GUARDED',
       'Stdlib root readiness mocks are scheduled with the fake-only root guard suite.',
       'scripts/ci-guard-occupied-space-root.py', ('held native-operation guards',)),
    _entry('test_user_molecule_occupied_space_root_worker.py', 'GUARDED',
       'NumPy preparation mocks require the fake-only root guard suite.',
       'scripts/ci-guard-occupied-space-root.py', ('numpy', 'held native-operation guards')),
)

class ClassificationError(ValueError):
    def __init__(self, details):
        self.details = details
        super().__init__('Invalid user-test classification: '+json.dumps(details, sort_keys=True))

def classify_test_files(root=ROOT, classifications=TEST_CLASSIFICATIONS):
    """Check the exact current file inventory without importing any tests."""
    root = Path(root)
    actual = {path.name for path in (root/'tests').glob('test_user_molecule_*.py')}
    seen, duplicates, malformed, rows = set(), [], [], []
    for index, entry in enumerate(classifications):
        if not isinstance(entry, dict) or set(entry) != {'file','category','reason','runner','requirements'}:
            malformed.append('entry['+str(index)+']: wrong fields'); continue
        name, runner = entry['file'], entry['runner']
        if (not isinstance(name, str) or not name.startswith('test_user_molecule_')
                or not name.endswith('.py') or '/' in name or '\\' in name):
            malformed.append('entry['+str(index)+']: invalid file'); continue
        if name in seen: duplicates.append(name)
        seen.add(name)
        if (entry['category'] not in ('MINIMAL','GUARDED','LOCAL_ONLY')
                or not isinstance(entry['reason'], str) or not entry['reason'].strip()
                or not isinstance(runner, str) or not runner.startswith('scripts/')
                or '\\' in runner or any(part in ('', '.', '..') for part in runner.split('/'))
                or not (root/runner).is_file() or not isinstance(entry['requirements'], list)
                or any(not isinstance(x, str) or not x.strip() for x in entry['requirements'])
                or (entry['category'] == 'MINIMAL' and entry['requirements'])):
            malformed.append(name+': invalid category/reason/runner/requirements')
        rows.append(dict(entry))
    details = {'unclassified_files': sorted(actual-seen), 'missing_files': sorted(seen-actual),
               'duplicate_files': sorted(set(duplicates)), 'malformed_entries': malformed}
    if any(details.values()): raise ClassificationError(details)
    for row in rows:
        row['test_sha256'] = hashlib.sha256((root/'tests'/row['file']).read_bytes()).hexdigest()
        row['runner_sha256'] = hashlib.sha256((root/row['runner']).read_bytes()).hexdigest()
        row['execution_here'] = 'PLANNED_MINIMAL' if row['category']=='MINIMAL' else 'NOT_EXECUTED_HERE'
    return {'status':'PASS_EXACT_FILE_CLASSIFICATION', 'file_total':len(rows),
            'category_counts':{key:sum(row['category']==key for row in rows)
                               for key in ('MINIMAL','GUARDED','LOCAL_ONLY')}, 'files':rows}

def test_ids(suite):
    if isinstance(suite, unittest.TestSuite):
        return [identity for child in suite for identity in test_ids(child)]
    return [suite.id()]

class RejectScientificImports(importlib.abc.MetaPathFinder):
    """Hold normal import entry points, including cached-module imports."""
    def __init__(self):
        self.attempts, self.installed = [], False
    def reject(self, fullname, entry_point):
        if isinstance(fullname,str) and fullname.split('.')[0] in SCIENTIFIC_PREFIXES:
            self.attempts.append({'module':fullname,'entry_point':entry_point})
            raise AssertionError('Scientific import forbidden in minimal CI: '+fullname)
    def find_spec(self, fullname, path=None, target=None):
        self.reject(fullname,'sys.meta_path')
        return None
    def install(self):
        if self.installed: raise RuntimeError('Import guard already installed')
        self.original_import, self.original_import_module = builtins.__import__, importlib.import_module
        def guarded_import(name,*args,**kwargs):
            self.reject(name,'builtins.__import__')
            return self.original_import(name,*args,**kwargs)
        def guarded_import_module(name,*args,**kwargs):
            self.reject(name,'importlib.import_module')
            return self.original_import_module(name,*args,**kwargs)
        self.guarded_import, self.guarded_import_module = guarded_import, guarded_import_module
        builtins.__import__, importlib.import_module = guarded_import, guarded_import_module
        sys.meta_path.insert(0,self); self.installed=True
    def snapshot(self):
        loaded=sorted(name for name in sys.modules if name.split('.')[0] in SCIENTIFIC_PREFIXES)
        held={'meta_path_finder':self.installed and any(item is self for item in sys.meta_path),
              'builtins_import':self.installed and builtins.__import__ is self.guarded_import,
              'importlib_import_module':self.installed and importlib.import_module is self.guarded_import_module}
        return {'status':'PASS' if all(held.values()) and not self.attempts and not loaded else 'FAIL',
                'held_bindings':held,'forbidden_import_attempts':list(self.attempts),
                'loaded_scientific_modules':loaded,
                'scope':'Python package import boundaries; not an OS/network security sandbox'}
    def close(self):
        if self.installed:
            builtins.__import__,importlib.import_module=self.original_import,self.original_import_module
            sys.meta_path[:]=[item for item in sys.meta_path if item is not self]
            self.installed=False

class AuditTestResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.executed_test_ids=[]
    def startTest(self,test):
        self.executed_test_ids.append(test.id()); super().startTest(test)

class AuditTestRunner(unittest.TextTestRunner):
    resultclass=AuditTestResult
    def _makeResult(self):
        self.last_result=super()._makeResult(); return self.last_result

def _save(path,record):
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def run_minimal_ci(output_root,*,root=ROOT,classifications=TEST_CLASSIFICATIONS,loader=None):
    root,output=Path(root).resolve(),Path(output_root).resolve()
    if output==root or root in output.parents or output.exists():
        raise ValueError('Use a new evidence directory outside the source checkout')
    output.mkdir(parents=True)
    record={'schema_version':'user-molecule-minimal-ci-v2','status':'STARTED',
            'classification':{'status':'NOT_CHECKED'},'groups':[],
            'unit_test_total':0,'unit_test_ids':[],'planned_test_ids':[],
            'guard':{'status':'NOT_INSTALLED'},
            'scientific_scf_grid_full_eri':'NOT_EXECUTED_BY_RUNNER',
            'production_compute_enabled':False,
            'scope':'Portable locked-minimal synthetic engineering only; other classifications explicitly deferred',
            'minimal_dependency_lock':'locks/requirements-user-molecule-ci.txt',
            'array_groups':list(ARRAY_PATTERNS),'array_execution':'NOT_EXECUTED_HERE',
            'reference_v1_v2':'SEPARATE_LOCAL_GUARDED_GROUP; NOT_EXECUTED_HERE',
            'scientific_adapter':'UNPUBLISHED_SOURCE; SEPARATE_LOCAL_GROUP'}
    summary=output/'summary.public.json'; _save(summary,record)
    guard,added_path,previous_env=RejectScientificImports(),False,{}
    try:
        record['classification']=classify_test_files(root,classifications)
        minimal=[row['file'] for row in record['classification']['files'] if row['category']=='MINIMAL']
        if not minimal: raise RuntimeError('No minimal test files classified')
        if any(name.split('.')[0] in SCIENTIFIC_PREFIXES for name in sys.modules):
            raise RuntimeError('Scientific modules already loaded before minimal CI guard')
        for variable,leaf in (('AI4ORGCHEM_EVIDENCE_TEST_STAGE','evidence'),
                              ('AI4ORGCHEM_REPORT_TEST_STAGE','report-export'),
                              ('AI4ORGCHEM_PRESERVATION_TEST_STAGE','run-preservation')):
            previous_env[variable]=os.environ.get(variable)
            os.environ[variable]=str(output/'synthetic-fixtures'/leaf)
        sys.path.insert(0,str(root)); added_path=True
        guard.install(); record['guard']=guard.snapshot(); _save(summary,record)
        actual_loader=loader or unittest.TestLoader()
        for index,pattern in enumerate(minimal):
            suite=actual_loader.discover(str(root/'tests'),pattern=pattern)
            planned=test_ids(suite)
            if not planned or len(planned)!=len(set(planned)) or set(planned)&set(record['planned_test_ids']):
                raise RuntimeError('Empty or duplicate planned test IDs: '+pattern)
            record['planned_test_ids'].extend(planned)
            row={'pattern':pattern,'status':'RUNNING','planned_test_ids':planned,
                 'test_ids':[],'tests':0,'failures':0,'errors':0,'skipped':0,
                 'log':'group-'+str(index).zfill(2)+'.log'}
            record['groups'].append(row); _save(summary,record)
            with (output/row['log']).open('w',encoding='utf-8') as stream:
                runner=AuditTestRunner(stream=stream,verbosity=2)
                try:
                    result=runner.run(suite)
                finally:
                    result=getattr(runner,'last_result',None)
                    if result is not None:
                        row.update(test_ids=list(result.executed_test_ids),tests=result.testsRun,
                                   failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped))
            actual=row['test_ids']; held=guard.snapshot()
            good=(result is not None and bool(result.testsRun) and result.wasSuccessful()
                  and not result.skipped and actual==planned
                  and len(actual)==len(set(actual))==result.testsRun and held['status']=='PASS')
            row['status']='PASS' if good else 'FAIL'
            record.update(status='RUNNING' if good else 'FAIL_ENGINEERING_ONLY',guard=held)
            _save(summary,record)
            if not good: raise RuntimeError('Minimal group failed, skipped, incomplete or guard changed: '+pattern)
        record['status']='PASS_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY',error_type=type(error).__name__,error=str(error))
        if isinstance(error,ClassificationError):
            record['classification']={'status':'FAIL',**error.details}
        raise
    finally:
        record['unit_test_total']=sum(row['tests'] for row in record['groups'])
        record['unit_test_ids']=[identity for row in record['groups'] for identity in row['test_ids']]
        if guard.installed:
            record['guard']=guard.snapshot()
            if record['guard']['status']!='PASS': record['status']='FAIL_ENGINEERING_ONLY'
        for row in record['groups']:
            if row['status']=='RUNNING':row['status']='INCOMPLETE'
        for entry in record['classification'].get('files',[]):
            group=next((row for row in record['groups'] if row['pattern']==entry['file']),None)
            if entry['category']=='MINIMAL':entry['execution_here']=group['status'] if group else 'NOT_EXECUTED'
        guard.close()
        if added_path:sys.path.remove(str(root))
        for variable,previous in previous_env.items():
            if previous is None:os.environ.pop(variable,None)
            else:os.environ[variable]=previous
        _save(summary,record)
    print(json.dumps({'status':record['status'],'unit_test_total':record['unit_test_total'],
                      'classified_files':record['classification']['file_total']},ensure_ascii=False))
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    run_minimal_ci(parser.parse_args().output_root)

if __name__=='__main__':
    main()
