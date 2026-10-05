import json
import math
from pathlib import Path
import tempfile
import unittest

from runtime.user_molecule.acceptance_resources import (
    Budget, BudgetBusy, ResourceError, _lock, _resolve_v1_paths, collect_cgroup, collect_cgroup_v1,
    identity_digest, qualify_exact_fixture,
)


IDENTITY = {'geometry_sha256': '1' * 64, 'profile_sha256': '2' * 64,
            'dependencies_sha256': '3' * 64, 'mode': 'independent-conditional'}


class AcceptanceResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='acceptance budget ')
        self.root = Path(self.temporary.name)
        self.path = self.root / 'batch.json'

    def tearDown(self):
        self.temporary.cleanup()

    def budget(self, **kwargs):
        return Budget(self.path, 'technical-acceptance-1', total_seconds=1800, **kwargs)

    def cgroup(self):
        values = {'memory.current': '120\n', 'memory.peak': '900\n', 'memory.max': str(4096 * 1024 ** 2),
                  'memory.swap.max': '0', 'cpu.max': '100000 100000\n',
                  'memory.events': 'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n'}
        directory = self.root / 'cgroup'
        directory.mkdir()
        for name, content in values.items():
            (directory / name).write_text(content, encoding='ascii')
        return directory

    def cgroup_v1(self):
        memory, cpu = self.root / 'memory-v1', self.root / 'cpu-v1'
        memory.mkdir()
        cpu.mkdir()
        bound = str(4096 * 1024 ** 2)
        values = {'memory.usage_in_bytes': '120', 'memory.max_usage_in_bytes': '900',
                  'memory.limit_in_bytes': bound, 'memory.memsw.limit_in_bytes': bound,
                  'memory.failcnt': '0', 'memory.oom_control': 'oom_kill_disable 0\nunder_oom 0\noom_kill 0\n'}
        for name, value in values.items():
            (memory / name).write_text(value, encoding='ascii')
        (cpu / 'cpu.cfs_quota_us').write_text('100000', encoding='ascii')
        (cpu / 'cpu.cfs_period_us').write_text('100000', encoding='ascii')
        return memory, cpu

    def v1_inspect(self):
        return {'source': 'DOCKER_INSPECT', 'oom_killed': False, 'container_id': 'a' * 64,
                'evidence_sha256': 'b' * 64, 'resource_identity_sha256': identity_digest(IDENTITY),
                'state_finished_at': '2026-10-05T10:30:00Z'}

    def test_reservation_survives_reopen_and_insufficient_budget_blocks(self):
        budget = self.budget()
        budget.reserve('first', 900, IDENTITY)
        budget.reserve('second', 900, IDENTITY)
        reopened = self.budget()
        self.assertEqual(reopened.snapshot()['unresolved_reserved_seconds'], 1800)
        self.assertEqual(reopened.snapshot()['remaining_seconds'], 0)
        with self.assertRaises(ResourceError):
            reopened.reserve('third', 1, IDENTITY)

    def test_failures_and_termination_overhead_charge_actual_wall(self):
        budget = self.budget()
        budget.reserve('timeout', 900, IDENTITY)
        state = budget.settle('timeout', 912.5, 'TIMEOUT')
        self.assertEqual(state['consumed_seconds'], 912.5)
        self.assertTrue(state['runs']['timeout']['timeout_exceeded'])
        budget.reserve('oom', 887, IDENTITY)
        state = budget.settle('oom', 200.25, 'OOM', {'oom_kill': 1})
        self.assertEqual(state['consumed_seconds'], 1112.75)
        self.assertEqual(state['remaining_seconds'], 687.25)
        self.assertEqual(self.budget().snapshot()['consumed_seconds'], 1112.75)

    def test_overrun_is_not_clamped_to_reservation(self):
        budget = self.budget()
        budget.reserve('slow-termination', 900, IDENTITY)
        state = budget.settle('slow-termination', 1801, 'FAILED')
        self.assertTrue(state['over_budget'])
        self.assertEqual(state['remaining_seconds'], 0)
        with self.assertRaises(ResourceError):
            budget.reserve('retry', 1, IDENTITY)

    def test_same_run_cannot_be_rereserved_or_resettled(self):
        budget = self.budget()
        budget.reserve('one', 10, IDENTITY)
        with self.assertRaises(ResourceError):
            budget.reserve('one', 10, IDENTITY)
        budget.settle('one', 2, 'COMPLETED')
        with self.assertRaises(ResourceError):
            budget.settle('one', 0, 'COMPLETED')
        with self.assertRaises(ResourceError):
            budget.settle('unknown', 0, 'LAUNCH_FAILED')

    def test_negative_nonfinite_boolean_and_missing_reason_are_rejected(self):
        budget = self.budget()
        budget.reserve('one', 10, IDENTITY)
        for wall in (-1, math.nan, math.inf, True):
            with self.subTest(wall=wall), self.assertRaises(ResourceError):
                budget.settle('one', wall, 'FAILED')
        with self.assertRaises(ResourceError):
            budget.settle('one', 1, '')
        self.assertEqual(budget.snapshot()['unresolved_reserved_seconds'], 10)

    def test_existing_batch_limits_cannot_be_reset_or_increased(self):
        self.budget().reserve('one', 10, IDENTITY)
        for kwargs in ({'batch_id': 'other', 'total_seconds': 1800},
                       {'batch_id': 'technical-acceptance-1', 'total_seconds': 7200},
                       {'batch_id': 'technical-acceptance-1', 'total_seconds': 1800, 'memory_limit_mib': 1024}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ResourceError):
                Budget(self.path, **kwargs)
        self.assertEqual(self.budget().snapshot()['unresolved_reserved_seconds'], 10)

    def test_hard_ceilings_and_identity_are_checked_before_reservation(self):
        for field, value in (('total_seconds', 7201), ('max_process_seconds', 901),
                             ('memory_limit_mib', 4097), ('threads', 2), ('threads', True)):
            with self.subTest(field=field), self.assertRaises(ResourceError):
                Budget(self.root / (field + '.json'), 'candidate', **{field: value})
        budget = self.budget()
        with self.assertRaises(ResourceError):
            budget.reserve('bad', 10, {**IDENTITY, 'geometry_sha256': 'short'})
        with self.assertRaises(ResourceError):
            budget.reserve('bad', 901, IDENTITY)
        self.assertEqual(budget.snapshot()['runs'], {})

    def test_corrupt_existing_ledger_is_preserved_and_refused(self):
        self.budget()
        value = json.loads(self.path.read_text(encoding='utf-8'))
        value['limits']['total_seconds'] = 7200
        self.path.write_text(json.dumps(value), encoding='utf-8')
        previous = self.path.read_bytes()
        with self.assertRaises(ResourceError):
            self.budget()
        self.assertEqual(self.path.read_bytes(), previous)

    def test_os_lock_refuses_second_holder_without_reset(self):
        budget = self.budget()
        with _lock(budget.lock_path):
            with self.assertRaises(BudgetBusy):
                budget.snapshot()

    def test_mutating_caller_identity_does_not_mutate_reservation(self):
        identity = dict(IDENTITY)
        budget = self.budget()
        budget.reserve('one', 10, identity)
        identity['mode'] = 'different'
        self.assertEqual(budget.snapshot()['runs']['one']['identity'], IDENTITY)

    def test_cgroup_peak_is_read_without_reset_and_limits_are_observed(self):
        directory = self.cgroup()
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        value = collect_cgroup(directory, phase='conditional-final')
        self.assertEqual(value['status'], 'COMPLETE')
        self.assertEqual(value['memory_peak_bytes'], 900)
        self.assertEqual(value['cpu_quota_us'], 100000)
        self.assertFalse(value['peak_reset_performed'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_missing_peak_unbounded_limits_and_bad_events_stay_unknown(self):
        directory = self.cgroup()
        (directory / 'memory.peak').unlink()
        (directory / 'memory.max').write_text('max', encoding='ascii')
        (directory / 'memory.events').write_text('oom invalid\n', encoding='ascii')
        value = collect_cgroup(directory)
        self.assertEqual(value['status'], 'PARTIAL')
        self.assertIsNone(value['memory_peak_bytes'])
        self.assertTrue(value['memory_limit_unbounded'])
        self.assertIsNone(value['memory_limit_bytes'])
        candidate = qualify_exact_fixture(IDENTITY, 14, [value])
        self.assertEqual(candidate['status'], 'BLOCKED')
        self.assertTrue(any('UNKNOWN_MEMORY_PEAK' in reason for reason in candidate['reasons']))
        self.assertTrue(any('UNKNOWN_OOM_COUNTERS' in reason for reason in candidate['reasons']))

    def test_resource_envelope_binds_exact_fixture_and_never_extrapolates(self):
        sample = collect_cgroup(self.cgroup())
        candidate = qualify_exact_fixture(IDENTITY, 14, [sample])
        self.assertEqual(candidate['status'], 'RESOURCE_CANDIDATE_EXACT_FIXTURE')
        self.assertEqual(candidate['observed_peak_bytes'], 900)
        self.assertFalse(candidate['n_ao_extrapolation_allowed'])
        self.assertFalse(candidate['production_activation'])
        self.assertEqual(candidate['scientific_qualification'], 'NOT_REVIEWED')
        self.assertNotEqual(identity_digest(IDENTITY), identity_digest({**IDENTITY, 'mode': 'production-copy'}))
        self.assertNotEqual(identity_digest(IDENTITY), identity_digest({**IDENTITY, 'geometry_sha256': '4' * 64}))

    def test_observed_oom_peak_overrun_and_swap_refuse_resource_candidate(self):
        sample = collect_cgroup(self.cgroup())
        for changed in ({**sample, 'memory_events': {'oom': 1, 'oom_kill': 0}},
                        {**sample, 'memory_peak_bytes': 4096 * 1024 ** 2 + 1},
                        {**sample, 'memory_swap_limit_bytes': 1024},
                        {**sample, 'cpu_quota_us': 200000}):
            with self.subTest(changed=changed):
                self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [changed])['status'], 'BLOCKED')

    def test_v1_native_definitions_and_hard_limits_are_preserved(self):
        value = collect_cgroup_v1(*self.cgroup_v1(), phase='ordinary-final')
        self.assertEqual(value['source'], 'CGROUP_V1')
        self.assertEqual(value['status'], 'COMPLETE')
        self.assertEqual(value['memory_current_bytes'], 120)
        self.assertEqual(value['memory_peak_bytes'], 900)
        self.assertEqual(value['memory_swap_limit_bytes'], 0)
        self.assertNotIn('oom', value['memory_events'])
        self.assertEqual(value['memory_events']['limit_failures'], 0)
        self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value])['status'], 'RESOURCE_CANDIDATE_EXACT_FIXTURE')

    def test_v1_observes_actual_paths_and_does_not_reset_peak(self):
        memory, cpu = self.cgroup_v1()
        before = {str(path): path.read_bytes() for directory in (memory, cpu) for path in directory.iterdir()}
        value = collect_cgroup_v1(memory, cpu)
        self.assertEqual(value['files']['memory.max_usage_in_bytes'], str(memory / 'memory.max_usage_in_bytes'))
        self.assertFalse(value['peak_reset_performed'])
        self.assertEqual(before, {str(path): path.read_bytes() for directory in (memory, cpu) for path in directory.iterdir()})

    def test_v1_combined_memsw_limit_is_converted_to_swap_allowance(self):
        memory, cpu = self.cgroup_v1()
        (memory / 'memory.memsw.limit_in_bytes').write_text(str(4097 * 1024 ** 2), encoding='ascii')
        value = collect_cgroup_v1(memory, cpu)
        self.assertEqual(value['memory_swap_limit_bytes'], 1024 ** 2)
        self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value])['status'], 'BLOCKED')

    def test_v1_missing_oom_kill_count_requires_bound_completed_inspect(self):
        memory, cpu = self.cgroup_v1()
        (memory / 'memory.oom_control').write_text('oom_kill_disable 0\nunder_oom 0\n', encoding='ascii')
        value = collect_cgroup_v1(memory, cpu)
        self.assertIsNone(value['memory_events']['oom_kill'])
        self.assertFalse(value['oom_kill_counter_available'])
        self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value])['status'], 'BLOCKED')
        candidate = qualify_exact_fixture(IDENTITY, 14, [value], external_oom_evidence=self.v1_inspect())
        self.assertEqual(candidate['status'], 'RESOURCE_CANDIDATE_EXACT_FIXTURE')
        self.assertIn('NOT_PROOF_OOM_NEVER_OCCURRED', candidate['oom_claim'])

    def test_v1_oom_false_alone_and_wrong_identity_cannot_substitute_history(self):
        memory, cpu = self.cgroup_v1()
        (memory / 'memory.oom_control').write_text('oom_kill_disable 0\nunder_oom 0\n', encoding='ascii')
        value = collect_cgroup_v1(memory, cpu)
        for evidence in ({'oom_killed': False}, {**self.v1_inspect(), 'resource_identity_sha256': 'c' * 64},
                         {**self.v1_inspect(), 'state_finished_at': '0001-01-01T00:00:00Z'},
                         {**self.v1_inspect(), 'oom_killed': True}):
            with self.subTest(evidence=evidence):
                self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value], external_oom_evidence=evidence)['status'], 'BLOCKED')

    def test_v1_limit_failure_current_oom_or_kill_refuses_candidate(self):
        memory, cpu = self.cgroup_v1()
        for failcnt, control in (('1', 'oom_kill_disable 0\nunder_oom 0\noom_kill 0\n'),
                                 ('0', 'oom_kill_disable 0\nunder_oom 1\noom_kill 0\n'),
                                 ('0', 'oom_kill_disable 0\nunder_oom 0\noom_kill 1\n')):
            (memory / 'memory.failcnt').write_text(failcnt, encoding='ascii')
            (memory / 'memory.oom_control').write_text(control, encoding='ascii')
            with self.subTest(failcnt=failcnt, control=control):
                sample = collect_cgroup_v1(memory, cpu)
                self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [sample], external_oom_evidence=self.v1_inspect())['status'], 'BLOCKED')

    def test_v1_unknown_memsw_support_refuses_no_swap_claim(self):
        memory, cpu = self.cgroup_v1()
        (memory / 'memory.memsw.limit_in_bytes').unlink()
        value = collect_cgroup_v1(memory, cpu)
        self.assertEqual(value['status'], 'PARTIAL')
        self.assertIsNone(value['memory_swap_limit_bytes'])
        self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value])['status'], 'BLOCKED')

    def test_v1_unbounded_kernel_sentinel_and_cpu_quota_are_unknown_limits(self):
        memory, cpu = self.cgroup_v1()
        (memory / 'memory.memsw.limit_in_bytes').write_text('9223372036854771712', encoding='ascii')
        (cpu / 'cpu.cfs_quota_us').write_text('-1', encoding='ascii')
        value = collect_cgroup_v1(memory, cpu)
        self.assertTrue(value['memory_swap_limit_unbounded'])
        self.assertTrue(value['cpu_limit_unbounded'])
        self.assertIsNone(value['cpu_quota_us'])
        self.assertEqual(qualify_exact_fixture(IDENTITY, 14, [value])['status'], 'BLOCKED')

    def test_v1_membership_resolves_relative_to_controller_mount_root(self):
        cgroup, mountinfo = self.root / 'cgroup.proc', self.root / 'mountinfo.proc'
        cgroup.write_text('5:memory:/docker/container/child\n4:cpu,cpuacct:/docker/container/child\n', encoding='ascii')
        mountinfo.write_text('29 23 0:25 /docker/container /sys/fs/cgroup/memory ro - cgroup cgroup rw,memory\n'
                            '30 23 0:26 /docker/container /sys/fs/cgroup/cpu,cpuacct ro - cgroup cgroup rw,cpu,cpuacct\n', encoding='ascii')
        paths = _resolve_v1_paths(cgroup, mountinfo)
        self.assertEqual(paths['memory']['resolved_path'], str(Path('/sys/fs/cgroup/memory') / 'child'))
        self.assertEqual(paths['cpu']['membership_path'], '/docker/container/child')
        self.assertEqual(paths['memory']['path_resolution'], 'MEMBERSHIP_RELATIVE_TO_MOUNT_ROOT')

    def test_v1_namespace_root_and_mountinfo_escaped_paths_are_preserved(self):
        cgroup, mountinfo = self.root / 'cgroup.proc', self.root / 'mountinfo.proc'
        cgroup.write_text('5:memory:/\n4:cpu,cpuacct:/\n', encoding='ascii')
        mountinfo.write_text('29 23 0:25 /docker/container /sys/cgroup/memory\\040space ro - cgroup cgroup rw,memory\n'
                            '30 23 0:26 /docker/container /sys/cgroup/cpu ro - cgroup cgroup rw,cpu,cpuacct\n', encoding='ascii')
        paths = _resolve_v1_paths(cgroup, mountinfo)
        self.assertEqual(paths['memory']['resolved_path'], str(Path('/sys/cgroup/memory space')))
        self.assertEqual(paths['memory']['path_resolution'], 'CGROUP_NAMESPACE_ROOT')

    def test_v1_discovery_never_falls_back_to_unrelated_parent_mount(self):
        cgroup, mountinfo = self.root / 'cgroup.proc', self.root / 'mountinfo.proc'
        cgroup.write_text('5:memory:/different/child\n4:cpu,cpuacct:/different/child\n', encoding='ascii')
        mountinfo.write_text('29 23 0:25 /docker/container /sys/cgroup/memory ro - cgroup cgroup rw,memory\n'
                            '30 23 0:26 /docker/container /sys/cgroup/cpu ro - cgroup cgroup rw,cpu,cpuacct\n', encoding='ascii')
        with self.assertRaises(ResourceError):
            _resolve_v1_paths(cgroup, mountinfo)


if __name__ == '__main__':
    unittest.main()
