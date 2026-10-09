"""Portable source-only reconstruction, identity, and archive safety tests."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare-science-install-source.py'
SPEC = importlib.util.spec_from_file_location('science_install_source', SCRIPT)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class ScienceInstallSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'runtime'
        self.root.mkdir()
        self.baseline_commit, self.science_commit = '1' * 40, '2' * 40
        self.baseline_files = {
            'LICENSE': b'Terms retained\n',
            'configs/qm/p09_exchange_integral_classes_v0.1.yaml': b'frozen: rules\n'}
        self.overlay_name = 'software/src/ai4orgchem/qm/user_molecule_adapter.py'
        self.overlay_raw = b'# source fixture; no scientific execution\n'
        self.files = dict(self.baseline_files, **{self.overlay_name: self.overlay_raw})
        self.baseline_raw = self.tar(self.baseline_files, self.baseline_commit, compressed=True)
        self.baseline_path = self.root.parent / 'baseline.tar.gz'
        self.baseline_path.write_bytes(self.baseline_raw)
        self.final_raw = source.canonical_archive(self.files, 'AI4OrgChem-' + self.science_commit + '/')
        self.materials = {
            source.JSON_PATHS[0]: {'source_commit': self.baseline_commit,
                                  'source_archive_url': 'https://codeload.github.com/CCcolab/AI4OrgChem/tar.gz/' + self.baseline_commit,
                                  'source_archive_sha256': source.digest(self.baseline_raw)},
            source.JSON_PATHS[1]: {'source_commit': self.science_commit, 'baseline_commit': self.baseline_commit,
                                  'source_archive_sha256': 'a' * 64,
                                  'condition_rules_sha256': source.digest(self.baseline_files['configs/qm/p09_exchange_integral_classes_v0.1.yaml'])},
            source.JSON_PATHS[2]: {name: source.digest(raw) for name, raw in self.baseline_files.items()},
            source.JSON_PATHS[3]: {name: source.digest(raw) for name, raw in self.files.items()}}
        retained = 'assets/science-install-overlay/' + self.science_commit[:8] + '/' + self.overlay_name
        self.lock = {
            'schema_version': 1, 'acquisition_method': 'public_baseline_plus_retained_overlay',
            'source_repository': 'https://github.com/CCcolab/AI4OrgChem',
            'source_commit': self.science_commit, 'baseline_commit': self.baseline_commit,
            'baseline_archive_url': self.materials[source.JSON_PATHS[0]]['source_archive_url'],
            'baseline_archive_sha256': source.digest(self.baseline_raw),
            'historical_archive_sha256': 'a' * 64, 'archive_matches_historical_bytes': False,
            'source_archive_sha256': source.digest(self.final_raw), 'source_archive_size_bytes': len(self.final_raw),
            'archive_prefix': 'AI4OrgChem-' + self.science_commit + '/',
            'baseline_file_count': len(self.baseline_files), 'source_file_count': len(self.files),
            'condition_rules_sha256': self.materials[source.JSON_PATHS[1]]['condition_rules_sha256'],
            'pinned_json_canonical_sha256': {name: source.canonical_digest(value) for name, value in self.materials.items()},
            'overlay': [{'path': self.overlay_name, 'retained_path': retained,
                         'sha256': source.digest(self.overlay_raw), 'size_bytes': len(self.overlay_raw)}]}
        path = self.root / retained
        path.parent.mkdir(parents=True)
        path.write_bytes(self.overlay_raw)
        self.save()

    @staticmethod
    def tar(files, commit, compressed=False, extra=()):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz' if compressed else 'w:') as bundle:
            for name, raw in (*files.items(), *extra):
                member = tarfile.TarInfo('AI4OrgChem-' + commit + '/' + name)
                member.size = len(raw)
                bundle.addfile(member, io.BytesIO(raw))
        return data.getvalue()

    def save(self, rebind=False):
        if rebind:
            self.lock['pinned_json_canonical_sha256'] = {name: source.canonical_digest(value) for name, value in self.materials.items()}
        for name, value in {**self.materials, 'locks/source.installation.lock.json': self.lock}.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

    def test_repository_pins_preserve_588_baseline_and_three_exact_retained_files(self):
        root, lock, baseline, files = source.load_config()
        self.assertEqual((len(baseline), len(files), len(lock['overlay'])), (588, 591, 3))
        for row in lock['overlay']:
            raw = (root / row['retained_path']).read_bytes()
            self.assertEqual(source.digest(raw), row['sha256'])
            self.assertEqual(len(raw), row['size_bytes'])
        self.assertNotEqual(lock['source_archive_sha256'], lock['historical_archive_sha256'])

    def test_prepare_twice_is_deterministic_and_extracts_all_exact_bytes(self):
        first, second = self.root.parent / 'first', self.root.parent / 'second'
        receipt = source.prepare(first, self.baseline_path, self.root)
        source.prepare(second, self.baseline_path, self.root)
        self.assertEqual((first / 'science.tar').read_bytes(), self.final_raw)
        self.assertEqual((first / 'science.tar').read_bytes(), (second / 'science.tar').read_bytes())
        self.assertEqual(receipt['scientific_execution'], 'NOT_EXECUTED')
        self.assertFalse(receipt['historical_acceptance_transferred'])
        self.assertFalse(receipt['archive_matches_historical_bytes'])
        destination = self.root.parent / 'extracted'
        result = source.extract(first / 'science.tar', destination, self.root)
        self.assertEqual(result['status'], 'EXTRACTED_RECONSTRUCTED_SOURCE_ONLY')
        actual = {path.relative_to(destination).as_posix(): path.read_bytes() for path in destination.rglob('*') if path.is_file()}
        self.assertEqual(actual, self.files)

    def test_network_mode_uses_only_the_pinned_public_baseline_url(self):
        class Response(io.BytesIO):
            pass
        with patch.object(source.urllib.request, 'urlopen', return_value=Response(self.baseline_raw)) as open_url:
            receipt = source.prepare(self.root.parent / 'download', root=self.root)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, self.lock['baseline_archive_url'])
        self.assertEqual(receipt['baseline_acquisition'], 'PINNED_PUBLIC_GITHUB_DOWNLOAD')

    def test_corrupted_public_archive_or_overlay_creates_no_output(self):
        self.baseline_path.write_bytes(self.baseline_raw + b'changed')
        target = self.root.parent / 'corrupt'
        with self.assertRaisesRegex(ValueError, 'baseline archive hash'):
            source.prepare(target, self.baseline_path, self.root)
        self.assertFalse(target.exists())
        self.baseline_path.write_bytes(self.baseline_raw)
        (self.root / self.lock['overlay'][0]['retained_path']).write_bytes(self.overlay_raw + b'changed')
        with self.assertRaisesRegex(ValueError, 'overlay hash/size'):
            source.prepare(target, self.baseline_path, self.root)
        self.assertFalse(target.exists())

    def test_pinned_baseline_member_content_must_match_even_with_valid_container_hash(self):
        modified = dict(self.baseline_files, LICENSE=b'changed')
        raw = self.tar(modified, self.baseline_commit, compressed=True)
        self.baseline_path.write_bytes(raw)
        self.lock['baseline_archive_sha256'] = source.digest(raw)
        self.materials[source.JSON_PATHS[0]]['source_archive_sha256'] = source.digest(raw)
        self.save(rebind=True)
        with self.assertRaisesRegex(ValueError, 'file hash mismatch'):
            source.prepare(self.root.parent / 'changed-baseline', self.baseline_path, self.root)

    def test_manifest_or_frozen_baseline_rebinding_is_rejected(self):
        self.materials[source.JSON_PATHS[3]]['LICENSE'] = 'b' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'JSON pin mismatch'):
            source.load_config(self.root)
        self.save(rebind=True)
        with self.assertRaisesRegex(ValueError, 'baseline files changed'):
            source.load_config(self.root)

    def test_duplicate_json_and_nonfinite_values_are_rejected(self):
        path = self.root / 'locks/source.installation.lock.json'
        for raw in ('{"schema_version":1,"schema_version":1}', '{"value":NaN}'):
            path.write_text(raw, encoding='utf-8')
            with self.assertRaises(ValueError):
                source.load_config(self.root)

    def test_archive_duplicate_unknown_missing_and_unsafe_members_are_rejected(self):
        expected = self.materials[source.JSON_PATHS[2]]
        samples = [self.tar(self.baseline_files, self.baseline_commit, extra=(('LICENSE', b'Terms retained\n'),)),
                   self.tar(self.baseline_files, self.baseline_commit, extra=(('extra', b'x'),)),
                   self.tar({'LICENSE': b'Terms retained\n'}, self.baseline_commit)]
        for name in ('../outside', '/absolute', 'C:/outside', 'dir\\outside', 'a/./b', 'a//b'):
            samples.append(self.tar(self.baseline_files, self.baseline_commit, extra=((name, b'x'),)))
        for raw in samples:
            with self.subTest(raw_size=len(raw)), self.assertRaises(ValueError):
                source.read_archive(raw, 'AI4OrgChem-' + self.baseline_commit + '/', expected, 'r:')

    def test_archive_links_are_rejected(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:') as bundle:
            item = tarfile.TarInfo('AI4OrgChem-' + self.baseline_commit + '/LICENSE')
            item.type = tarfile.SYMTYPE
            item.linkname = '../../outside'
            bundle.addfile(item)
        with self.assertRaisesRegex(ValueError, 'type/prefix'):
            source.read_archive(data.getvalue(), 'AI4OrgChem-' + self.baseline_commit + '/', self.materials[source.JSON_PATHS[2]], 'r:')

    def test_existing_target_and_wrong_new_archive_are_rejected_without_replacement(self):
        target = self.root.parent / 'existing'
        target.mkdir()
        saved = target / 'saved'
        saved.write_bytes(b'unchanged')
        with self.assertRaisesRegex(ValueError, 'must be new'):
            source.prepare(target, self.baseline_path, self.root)
        self.assertEqual(saved.read_bytes(), b'unchanged')
        archive = self.root.parent / 'wrong.tar'
        archive.write_bytes(self.final_raw + b'changed')
        fresh = self.root.parent / 'fresh'
        with self.assertRaisesRegex(ValueError, 'archive hash/size'):
            source.extract(archive, fresh, self.root)
        self.assertFalse(fresh.exists())

    def test_overlay_parent_link_is_refused(self):
        blocked = (self.root / self.lock['overlay'][0]['retained_path']).parent
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == blocked or original(path)):
            with self.assertRaisesRegex(ValueError, 'linked path'):
                source.prepare(self.root.parent / 'linked', self.baseline_path, self.root)

    def test_old_archive_hash_cannot_be_reused_as_the_new_archive_identity(self):
        self.lock['source_archive_sha256'] = self.lock['historical_archive_sha256']
        self.save()
        with self.assertRaisesRegex(ValueError, 'archive binding'):
            source.load_config(self.root)


if __name__ == '__main__':
    unittest.main()
