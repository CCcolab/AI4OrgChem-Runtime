"""W06 tests and one actual metadata Check/blocked Compute, no molecular SCF."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path.cwd()
OUTPUT = Path('/output')
sys.path.insert(0, str(ROOT))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    # Enforce the numerical boundary during the whole test process, not just by
    # trusting the test names. Imports/metadata remain available; all molecular
    # SCF, grid construction and integral calls below are forbidden.
    from pyscf import gto, scf
    from pyscf.dft import gen_grid
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Molecular SCF/grid/integrals forbidden in W06 engineering tests')
    scf.hf.SCF.kernel = forbidden
    scf.hf.kernel = forbidden
    gen_grid.Grids.build = forbidden
    gto.Mole.intor = forbidden
    gto.Mole.intor_by_shell = forbidden
    rows = []
    for pattern in ('test_user_molecule_*.py', 'test_reference_user_molecule.py', 'test_runtime.py'):
        suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        rows.append({'pattern':pattern,'tests':result.testsRun,'failures':len(result.failures),
                     'errors':len(result.errors),'skipped':len(result.skipped)})
        save(OUTPUT/'test-progress.json', {'groups':rows})
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError('Unit group failed or was skipped: '+pattern)
    from runtime.user_molecule.__main__ import execute, main as cli_main
    from runtime.user_molecule.records import load
    import runtime.user_molecule.records as records
    assert Path(records.__file__).is_relative_to(ROOT)
    assert Path(sys.modules['reference.user_molecule'].__file__).is_relative_to(ROOT)
    request = ROOT/'examples/user-molecule/w05-candidates/ethene-planar-technical-v1/request-pilot.json'
    checked, computed = OUTPUT/'metadata-check', OUTPUT/'blocked-compute'
    assert execute(SimpleNamespace(request=request,output_dir=checked,action='check')) == 0
    receipt = load(checked/'preflight.json')
    assert not receipt['compute_eligible'] and receipt['inspection']['nao'] == 14
    assert all(receipt['inspection'][key] is False for key in ('scf_executed','grid_built','full_eri_allocated'))
    brief = (checked/'report.md').read_text()
    assert '碳 π 组：A=[1]；B=[2]' in brief
    assert '比较可用：False' in brief and '研究资格：NOT_REVIEWED' in brief
    code = execute(SimpleNamespace(request=request,output_dir=computed,action='compute',check_run=checked,lock_root='/locks'))
    assert code == 20
    result = load(computed/'result.json')
    assert result['execution_status']=='BLOCKED' and result['delta_hartree'] is None
    assert result['numerical_status']=='NOT_EXECUTED'
    def hashes():
        return {str(p.relative_to(checked)):hashlib.sha256(p.read_bytes()).hexdigest() for p in checked.rglob('*') if p.is_file()}
    before = hashes()
    sys.argv = ['user-molecule','report','--run-directory',str(checked)]
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):
        assert cli_main() == 0
    assert hashes() == before
    assert '碳 π 组：A=[1]；B=[2]' in stream.getvalue()
    (OUTPUT/'readonly-report.txt').write_text(stream.getvalue(),encoding='utf-8')
    save(OUTPUT/'w06-engineering-tests.json', {'status':'PASS_ENGINEERING_ONLY','groups':rows,
        'unit_test_total':sum(row['tests'] for row in rows),'metadata_check':'PASS; nAO=14',
        'blocked_compute':'PASS; exit=20; no energies','readonly_report':'PASS; bytes unchanged',
        'guarded_operations':['SCF.kernel','hf.kernel','Grids.build','Mole.intor','Mole.intor_by_shell'],
        'molecular_scf':'NOT_EXECUTED','molecular_reference':'NOT_EXECUTED',
        'toy_models':'analytical 2/3 AO arrays; not molecules or PySCF integrals',
        'production_compute_enabled':False,'research_scope_approval':'NOT_REVIEWED'})


if __name__ == '__main__':
    main()
