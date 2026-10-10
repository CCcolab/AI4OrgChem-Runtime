"""Static entrypoint contracts; no daemon, container, or scientific calls."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DockerPowerShellEntrypoints(unittest.TestCase):
    def text(self, name):
        return (ROOT / 'scripts' / name).read_text(encoding='utf-8')

    def test_current_powershell_tree_has_only_current_platform_names(self):
        withdrawn = 'w' + 'slc'
        for path in (ROOT / 'scripts').glob('*.ps1'):
            with self.subTest(path=path.name):
                self.assertNotIn(withdrawn, path.name.lower())
                self.assertNotIn(withdrawn, path.read_text(encoding='utf-8').lower())
        self.assertTrue((ROOT / 'scripts' / 'probe-docker.ps1').is_file())
        self.assertTrue((ROOT / 'scripts' / 'acceptance-docker.ps1').is_file())

    def test_bootstrap_delegates_to_docker_script_without_engine_selection(self):
        text = self.text('start-runtime.ps1')
        self.assertIn("(Join-Path $PSScriptRoot 'run-docker.ps1')", text)
        self.assertNotIn("'-Engine'", text)
        self.assertIn('$global:LASTEXITCODE=$code', text)
        self.assertIn('run-manifest.json', text)
        self.assertIn('[switch]$CheckOnly', text)

    def test_docker_run_preserves_identity_output_locks_classification_and_exit(self):
        text = self.text('run-docker.ps1')
        self.assertIn("$enginePath = Get-Engine 'docker'", text)
        self.assertNotIn('[string] $Engine', text)
        self.assertIn("'run','--rm','--network','none'", text)
        self.assertIn('Get-ImageIdentity $enginePath $Image', text)
        self.assertIn('& $enginePath @arguments $identity.Id @runtimeArgs', text)
        self.assertIn('source=$output,target=/work', text)
        self.assertIn('source=$locks,target=/locks', text)
        self.assertIn("[IO.FileShare]::None", text)
        self.assertIn('Classification runs must be under OutputRoot', text)
        self.assertIn('if ($null -ne $hostLock) { $hostLock.Dispose() }', text)
        self.assertIn('exit $taskExit', text)
        common = self.text('Runtime.Common.ps1')
        self.assertIn("$imageInfo.Config.User -ne '10001:10001'", common)
        dockerfile = (ROOT / 'container' / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('chmod -R a-w /opt/ai4orgchem /opt/runtime /opt/venv', dockerfile)

    def test_build_checks_pinned_source_before_docker_access(self):
        text = self.text('build-docker.ps1')
        engine_index = text.index("$enginePath = Get-Engine 'docker'")
        self.assertLess(text.index("'SOURCE_PREFLIGHT_PASS'"), engine_index)
        self.assertLess(text.index('Prepared source byte/object verification failed; no engine accessed'), engine_index)
        self.assertLess(text.index('Commit reviewed runtime files before building an identified image'), engine_index)
        self.assertIn('RUNTIME_COMMIT=$revision', text)
        self.assertIn('DEPENDENCY_LOCK_SHA256=$lockHash', text)
        self.assertNotIn('[string] $Engine', text)

    def test_probe_and_acceptance_keep_execution_scope_explicit(self):
        probe = self.text('probe-docker.ps1')
        self.assertIn('scientific_calls=0', probe)
        self.assertIn('PROBED_NOT_VALIDATED', probe)
        self.assertIn("@('run','--help')", probe)
        self.assertNotIn('$identity.Id', probe)
        self.assertNotIn('--mount', probe)
        acceptance = self.text('acceptance-docker.ps1')
        self.assertIn("'run','--rm','--network','none'", acceptance)
        self.assertIn('Docker OCI only; no L3/L4', acceptance)
        self.assertIn('persistent-output-hashes-after-container-deletion', acceptance)
        self.assertIn("'exit-code-37'", acceptance)
        self.assertIn('L4_resume_supported=$false', self.text('backup-local.ps1'))


if __name__ == '__main__':
    unittest.main()
