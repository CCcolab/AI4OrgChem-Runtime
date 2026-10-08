import importlib.util,json,tempfile,unittest,subprocess
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from runtime.high_cost_cases import save,digest,limits
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('high_cost_host_tests',ROOT/'scripts/run-high-cost-case.py');host=importlib.util.module_from_spec(s);s.loader.exec_module(host)
class Supervisor(unittest.TestCase):
    @contextmanager
    def host_source_fixture(self,overlay=True):
        """An exact-size artificial base avoids touching scientific files."""
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows=[]
            names=sorted(host.HOST_LAUNCHER_FILES)+['reference/fixture/item%03d.bin'%n for n in range(105)]
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('base:'+name).encode())
                rows.append({'path':name,'sha256':digest(path),'size':path.stat().st_size})
            source=root/'locks/high-cost-source.json';save(source,{'files':rows})
            source_sha=digest(source);lock=root/'locks/high-cost-host-launcher.json'
            record={'source_sha256':source_sha,'image_id':host.BASE_IMAGE_ID}
            with patch.object(host,'ROOT',root),patch.object(host,'SOURCE_LOCK',source),\
                 patch.object(host,'HOST_LAUNCHER_LOCK',lock),patch.object(host,'BASE_SOURCE_SHA256',source_sha):
                if overlay:
                    for name in host.HOST_LAUNCHER_FILES:(root/name).write_bytes(('host-patch:'+name).encode())
                    save(lock,host.make_host_launcher_lock(record));record['host_launcher_lock_sha256']=digest(lock)
                yield root,record
    def test_original_base_source_without_overlay_remains_compatible(self):
        with self.host_source_fixture(overlay=False) as (root,record):
            identity=host.verify_source(record)
            self.assertEqual(identity['scope'],'BASELINE_NO_OVERLAY')
            self.assertIsNone(identity['host_launcher_lock_sha256'])
    def test_registered_host_patch_preserves_other_105_base_files(self):
        with self.host_source_fixture() as (root,record):
            identity=host.verify_source(record)
            self.assertEqual(identity['scope'],'HOST_FINAL_EVIDENCE_ONLY')
            self.assertEqual(set(identity['files']),host.HOST_LAUNCHER_FILES)
            self.assertEqual(identity['host_launcher_lock_sha256'],record['host_launcher_lock_sha256'])
    def test_host_patch_without_registration_is_refused(self):
        with self.host_source_fixture() as (root,record):
            del record['host_launcher_lock_sha256']
            with self.assertRaisesRegex(ValueError,'Host source byte identity'):host.verify_source(record)
    def test_uncovered_scientific_file_change_is_refused(self):
        with self.host_source_fixture() as (root,record):
            (root/'reference/fixture/item000.bin').write_bytes(b'changed science')
            with self.assertRaisesRegex(ValueError,'Host source byte identity'):host.verify_source(record)
    def test_registered_host_file_mutation_is_refused(self):
        with self.host_source_fixture() as (root,record):
            (root/'scripts/run-high-cost-case.py').write_bytes(b'changed after registration')
            with self.assertRaisesRegex(ValueError,'Host source byte identity'):host.verify_source(record)
    def test_registered_host_lock_hash_mutation_is_refused(self):
        with self.host_source_fixture() as (root,record):
            record['host_launcher_lock_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'lock SHA differs'):host.verify_source(record)
    def test_host_lock_source_image_and_scope_bindings_are_not_aliases(self):
        for field,value in [('base_source_sha256','0'*64),('image_id','sha256:'+'0'*64),('scope','ARBITRARY_OVERRIDE')]:
            with self.subTest(field=field),self.host_source_fixture() as (root,record):
                overlay=host.read_json(host.HOST_LAUNCHER_LOCK);overlay[field]=value
                save(host.HOST_LAUNCHER_LOCK,overlay);record['host_launcher_lock_sha256']=digest(host.HOST_LAUNCHER_LOCK)
                with self.assertRaises(ValueError):host.verify_source(record)
    def test_host_lock_cannot_cover_a_third_path(self):
        with self.host_source_fixture() as (root,record):
            overlay=host.read_json(host.HOST_LAUNCHER_LOCK)
            overlay['files']['reference/fixture/item000.bin']={'base_sha256':'0'*64,'sha256':'0'*64}
            save(host.HOST_LAUNCHER_LOCK,overlay);record['host_launcher_lock_sha256']=digest(host.HOST_LAUNCHER_LOCK)
            with self.assertRaisesRegex(ValueError,'two frozen host file'):host.verify_source(record)
    def test_host_override_cannot_claim_a_different_base_blob(self):
        with self.host_source_fixture() as (root,record):
            overlay=host.read_json(host.HOST_LAUNCHER_LOCK)
            overlay['files']['scripts/run-high-cost-case.py']['base_sha256']='0'*64
            save(host.HOST_LAUNCHER_LOCK,overlay);record['host_launcher_lock_sha256']=digest(host.HOST_LAUNCHER_LOCK)
            with self.assertRaisesRegex(ValueError,'override base/hash differs'):host.verify_source(record)
    def test_worker_source_registration_cannot_be_rebound(self):
        with self.host_source_fixture() as (root,record):
            record['source_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'base source or image differs'):host.verify_source(record)
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
    def test_final_manifest_includes_post_refusal_probe_cleanup_journal(self):
        """Exercise the saved-log race without launching Docker or science."""
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            record=host.read_json(ROOT/'validation/high-cost-cases/candidate-image.json')
            calls=[]
            def fake_docker(arguments,**kwargs):
                calls.append(arguments[1:])
                if arguments[1:3]==['image','inspect']:
                    data=[{'Id':record['image_id']}];code=0;stderr=b''
                elif arguments[1]=='info':
                    data={'NCPU':22,'MemTotal':16*1024**3};code=0;stderr=b''
                elif arguments[1]=='run':
                    self.assertIn('high-cost-resource-probe-',arguments[arguments.index('--name')+1])
                    data={'available_bytes':1024**3,'total_bytes':16*1024**3};code=0;stderr=b''
                elif arguments[1]=='inspect' and arguments[2].startswith('high-cost-resource-probe-'):
                    data=[];code=1;stderr=b'error: no such object: resource probe\n'
                else:
                    self.fail('Unexpected Docker or scientific operation: '+repr(arguments))
                return subprocess.CompletedProcess(arguments,code,json.dumps(data).encode(),stderr)
            args=SimpleNamespace(task='P11',mode='preflight',unit=None,output_root=root,
                                 budget=None,inputs=None,docker_executable='fake-docker')
            with patch.object(host,'verify_source',return_value={'scope':'TEST_ZERO_KERNEL'}),patch.object(host,'image_check'),\
                 patch.object(host,'host_memory',return_value={'total_bytes':32*1024**3,'available_bytes':16*1024**3}),\
                 patch.object(host.subprocess,'run',side_effect=fake_docker):
                code,run,e=host.run(args)
            self.assertEqual(code,40)
            self.assertEqual(e['status'],'BLOCKED_RESOURCE_CAPACITY')
            self.assertFalse(e['worker_started'])
            self.assertTrue(e['owned_capacity_probe_closed'])
            self.assertTrue(e['owned_lock_released'])
            self.assertEqual(e['host_launcher'],{'scope':'TEST_ZERO_KERNEL'})
            journal=[json.loads(line) for line in (run/'commands.jsonl').read_text().splitlines()]
            self.assertEqual(len(journal),4)
            self.assertEqual(journal[-1]['arguments'][1],'inspect')
            self.assertEqual(journal[-1]['exit_code'],1)
            manifest=host.read_json(run/'host-run-manifest.json')
            self.assertIn(journal[-1]['stdout'],manifest['files'])
            self.assertIn(journal[-1]['stderr'],manifest['files'])
            self.assertIn('host-execution.json',manifest['files'])
            self.assertNotIn('host-run-manifest.json',manifest['files'])
            for name,sha in manifest['files'].items():
                self.assertEqual(digest(run/name),sha,name)
            self.assertEqual(manifest['files']['commands.jsonl'],digest(run/'commands.jsonl'))
            self.assertFalse(any(row[0] in ['create','start'] for row in calls))
if __name__=='__main__':unittest.main()
