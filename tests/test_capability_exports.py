"""Consumer drift checks against the single current capability registry."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capability_exports_test', ROOT/'scripts/sync-current-capabilities.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class CapabilityExportTests(unittest.TestCase):
    def test_all_exported_blocks_equal_the_current_registry(self):
        for name, raw in m.targets().items():
            with self.subTest(path=name):
                self.assertEqual((ROOT/name).read_bytes(), raw)

    def test_web_json_and_readme_refer_to_one_current_registry(self):
        raw = (ROOT/'configs/runtime-capabilities-v2.json').read_bytes()
        registry = json.loads(raw)
        self.assertEqual((ROOT/'docs/runtime-guide/capabilities-v2.json').read_bytes(), raw)
        page = (ROOT/'docs/index.html').read_text(encoding='utf-8')
        self.assertIn(hashlib.sha256(raw).hexdigest(), page)
        for row in registry['capabilities']:
            self.assertIn(m.html.escape(row['name'], quote=False), page)
        self.assertIn('<details id="current-service-registry">', page)
        for name in ('README.md', 'README_zh-CN.md'):
            text = (ROOT/name).read_text(encoding='utf-8')
            self.assertIn('configs/runtime-capabilities-v2.json', text)
            self.assertIn(registry['ci']['url'], text)

    def test_repeated_generation_is_idempotent_without_changes(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/sync-current-capabilities.py')],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['generated_files'], [])


if __name__ == '__main__':
    unittest.main()
