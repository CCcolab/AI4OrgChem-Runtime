"""Bounded stop commands use the old hard allowance and cannot certify success."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_stop_host',ROOT/'scripts/diagnose-user-molecule-root-native.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class NativeStopSupervisionTests(unittest.TestCase):
    def test_stop_at275_uses18_grace20_command_window_and_five_nominal_evidence_seconds(self):
        tool=Mock()
        with patch.object(host.time,'monotonic',return_value=275):
            value=host.stop_owned_container(tool,'owned',started=0,duration=300)
        tool.assert_called_once_with('stop','--time','18','owned',timeout=20)
        self.assertEqual(value['nominal_evidence_reserve_seconds'],5)
        self.assertEqual(value['remaining_before_stop_seconds'],25)
        self.assertIn('NOT_SUCCESS',value['scope'])

    def test_late_stop_reduces_grace_and_timeout_instead_of_extending_budget(self):
        tool=Mock()
        with patch.object(host.time,'monotonic',return_value=290):
            value=host.stop_owned_container(tool,'owned',started=0,duration=300)
        tool.assert_called_once_with('stop','--time','3','owned',timeout=5)
        self.assertEqual(value['remaining_before_stop_seconds'],10)

    def test_no_evidence_window_refuses_without_tool_or_claiming_closed(self):
        for now in (295,300,301):
            tool=Mock()
            with self.subTest(now=now),patch.object(host.time,'monotonic',return_value=now),self.assertRaises(TimeoutError):
                host.stop_owned_container(tool,'owned',started=0,duration=300)
            tool.assert_not_called()

    def test_stop_timeout_is_propagated_and_never_becomes_deletion_or_success(self):
        tool=Mock(side_effect=TimeoutError('daemon stop stalled'))
        with patch.object(host.time,'monotonic',return_value=275),self.assertRaisesRegex(TimeoutError,'stalled'):
            host.stop_owned_container(tool,'owned',started=0,duration=300)
        self.assertEqual(tool.call_count,1)

    def test_docker_command_timeout_is_clamped_to_hard_remaining_and_logs_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tool=host.DockerCommands('not-a-real-engine',root)
            tool.hard_deadline_monotonic=300
            with patch.object(host.time,'monotonic',return_value=293), \
                    patch.object(host.subprocess,'run',side_effect=subprocess.TimeoutExpired('toy',7)) as run, \
                    self.assertRaises(subprocess.TimeoutExpired):
                tool('stop','--time','18','owned',timeout=20)
            self.assertEqual(run.call_args.kwargs['timeout'],7)
            self.assertEqual(tool.commands[-1]['error_type'],'TimeoutExpired')

    def test_soft_deadline_inspection_is_clamped_and_stop_checks_before_new_poll(self):
        # Structural wiring supplements execution faults without real engine I/O.
        import ast
        tree=ast.parse((ROOT/'scripts/diagnose-user-molecule-root-native.py').read_text(encoding='utf-8'))
        main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_supervisor')
        loop=next(node for node in ast.walk(main) if isinstance(node,ast.While))
        self.assertIn('soft_remaining',ast.unparse(loop.body[0]))
        self.assertIsInstance(loop.body[1],ast.If)
        inspected=ast.unparse(loop.body[2])
        self.assertIn('timeout=min(5, soft_remaining)',inspected)
        self.assertIn('stop_owned_container',ast.unparse(loop.body[1]))


if __name__=='__main__':unittest.main()
