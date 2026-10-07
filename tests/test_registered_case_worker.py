"""Admission refusal and durable receipts only; no real adapter/native path."""
from __future__ import annotations

import builtins
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import runtime.registered_cases as registry
from runtime.registered_cases import __main__ as worker


def contract_fixture(task='p01-orbital-density'):
    scientific = task == 'p01-orbital-density'
    now = time.time()
    contract = {'schema': 'registered-case-execution-v1', 'task': task,
        'protocol_id': 'P01_ETHENE_OCCUPIED_GAUGE_CONTROL_V0.1' if scientific else 'TOY_P02_PROTOCOL',
        'scientific_execution_authorized': scientific,
        'runtime_commit': 'a' * 40, 'source_snapshot_sha256': 'b' * 64,
        'dependency_lock_sha256': 'c' * 64, 'execution_id': 'd' * 32,
        'memory_limit_bytes': 1073741824, 'threads': 1, 'maximum_processes': 1,
        'wall_time_limit_seconds': 120, 'stop_after_seconds': 100,
        'started_epoch': now, 'stop_deadline_epoch': now + 100, 'hard_deadline_epoch': now + 120,
        'scf_kernel_call_limit': int(scientific), 'boys_kernel_call_limit': int(scientific),
        'pipek_mezey_kernel_call_limit': int(scientific)}
    if scientific:
        contract['p01_protocol_sha256'] = 'd137c04a22fd221129f7a1e62fcafa6928e7ddee1493082ca40158a3c230ac47'
    return contract


