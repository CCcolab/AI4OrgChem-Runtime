"""Current navigation declarations remain separate from execution and historical evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('local_capabilities',ROOT/'scripts/local-runtime-capabilities.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CurrentCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.record=MODULE.load_capabilities(MODULE.CURRENT)
        self.rows={r['id']:r for r in self.record['capabilities']}

    def rejected(self,change):
        record=copy.deepcopy(self.record)
        change(record)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'record.json'
            path.write_text(json.dumps(record),encoding='utf-8')
            with self.assertRaises(ValueError): MODULE.load_capabilities(path)

    def test_all_current_modules_and_scoped_compute(self):
        self.assertEqual(set(self.rows),{'ordinary-molecular-single-point','p02-statistics','p13-graph-ledger','p01-orbital-density',*('P'+str(i).zfill(2) for i in range(3,13)),'p14-fixed-tasks','user-compute','root-native-diagnostic'})
        self.assertTrue(self.rows['ordinary-molecular-single-point']['execution_enabled'])
        self.assertFalse(self.rows['user-compute']['execution_enabled'])
        self.assertEqual(self.rows['user-compute']['status'],'BLOCKED')
        self.assertNotIn('compute_enabled',self.record)

    def run_cli(self,*extra):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/local-runtime-capabilities.py'),'--json',*extra],capture_output=True,text=True,encoding='utf-8')

    def test_history_requires_an_explicit_local_archive(self):
        result=self.run_cli('--historical')
        self.assertEqual(result.returncode,2)
        self.assertIn('LOCAL_ARCHIVE_ONLY',result.stderr)
        self.assertEqual(result.stdout,'')
        self.assertFalse(hasattr(MODULE,'HISTORICAL'))
        result=self.run_cli('--historical-file','unused-local-file.json')
        self.assertEqual(result.returncode,2)
        self.assertIn('LOCAL_ARCHIVE_ONLY',result.stderr)

    def test_explicit_synthetic_v1_local_archive_is_read_without_modification(self):
        historical={
            'schema_version':'local-runtime-capabilities-v1',
            'declaration_grants_execution_authorization':False,
            'compute_enabled':False,
            'capabilities':[{'id':'local-test','name':'Synthetic local archive',
                             'status':'NOT_EXECUTED','scope':'A historical test fixture, not current service acceptance'}],
        }
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'historical.json'
            original=(json.dumps(historical,ensure_ascii=False,indent=2)+'\r\n').encode('utf-8')
            path.write_bytes(original)
            self.assertEqual(MODULE.load_capabilities(path),historical)
            result=self.run_cli('--historical','--historical-file',str(path))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),historical)
            self.assertEqual(path.read_bytes(),original)

    def test_current_registry_and_public_projection_do_not_become_historical_originals(self):
        result=self.run_cli()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['schema_version'],'runtime-capabilities-v2')
        result=self.run_cli('--historical','--historical-file',str(MODULE.CURRENT))
        self.assertEqual(result.returncode,2)
        self.assertIn('LOCAL_ARCHIVE_ONLY',result.stderr)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'projection.json'
            path.write_text(json.dumps({'schema_version':'local-runtime-capabilities-v1-public-projection'}),encoding='utf-8')
            result=self.run_cli('--historical','--historical-file',str(path))
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')

    def test_ci_and_publication_are_scoped_to_recorded_commit(self):
        self.assertEqual(self.record['publication']['source']['status'],'PUBLIC')
        self.assertEqual(self.record['publication']['guide']['status'],'PUBLIC_STATIC_GUIDE')
        self.assertFalse(self.record['publication']['guide']['online_calculation'])
        self.assertEqual(self.record['ci']['run_id'],38003025857)
        self.assertEqual(self.record['ci']['commit'],'86e29b47b38fbd31717ff9aac653386d2e3f768d')
        self.assertEqual(self.record['ci']['successful_jobs'],3)
        self.assertEqual(self.record['distribution']['public_prebuilt_image'],'BLOCKED')

    def test_build_and_host_acceptance_identities_are_distinct(self):
        ordinary=self.rows['ordinary-molecular-single-point']
        self.assertEqual(ordinary['build']['historical_image_build_runtime_commit'],'1f139aa87dbd1dca8e318b5e9d0226b2a7c8668b')
        self.assertTrue(ordinary['build']['historical_acceptance_does_not_certify_current_code'])
        self.assertEqual({r['host_launcher_commit'] for r in ordinary['accepted_runs']},{'a3f6ec7536c510f06b7d521bc09515eb451b9cff'})
        self.assertEqual(len(self.rows['P11']['accepted_runs']),1)
        self.assertEqual(len(self.rows['P12']['accepted_runs']),1)
        self.assertEqual(self.rows['P12']['accepted_runs'][0]['unit'],'P12-N12-G')

    def test_source_authority_keeps_frozen_baseline_and_captured_overlay(self):
        source=self.record['source_authority']
        self.assertEqual(source['baseline_commit'],'28511f3d84fa65707a107cde1e8121a7b4334ecb')
        self.assertEqual(source['baseline_files'],588)
        self.assertEqual(source['adapter_files'],3)
        self.assertEqual(source['adapter_context_commit'],'cc7437901119e71ef7945a12813c021c383e7648')

    def test_navigation_evidence_exists_and_json_pointers_resolve(self):
        for row in self.rows.values():
            references=row['evidence']+[r['record'] for r in row['accepted_runs']]
            for reference in references:
                path=ROOT/reference['path']
                self.assertTrue(path.is_file(),str(path))
                if reference.get('pointer'):
                    value=json.loads(path.read_bytes())
                    for part in reference['pointer'].lstrip('/').split('/'):
                        part=part.replace('~1','/').replace('~0','~')
                        value=value[int(part)] if isinstance(value,list) else value[part]

    def test_declaration_cannot_grant_execution_authorization(self):
        self.rejected(lambda r:r.update(declaration_grants_execution_authorization=True))
        self.rejected(lambda r:r.update(compute_enabled=False))
        self.rejected(lambda r:r['capabilities'].append(copy.deepcopy(r['capabilities'][0])))

    def test_missing_identity_and_enabled_blocked_service_are_rejected(self):
        self.rejected(lambda r:r['capabilities'][0].pop('source'))
        self.rejected(lambda r:r['capabilities'][0]['qualification'].pop('science'))
        self.rejected(lambda r:next(v for v in r['capabilities'] if v['id']=='user-compute').update(execution_enabled=True))


if __name__=='__main__':unittest.main()
