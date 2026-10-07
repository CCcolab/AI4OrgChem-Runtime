"""New root source-binding engineering under retained native-operation guards."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=('test_root_native_contract.py','test_root_native_accounting.py','test_root_native_candidate.py',
    'test_root_native_binding.py','test_root_native_supervisor.py','test_reference_occupied_space_root_candidate.py',
    'test_root_native_lifecycle.py','test_native_pre_dispatch_stop.py','test_native_stop_supervision.py',
    'test_native_overhead_probe.py','test_native_shutdown_probe.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-root',type=Path,required=True)
    output=parser.parse_args().output_root.resolve()
    if output==ROOT or ROOT in output.parents or output.exists():raise ValueError('Fresh external output required')
    output.mkdir(parents=True)
    sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location('native_root_guard_helpers',ROOT/'scripts/ci-guard-budget-recording.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.tmpfs_mount(Path(tempfile.gettempdir()).resolve())
    attempts=[];bindings=helper.install_guards(attempts)
    from pyscf import gto
    def no_nuclear(*_args,**_kwargs):
        attempts.append('Mole.energy_nuc');raise AssertionError('Native nuclear call forbidden')
    gto.Mole.energy_nuc=no_nuclear;bindings.append((gto.Mole,'energy_nuc',no_nuclear,'Mole.energy_nuc'))
    record={'status':'RUNNING','groups':[],'scope':'SOURCE_NATIVE_BACKEND_ENGINEERING_WITH_NO_NATIVE_CALLS',
        'scientific_execution_authorized':False,'scientific_budget':None,'new_true_F_NR_SCF_grid_integral_calls':0,
        'new_nuclear_energy_calls':0,'Compute':False,'GitHub_Actions':'NOT_EXECUTED'}
    seen=set();started=time.monotonic()
    try:
        for pattern in PATTERNS:
            suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern)
            planned=helper.test_ids(suite)
            with (output/(pattern+'.log')).open('w',encoding='utf-8') as stream:
                result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=helper.RecordedResult).run(suite)
            changed=[label for owner,name,guard,label in bindings if getattr(owner,name)is not guard]
            good=(result.testsRun>0 and result.wasSuccessful() and not result.skipped and result.executed_test_ids==planned
                and not seen.intersection(planned) and not attempts and not changed)
            record['groups'].append({'pattern':pattern,'status':'PASS' if good else 'FAIL','tests':result.testsRun,
                'planned_ids':planned,'actual_ids':result.executed_test_ids,'skips':len(result.skipped),
                'failures':len(result.failures),'errors':len(result.errors),'changed_guards':changed})
            seen.update(result.executed_test_ids)
            if not good:raise RuntimeError('Guarded engineering group failed: '+pattern)
        record['status']='PASS_SCOPED_NATIVE_BINDING_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY',error_type=type(error).__name__,error=str(error));raise
    finally:
        changed=[label for owner,name,guard,label in bindings if getattr(owner,name)is not guard]
        record.update(unique_tests=len(seen),actual_ids=[i for row in record['groups'] for i in row['actual_ids']],
            guard_operations=[row[3] for row in bindings],forbidden_attempts=attempts,changed_guards=changed,
            guard_status='PASS' if len(bindings)==14 and not attempts and not changed else 'FAIL',
            elapsed_seconds=time.monotonic()-started)
        helper.save(output/'summary.json',record)
    print(json.dumps({'status':record['status'],'unique_tests':len(seen),'native_calls':0}))


if __name__=='__main__':main()
