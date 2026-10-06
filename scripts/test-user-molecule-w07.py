"""Host-only W07 integration checks of saved Report evidence and export guards.

Uses the Windows PowerShell 5.1 bootstrap and existing PowerShell 7 / ordinary
Python. Never invokes Check, Compute, Docker, scientific dependencies or network.
The failed scientific run is read as historical evidence, never recomputed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reject_links(path):
    for component in (*reversed(path.parents), path):
        try:
            observed = component.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(observed.st_mode) and
                not getattr(observed, 'st_file_attributes', 0) & 0x400,
                'Symlink or reparse component: ' + str(component))


def snapshot(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        reject_links(path)
        if path.is_file():
            raw = path.read_bytes()
            files[path.relative_to(directory).as_posix()] = {
                'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return files


def snapshot_digest(files):
    raw = json.dumps(files, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def differences(before, after):
    return {'added_files': sorted(after.keys() - before.keys()),
            'removed_files': sorted(before.keys() - after.keys()),
            'changed_files': sorted(name for name in before.keys() & after.keys()
                                    if before[name] != after[name])}


def verify_export(directory, source, expected_report_exit):
    files = snapshot(directory)
    require(set(files) == {'report.md', 'report-summary.json', 'run-manifest.json'},
            'Unexpected generated Report file set')
    receipt = load(directory / 'run-manifest.json')
    require(receipt['action'] == 'READONLY_REPORT_EXPORT', 'Export action mismatch')
    require(receipt['source_directory'] == str(source.resolve()), 'Export source mismatch')
    require(receipt['scientific_processes_started'] == 0, 'Report recorded scientific work')
    require(receipt['report_exit_code'] == expected_report_exit, 'Export report exit mismatch')
    require(receipt['files'] == {name: entry for name, entry in files.items()
                                if name != 'run-manifest.json'}, 'Export manifest mismatch')
    summary = load(directory / 'report-summary.json')
    require(summary['report_exit_code'] == expected_report_exit, 'Summary report exit mismatch')
    require(summary['method_status'] == 'NOT_REVIEWED', 'Report must not grant method approval')
    require(summary['comparison_available'] is False and summary['delta_hartree'] is None
            and summary['delta_kcal_mol'] is None, 'Report must retain unavailable comparison')
    return {'generated_files': files, 'manifest_verified': True, 'report_summary': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--check-run', type=Path, required=True,
                        help='One existing valid Check run, not its parent output directory')
    parser.add_argument('--failed-run', type=Path, required=True,
                        help='Existing failed v2 scientific acceptance run; read only')
    parser.add_argument('--powershell7', type=Path, required=True)
    parser.add_argument('--python-executable', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output_root.absolute()
    check, failed = args.check_run.absolute(), args.failed_run.absolute()
    ps7, python = args.powershell7.absolute(), args.python_executable.absolute()
    ps51 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / (
        'System32/WindowsPowerShell/v1.0/powershell.exe')
    require(os.name == 'nt', 'W07 bootstrap integration runner requires Windows')
    for path in (output, check, failed, ps7, python, ps51):
        reject_links(path)
    output, check, failed, ps7, python, ps51 = (
        path.resolve() for path in (output, check, failed, ps7, python, ps51))
    require(not output.exists() and output != root and not output.is_relative_to(root),
            'New evidence directory outside runtime required')
    require(check.is_dir() and failed.is_dir() and check != failed,
            'Two distinct existing source runs required')
    require(not output.is_relative_to(check) and not output.is_relative_to(failed),
            'Output must not be inside an original source run')
    require(all(path.is_file() for path in (ps7, python, ps51)),
            'Existing PowerShell 5.1, PowerShell 7 and ordinary Python required')
    git_status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)
    require(not git_status.strip(), 'Clean committed runtime required')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode('ascii').strip()
    require(load(check / 'preflight.json')['input_status'] == 'VALID',
            'Check source must be an actual valid input run')
    require(load(check / 'preflight.json')['compute_eligible'] is False,
            'This runner tests the current gated Check candidate')
    protected_before = {'check': snapshot(check), 'historical_failed': snapshot(failed)}
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    summary = {'status': 'RUNNING', 'host_source_commit': commit,
               'operator_kind': 'AGENT_SIMULATED_USER', 'execution_environment': 'LOCAL_CI_WINDOWS_HOST',
               'scope': 'W07 Report integration; not scientific or real-user qualification',
               'github_actions': 'NOT_EXECUTED', 'scientific_compute_started': 0,
               'check_compute_or_docker_invocations': 0, 'image_rebuild': False,
               'human_feedback': 'DEFERRED_BY_USER_NOT_CURRENT_ENGINEERING_BLOCKER',
               'source_directories': {'check': str(check), 'historical_failed': str(failed)},
               'protected_sources_before': protected_before, 'cases': cases}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def run_case(name, source, expected, *, basic=False, destination=None, inspect=None):
        argv = [str(ps51), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(root / 'scripts/start-user-molecule.ps1'), '-PowerShell7', str(ps7),
                '-Action', 'Report', '-RunDirectory', str(source)]
        if not basic:
            argv += ['-PythonExecutable', str(python)]
        if destination is not None:
            argv += ['-ReportExportDirectory', str(destination)]
        before = snapshot(source)
        row = {'case': name, 'arguments': argv, 'expected_exit_code': expected,
               'process_exit_code': None, 'status': 'RUNNING', 'basic_without_python': basic,
               'source_directory': str(source), 'host_source_commit': commit,
               'source_byte_snapshot_sha256_before': snapshot_digest(before)}
        started = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=60)
            (output / (name + '.stdout.log')).write_bytes(result.stdout)
            (output / (name + '.stderr.log')).write_bytes(result.stderr)
            row['process_exit_code'] = result.returncode
            require(result.returncode == expected,
                    'Unexpected process exit: ' + str(result.returncode))
            if inspect is not None:
                row['observations'] = inspect()
            row['status'] = 'PASS_EXPECTATION'
        except subprocess.TimeoutExpired as exc:
            (output / (name + '.stdout.log')).write_bytes(exc.stdout or b'')
            (output / (name + '.stderr.log')).write_bytes(exc.stderr or b'')
            row['status'], row['error'] = 'FAIL', 'Report process exceeded 60 seconds'
        except Exception as exc:
            row['status'], row['error'] = 'FAIL', str(exc)
        finally:
            for stream_name in ('stdout', 'stderr'):
                log = output / (name + '.' + stream_name + '.log')
                if not log.exists():
                    log.write_bytes(b'')
            row['elapsed_seconds'] = time.monotonic() - started
            try:
                after = snapshot(source)
                row['source_byte_snapshot_sha256_after'] = snapshot_digest(after)
                row['source_file_changes'] = differences(before, after)
                row['source_unchanged'] = before == after
                require(before == after, 'Report modified source evidence')
            except Exception as exc:
                row['status'], row['source_preservation_error'] = 'FAIL', str(exc)
            cases.append(row)
            save(output / (name + '.execution.json'), row)
        return row

    def unavailable_check_export():
        value = verify_export(check_export, check, 0)
        state = value['report_summary']
        require(state['record_integrity'] == 'MATCHED' and state['input_status'] == 'VALID',
                'Valid Check integrity/input mismatch')
        require(state['scientific_execution_status'] == state['numerical_status'] == 'NOT_EXECUTED'
                and state['compute_eligible'] is False, 'Check must retain unexecuted science')
        return value

    try:
        exports = output / 'exports'
        exports.mkdir()
        check_export = exports / 'valid-check'
        run_case('basic-valid-check', check, 0, basic=True)
        run_case('advanced-valid-check', check, 0)
        run_case('fresh-external-export', check, 0, destination=check_export,
                 inspect=unavailable_check_export)
        check_export_before = snapshot(check_export) if check_export.exists() else None

        def repeated_export_observation():
            require(check_export_before is not None and snapshot(check_export) == check_export_before,
                    'Repeated export changed existing report')
            return {'existing_export_unchanged': True}

        run_case('reject-existing-export', check, 40, destination=check_export,
                 inspect=repeated_export_observation)
        nested_export = check / 'w07-report-must-not-be-created'
        require(not nested_export.exists(), 'Source-nested refusal destination must start absent')

        def source_nested_observation():
            require(not nested_export.exists(), 'Rejected source-nested export created a directory')
            return {'destination_not_created': True}

        run_case('reject-source-nested-export', check, 40, destination=nested_export,
                 inspect=source_nested_observation)
        controls = output / 'controls'
        controls.mkdir()
        corrupt = controls / 'corrupt-evidence-copy'
        shutil.copytree(check, corrupt)
        with (corrupt / 'preflight.json').open('ab') as stream:
            stream.write(b' ')
        run_case('reject-corrupt-evidence', corrupt, 40)
        incomplete = controls / 'manifested-but-incomplete-copy'
        shutil.copytree(check, incomplete,
                        ignore=lambda directory, names: ['request.normalized.json']
                        if Path(directory) == check / 'input' else [])
        receipt = load(incomplete / 'run-manifest.json')
        require('input/request.normalized.json' in receipt['files'],
                'Valid source must register normalized request snapshot')
        del receipt['files']['input/request.normalized.json']
        receipt['fixture_kind'] = 'SYNTHETIC_INCOMPLETE_EVIDENCE_CONTROL_NOT_AN_ORIGINAL_RUN'
        (incomplete / 'run-manifest.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
            encoding='utf-8', newline='\n')
        save(controls / 'CONTROL_FIXTURES.json', {
            'source': str(check), 'not_original_runs': True,
            'corrupt-evidence-copy': 'One whitespace byte appended to copied preflight.json; original manifest retained',
            'manifested-but-incomplete-copy': 'Copied normalized request omitted and only copied manifest entry removed'})
        run_case('basic-incomplete-control', incomplete, 0, basic=True)
        incomplete_export = exports / 'incomplete-control'

        def incomplete_observation():
            value = verify_export(incomplete_export, incomplete, 40)
            state = value['report_summary']
            require(state['record_integrity'] == 'UNVERIFIED', 'Missing evidence must be UNVERIFIED')
            require('REQUEST_SNAPSHOT_MISSING' in state['evidence_issues'],
                    'Missing normalized request must be identified')
            return value

        run_case('advanced-incomplete-control', incomplete, 40,
                 destination=incomplete_export, inspect=incomplete_observation)
        failed_export = exports / 'historical-scientific-failure'

        def historical_failure_observation():
            value = verify_export(failed_export, failed, 0)
            state = value['report_summary']
            require(state['record_integrity'] == 'MATCHED', 'Historical evidence integrity mismatch')
            require(state['execution_status'] == 'FAILED' and
                    state['numerical_status'] == state['research_status'] == 'NOT_QUALIFIED',
                    'Report exit 0 must retain saved scientific failure')
            require(state['scientific_execution_status'] == 'EXECUTED',
                    'Historical scientific execution should remain identified as historical')
            value['historical_only_no_new_scientific_execution'] = True
            return value

        run_case('historical-failed-run', failed, 0, destination=failed_export,
                 inspect=historical_failure_observation)
    except Exception as exc:
        summary['setup_or_fixture_error'] = str(exc)
    finally:
        try:
            protected_after = {'check': snapshot(check), 'historical_failed': snapshot(failed)}
            summary['protected_sources_after'] = protected_after
            summary['protected_sources_unchanged'] = protected_after == protected_before
            summary['protected_source_byte_snapshot_sha256'] = {
                name: {'before': snapshot_digest(protected_before[name]),
                       'after': snapshot_digest(protected_after[name])}
                for name in protected_before}
        except Exception as exc:
            summary['protected_sources_unchanged'] = False
            summary['source_preservation_error'] = str(exc)
        summary['counts'] = {'expected_cases': 9, 'executed_cases': len(cases),
                             'pass_expectation': sum(row['status'] == 'PASS_EXPECTATION' for row in cases),
                             'failed_cases': sum(row['status'] != 'PASS_EXPECTATION' for row in cases),
                             'scientific_runs_started': 0}
        summary['status'] = ('PASS_W07_HOST_REPORT_ENGINEERING_ONLY'
                             if len(cases) == 9 and all(row['status'] == 'PASS_EXPECTATION' for row in cases)
                             and summary['protected_sources_unchanged'] and not summary.get('setup_or_fixture_error')
                             else 'FAIL_W07_HOST_REPORT_ENGINEERING')
        summary['research_w07_and_production_compute'] = 'BLOCKED_UNCHANGED'
        summary['wslc'] = 'BLOCKED_PAUSED'
        save(output / 'summary.json', summary)
        print(json.dumps({'status': summary['status'], 'counts': summary['counts'],
                          'output_directory': str(output), 'host_source_commit': commit},
                         ensure_ascii=False))
    return 0 if summary['status'] == 'PASS_W07_HOST_REPORT_ENGINEERING_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
