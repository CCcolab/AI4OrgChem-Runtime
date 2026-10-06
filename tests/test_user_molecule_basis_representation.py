import copy
import hashlib
import unittest

import test_user_molecule_residual_preparation as fixtures
from runtime.user_molecule.residual_preparation import restore_legacy_basis_representation
from runtime.user_molecule.residual_bridge import BridgeRefusal


class LegacyBasisRepresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ResidualPreparationTests()
        self.fixture.setUp()
        self.fixture.context.metadata = copy.deepcopy(self.fixture.record['metadata'])

    def reverse(self):
        mol=self.fixture.mol
        mol._basis={name:mol._basis[name] for name in ('H','C')}
        self.fixture.context.metadata['basis_expansion_sha256']=hashlib.sha256(repr(mol._basis).encode()).hexdigest()

    def test_exact_other_key_order_restores_hash_without_basis_or_atom_changes(self):
        self.reverse();before=copy.deepcopy(self.fixture.record)
        receipt=restore_legacy_basis_representation(context=self.fixture.context,ordinary_record=self.fixture.record)
        self.assertTrue(receipt['representation_changed'])
        self.assertEqual(receipt['matched_sha256'],before['metadata']['basis_expansion_sha256'])
        self.assertFalse(receipt['basis_values_changed'])
        self.assertEqual(self.fixture.record,before)
        self.assertEqual(self.fixture.verify()['status'],'PASS_CACHED_MAPPING_ONLY')
        self.assertEqual(self.fixture.mol.forbidden_calls,0)

    def test_original_order_is_explicitly_verified_without_change(self):
        receipt=restore_legacy_basis_representation(context=self.fixture.context,ordinary_record=self.fixture.record)
        self.assertFalse(receipt['representation_changed'])
        self.assertEqual(self.fixture.verify()['status'],'PASS_CACHED_MAPPING_ONLY')

    def test_changed_numeric_or_typed_basis_values_cannot_be_repaired_by_reordering(self):
        self.fixture.mol._basis['C']='OTHER_VALUES_SAME_BASIS_NAME'
        self.fixture.context.metadata['basis_expansion_sha256']=hashlib.sha256(repr(self.fixture.mol._basis).encode()).hexdigest()
        with self.assertRaises(BridgeRefusal) as error:
            restore_legacy_basis_representation(context=self.fixture.context,ordinary_record=self.fixture.record)
        self.assertEqual(error.exception.reason,'LEGACY_BASIS_IDENTITY_NOT_REPRODUCED')
        self.assertEqual(self.fixture.mol.forbidden_calls,0)

    def test_other_metadata_difference_is_never_overwritten(self):
        self.reverse();self.fixture.context.metadata['atom_order_preserved']=False
        with self.assertRaises(BridgeRefusal) as error:
            restore_legacy_basis_representation(context=self.fixture.context,ordinary_record=self.fixture.record)
        self.assertEqual(error.exception.reason,'LEGACY_BASIS_OTHER_METADATA_REFUSED')
        self.assertFalse(self.fixture.context.metadata['atom_order_preserved'])


if __name__=='__main__':unittest.main()
