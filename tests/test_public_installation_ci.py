"""Independent mock regressions for CI timeout evidence and owned-container cleanup.

No Docker process, installed environment or scientific module is executed.
The embedded file probe is executed only against fake os/pathlib/sys modules.
"""
import builtins
import errno
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('public_installation_ci',ROOT/'scripts/ci-installation-engineering.py')
host=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)
IMAGE='sha256:'+'a'*64
CID='b'*64


class EngineAfterCreateTimeout:
    """Daemon created a container but the CLI did not return its ID in time."""
    def __init__(self,*,wrong_image=False,wrong_label=False,cleanup_timeout=False):
        self.commands=[]
        self.owner=None
        self.program=None
        self.wrong_image=wrong_image
        self.wrong_label=wrong_label
        self.cleanup_timeout=cleanup_timeout
        self.removed=False

    def __call__(self,command,**kwargs):
        self.commands.append(list(command))
        if command[:2]==['docker','create']:
            self.owner=command[command.index('--name')+1]
            self.program=command[command.index('-c')+1]
            raise subprocess.TimeoutExpired(command,kwargs['timeout'],output=b'partial create output',stderr=b'create deadline')
        if command[:2]==['docker','inspect']:
            if command[2]==self.owner:
                if self.cleanup_timeout:
                    raise subprocess.TimeoutExpired(command,kwargs['timeout'],output=b'partial inspect output',stderr=b'inspect deadline')
                value=[{'Id':CID,'Image':'sha256:'+'c'*64 if self.wrong_image else IMAGE,
                        'Config':{'Labels':{'ai4orgchem.installation.ci-owner':'another-owner' if self.wrong_label else self.owner}}}]
                return subprocess.CompletedProcess(command,0,json.dumps(value).encode(),b'')
            if command[2]==CID and self.removed:
                return subprocess.CompletedProcess(command,1,b'',b'Error: No such object: '+CID.encode())
        if command==['docker','rm','--force',CID]:
            self.removed=True
            return subprocess.CompletedProcess(command,0,CID.encode(),b'')
        raise AssertionError('Unexpected engine operation: '+repr(command))


