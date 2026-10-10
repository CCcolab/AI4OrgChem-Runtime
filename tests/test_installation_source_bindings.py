"""Exact installation host rebind and scientific row refusals; zero science."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installation_bindings_test', ROOT/'scripts/installation_source_bindings.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InstallationSourceBindingTests(unittest.TestCase):
    def material(self, family):
        spec = m.CATALOGS[family]
        raw = (ROOT/spec['path']).read_bytes()
        return raw, lambda name: (ROOT/name).read_bytes()

    def test_actual_frozen_catalogs_and_exact_reviewed_host_delta(self):
        for family, spec in m.CATALOGS.items():
            with self.subTest(family=family):
                baseline, read = self.material(family)
                raw, derived, binding = m.derive(family, baseline, read)
                self.assertEqual(m.digest(baseline), spec['sha256'])
                before, after = m.rows(json.loads(baseline)), m.rows(derived)
                self.assertEqual(set(before), set(after))
                self.assertEqual(set(name for name in before if before[name] != after[name]), set(spec['overrides']))
                self.assertEqual(binding['unchanged_rows'], spec['count']-len(spec['overrides']))
                m.validate_binding(family, binding, m.digest(raw))

    def test_current_launcher_bytes_cannot_impersonate_original_catalog(self):
        for family in m.CATALOGS:
            baseline, read = self.material(family)
            original = m.rows(json.loads(baseline))
            self.assertTrue(any(m.digest(read(name)) != row['sha256'] for name, row in original.items()))

    def test_changed_science_cannot_be_accepted_by_self_consistent_new_catalog(self):
        for family, spec in m.CATALOGS.items():
            baseline, read = self.material(family)
            name = next(name for name in m.rows(json.loads(baseline)) if name.startswith('runtime/'))
            with self.assertRaisesRegex(ValueError, 'Frozen scientific/source bytes'):
                m.derive(family, baseline, lambda candidate: read(candidate)+b'\n# altered\n' if candidate == name else read(candidate))

    def test_unknown_host_bytes_or_changed_original_catalog_are_refused(self):
        for family, spec in m.CATALOGS.items():
            baseline, read = self.material(family)
            name = next(iter(spec['overrides']))
            with self.assertRaisesRegex(ValueError, 'Unreviewed engineering host'):
                m.derive(family, baseline, lambda candidate: read(candidate)+b'\n# unexpected\n' if candidate == name else read(candidate))
            with self.assertRaisesRegex(ValueError, 'Original source catalog'):
                m.derive(family, baseline+b'\n', read)

    def test_binding_cannot_expand_paths_or_change_counts(self):
        for family in m.CATALOGS:
            baseline, read = self.material(family)
            raw, _, binding = m.derive(family, baseline, read)
            for key, value in [('unchanged_rows', 0), ('file_count', 1000), ('kind', 'ALLOW_ANY_HOST')]:
                bad = deepcopy(binding); bad[key] = value
                with self.assertRaises(ValueError): m.validate_binding(family, bad, m.digest(raw))
            bad = deepcopy(binding)
            bad['host_overrides']['runtime/altered.py'] = {'base_sha256': 'a'*64, 'sha256': 'b'*64, 'size': 1}
            with self.assertRaises(ValueError): m.validate_binding(family, bad, m.digest(raw))

    def test_preserved_baseline_and_deterministic_derived_bytes_required(self):
        family = 'molecular-service'
        baseline, read = self.material(family)
        raw, _, expected = m.derive(family, baseline, read)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'locks').mkdir()
            (root/m.baseline_path(family)).write_bytes(baseline)
            (root/m.CATALOGS[family]['path']).write_bytes(raw)
            for name in m.rows(json.loads(baseline)):
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(read(name))
            self.assertEqual(m.bind(root, family)[1], expected)
            # Same parsed JSON but changed serialized identity is still refused.
            (root/m.CATALOGS[family]['path']).write_bytes(raw+b'\n')
            with self.assertRaises(ValueError): m.bind(root, family)


if __name__ == '__main__':
    unittest.main()
