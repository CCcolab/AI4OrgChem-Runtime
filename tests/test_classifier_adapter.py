"""Frozen fixtures test path adaptation only; never report a new QM rerun."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.cli import ROOT, load

SOURCE = Path(os.environ.get('AI4ORGCHEM_TEST_SOURCE', '/opt/ai4orgchem'))


@unittest.skipUnless(sys.platform == 'linux' and SOURCE.is_dir(), 'Linux fixed-source fixture required')
class ClassifierAdapterTests(unittest.TestCase):
    def test_path_adapter_on_four_frozen_fixtures(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            view = run / 'view'
            view.mkdir()
            for name in ('configs', 'evidence'):
                (view / name).symlink_to(SOURCE / name, target_is_directory=True)
            files = {
                'smoke':'p14_benzotricyclobutadiene_fixed_geometry_smoke_v0.1.json',
                'optimization':'p14_C12H6_B3LYPG_6_31Gd_production_optimization_v0.1.json',
                'equivalence':'p14_memory_controlled_eri_equivalence_v0.1.json',
                'source-level':'p14_C12H6_source_level_fixed_geometry_v0.1.json'}
            arguments = []
            for key, filename in files.items():
                target = view / (key + '.json')
                shutil.copyfile(SOURCE / 'evidence/P01-P14/P14/processed' / filename, target)
                arguments.extend(['--'+key,str(target)])
            env = os.environ.copy()
            env.update(PYTHONPATH=str(SOURCE/'software/src'),PYTHONDONTWRITEBYTECODE='1')
            completed = subprocess.run([sys.executable,str(ROOT/'runtime/classify.py'),
                '--source',str(SOURCE),'--view',str(view),'--protocol',str(SOURCE/'configs/qm/p14_strained_aromatic_pi_distortivity_v0.1.yaml'),
                '--output',str(run/'fixture-result.json'),'--report',str(run/'fixture-report.md'),*arguments],env=env,capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode())
            rebuilt = load(run/'fixture-result.json')
            frozen = load(SOURCE/'evidence/P01-P14/P14/result.json')
            for field in ('quantitative_evidence','decision_checks','optimization_eligibility_checks','decision_verdict','classification'):
                self.assertEqual(rebuilt[field],frozen[field])

    def test_actual_cli_refuses_missing_classification_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run([sys.executable,'-m','runtime.cli','run','p14-classify',
                '--source',str(SOURCE),'--output-root',directory],cwd=ROOT,capture_output=True)
            self.assertEqual(completed.returncode,2,completed.stderr.decode())
            manifests = list(Path(directory).glob('*/run-manifest.json'))
            self.assertEqual(len(manifests),1)
            record = load(manifests[0])
            self.assertEqual(record['status'],'FAIL')
            self.assertIn('frozen defaults are forbidden',record['error'])
            self.assertEqual(record['commands'],[])
