"""Owned recovery and file-I/O admission using a fake daemon; zero science."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('host_safety_test', ROOT/'scripts/runtime_host_safety.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
IMAGE, CID, TOKEN = 'sha256:'+'a'*64, 'e'*64, 'd'*32


class ProbeDaemon:
    def __init__(self, output, outcome='success'):
        self.output, self.outcome, self.calls, self.removed = Path(output), outcome, [], False
    def __call__(self, *args, timeout=10, allow_failure=False):
        self.calls.append(args)
        def response(code=0, stdout=b'', stderr=b''):
            if code and not allow_failure: raise RuntimeError('Mock daemon command failed')
            return subprocess.CompletedProcess(args, code, stdout, stderr)
        if args[0] == 'create':
            self.name = args[args.index('--name')+1]
            self.label, self.owner = args[args.index('--label')+1].split('=', 1)
            self.assert_intent_saved_before_create = bool(list(self.output.glob('output-probe-intent-*.json')))
            self.command = args
            if self.outcome in ('create-timeout', 'late-create'): raise subprocess.TimeoutExpired(args, timeout)
            if self.outcome == 'short-cid': return response(stdout=b'incomplete')
            return response(stdout=CID.encode())
        if args[0] == 'inspect':
            if self.outcome == 'late-create':
                return response(1, stderr=('Error: No such object: '+args[1]).encode())
            if self.removed:
                if self.outcome == 'deletion-unknown': return response(1, stderr=b'Cannot connect to daemon')
                if self.outcome != 'still-present': return response(1, stderr=('Error: No such object: '+args[1]).encode())
            row = {'Id': CID, 'Name': '/'+self.name, 'Image': IMAGE,
                   'Config': {'User': '10001:10001', 'Labels': {self.label: self.owner}},
                   'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none'},
                   'State': {'Running': False, 'ExitCode': 1 if self.outcome == 'unwritable' else 0}}
            if self.outcome == 'foreign-owner': row['Config']['Labels'][self.label] = 'f'*32
            return response(stdout=json.dumps([row]).encode())
        if args[0] == 'start':
            if self.outcome == 'unwritable': return response(1, stderr=b'PermissionError: UID10001 output denied')
            receipt = {'owner': self.owner, 'parent_execution_id': TOKEN, 'uid': 10001,
                       'scientific_calls': 0, 'status': 'CREATED_AND_REMOVED'}
            return response(stdout=json.dumps(receipt).encode())
        if args[0] == 'rm':
            if self.outcome == 'rm-failure': return response(1, stderr=b'rm failure')
            self.removed = True; return response()
        raise AssertionError('Unexpected probe command')


class HostSafetyTests(unittest.TestCase):
    def test_exact_owned_name_recovery_and_explicit_absence(self):
        row = {'Id': CID, 'Name': '/own-name', 'Image': IMAGE, 'Config': {'Labels': {'owner': TOKEN}}}
        docker = lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, json.dumps([row]).encode(), b'')
        self.assertEqual(m.recover_created_container(docker, name='own-name', image_id=IMAGE, label_key='owner', token=TOKEN), CID)
        absent = lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, b'', b'Error: No such container: own-name')
        self.assertIsNone(m.recover_created_container(absent, name='own-name', image_id=IMAGE, label_key='owner', token=TOKEN))

    def test_other_identity_absence_or_malformed_json_is_unknown(self):
        for code, out, err in [(1,b'',b'Error: No such object: foreign'), (1,b'',b'Cannot connect to daemon'),
                               (0,b'[]',b''), (0,b'not-json',b''), (0,b'{}',b'')]:
            with self.subTest(stdout=out, stderr=err):
                docker = lambda *args, **kwargs: subprocess.CompletedProcess(args, code, out, err)
                with self.assertRaises(m.HostSafetyError) as raised:
                    m.recover_created_container(docker, name='own-name', image_id=IMAGE, label_key='owner', token=TOKEN)
                self.assertTrue(raised.exception.cleanup_unknown)

    def test_probe_success_retains_intent_and_checks_confinement(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = ProbeDaemon(directory)
            m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
            self.assertTrue(docker.assert_intent_saved_before_create)
            args = docker.command
            for flag, value in [('--user','10001:10001'),('--network','none'),('--entrypoint','/opt/venv/bin/python')]:
                self.assertEqual(args[args.index(flag)+1], value)
            self.assertIn('--read-only', args); self.assertTrue(docker.removed)
            self.assertIn('os.O_EXCL', args[-1]); self.assertIn('if created: os.unlink(path)', args[-1])
            for name in ('pyscf','ai4orgchem','rdkit','scipy'): self.assertNotIn(name, args[-1])

    def test_permission_refusal_after_owned_removal_is_not_unknown_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = ProbeDaemon(directory, 'unwritable')
            with self.assertRaises(m.HostSafetyError) as raised:
                m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
            self.assertFalse(raised.exception.cleanup_unknown); self.assertTrue(docker.removed)

    def test_create_timeout_or_bad_stdout_recovers_by_name_without_start(self):
        for outcome in ('create-timeout','short-cid'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                docker = ProbeDaemon(directory, outcome)
                with self.assertRaises(m.HostSafetyError) as raised:
                    m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
                self.assertFalse(raised.exception.cleanup_unknown); self.assertTrue(docker.removed)
                self.assertFalse(any(c[0]=='start' for c in docker.calls))

    def test_foreign_owner_is_never_started_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = ProbeDaemon(directory, 'foreign-owner')
            with self.assertRaises(m.HostSafetyError) as raised:
                m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
            self.assertTrue(raised.exception.cleanup_unknown)
            self.assertFalse(any(c[0] in ('start','rm') for c in docker.calls))

    def test_immediate_absence_after_create_timeout_does_not_close_pending_request(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = ProbeDaemon(directory, 'late-create')
            with self.assertRaises(m.HostSafetyError) as raised:
                m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
            self.assertTrue(raised.exception.cleanup_unknown)
            self.assertFalse(any(c[0] in ('start','rm') for c in docker.calls))

    def test_unconfirmed_deletion_or_rm_failure_quarantines(self):
        for outcome in ('deletion-unknown','still-present','rm-failure'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                docker = ProbeDaemon(directory, outcome)
                with self.assertRaises(m.HostSafetyError) as raised:
                    m.probe_output_writable(docker, image_id=IMAGE, output_path=directory, token=TOKEN, label_key='owner')
                self.assertTrue(raised.exception.cleanup_unknown)


if __name__ == '__main__':
    unittest.main()
