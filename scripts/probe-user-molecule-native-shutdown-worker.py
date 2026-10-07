"""Real signal delivery to a zero-native engineering-only fresh toy ledger.

Exit 42 means the expected cooperative engineering stop closed its handles.
It is never scientific acceptance. The ignore-signal scenario intentionally has
no final receipt: an owned host must stop it, and a kill remains UNKNOWN.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
WAIT_SECONDS = 12.0
IGNORE_SECONDS = 15.0
MODE = 'ENGINEERING_SIMULATED_NATIVE'
EXPECTED_GUARDS = frozenset(('SCF.kernel', 'hf.kernel', 'RHF.kernel', 'UHF.kernel',
    'ROHF.kernel', 'RKS.kernel', 'UKS.kernel', 'ROKS.kernel', 'Grids.build',
    'Mole.intor', 'Mole.intor_by_shell', 'NumInt.nr_rks', 'numint.nr_rks', 'Mole.energy_nuc'))
SOURCE_FILES = ('scripts/probe-user-molecule-native-shutdown-worker.py',
    'runtime/user_molecule/root_native_lifecycle.py', 'runtime/user_molecule/root_native_accounting.py',
    'runtime/user_molecule/residual_budget.py', 'runtime/user_molecule/acceptance_resources.py',
    'scripts/ci-guard-budget-recording.py', 'scripts/ci-guard-seed-v2.py',
    'scripts/diagnose-user-molecule-occupied-space-response-worker.py',
    'scripts/diagnose-user-molecule-seed-v2-worker.py')


def save(path, value):
    """Publish a complete new JSON record atomically; preserve partial failures."""
    path = Path(path)
    if path.exists():
        raise FileExistsError('Do not overwrite probe evidence: '+str(path))
    pending = path.with_name(path.name+'.pending')
    with pending.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def load_module(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    if spec is None or spec.loader is None:
        raise RuntimeError('Probe helper unavailable: '+relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard_snapshot(bindings, attempted):
    names = [row[3] for row in bindings]
    changed = [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
    held = (len(names) == 14 and len(set(names)) == 14 and set(names) == EXPECTED_GUARDS
            and not changed and not attempted)
    return {'status': 'PASS_HELD14_NATIVE_OPERATION_GUARDS' if held else 'FAIL_OR_UNKNOWN_NATIVE_GUARDS',
        'guarded_operations': names, 'forbidden_attempts': list(attempted), 'changed_guards': changed,
        'actual_native_NR_calls': 0 if held else None,
        'actual_native_count_scope': 'OWNED_HELD14_FORBIDDEN_APIS_NO_ATTEMPTS_NOT_SIMULATED_DISPATCH_COUNTS',
        'scope': 'ENGINEERING_PROCESS_ONLY_NOT_A_MOLECULAR_RUN_OR_OS_SECURITY_AUTHENTICATION'}


def wait_for_signal(controller):
    limit = time.monotonic()+WAIT_SECONDS
    while not controller.snapshot()['stop_requested']:
        if time.monotonic() >= limit:
            raise TimeoutError('Expected external signal did not arrive within12 seconds')
        time.sleep(.025)


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('before-charge', 'during-delegate', 'ignore-signal'), required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('/output'))
    return parser


def toy_identity(*, batch, scenario, source, versions, density_id):
    """Required bookkeeping digests describe a synthetic fixture, no molecule."""
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    return {'mode': MODE, 'execution_kind': MODE, 'scientific_execution_authorized': False,
        'geometry_sha256': digest(b'FIXED_SYNTHETIC_SHUTDOWN_GEOMETRY_NOT_A_MOLECULE'),
        'profile_sha256': digest((MODE+';PURE_FIXED_DELEGATE;NO_SCIENTIFIC_PROFILE').encode('ascii')),
        'dependencies_sha256': digest(json.dumps(versions, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')),
        'initial_density_id': density_id, 'batch_id': batch, 'scenario': scenario,
        'source_file_sha256': dict(source), 'execution_grant': None, 'scientific_budget_reserved': False,
        'budget_reservation': None, 'Compute': False}


def run_probe(args):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    output = args.output_dir.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Probe output must be outside readonly source')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Fresh probe output required; no resume or overwrite')
    source = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    commit = os.environ.get('AI4ORGCHEM_RUNTIME_TEST_COMMIT')
    if commit is not None and re.fullmatch('[0-9a-f]{40}', commit) is None:
        raise ValueError('When supplied, runtime commit must be a complete SHA')
    save(output/'probe-source-identity.json', {'schema': 'zero-native-shutdown-probe-source-v1',
        'runtime_test_commit': commit, 'source_file_sha256': source,
        'self_source_sha256': source[SOURCE_FILES[0]], 'scenario': args.scenario,
        'execution_kind': MODE, 'scientific_execution_authorized': False,
        'scientific_budget': None, 'old_scientific_inputs_or_grant_read': False, 'Compute': False})
    from runtime.user_molecule.root_native_lifecycle import CooperativeStopRequested, StopController
    from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
    from runtime.user_molecule.root_native_accounting import RootNativeAccounting
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    controller = StopController()
    bindings, attempted = [], []
    with controller.installed():
        platform_helper = load_module('scripts/diagnose-user-molecule-occupied-space-response-worker.py', 'probe_platform_helpers')
        platform = platform_helper.platform_preflight(roots={'root_filesystem': '/', 'runtime_source': ROOT})
        save(output/'platform-preflight.json', platform)
        if platform['status'] != 'PASS_ACTUAL_PLATFORM_PREFLIGHT':
            raise RuntimeError('Actual non-root readonly offline platform preflight failed')
        guard_helper = load_module('scripts/ci-guard-budget-recording.py', 'probe_native_guard_helpers')
        tmpfs = guard_helper.tmpfs_mount(Path('/tmp'))
        resource_helper = platform_helper.shared_helpers(ROOT)
        cgroup = collect_cgroup(phase='BEFORE_ENGINEERING_HANDLES')
        quota, period = cgroup.get('cpu_quota_us'), cgroup.get('cpu_period_us')
        reasons = resource_helper.resource_reasons(cgroup)
        if type(quota) is not int or type(period) is not int or quota != period:
            reasons.append('EXACT_ONE_CPU_REQUIRED')
        save(output/'resource-preflight.json', {'cgroup': cgroup, 'tmpfs': tmpfs, 'reasons': reasons})
        if reasons:
            raise RuntimeError('Actual1GiB/1CPU/zero-swap resource preflight failed')
        versions = {name: importlib.metadata.version(name) for name in ('pyscf', 'numpy', 'scipy')}
        save(output/'dependency-identity.json', versions)
        if versions != {'pyscf': '2.14.0', 'numpy': '2.5.1', 'scipy': '1.18.0'}:
            raise RuntimeError('Pinned candidate dependencies differ')
        bindings = guard_helper.install_guards(attempted)
        from pyscf import gto
        def no_nuclear(*_args, **_kwargs):
            attempted.append('Mole.energy_nuc')
            raise AssertionError('Native nuclear energy forbidden in shutdown engineering')
        gto.Mole.energy_nuc = no_nuclear
        bindings.append((gto.Mole, 'energy_nuc', no_nuclear, 'Mole.energy_nuc'))
        initial_guard = guard_snapshot(bindings, attempted)
        save(output/'guard-ready-status.json', initial_guard)
        if initial_guard['actual_native_NR_calls'] != 0:
            raise RuntimeError('All14 native guards must be held before constructing toy handles')
        batch = 'shutdown-probe-'+uuid.uuid4().hex
        did = hashlib.sha256(b'FIXED_ENGINEERING_TOY_DENSITY_NOT_A_MOLECULE').hexdigest()
        identity = toy_identity(batch=batch, scenario=args.scenario, source=source, versions=versions, density_id=did)
        journal = ConditionalCallbackBudget(path=output/'callbacks.json', batch_id=batch, identity=identity,
            path_limits={'independent_reference': 201}, total_limit=201)
        accounting = RootNativeAccounting(output/'accounting', journal, execution_kind=MODE,
            scientific_execution_authorized=False)
        def ready():
            save(output/'READY.json', {'status': 'READY_FOR_EXTERNAL_ENGINEERING_SIGTERM', 'scenario': args.scenario,
                'execution_kind': MODE, 'scientific_execution_authorized': False, 'scientific_budget': None,
                'source_sha256': source[SOURCE_FILES[0]], 'guard_snapshot': guard_snapshot(bindings, attempted),
                'controller': controller.snapshot(), 'accounting_snapshot': accounting.snapshot(),
                'expected_exit_code': 137 if args.scenario == 'ignore-signal' else 42,
                'Compute': False})
        if args.scenario == 'ignore-signal':
            ready()
            limit = time.monotonic()+IGNORE_SECONDS
            while time.monotonic() < limit:
                # Intentionally omit checkpoints, not an alternative live runner.
                time.sleep(.025)
            save(output/'ignore-signal-timeout.json', {'status': 'NO_FORCED_KILL_RECEIPT_UNKNOWN_ENGINEERING_ONLY',
                'controller': controller.snapshot(), 'final_shutdown_receipt': 'MISSING', 'Compute': False})
            return 24
        token = None
        stopped = False
        failure = None
        final = None
        try:
            if args.scenario == 'before-charge':
                ready(); wait_for_signal(controller)
                controller.checkpoint('BEFORE_TOY_CHARGE')
            else:
                controller.checkpoint('BEFORE_TOY_CHARGE')
                token = accounting.begin_callback(did, 'CURRENT_INITIAL')
                context = {'slot_id': token.slot_id, 'density_id': did,
                    'path_id': 'independent_reference', 'phase': 'CURRENT_INITIAL'}
                def fixed_delegate():
                    ready(); wait_for_signal(controller)
                    return 0.0
                value = accounting.native_nr(token, fixed_delegate, context_binding=context,
                    pre_dispatch_check=lambda: controller.checkpoint('BEFORE_SIMULATED_DELEGATE'))
                if value != 0.0:
                    raise RuntimeError('Fixed pure delegate changed')
                controller.checkpoint('AFTER_SIMULATED_DELEGATE')
            raise RuntimeError('Expected cooperative checkpoint did not stop')
        except CooperativeStopRequested as error:
            stopped = True; failure = error
            if token is not None and journal.snapshot()['pending_slots']:
                accounting.fail_callback(token, error)
        except BaseException as error:
            failure = error
            if token is not None and journal.snapshot()['pending_slots']:
                accounting.fail_callback(token, error)
        finally:
            final = accounting.close('EXPECTED_ENGINEERING_STOP_NO_RETRY' if stopped else 'ENGINEERING_FAILURE_NO_RETRY')
            save(output/'journal-final.json', journal.snapshot())
            save(output/'accounting-final.json', final)
            guard = guard_snapshot(bindings, attempted)
            save(output/'guard-status.json', guard)
            resource = collect_cgroup(phase='AFTER_ENGINEERING_HANDLE_CLOSE')
            save(output/'resource-final.json', resource)
            counts = final['callback_slots']; simulated = final['engineering_simulated_native_counts']
            wanted = ({'charged': 0, 'pending': 0, 'succeeded': 0, 'failed': 0, 'limit': 201}
                      if args.scenario == 'before-charge' else
                      {'charged': 1, 'pending': 0, 'succeeded': 0, 'failed': 1, 'limit': 201})
            wanted_simulated = {'entered': 0, 'completed': 0, 'failed': 0} if args.scenario == 'before-charge' else {'entered': 1, 'completed': 1, 'failed': 0}
            source_unknown = all(final['source_native_dispatch_counts'][key] is None for key in ('entered', 'completed', 'failed'))
            good = (stopped and final['closed'] is True and final['persistence_intact'] is True
                and counts == wanted and simulated == wanted_simulated and source_unknown
                and guard['actual_native_NR_calls'] == 0 and not resource_helper.resource_reasons(resource))
            save(output/'shutdown-probe-receipt.json', {'status': 'STOPPED_ENGINEERING_ONLY_CLOSED' if good else 'FAIL_OR_UNKNOWN_ENGINEERING_SHUTDOWN',
                'scenario': args.scenario, 'controller': controller.snapshot(),
                'execution_kind': MODE, 'scientific_execution_authorized': False, 'scientific_budget': None,
                'journal_snapshot': journal.snapshot(), 'accounting_snapshot': final,
                'engineering_simulated_native_counts': simulated,
                'source_native_accounting_counts': final['source_native_dispatch_counts'],
                'actual_native_NR_calls': guard['actual_native_NR_calls'], 'actual_native_evidence': guard,
                'error_type': None if failure is None else type(failure).__name__,
                'error': None if failure is None else str(failure),
                'expected_engineering_exit_code': 42 if good else 20,
                'scientific_acceptance': 'NOT_EXECUTED_NO_MOLECULE_NO_GRANT',
                'automatic_retry': False, 'resume': False, 'Compute': False})
        return 42 if good else 20


def main():
    args = argument_parser().parse_args()
    try:
        return run_probe(args)
    except BaseException as error:
        print(json.dumps({'status': 'FAIL_OR_UNKNOWN_ENGINEERING_SHUTDOWN',
            'type': type(error).__name__, 'message': str(error), 'actual_native_NR_calls': None,
            'scientific_execution_authorized': False, 'scientific_budget': None, 'Compute': False}), flush=True)
        return 20


if __name__ == '__main__':
    raise SystemExit(main())
