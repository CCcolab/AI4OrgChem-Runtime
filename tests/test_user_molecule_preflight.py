"""Resource observations on v1, v2 and hybrid hierarchies; no science execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime.user_molecule.preflight import cpu_snapshot


class CpuHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.mount = self.root / 'cpu'
        self.mount.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def snapshot(self, memberships, filesystem, controllers):
        (self.proc / 'cgroup').write_text(memberships)
        (self.proc / 'mountinfo').write_text(
            f'1 0 0:1 / {self.mount.as_posix()} rw - {filesystem} none {controllers}\n')
        with patch('os.sched_getaffinity', return_value={0, 1, 2, 3}):
            return cpu_snapshot(self.proc)

    def test_hybrid_inactive_v2_does_not_hide_v1_limit(self):
        (self.mount / 'cpu.cfs_quota_us').write_text('100000')
        (self.mount / 'cpu.cfs_period_us').write_text('100000')
        value = self.snapshot('0::/unused\n2:cpu,cpuacct:/\n', 'cgroup', 'rw,cpu,cpuacct')
        self.assertEqual(value['errors'], [])
        self.assertEqual(value['effective_cpus'], 1)

    def test_v2_nested_ancestor_and_fractional_quota(self):
        child = self.mount / 'job'
        child.mkdir()
        (child / 'cpu.max').write_text('max 100000')
        (self.mount / 'cpu.max').write_text('150000 100000')
        value = self.snapshot('0::/job\n', 'cgroup2', 'rw')
        self.assertEqual(value['quota_samples'], [None, 1.5])
        self.assertEqual(value['effective_cpus'], 1.5)
        self.assertEqual(value['errors'], [])

    def test_unlimited_v1_still_honors_affinity(self):
        (self.mount / 'cpu.cfs_quota_us').write_text('-1')
        (self.mount / 'cpu.cfs_period_us').write_text('100000')
        value = self.snapshot('2:cpu,cpuacct:/\n', 'cgroup', 'rw,cpu,cpuacct')
        self.assertEqual(value['effective_cpus'], 4)
        self.assertEqual(value['errors'], [])

    def test_missing_and_malformed_counters_remain_unknown(self):
        value = self.snapshot('0::/\n', 'cgroup2', 'rw')
        self.assertIsNone(value['effective_cpus'])
        self.assertTrue(value['errors'])
        (self.mount / 'cpu.max').write_text('150000 0')
        value = self.snapshot('0::/\n', 'cgroup2', 'rw')
        self.assertIsNone(value['effective_cpus'])
        self.assertIn('ZeroDivisionError', value['errors'])


if __name__ == '__main__':
    unittest.main()
