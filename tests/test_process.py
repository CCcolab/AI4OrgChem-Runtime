"""Linux subprocess/lock contracts, with small synthetic non-scientific children."""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from runtime.cli import execute, host_lock


@unittest.skipUnless(sys.platform == 'linux', 'Linux task process semantics')
class ProcessTests(unittest.TestCase):
    def test_failure_exit_code_and_logs_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            code = execute([sys.executable, '-c', 'import sys; print("kept"); print("failure", file=sys.stderr); sys.exit(37)'], os.environ.copy(), directory, run, 0)
            self.assertEqual(code, 37)
            self.assertIn('kept', (run / '00-stdout.log').read_text())
            self.assertIn('failure', (run / '00-stderr.log').read_text())

    def test_shared_host_lock_refuses_second_task(self):
        with tempfile.TemporaryDirectory() as directory:
            with host_lock(Path(directory)):
                with self.assertRaises(RuntimeError):
                    with host_lock(Path(directory)):
                        self.fail('second quantum job admitted')

    def test_interrupt_keeps_written_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            checkpoint = run / 'checkpoint.json'
            # Worker catches SIGTERM through the same interrupt path as CLI.
            worker_code = '''import os,signal,sys
from pathlib import Path
from runtime.cli import execute
def stop(*args): raise SystemExit(143)
signal.signal(signal.SIGTERM,stop)
run=Path(sys.argv[1])
execute([sys.executable,'-c', 'import time; from pathlib import Path; Path('+repr(str(run/'checkpoint.json'))+').write_text("checkpoint"); time.sleep(120)'],os.environ.copy(),str(run),run,0)
'''
            child = subprocess.Popen([sys.executable, '-c', worker_code, directory])
            try:
                deadline = time.monotonic() + 10
                while not checkpoint.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(checkpoint.exists())
                child.send_signal(signal.SIGTERM)
                self.assertEqual(child.wait(timeout=20), 143)
                self.assertEqual(checkpoint.read_text(), 'checkpoint')
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
