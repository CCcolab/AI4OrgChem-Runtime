import json
import tempfile
import unittest
from pathlib import Path

from runtime.cli import digest, load, validated_input, verify_source
from runtime.resources import memory_snapshot, remaining, require_memory


class ResourceTests(unittest.TestCase):
    def test_limits_and_units(self):
        self.assertIsNone(remaining('max', '100'))
        self.assertIsNone(remaining(str(2**63 - 4096), '100'))
        self.assertEqual(remaining('100', '120'), 0)
        require_memory('p14-fixed', {'effective_available_bytes': 13000 * 1024**2})
        with self.assertRaises(MemoryError):
            require_memory('p14-optimize', {'effective_available_bytes': 13000 * 1024**2})
        with self.assertRaises(MemoryError):
            require_memory('p14-fixed', {'effective_available_bytes': 'UNKNOWN'})

    def test_nested_cgroup_v2_parent_limit_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc, group = root / 'proc', root / 'cgroup'
            (proc / 'self').mkdir(parents=True)
            (group / 'child').mkdir(parents=True)
            (proc / 'meminfo').write_text('MemAvailable: 20000000 kB\n')
            (proc / 'self/cgroup').write_text('0::/child\n')
            (proc / 'self/mountinfo').write_text('1 2 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n')
            (group / 'memory.max').write_text('1000')
            (group / 'memory.current').write_text('700')
            (group / 'child/memory.max').write_text('max')
            (group / 'child/memory.current').write_text('100')
            self.assertEqual(memory_snapshot(proc, group)['effective_available_bytes'], 300)

    def test_cgroup_v1(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc, group = root / 'proc', root / 'cgroup'
            (proc / 'self').mkdir(parents=True)
            (group / 'memory').mkdir(parents=True)
            (proc / 'meminfo').write_text('MemAvailable: 20000000 kB\n')
            (proc / 'self/cgroup').write_text('5:memory:/\n')
            (proc / 'self/mountinfo').write_text('1 2 0:1 / /sys/fs/cgroup/memory rw - cgroup cgroup rw,memory\n')
            (group / 'memory/memory.limit_in_bytes').write_text('900')
            (group / 'memory/memory.usage_in_bytes').write_text('100')
            self.assertEqual(memory_snapshot(proc, group)['effective_available_bytes'], 800)
            # Docker on a hybrid kernel: v1 memory is authoritative, while the
            # unmounted, unused v2 membership must not hide its real limit.
            (proc / 'self/cgroup').write_text('5:memory:/\n0::/\n')
            self.assertEqual(memory_snapshot(proc, group)['effective_available_bytes'], 800)

    def test_missing_cgroup_counters_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'proc/self').mkdir(parents=True)
            (root / 'proc/meminfo').write_text('MemAvailable: 20000000 kB\n')
            (root / 'proc/self/cgroup').write_text('0::/\n')
            (root / 'proc/self/mountinfo').write_text('1 2 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n')
            snapshot = memory_snapshot(root / 'proc', root / 'group')
            self.assertEqual(snapshot['effective_available_bytes'], 'UNKNOWN')
            with self.assertRaises(MemoryError):
                require_memory('p14-fixed', snapshot)


class InputTests(unittest.TestCase):
    def test_no_default_frozen_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                validated_input(Path(directory), 'p14-smoke', 'sha', {}, {})

    def test_result_tampering_and_wrong_run_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            result = run / 'result.json'
            result.write_text(json.dumps({'protocol_id': 'p14-strained-aromatic-pi-distortivity/0.1', 'proposition_id': 'P14'}))
            manifest = {'task': 'p14-smoke', 'status': 'PASS', 'process_exit_code': 0, 'source_commit': 'sha',
                        'input_sha256': {}, 'dependencies': {}, 'run_id': 'fresh', 'output_sha256': {'result.json': digest(result)}}
            (run / 'run-manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(validated_input(run, 'p14-smoke', 'sha', {}, {})[1], 'fresh')
            with self.assertRaises(ValueError):
                validated_input(run, 'p14-fixed', 'sha', {}, {})
            with self.assertRaises(ValueError):
                validated_input(run, 'p14-smoke', 'other', {}, {})
            result.write_text('{}')
            with self.assertRaises(ValueError):
                validated_input(run, 'p14-smoke', 'sha', {}, {})

    def test_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{"verdict":"FAIL","verdict":"PASS"}')
            with self.assertRaises(ValueError):
                load(path)


if __name__ == '__main__':
    unittest.main()
