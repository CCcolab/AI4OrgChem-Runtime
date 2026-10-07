"""Scoped fake-only root engineering; no native molecular API is allowed."""
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
PATTERNS=('test_reference_occupied_space_root_candidate.py',
    'test_user_molecule_occupied_space_root_contract.py',
    'test_user_molecule_occupied_space_root_supervisor.py',
    'test_user_molecule_occupied_space_root_worker.py',
    'test_reference_residual_budgeted_candidate.py',
    'test_reference_residual_candidate.py',
    'test_user_molecule_residual_budget.py',
    'test_user_molecule_solver_candidate.py',
    'test_user_molecule_occupied_space_seeds.py',
    'test_user_molecule_occupied_space_admission.py',
    'test_user_molecule_occupied_space_response_contract.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=Path('/output'))
    output=parser.parse_args().output_root.resolve()
    if output==ROOT or output.is_relative_to(ROOT):raise ValueError('Evidence must be outside source')
    output.mkdir(parents=True,exist_ok=True)
    result_path=output/'occupied-space-root-engineering-tests.json'
    if result_path.exists():raise ValueError('Fresh engineering output required')
    sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location('root_guard_helpers',ROOT/'scripts/ci-guard-budget-recording.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    spec2=importlib.util.spec_from_file_location('root_mount_helpers',ROOT/'scripts/ci-guard-occupied-space.py')
    mounts=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(mounts)
    scratch=Path(tempfile.gettempdir()).resolve()
    inputs=Path(os.environ['AI4ORGCHEM_OCCUPIED_ROOT_INPUT_DIR']).resolve()
    for alias in ('AI4ORGCHEM_OCCUPIED_SEED_INPUT_DIR','AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR'):
        if os.environ.get(alias)!=str(inputs):raise ValueError('Explicit retained input aliases must agree')
    synthetic_mount=helpers.tmpfs_mount(scratch);input_mount=mounts._readonly_mount(inputs)
    for variable,leaf in (('AI4ORGCHEM_EVIDENCE_TEST_STAGE','evidence'),
        ('AI4ORGCHEM_REPORT_TEST_STAGE','reports'),('AI4ORGCHEM_PRESERVATION_TEST_STAGE','preservation')):
        os.environ[variable]=str(scratch/'occupied-root-engineering-fixtures'/leaf)
    attempts=[];bindings=helpers.install_guards(attempts)
    from pyscf import gto
    def no_nuclear(*_args,**_kwargs):
        attempts.append('Mole.energy_nuc');raise AssertionError('Molecular nuclear evaluation forbidden')
    gto.Mole.energy_nuc=no_nuclear;bindings.append((gto.Mole,'energy_nuc',no_nuclear,'Mole.energy_nuc'))
    rows=[];seen=set();started=time.monotonic()
    record={'status':'RUNNING','scope':'TARGETED_FAKE_ONLY_ROOT_IMPLEMENTATION_AND_GUARDED_REGRESSIONS',
        'planned_groups':PATTERNS,'groups':rows,'synthetic_fixture_mount':synthetic_mount,
        'sealed_input_mount':input_mount,'guarded_operations':[row[3] for row in bindings],
        'forbidden_operation_attempts':attempts,'scientific_budget':None,
        'scientific_execution_authorized':False,'new_real_F_NR_SCF_grid_integral_calls':0,
        'new_nuclear_repulsion_calls':0,'root_search':'NOT_EXECUTED','Compute':False,
        'full_W01_W07_CI':'NOT_EXECUTED','GitHub_Actions':'NOT_EXECUTED'}
    try:
        groups=[(pattern,unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern)) for pattern in PATTERNS]
        record['planned_test_ids']=[name for _,suite in groups for name in helpers.test_ids(suite)]
        if len(record['planned_test_ids'])!=len(set(record['planned_test_ids'])):raise ValueError('Duplicate planned test IDs')
        for pattern,suite in groups:
            planned=helpers.test_ids(suite)
            result=unittest.TextTestRunner(verbosity=2,resultclass=helpers.RecordedResult).run(suite)
            executed=result.executed_test_ids
            changed=[label for owner,name,guard,label in bindings if getattr(owner,name)is not guard]
            good=(bool(result.testsRun) and result.wasSuccessful() and not result.skipped and planned==executed
                and len(executed)==result.testsRun and not seen.intersection(executed) and not attempts and not changed)
            rows.append({'pattern':pattern,'tests':result.testsRun,'planned_test_ids':planned,'test_ids':executed,
                'status':'PASS_ENGINEERING_ONLY' if good else 'FAIL',
                'failures':[{'test_id':test.id(),'detail':detail} for test,detail in result.failures],
                'errors':[{'test_id':test.id(),'detail':detail} for test,detail in result.errors],
                'skips':[{'test_id':test.id(),'reason':reason} for test,reason in result.skipped],
                'guard_bindings_checked':len(bindings),'changed_guard_bindings':changed})
            seen.update(executed);helpers.save(output/'test-progress.json',record)
            if not good:raise RuntimeError('Engineering group or guard failed: '+pattern)
        from reference import occupied_space_root_candidate as candidate
        value=candidate.ENGINEERING_FAKE_CALLBACK_COUNTS
        if (set(value)!={'entered','completed','failed'} or any(type(n)is not int or n<0 for n in value.values())
                or value['entered']!=value['completed']+value['failed'] or value['entered']<1):
            raise RuntimeError('Unsettled explicit root fake counters')
        record['root_test_double_callback_counts']={'counts':dict(value),
            'scope':'EXPLICIT_ROOT_TEST_DOUBLE_LAYER_NOT_NATIVE_F',
            'regression_callback_layers':'NOT_ADDITIVELY_INSTRUMENTED_BY_THIS_COUNTER'}
        if candidate.LIVE_EXECUTION_IMPLEMENTED is not False:raise RuntimeError('Live execution must remain disabled')
        record['status']='PASS_SCOPED_ENGINEERING_ONLY'
    except BaseException as error:
        record.update(status='FAIL_ENGINEERING_ONLY',error_type=type(error).__name__,error=str(error));raise
    finally:
        changed=[label for owner,name,guard,label in bindings if getattr(owner,name)is not guard]
        record.update(executed_test_ids=[name for row in rows for name in row['test_ids']],
            unique_tests=len(seen),test_executions=sum(row['tests'] for row in rows),
            elapsed_seconds=time.monotonic()-started,changed_guard_bindings=changed,
            guard_status='PASS' if len(bindings)==14 and not changed and not attempts else 'FAIL')
        helpers.save(result_path,record)
    print(json.dumps({'status':record['status'],'unique_tests':len(seen),'native_F':0,'Compute':False}))


if __name__=='__main__':main()
