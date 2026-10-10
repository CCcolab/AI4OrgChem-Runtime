"""Current presentation, byte identities and retired-engine regressions; zero science."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_IDENTIFIER = bytes((119, 115, 108, 99)).decode('ascii')


class PublicPlatformScopeTests(unittest.TestCase):
    def test_current_source_documents_and_metadata_do_not_reintroduce_retired_engine(self):
        pattern = re.compile(LEGACY_IDENTIFIER+r'(?!onfig)', re.I)
        roots = [ROOT/'README.md', ROOT/'README_zh-CN.md', ROOT/'configs', ROOT/'docs',
                 ROOT/'scripts', ROOT/'validation', ROOT/'runtime', ROOT/'evidence']
        for root in roots:
            files = [root] if root.is_file() else root.rglob('*')
            for path in files:
                if not path.is_file() or path.suffix not in {'.md','.json','.html','.py','.ps1','.yml','.txt'}:
                    continue
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertNotRegex(path.read_text('utf-8-sig'), pattern)
                    self.assertNotRegex(path.relative_to(ROOT).as_posix(), pattern)

    def test_exact_public_projection_hashes_and_no_original_acceptance_transfer(self):
        record = json.loads((ROOT/'validation/public-projections-20261010.json').read_bytes())
        self.assertFalse(record['history_rewritten'])
        self.assertTrue(record['originals_preserved_local'])
        for row in record['projections']:
            path=ROOT/row['path']
            with self.subTest(path=row['path']):
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['projection_sha256'])
                if path.suffix=='.json':
                    projection=json.loads(path.read_bytes())['_public_projection']
                    self.assertEqual(projection['original_sha256'],row['original_sha256'])
                    self.assertFalse(projection['acceptance_transferred_to_current_code'])
                    self.assertFalse(projection['scientific_numeric_values_changed'])

    def test_only_current_platforms_and_current_docker_launchers(self):
        record=json.loads((ROOT/'configs/runtime-capabilities-v2.json').read_bytes())
        self.assertEqual(set(record['platforms']),{'docker','ordinary_wsl2'})
        self.assertFalse(record['declaration_grants_execution_authorization'])
        for kind in ['build','run','probe']:
            self.assertTrue((ROOT/'scripts'/f'{kind}-docker.ps1').is_file())
            self.assertFalse((ROOT/'scripts'/f'{kind}-{LEGACY_IDENTIFIER}.ps1').exists())
        html=(ROOT/'docs/index.html').read_text('utf-8')
        table=re.search(r'<table id="history-registry".*?</table>',html,re.S).group(0)
        for row in re.findall(r'<tr\b[^>]*>.*?</tr>',table,re.S):
            self.assertEqual(len(re.findall(r'<t[hd]\b',row)),3)


if __name__=='__main__':unittest.main()