class RegisteredCaseWorkerAdmissionTests(unittest.TestCase):
    def run_refusal(self, *, verify_error=None, source_sha=None, dependency_sha=None,
                    installed_version='PINNED_TEST_VERSION', resource=None, environment_change=None):
        contract = contract_fixture()
        spec = {'protocol_id': contract['protocol_id'], 'protocol_sha256': contract['p01_protocol_sha256'], 'module': 'p01'}
        dependency_lock = {'packages': {'toy-package': 'PINNED_TEST_VERSION'}, 'python_version': 'TEST_PYTHON_VERSION'}
        forbidden_imports = []
        original_import = builtins.__import__
        forbidden_prefixes = ('pyscf', 'runtime.registered_cases.p01', 'runtime.registered_cases.p02',
            'runtime.registered_cases.p13', 'runtime.registered_cases.native_guard',
            'runtime.user_molecule.root_native_lifecycle')

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            resolved = importlib.util.resolve_name('.' * level + name, globals['__package__']) if level and globals and globals.get('__package__') else name
            if any(resolved == prefix or resolved.startswith(prefix + '.') for prefix in forbidden_prefixes):
                forbidden_imports.append(resolved)
                raise AssertionError('Adapter/native import must not occur after blocked admission: ' + resolved)
            return original_import(name, globals, locals, fromlist, level)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve()
            contract_path = Path(tmp) / 'unwritten-contract.json'
            # Only the container /output token maps to this fresh host fixture;
            # no real /output, source files, source lock or contract are written.
            def paths(value): return output if str(value) == '/output' else Path(value)
            def load(path):
                if Path(path) == contract_path: return copy.deepcopy(contract)
                if Path(path) == worker.DEPENDENCY_LOCK: return copy.deepcopy(dependency_lock)
                raise AssertionError('Unexpected fixture input read: ' + str(path))
            real_digest = registry.digest
            def hashes(path):
                if Path(path) == contract_path: return 'e' * 64
                if Path(path) == worker.DEPENDENCY_LOCK: return dependency_sha or contract['dependency_lock_sha256']
                return real_digest(path)
            environment = {'AI4ORGCHEM_RUNTIME_COMMIT': contract['runtime_commit'],
                'AI4ORGCHEM_REGISTERED_SOURCE_SHA256': contract['source_snapshot_sha256'],
                'AI4ORGCHEM_REGISTERED_DEPENDENCY_SHA256': contract['dependency_lock_sha256']}
            environment.update(environment_change or {})
            adapter_import = Mock(side_effect=AssertionError('Adapter dispatch must remain absent'))
            preflight = Mock(return_value=resource or {'registered_status': 'BLOCKED', 'registered_reasons': ['toy resource refusal']})
            stdout = io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(worker, 'Path', side_effect=paths))
                stack.enter_context(patch.object(worker, 'strict_load', side_effect=load))
                stack.enter_context(patch.object(registry, 'strict_load', return_value={'tasks': {contract['task']: spec}}))
                source_check = stack.enter_context(patch.object(worker, 'verify_source', side_effect=verify_error))
                stack.enter_context(patch.object(worker, 'source_snapshot_sha256', return_value=source_sha or contract['source_snapshot_sha256']))
                stack.enter_context(patch.object(worker, 'digest', side_effect=hashes))
                stack.enter_context(patch.object(worker.metadata, 'version', return_value=installed_version))
                stack.enter_context(patch.object(worker.platform, 'python_version', return_value='TEST_PYTHON_VERSION'))
                stack.enter_context(patch.object(worker, 'resource_observation', preflight))
                stack.enter_context(patch.object(worker.importlib, 'import_module', adapter_import))
                stack.enter_context(patch.dict(worker.os.environ, environment))
                stack.enter_context(patch.object(builtins, '__import__', side_effect=guarded_import))
                stack.enter_context(redirect_stdout(stdout))
                code = worker.main(['--task', contract['task'], '--contract', str(contract_path), '--output-dir', '/output'])
            receipt = json.loads((output / 'worker-receipt.json').read_text(encoding='utf-8'))
            manifest = json.loads((output / 'run-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(code, 2); self.assertEqual(receipt['status'], 'BLOCKED')
            self.assertEqual(receipt['worker_exit_code'], 2)
            self.assertFalse(receipt['automatic_retry']); self.assertFalse(receipt['resume'])
            self.assertEqual(receipt['general_user_compute'], 'BLOCKED')
            self.assertEqual(receipt['execution_id'], contract['execution_id'])
            self.assertEqual(receipt['run_manifest_sha256'], real_digest(output / 'run-manifest.json'))
            for key in ('actual_scf_kernel_calls', 'actual_boys_kernel_calls', 'actual_pipek_mezey_kernel_calls', 'new_conditional_NR_calls'):
                self.assertIn(key, receipt); self.assertIsNone(receipt[key], 'unobserved counts must not become fabricated zero')
            self.assertFalse(forbidden_imports); adapter_import.assert_not_called()
            self.assertFalse((output / 'case').exists()); self.assertFalse((output / 'guard-receipt.json').exists())
            self.assertIn('"status": "BLOCKED"', stdout.getvalue())
            resource_record = None
            if (output / 'resource-start.json').exists():
                resource_record = json.loads((output / 'resource-start.json').read_text())
                self.assertEqual(manifest['output_sha256']['resource-start.json'], real_digest(output / 'resource-start.json'))
            return receipt, preflight.call_count, source_check.call_count, resource_record

    def test_source_bytes_tamper_persists_blocked_before_dependencies_resources_or_import(self):
        receipt, resource_calls, source_calls, resource = self.run_refusal(verify_error=ValueError('Source bytes differ: locked.py'))
        self.assertIn('Source bytes differ', receipt['error']['message'])
        self.assertEqual(resource_calls, 0); self.assertEqual(source_calls, 1); self.assertIsNone(resource)
        self.assertNotIn('dependency_check', receipt)

    def test_source_or_dependency_lock_digest_mismatch_never_enters_native_path(self):
        for mismatch in ({'source_sha': '0' * 64}, {'dependency_sha': '0' * 64}):
            with self.subTest(mismatch=mismatch):
                receipt, resource_calls, source_calls, resource = self.run_refusal(**mismatch)
                self.assertIn('Execution source/dependency lock differs', receipt['error']['message'])
                self.assertEqual(resource_calls, 0); self.assertEqual(source_calls, 1); self.assertIsNone(resource)

    def test_image_identity_environment_mismatch_is_durable_blocked(self):
        receipt, resource_calls, _, _ = self.run_refusal(environment_change={'AI4ORGCHEM_RUNTIME_COMMIT': 'f' * 40})
        self.assertIn('Image build identity differs: runtime_commit', receipt['error']['message'])
        self.assertEqual(resource_calls, 0); self.assertNotIn('dependency_check', receipt)

    def test_dependency_distribution_mismatch_blocks_before_resource_preflight(self):
        receipt, resource_calls, _, resource = self.run_refusal(installed_version='WRONG_TEST_VERSION')
        self.assertEqual(receipt['source_check'], 'PASS')
        self.assertIn('Installed dependencies differ', receipt['error']['message'])
        self.assertEqual(resource_calls, 0); self.assertIsNone(resource)
        self.assertNotIn('dependency_check', receipt)

    def test_blocked_resource_receipt_persists_and_never_imports_adapter_or_guard(self):
        refused = {'registered_status': 'BLOCKED', 'registered_reasons': ['toy memory/swap/CPU refusal'],
                   'scope': 'ENGINEERING_FAKE_RESOURCE_READ_NO_PYSCF'}
        receipt, resource_calls, _, resource = self.run_refusal(resource=refused)
        self.assertEqual(receipt['source_check'], 'PASS'); self.assertEqual(receipt['dependency_check'], 'PASS')
        self.assertEqual(resource_calls, 1); self.assertEqual(resource, refused)
        self.assertIn('Resource/platform preflight failed', receipt['error']['message'])
        self.assertNotIn('resource_check', receipt)


if __name__ == '__main__': unittest.main()
