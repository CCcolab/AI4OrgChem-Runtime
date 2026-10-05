"""Check/compute/report without changing the legacy task CLI."""
import argparse
import os
import sys
import traceback
from pathlib import Path
from .input import InputError, read_request
from .records import load, save, file_hash, manifest, report
from .preflight import observations, verify_source, identity

ROOT = Path(__file__).resolve().parents[2]


def validate(value, schema_name):
    from jsonschema import Draft202012Validator
    Draft202012Validator(load(ROOT/'schemas'/schema_name)).validate(value)


def execute(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name in ('preflight.json', 'result.json', 'runtime-progress.json'):
        if (output/name).exists():
            raise InputError('output contains prior service records; use a new run', 40)
    save(output/'runtime-progress.json', {'stage': 'INPUT_CHECK'})
    bundle = read_request(args.request, load(ROOT/'schemas/user-molecule-request-v1.json'))
    profile_path = ROOT/'profiles/user-molecule'/(bundle['request']['calculation_profile']+'.json')
    profile = load(profile_path)
    source = Path(os.environ.get('AI4ORGCHEM_SOURCE', '/opt/ai4orgchem'))
    source_lock = verify_source(ROOT, source)
    sys.path.insert(0, str(source/'software/src'))
    from ai4orgchem.qm.user_molecule_adapter import inspect, compute
    identities = identity(ROOT, bundle, profile_path, source_lock)
    # Output copies are evidence; actual request-snapshot mount is separately read-only.
    input_dir = output/'input'
    input_dir.mkdir()
    (input_dir/'request.original.json').write_bytes(bundle['request_bytes'])
    (input_dir/'request.normalized.json').write_bytes(bundle['normalized_bytes'])
    (input_dir/'molecule.xyz').write_bytes(bundle['xyz_bytes'])
    inspected = inspect(bundle['request'], bundle['atoms'], profile)
    if inspected['dependencies'] != profile['expected_dependencies']:
        raise InputError('scientific dependency identity mismatch', 40)
    resources = observations()
    reasons = list(profile['blocked_reasons']) if not profile['compute_enabled'] else []
    if inspected['nao'] > profile['maximum_inspect_nao']:
        raise InputError('nAO exceeds engineering inspect limit; computation not started', 11)
    if resources['memory']['effective_available_bytes'] == 'UNKNOWN' or resources['cpu']['errors']:
        reasons.append('RESOURCE_OBSERVATION_UNKNOWN')
    preflight = {'schema_version': 1, 'input_status': 'VALID', 'compute_eligible': not reasons,
        'method_status': 'NOT_REVIEWED', 'reasons': reasons, 'inspection': inspected,
        'resources': resources, 'identities': identities, 'atom_mapping': bundle['atom_mapping']}
    validate(preflight, 'user-molecule-preflight-v1.json')
    save(output/'preflight.json', preflight)
    save(output/'runtime-progress.json', {'stage': 'INPUT_CHECK_COMPLETED', 'scf_executed': False})
    if args.action == 'check':
        (output/'report.md').write_text(report(preflight), encoding='utf-8')
        manifest(output, action='check', input_status='VALID', execution_status='COMPLETED',
                 numerical_status='NOT_EXECUTED', compute_eligible=preflight['compute_eligible'], identities=identities)
        return 0
    parent = Path(args.check_run)
    parent_receipt = load(parent/'preflight.json')
    if parent_receipt['identities'] != identities:
        raise InputError('check receipt/input/profile/image/source identity mismatch; check again', 20)
    parent_manifest = load(parent/'run-manifest.json')
    expected_receipt = parent_manifest['files']['preflight.json']['sha256']
    if file_hash(parent/'preflight.json') != expected_receipt:
        raise InputError('check receipt hash mismatch', 20)
    result = {'schema_version': 1, 'input_status': 'VALID', 'execution_status': 'BLOCKED',
        'numerical_status': 'NOT_EXECUTED', 'research_status': 'NOT_REVIEWED', 'comparison_available': False,
        'delta_hartree': None, 'delta_kcal_mol': None, 'reasons': reasons, 'identities': identities}
    if not reasons:
        model = profile.get('resource_model')
        cap = profile.get('maximum_compute_nao')
        available = resources['memory']['effective_available_bytes']
        if not model or not cap or inspected['nao'] > cap:
            result['reasons'] = ['RESOURCE_MODEL_NOT_CALIBRATED_OR_SCALE_UNSUPPORTED']
        elif available < model['required_peak_bytes']:
            result['reasons'] = ['EFFECTIVE_MEMORY_INSUFFICIENT']
        else:
            import fcntl
            lock_path = Path(args.lock_root)/'quantum.lock'
            with lock_path.open('a+') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise InputError('another runtime compute holds shared lock', 20) from exc
                raw = compute(bundle['request'], bundle['atoms'], profile,
                              progress=lambda v: save(output/'runtime-progress.json', v))
            result.update(raw)
            result['execution_status'] = 'COMPLETED'
            result['numerical_status'] = 'NUMERICALLY_QUALIFIED' if result['comparison_available'] else 'NOT_QUALIFIED'
    validate(result, 'user-molecule-result-v1.json')
    save(output/'result.json', result)
    (output/'report.md').write_text(report(result), encoding='utf-8')
    manifest(output, action='compute', check_receipt_sha256=expected_receipt, identities=identities,
             execution_status=result['execution_status'], numerical_status=result['numerical_status'])
    return 20 if result['execution_status'] == 'BLOCKED' else (0 if result['comparison_available'] else 30)


def main():
    parser = argparse.ArgumentParser(description='Experimental user molecule service; compute remains gated pending W05/W06.')
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('check', 'compute'):
        child = sub.add_parser(action)
        child.add_argument('--request', required=True)
        child.add_argument('--output-dir', required=True)
        if action == 'compute':
            child.add_argument('--check-run', required=True)
            child.add_argument('--lock-root', default='/locks')
    child = sub.add_parser('report')
    child.add_argument('--run-directory', required=True)
    args = parser.parse_args()
    if args.action == 'report':
        path = Path(args.run_directory)
        record = load(path/('result.json' if (path/'result.json').exists() else 'preflight.json'))
        print(report(record))
        return 0
    try:
        return execute(args)
    except Exception as exc:
        code = exc.code if isinstance(exc, InputError) else 40
        output = Path(args.output_dir)
        # Never replace an existing result with a generic error after a retry.
        if not (output/'result.json').exists():
            save(output/'error.json', {'error_type': type(exc).__name__, 'message': str(exc), 'exit_code': code})
            manifest(output, action=args.action, execution_status='FAILED', numerical_status='NOT_EXECUTED', exit_code=code)
        print(str(exc), file=sys.stderr)
        if code == 40:
            traceback.print_exc()
        return code


if __name__ == '__main__':
    raise SystemExit(main())
