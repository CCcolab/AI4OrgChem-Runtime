"""Host Report exports are derived files, never overwritten run evidence."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.user_molecule.__main__ import main
from runtime.user_molecule.records import manifest, save

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_STAGE=Path(r'D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-report-engineering\export-tests\temporary-runs')


class ReportExportTests(unittest.TestCase):
    def setUp(self):
        self.bound=Path(os.environ.get('AI4ORGCHEM_REPORT_TEST_STAGE',str(DEFAULT_STAGE))).resolve()
        self.bound.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='报告 export ',dir=self.bound)
        self.root=Path(self.temp.name).resolve()
        self.source=self.root/'saved check';self.source.mkdir()
        save(self.source/'input/request.normalized.json',{'research_question':'中文问题 Å <标签>',
             'calculation_profile':'pilot-b3lypg-sto3g-grid2-v1',
             'fragments':[{'id':'A','carbon_atom_indices_1based':[1]},{'id':'B','carbon_atom_indices_1based':[2]}]})
        save(self.source/'preflight.json',{'input_status':'VALID','compute_eligible':False,
             'method_status':'NOT_REVIEWED','reasons':['SYNTHETIC_ENGINEERING_ONLY'],
             'identities':{'image_id':'SYNTHETIC_NOT_A_REAL_IMAGE'}})
        manifest(self.source,action='check',execution_status='COMPLETED',numerical_status='NOT_EXECUTED')

    def tearDown(self):
        assert self.root.is_relative_to(self.bound) and self.root!=self.bound
        self.temp.cleanup()

    def snapshot(self,path):
        return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}

    def invoke(self,*args):
        stdout,stderr=io.StringIO(),io.StringIO()
        original=__import__
        def guarded(name,*values,**options):
            if name.split('.')[0] in ('pyscf','numpy','scipy','ai4orgchem','rdkit'):
                raise AssertionError('Report attempted a scientific import: '+name)
            return original(name,*values,**options)
        with (patch('sys.argv',['user-molecule','report','--run-directory',str(self.source),*map(str,args)]),
              patch('builtins.__import__',side_effect=guarded),
              contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr)):
            code=main()
        return code,stdout.getvalue(),stderr.getvalue()

    def test_export_is_fresh_hash_bound_and_original_run_is_unchanged(self):
        before=self.snapshot(self.source);dest=self.root/'new report'
        code,text,error=self.invoke('--export-directory',dest)
        self.assertEqual(code,0,error);self.assertIn('中文问题',text)
        self.assertEqual(self.snapshot(self.source),before)
        summary=json.loads((dest/'report-summary.json').read_text(encoding='utf-8'))
        self.assertFalse(summary['compute_eligible']);self.assertFalse(summary['comparison_available'])
        self.assertIsNone(summary['delta_hartree'])
        receipt=json.loads((dest/'run-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['scientific_processes_started'],0)
        self.assertEqual(receipt['source_directory'],str(self.source.resolve()))
        for name,entry in receipt['files'].items():
            data=(dest/name).read_bytes()
            self.assertEqual(len(data),entry['size_bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])

    def test_existing_export_is_never_overwritten(self):
        dest=self.root/'existing report';dest.mkdir();(dest/'notes.txt').write_bytes(b'user notes')
        before=self.snapshot(dest);source_before=self.snapshot(self.source)
        code,_,error=self.invoke('--export-directory',dest)
        self.assertEqual(code,40);self.assertIn('new directory',error)
        self.assertEqual(self.snapshot(dest),before)
        self.assertEqual(self.snapshot(self.source),source_before)

    def test_export_inside_original_run_is_rejected_without_creating_directory(self):
        dest=self.source/'derived';before=self.snapshot(self.source)
        code,_,_=self.invoke('--export-directory',dest)
        self.assertEqual(code,40);self.assertFalse(dest.exists())
        self.assertEqual(self.snapshot(self.source),before)

    def test_same_source_and_export_path_is_rejected(self):
        before=self.snapshot(self.source)
        self.assertEqual(self.invoke('--export-directory',self.source)[0],40)
        self.assertEqual(self.snapshot(self.source),before)

    def test_unverified_source_exports_diagnostics_not_a_success_claim(self):
        (self.source/'run-manifest.json').unlink()
        before=self.snapshot(self.source);dest=self.root/'unverified diagnosis'
        code,text,_=self.invoke('--export-directory',dest)
        self.assertEqual(code,40);self.assertIn('UNVERIFIED',text)
        summary=json.loads((dest/'report-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['record_integrity'],'UNVERIFIED')
        self.assertFalse(summary['comparison_available']);self.assertIsNone(summary['delta_hartree'])
        self.assertEqual(self.snapshot(self.source),before)

    def test_changed_record_does_not_get_an_export_or_rewritten_manifest(self):
        (self.source/'preflight.json').write_bytes(b'{"input_status":"VALID","compute_eligible":true}')
        before=self.snapshot(self.source);dest=self.root/'tampered export'
        code,_,error=self.invoke('--export-directory',dest)
        self.assertEqual(code,40);self.assertIn('byte mismatch',error)
        self.assertFalse(dest.exists());self.assertEqual(self.snapshot(self.source),before)

    def test_actual_cli_outputs_utf8_even_when_environment_requests_ascii(self):
        env=dict(os.environ,PYTHONIOENCODING='ascii',PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report-user-molecule.py'),
             'report','--run-directory',str(self.source)],env=env,cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8'))
        text=result.stdout.decode('utf-8')
        self.assertIn('中文问题',text);self.assertIn('Å',text)

    def test_readonly_host_wrapper_rejects_compute_before_creating_run(self):
        dest=self.root/'must not become a compute run'
        before=self.snapshot(self.source)
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report-user-molecule.py'),
            'compute','--request',str(self.source/'missing.json'),'--output-dir',str(dest),
            '--check-run',str(self.source)],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,40)
        self.assertIn(b'report only',result.stderr)
        self.assertFalse(dest.exists());self.assertEqual(self.snapshot(self.source),before)


if __name__=='__main__':
    unittest.main()
