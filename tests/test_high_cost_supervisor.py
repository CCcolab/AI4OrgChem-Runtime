import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from runtime.high_cost_cases import save,digest,limits
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('high_cost_host_tests',ROOT/'scripts/run-high-cost-case.py');host=importlib.util.module_from_spec(s);s.loader.exec_module(host)
class Supervisor(unittest.TestCase):
    def test_output_inside_science_or_runtime_is_rejected(self):
        with self.assertRaises(ValueError):host.validate_directory(ROOT/'runs')
    def test_container_ownership_cannot_be_substituted(self):
        c={'image_id':'sha256:'+'a'*64,'execution_id':'b'*32}
        d={'Id':'c'*64,'Image':c['image_id'],'Config':{'Labels':{host.LABEL:'other'}}}
        with self.assertRaises(ValueError):host.ownership(d,c,'c'*64)
    def test_dependency_identity_must_be_same_environment(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'source';run=root/'run';source.mkdir();run.mkdir()
            save(source/'worker-receipt.json',{'status':'PASS_SCOPED_HIGH_COST_STATE','unit':'prior','mode':'live'})
            save(source/'result.json',{'status':'PASS','source_sha256':'wrong'})
            save(root/'host-execution.json',{'status':'PASS_SCOPED_HIGH_COST_LIVE','container_removed':True})
            with self.assertRaises(ValueError):host.snapshot_inputs({'prior':source},run,{'source_sha256':'expected','dependencies_sha256':'d','profile_sha256':'p','image_id':'i'},{'dependencies':['prior']})
    def test_copy_time_mutation_cannot_be_rebound_by_new_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'source';run=root/'run';source.mkdir();run.mkdir()
            identity={k:k+'-same' for k in ['source_sha256','dependencies_sha256','profile_sha256','image_id']}
            save(source/'result.json',{'status':'PASS',**identity});(source/'density.bin').write_bytes(b'original')
            save(source/'run-manifest.json',{'files':{'result.json':digest(source/'result.json'),'density.bin':digest(source/'density.bin')}})
            save(source/'worker-receipt.json',{'status':'PASS_SCOPED_HIGH_COST_STATE','unit':'prior','mode':'live','run_manifest_sha256':digest(source/'run-manifest.json'),'result_sha256':digest(source/'result.json')})
            save(root/'host-execution.json',{'status':'PASS_SCOPED_HIGH_COST_LIVE','container_removed':True})
            original=host.shutil.copytree
            def mutating_copy(src,dest,**kw):
                result=original(src,dest,**kw);(Path(dest)/'density.bin').write_bytes(b'changed')
                save(Path(dest)/'run-manifest.json',{'files':{'result.json':digest(Path(dest)/'result.json'),'density.bin':digest(Path(dest)/'density.bin')}})
                return result
            with patch.object(host.shutil,'copytree',side_effect=mutating_copy):
                with self.assertRaisesRegex(ValueError,'during snapshot'):host.snapshot_inputs({'prior':source},run,identity,{'dependencies':['prior']})
    def test_success_dependency_is_copied_and_revalidated(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'source';run=root/'run';source.mkdir();run.mkdir()
            identity={k:k+'-same' for k in ['source_sha256','dependencies_sha256','profile_sha256','image_id']}
            save(source/'result.json',{'status':'PASS',**identity});save(source/'run-manifest.json',{'files':{'result.json':digest(source/'result.json')}})
            save(source/'worker-receipt.json',{'status':'PASS_SCOPED_HIGH_COST_STATE','unit':'prior','mode':'live','run_manifest_sha256':digest(source/'run-manifest.json'),'result_sha256':digest(source/'result.json')})
            save(root/'host-execution.json',{'status':'PASS_SCOPED_HIGH_COST_LIVE','container_removed':True})
            result=host.snapshot_inputs({'prior':source},run,identity,{'dependencies':['prior']})
            self.assertEqual(result['prior']['result_sha256'],digest(source/'result.json'))
    def test_resource_probe_is_not_a_scientific_optimisation(self):
        from runtime.high_cost_cases.resources import admission
        r=limits('P11','preflight');v=admission(r,{'NCPU':22,'MemTotal':16*1024**3},{'available_bytes':12*1024**3},{'available_bytes':6*1024**3},100*1024**3,live=False)
        self.assertEqual(v['status'],'PASS')
if __name__=='__main__':unittest.main()
