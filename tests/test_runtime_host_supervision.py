"""Three real supervisor flows with fake Docker outcomes; no scientific calls."""
import contextlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:'+'a'*64
CID = 'e'*64


def host_module(family):
    path = ROOT/('scripts/run-'+family+'.py')
    spec = importlib.util.spec_from_file_location('host_supervision_test_'+family.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class DockerOutcome:
    def __init__(self, host, outcome):
        self.host, self.outcome, self.calls, self.removed = host, outcome, [], False
    def __call__(self, command, *, capture_output, timeout):
        args = command[1:]; self.calls.append(args)
        def response(code=0, out=b'', err=b''):
            return subprocess.CompletedProcess(command, code, out, err)
        if args[:2] == ['image', 'inspect']:
            return response(out=json.dumps([{'Id': IMAGE}]).encode())
        if args[0] == 'create':
            self.name = args[args.index('--name')+1]
            label = args[args.index('--label')+1]
            self.token = label.split('=', 1)[1]
            if self.outcome == 'short-cid': return response(out=b'short')
            raise subprocess.TimeoutExpired(command, timeout, output=b'partial create')
        if args[0] == 'inspect':
            if self.removed or self.outcome == 'absent':
                return response(1, err=('Error: No such object: '+str(args[1])).encode())
            if self.outcome == 'unknown':
                return response(1, err=b'Cannot connect to Docker daemon')
            row = {'Id': CID, 'Image': IMAGE, 'Name': '/'+self.name,
                   'Config': {'Labels': {self.host.LABEL: self.token}},
                   'State': {'Running': False, 'ExitCode': 0, 'OOMKilled': False}}
            if self.outcome == 'foreign-label': row['Config']['Labels'][self.host.LABEL] = 'f'*32
            if self.outcome == 'foreign-image': row['Image'] = 'sha256:'+'f'*64
            return response(out=json.dumps([row]).encode())
        if args[0] == 'rm':
            self.removed = True; return response()
        raise AssertionError('No start/scientific dispatch allowed: '+repr(args))


class SupervisorCreateRecoveryTests(unittest.TestCase):
    FAMILIES = [('molecular-service', 'molecular-service', 'single-point', '.molecular-service-locks'),
                ('registered-case', 'registered-cases', 'p02-statistics', '.registered-case-locks'),
                ('protocol-case', 'protocol-cases', 'P07', '.protocol-case-locks')]

    def scenario(self, family, outcome, *, probe_error=None):
        script, service, task, lock_name = family
        host = host_module(script)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; (source/'validation'/service).mkdir(parents=True)
            host.save(source/'validation'/service/'candidate-image.json', {'image_id': IMAGE})
            args = SimpleNamespace(output_root=root/'runs', lock_root=None, docker_executable='mock-docker',
                                   task=task, image=None, request=root/'request.json')
            fake = DockerOutcome(host, outcome)
            def contract(*args, **kwargs):
                token = args[2]
                return {'task': task, 'case': task, 'execution_id': token,
                        'resources': {'cpus': 1, 'threads': 1}}
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(host, 'ROOT', source))
                stack.enter_context(patch.object(host, 'validate_image_record', side_effect=lambda value: value))
                stack.enter_context(patch.object(host, 'verify_image_inspection', return_value=None))
                stack.enter_context(patch.object(host, 'host_git_identity', return_value={'scope': 'SYNTHETIC_NO_SCIENCE'}))
                stack.enter_context(patch.object(host, 'build_contract', side_effect=contract))
                stack.enter_context(patch.object(host, 'probe_output_writable', side_effect=probe_error))
                if script == 'molecular-service':
                    stack.enter_context(patch.object(host, 'snapshot_input', return_value={'scope': 'SYNTHETIC'}))
                    stack.enter_context(patch.object(host, 'verify_input_snapshot', return_value={'scope': 'SYNTHETIC'}))
                code, run, record = host.supervise(args, executor=fake)
            self.assertNotEqual(code, 0)
            self.assertFalse(record['worker_started'])
            self.assertFalse(any(c[0] == 'start' for c in fake.calls))
            saved = host.read_json(run/'host-execution.json')
            self.assertEqual(saved, record)
            lock_retained = (root/'runs'/lock_name/'active.lock').exists()
            return record, fake.calls, lock_retained

    def test_create_timeout_with_owned_container_is_recovered_removed_and_recorded(self):
        for family in self.FAMILIES:
            with self.subTest(family=family[0]):
                record, calls, lock = self.scenario(family, 'owned')
                self.assertEqual(record['create_recovery'], 'OWNED_ID_RECOVERED')
                self.assertTrue(record['container_removed'])
                self.assertTrue(any(c[0] == 'rm' and CID in c for c in calls))
                self.assertFalse(lock)

    def test_absence_after_uncertain_create_and_daemon_unknown_both_quarantine(self):
        for family in self.FAMILIES:
            with self.subTest(family=family[0]):
                record, calls, lock = self.scenario(family, 'absent')
                self.assertEqual(record['create_recovery'], 'ABSENT_NOW_CREATE_COMPLETION_UNKNOWN')
                self.assertTrue(lock); self.assertFalse(any(c[0] == 'rm' for c in calls))
                record, calls, lock = self.scenario(family, 'unknown')
                self.assertEqual(record['create_recovery'], 'UNKNOWN_QUARANTINED')
                self.assertTrue(lock); self.assertFalse(any(c[0] == 'rm' for c in calls))

    def test_foreign_image_or_owner_never_removed_and_lock_is_retained(self):
        for family in self.FAMILIES:
            for outcome in ('foreign-label', 'foreign-image'):
                with self.subTest(family=family[0], outcome=outcome):
                    _, calls, lock = self.scenario(family, outcome)
                    self.assertTrue(lock)
                    self.assertFalse(any(c[0] == 'rm' for c in calls))

    def test_malformed_create_stdout_still_recovers_owned_name(self):
        for family in self.FAMILIES:
            with self.subTest(family=family[0]):
                record, _, lock = self.scenario(family, 'short-cid')
                self.assertTrue(record['container_removed']); self.assertFalse(lock)

    def test_unwritable_probe_prevents_main_create_and_unknown_probe_keeps_lock(self):
        from runtime_host_safety import HostSafetyError
        for family in self.FAMILIES:
            for unknown in (False, True):
                with self.subTest(family=family[0], cleanup_unknown=unknown):
                    error = HostSafetyError('Synthetic output permission/refusal', cleanup_unknown=unknown)
                    record, calls, lock = self.scenario(family, 'owned', probe_error=error)
                    self.assertFalse(any(c[0] == 'create' for c in calls))
                    self.assertEqual(lock, unknown)
                    self.assertEqual(record['status'], 'REFUSED_OR_UNKNOWN_OUTPUT_PREFLIGHT')


if __name__ == '__main__':
    unittest.main()