class PublicInstallationCITests(unittest.TestCase):
    def test_timeout_preserves_partial_output_and_unknown_command_status(self):
        for stdout,stderr in [(b'partial stdout',b'partial stderr'),(None,None)]:
            with self.subTest(stdout=stdout),tempfile.TemporaryDirectory() as folder:
                directory=Path(folder)
                command=['fake-tool','--input','two words']
                failure=subprocess.TimeoutExpired(command,7,output=stdout,stderr=stderr)
                with patch.object(host.subprocess,'run',side_effect=failure),self.assertRaises(subprocess.TimeoutExpired):
                    host.run(command,directory,'operation',cwd=directory,expected=23,timeout=7)
                self.assertEqual((directory/'operation.stdout.log').read_bytes(),stdout or b'')
                self.assertEqual((directory/'operation.stderr.log').read_bytes(),stderr or b'')
                record=json.loads((directory/'operation.command.json').read_bytes())
                self.assertEqual(record['command'],command)
                self.assertEqual(record['cwd'],str(directory))
                self.assertIsNone(record['exit_code'])
                self.assertEqual(record['status'],'TIMEOUT_IDENTITY_UNKNOWN')
                self.assertEqual(record['timeout_seconds'],7)
                self.assertEqual(record['expected_exit_code'],23)

    def test_create_timeout_recovers_own_container_by_name_label_and_image(self):
        engine=EngineAfterCreateTimeout()
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            with patch.object(host.subprocess,'run',side_effect=engine),self.assertRaises(subprocess.TimeoutExpired):
                host.docker_probe(IMAGE,directory/'bind-output','own',writable=False)
            self.assertTrue(engine.removed)
            self.assertEqual(engine.commands[1],['docker','inspect',engine.owner])
            self.assertEqual(engine.commands[2],['docker','rm','--force',CID])
            self.assertEqual(engine.commands[3],['docker','inspect',CID])
            self.assertFalse(any(c[:2]==['docker','start'] for c in engine.commands))
            create=json.loads((directory/'own-create.command.json').read_bytes())
            self.assertEqual(create['status'],'TIMEOUT_IDENTITY_UNKNOWN')
            inspected=json.loads((directory/'own-cleanup-inspect.command.json').read_bytes())
            self.assertEqual(inspected['command'],['docker','inspect',engine.owner])
            self.assertEqual(inspected['exit_code'],0)
            self.assertEqual(json.loads((directory/'own-absent.command.json').read_bytes())['exit_code'],1)

    def test_foreign_image_or_owner_label_never_deleted(self):
        for options in [{'wrong_image':True},{'wrong_label':True}]:
            with self.subTest(**options),tempfile.TemporaryDirectory() as folder:
                engine=EngineAfterCreateTimeout(**options)
                with patch.object(host.subprocess,'run',side_effect=engine),self.assertRaisesRegex(ValueError,'ownership differs'):
                    host.docker_probe(IMAGE,Path(folder)/'bind-output','foreign',writable=False)
                self.assertFalse(engine.removed)
                self.assertFalse(any(c[:2] in (['docker','rm'],['docker','start']) for c in engine.commands))
                self.assertTrue((Path(folder)/'foreign-cleanup-inspect.stdout.log').is_file())

    def test_cleanup_inspect_timeout_preserves_evidence_without_removal(self):
        engine=EngineAfterCreateTimeout(cleanup_timeout=True)
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            with patch.object(host.subprocess,'run',side_effect=engine),self.assertRaises(subprocess.TimeoutExpired):
                host.docker_probe(IMAGE,directory/'bind-output','inspect-timeout',writable=False)
            self.assertEqual((directory/'inspect-timeout-cleanup-inspect.stdout.log').read_bytes(),b'partial inspect output')
            self.assertEqual((directory/'inspect-timeout-cleanup-inspect.stderr.log').read_bytes(),b'inspect deadline')
            record=json.loads((directory/'inspect-timeout-cleanup-inspect.command.json').read_bytes())
            self.assertEqual(record['status'],'TIMEOUT_IDENTITY_UNKNOWN')
            self.assertIsNone(record['exit_code'])
            self.assertFalse(engine.removed)

    def probe_program(self):
        engine=EngineAfterCreateTimeout()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(host.subprocess,'run',side_effect=engine),self.assertRaises(subprocess.TimeoutExpired):
                host.docker_probe(IMAGE,Path(folder)/'fake-output','extract-program',writable=False)
        return engine.program

    def execute_program(self,*,source_errno=errno.EROFS,output_denied=False):
        program=self.probe_program()
        writes=[]
        class FakePath:
            def __init__(self,name):self.name=name
            def write_text(self,value):
                writes.append((self.name,value))
                if self.name=='/opt/runtime/__ci_forbidden_write':
                    raise OSError(source_errno,'synthetic source refusal')
                if self.name=='/out/persisted.json' and output_denied:
                    raise PermissionError(errno.EACCES,'synthetic bind refusal')
                if self.name!='/out/persisted.json':raise AssertionError('Unexpected fake path')
        def exit_with(code):raise SystemExit(code)
        modules={'errno':errno,'json':json,'os':SimpleNamespace(geteuid=lambda:10001),
                 'pathlib':SimpleNamespace(Path=FakePath),'sys':SimpleNamespace(exit=exit_with)}
        def import_only_mocked(name,*args,**kwargs):
            if name not in modules:raise AssertionError('Unexpected program import: '+name)
            return modules[name]
        namespace={'__builtins__':{**vars(builtins),'__import__':import_only_mocked}}
        output=io.StringIO()
        with patch('sys.stdout',output):
            try:exec(compile(program,'<mocked-ci-file-probe>','exec'),namespace)
            except SystemExit as result:return result.code,writes,output.getvalue()
        self.fail('The fixed probe must return a recorded exit code')

    def test_erofs_source_refusal_continues_to_writable_output_probe(self):
        code,writes,output=self.execute_program()
        self.assertEqual(code,23)
        self.assertEqual([name for name,_ in writes],['/opt/runtime/__ci_forbidden_write','/out/persisted.json'])
        self.assertEqual(json.loads(writes[1][1]),{'uid':10001,'science_calls':0})
        self.assertIn('BIND_WRITABLE',output)

    def test_erofs_source_and_unwritable_output_keep_negative_exit(self):
        code,writes,output=self.execute_program(output_denied=True)
        self.assertEqual(code,19)
        self.assertEqual(len(writes),2)
        self.assertIn('BIND_PERMISSION_REFUSED',output)

    def test_unrelated_source_io_error_is_not_accepted_as_readonly(self):
        with self.assertRaises(OSError) as error:self.execute_program(source_errno=errno.EIO)
        self.assertEqual(error.exception.errno,errno.EIO)


if __name__=='__main__':unittest.main()
