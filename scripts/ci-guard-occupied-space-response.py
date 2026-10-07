"""Targeted engineering tests for the twelve-point real-worker candidate.

Both fake and live-declaration test doubles run behind thirteen held native
API guards.  A live mode label in a test is never a native F observation.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=('test_user_molecule_occupied_space_response.py',
          'test_user_molecule_occupied_space_response_contract.py',
          'test_user_molecule_occupied_space_supervisor.py',
          'test_user_molecule_occupied_space_worker.py',
          'test_user_molecule_occupied_space_seeds.py',
          'test_user_molecule_occupied_space_admission.py',
          'test_user_molecule_occupation_response.py',
          'test_user_molecule_residual_budget.py',
          'test_user_molecule_solver_candidate.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=Path('/output'))
    output=parser.parse_args().output_root.resolve()
    if output.is_relative_to(ROOT):raise ValueError('Evidence must be outside committed read-only source')
    output.mkdir(parents=True,exist_ok=True)
    result_path=output/'occupied-space-response-engineering-tests.json'
    if result_path.exists():raise ValueError('Do not overwrite a previous engineering run')
    sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location('occupied_response_guard_helpers',ROOT/'scripts/ci-guard-budget-recording.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    # Import only the mount-inspection helper, not its previous test main.
    spec2=importlib.util.spec_from_file_location('occupied_response_mount_helpers',ROOT/'scripts/ci-guard-occupied-space.py')
    mount_helpers=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(mount_helpers)
    scratch=Path(tempfile.gettempdir()).resolve()
    synthetic_mount=helpers.tmpfs_mount(scratch)
    inputs=Path(os.environ['AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR']).resolve()
    if os.environ.get('AI4ORGCHEM_OCCUPIED_SEED_INPUT_DIR')!=str(inputs):
        raise ValueError('Both explicit test input aliases must refer to the same sealed input')
    actual_input_mount=mount_helpers._readonly_mount(inputs)
    for variable,leaf in (('AI4ORGCHEM_EVIDENCE_TEST_STAGE','evidence'),
                          ('AI4ORGCHEM_REPORT_TEST_STAGE','reports'),
                          ('AI4ORGCHEM_PRESERVATION_TEST_STAGE','preservation')):
        os.environ[variable]=str(scratch/'occupied-response-engineering-fixtures'/leaf)
    attempts=[];bindings=helpers.install_guards(attempts)
    started=time.monotonic();rows=[];seen=set()
    record={'status':'RUNNING','scope':'TARGETED_ARRAY_AND_GUARDED_TEST_DOUBLE_ENGINEERING_ONLY',
        'planned_groups':PATTERNS,'groups':rows,'synthetic_fixture_mount':synthetic_mount,
        'sealed_input_mount':actual_input_mount,'guarded_operations':[row[3] for row in bindings],
        'forbidden_operation_attempts':attempts,'scientific_budget':None,
        'new_real_F_NR_SCF_grid_integral_calls':0,'Compute':False,
        'full_W01_W07_CI':'NOT_EXECUTED','GitHub_Actions':'NOT_EXECUTED'}
    try:
        groups=[(pattern,unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern)) for pattern in PATTERNS]
        record['planned_test_ids']=[name for _,suite in groups for name in helpers.test_ids(suite)]
        if len(record['planned_test_ids'])!=len(set(record['planned_test_ids'])):raise ValueError('Duplicate planned test IDs')
        for pattern,suite in groups:
            planned=helpers.test_ids(suite)
            result=unittest.TextTestRunner(verbosity=2,resultclass=helpers.RecordedResult).run(suite)
            executed=result.executed_test_ids
            changed=[label for owner,name,guard,label in bindings if getattr(owner,name) is not guard]
            good=(bool(result.testsRun) and result.wasSuccessful() and not result.skipped and planned==executed
                and len(executed)==result.testsRun and not seen.intersection(executed) and not attempts and not changed)
            rows.append({'pattern':pattern,'tests':result.testsRun,'planned_test_ids':planned,'test_ids':executed,
                'status':'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                'failures':[{'test_id':test.id(),'detail':detail} for test,detail in result.failures],
                'errors':[{'test_id':test.id(),'detail':detail} for test,detail in result.errors],
                'skips':[{'test_id':test.id(),'reason':reason} for test,reason in result.skipped],
                'guard_bindings_checked':len(bindings),'changed_guard_bindings':changed})
            seen.update(executed)
            helpers.save(output/'test-progress.json',record)
            if not good:raise RuntimeError('Engineering group/guard failed: '+pattern)
        from runtime.user_molecule import occupied_space_response as adapter
        counters={}
        for key in ('ENGINEERING_FAKE_CALLBACK_COUNTS','PREPARED_WRAPPER_CALLBACK_COUNTS'):
            value=getattr(adapter,key,None)
            if not isinstance(value,dict) or set(value)!={'entered','completed','failed'}:
                raise RuntimeError('Explicit response wrapper counters unavailable: '+key)
            if any(type(n)is not int or n<0 for n in value.values()) or value['entered']!=value['completed']+value['failed']:
                raise RuntimeError('Unsettled response test wrapper counters: '+key)
            counters[key]=dict(value)
        record['test_double_wrapper_counts']={'counts':counters,
            'scope':'LIVE_DECLARATION_WITH_SYNTHETIC_CALLBACKS_IS_NOT_NATIVE_SCIENCE',
            'older_callback_layers':'NOT_ADDITIVELY_INSTRUMENTED_BY_THIS_COUNTER'}
        record['status']='PASS_SCOPED_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY',error_type=type(error).__name__,error=str(error));raise
    finally:
        changed=[label for owner,name,guard,label in bindings if getattr(owner,name) is not guard]
        record.update(executed_test_ids=[name for row in rows for name in row['test_ids']],
            unique_tests=len(seen),test_executions=sum(row['tests'] for row in rows),
            elapsed_seconds=time.monotonic()-started,changed_guard_bindings=changed,
            guard_status='PASS' if len(bindings)==13 and not changed and not attempts else 'FAIL')
        helpers.save(result_path,record)
    print(json.dumps({'status':record['status'],'unique_tests':len(seen),'native_F':0,'Compute':False}))


if __name__=='__main__':main()
