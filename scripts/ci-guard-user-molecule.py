"""Metadata-only guard probe in the unchanged r3 image; no numeric integrals."""
import hashlib, json, os
from pathlib import Path
from unittest.mock import patch
from pyscf import gto, dft, scf
from ai4orgchem.qm.user_molecule_adapter import inspect

profile_path=Path('/workspace/profiles/user-molecule/research-b3lypg-631gd-grid3-v1.json')
profile=json.loads(profile_path.read_text(encoding='utf-8'))
assert profile['compute_enabled'] is False
request={'resources':{'threads':1},'fragments':[{'id':'A','carbon_atom_indices_1based':[1,2]},
                                                {'id':'B','carbon_atom_indices_1based':[3,4]}]}
atoms=[['C',[-2.,0.,0.]],['C',[-.7,0.,0.]],['C',[.7,0.,0.]],['C',[2.,0.,0.]]]
original_intor=gto.Mole.intor
original_shell=gto.Mole.intor_by_shell
def guarded_intor(mol,name,*args,**kwargs):
    if name.startswith('int2e'):raise AssertionError('Inspect must not call ERI integrals')
    return original_intor(mol,name,*args,**kwargs)
def guarded_shell(mol,name,*args,**kwargs):
    if name.startswith('int2e'):raise AssertionError('Inspect must not call shell ERI integrals')
    return original_shell(mol,name,*args,**kwargs)
forbidden=AssertionError('SCF or grid execution is forbidden in this metadata probe')
with patch.object(gto.Mole,'intor',guarded_intor),patch.object(gto.Mole,'intor_by_shell',guarded_shell),\
     patch.object(scf.hf.SCF,'kernel',side_effect=forbidden),patch('pyscf.scf.hf.kernel',side_effect=forbidden),\
     patch.object(dft.gen_grid.Grids,'build',side_effect=forbidden):
    result=inspect(request,atoms,profile)
assert result['nao']==56 and result['electron_count']==24
assert len(result['ao_labels'])==len(result['ao_descriptors'])==56
pi=[label for label,descriptor in zip(result['ao_labels'],result['ao_descriptors']) if descriptor['kind']=='pi']
assert len(pi)==16
d_pi=[label for label in pi if label[2].endswith('d')]
assert len(d_pi)==8 and {x[3] for x in d_pi}=={'xz','yz'}
assert {x['fragment'] for x in result['ao_descriptors'] if x['kind']=='pi'}=={'A','B'}
assert result['grid_effective']['level']==3 and result['grid_effective']['alignment']==8
assert result['dependencies']==profile['expected_dependencies']
assert result['scf_executed'] is False and result['grid_built'] is False and result['full_eri_allocated'] is False
record={'status':'PASS','purpose':'RESEARCH_PROFILE_METADATA_ONLY','profile_sha256':hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        'image_id':os.environ['AI4ORGCHEM_IMAGE_ID'],'uid':os.getuid(), 'guarded_calls':['SCF','grid build','int2e/full ERI','shell ERI'],
        'pi_ao_count':len(pi),'d_pi_ao_count':len(d_pi),'d_pi_components':['xz','yz'],'inspection':result,
        'scientific_acceptance':'NOT_EXECUTED','compute_enabled':False}
Path('/output/guarded-inspect.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','nao':result['nao'],'pi_ao_count':len(pi),'d_pi_ao_count':len(d_pi),'scf_executed':False}))
