"""Engineering tests for local services; real PySCF imports are disabled."""
from pathlib import Path
import argparse
import hashlib
import importlib.abc
import json
import os
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=('test_registered_*.py','test_protocol_cases_*.py','test_high_cost_*.py',
          'test_molecular_service_*.py','test_native_wsl2_check.py')

class NoQuantumImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname=='pyscf' or fullname.startswith('pyscf.'):
            raise ModuleNotFoundError('Real PySCF imports are disabled in engineering CI')
        return None

def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite): yield from leaves(item)
        else: yield item

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',required=True,type=Path)
    args=parser.parse_args()
    if args.output_root.exists(): parser.error('Use a new output directory; no overwrite')
    args.output_root.mkdir(parents=True)
    if os.environ.get('AI4ORGCHEM_HIGH_COST_SCIENTIFIC_TESTS') not in (None,'','0'):
        parser.error('Scientific opt-in is incompatible with this engineering job')
    if any(name=='pyscf' or name.startswith('pyscf.') for name in sys.modules):
        parser.error('PySCF was already imported; use a clean process')
    sys.path.insert(0,str(ROOT)); sys.meta_path.insert(0,NoQuantumImports())
    loader=unittest.TestLoader(); groups=[]; suite=unittest.TestSuite()
    for pattern in PATTERNS:
        group=loader.discover(str(ROOT/'tests'),pattern=pattern)
        ids=[test.id() for test in leaves(group)]
        groups.append({'pattern':pattern,'test_ids':ids,'discovered':len(ids)})
        suite.addTests(group)
    all_ids=[identity for group in groups for identity in group['test_ids']]
    if len(all_ids)!=len(set(all_ids)): raise RuntimeError('Duplicate engineering test identities')
    files=sorted({path for pattern in PATTERNS for path in (ROOT/'tests').glob(pattern)})
    with (args.output_root/'tests.log').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    report={'schema':'local-services-engineering-ci-v1',
            'status':'PASS_ENGINEERING_WITH_DECLARED_SKIPS' if result.wasSuccessful() and result.skipped else 'PASS_ENGINEERING' if result.wasSuccessful() else 'FAIL_ENGINEERING',
            'scope':'Registered cases, batch2/batch3, ordinary molecular service and native WSL2 Check engineering; no actual SCF/optimization/platform acceptance',
            'executed':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
            'skipped':[{'test':test.id(),'reason':reason} for test,reason in result.skipped],
            'failures':[{'test':test.id(),'traceback':trace} for test,trace in result.failures],
            'errors':[{'test':test.id(),'traceback':trace} for test,trace in result.errors],
            'discovered_unique':len(all_ids),'groups':groups,'real_quantum_imports':'BLOCKED',
            'scientific_tests_opted_in':False,'remote_GitHub_Actions':'NOT_EXECUTED',
            'test_source_files':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    (args.output_root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['status','executed','passed','skipped','discovered_unique']},ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
