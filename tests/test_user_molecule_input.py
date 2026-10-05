import copy
import json
from pathlib import Path
import tempfile
import unittest
from runtime.user_molecule.input import read_request, parse_xyz, strict_json, InputError
from runtime.user_molecule.records import save, load

ROOT=Path(__file__).resolve().parents[1]


class UserMoleculeInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='分子 request ')
        self.root=Path(self.temporary.name)
        self.schema=json.loads((ROOT/'schemas/user-molecule-request-v1.json').read_text())
        self.request=json.loads((ROOT/'examples/user-molecule/templates/request.json').read_text(encoding='utf-8'))
        self.xyz=(ROOT/'examples/user-molecule/templates/molecule.xyz').read_bytes()
        (self.root/'molecule.xyz').write_bytes(self.xyz)
        self.path=self.root/'request.json'
        self.write(self.request)
    def tearDown(self):
        self.temporary.cleanup()
    def write(self,value):
        self.path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    def test_unicode_space_input_and_explicit_atom_mapping(self):
        bundle=read_request(self.path,self.schema)
        self.assertEqual(len(bundle['atoms']),4)
        self.assertEqual(bundle['atom_mapping'][0]['index_0based'],0)
        self.assertEqual(bundle['atom_mapping'][2]['pi_group'],'B')
    def test_unknown_fields_types_limits_and_profiles(self):
        cases=[('extra','x'),('charge',True),('charge',1),('multiplicity',2),('coordinate_unit','bohr'),
               ('calculation_profile','unknown'),('condition_definition_acknowledged',False),('research_question','x'*513)]
        for key,value in cases:
            with self.subTest(key=key):
                changed=copy.deepcopy(self.request);changed[key]=value;self.write(changed)
                with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_resource_integer_and_hard_bounds(self):
        for name,value in [('threads',True),('threads',3),('memory_limit_mib',4097),('wall_time_limit_seconds',901)]:
            with self.subTest(name=name):
                changed=copy.deepcopy(self.request);changed['resources'][name]=value;self.write(changed)
                with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_duplicate_and_nonfinite_json(self):
        for data in [b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}']:
            with self.subTest(data=data),self.assertRaises(InputError):strict_json(data)
    def test_geometry_path_escape_absolute_uri_missing(self):
        for name in ['../molecule.xyz','C:\\secret.xyz','/tmp/a.xyz','https://example/a.xyz','missing.xyz']:
            with self.subTest(name=name):
                changed=copy.deepcopy(self.request);changed['geometry_file']=name;self.write(changed)
                with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_symlink_rejected(self):
        link=self.root/'alias.xyz'
        try:link.symlink_to(self.root/'molecule.xyz')
        except OSError:self.skipTest('host does not permit symlink fixture')
        changed=copy.deepcopy(self.request);changed['geometry_file']='alias.xyz';self.write(changed)
        with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_carbon_groups_missing_overlap_hydrogen_out_of_range(self):
        for indices in [[3],[2,3],[3,5],[]]:
            with self.subTest(indices=indices):
                changed=copy.deepcopy(self.request);changed['fragments'][1]['carbon_atom_indices_1based']=indices;self.write(changed)
                with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_xyz_truncation_extra_structure_element_nonfinite_nonplanar_collision(self):
        examples=[b'4\ncomment\nC 0 0 0\n',self.xyz+b'C 4 0 0\n',self.xyz.replace(b'C -2.0',b'N -2.0'),
                  self.xyz.replace(b'-2.0',b'nan'),self.xyz.replace(b'C -2.0 0.0 0.0',b'C -2.0 0.0 0.1'),
                  self.xyz.replace(b'C -0.7 0.0 0.0',b'C -2.0 0.0 0.0')]
        for example in examples:
            with self.subTest(example=example),self.assertRaises(InputError):parse_xyz(example)
    def test_request_size_cap(self):
        self.path.write_bytes(b' '*262145)
        with self.assertRaises(InputError):read_request(self.path,self.schema)
    def test_input_mutation_changes_receipt_identity(self):
        first=read_request(self.path,self.schema)
        (self.root/'molecule.xyz').write_bytes(self.xyz.replace(b'-2.0',b'-2.1'))
        second=read_request(self.path,self.schema)
        self.assertNotEqual(first['xyz_sha256'],second['xyz_sha256'])
    def test_strict_atomic_records_reject_nan(self):
        path=self.root/'record.json';save(path,{'value':None,'reason':'UNDEFINED'})
        self.assertIsNone(load(path)['value'])
        with self.assertRaises(ValueError):save(path,{'value':float('nan')})
        self.assertIsNone(load(path)['value'])

if __name__=='__main__':unittest.main()
