"""Read existing run evidence without calculation, approval, or record mutation."""
import copy
import hashlib
from pathlib import Path, PureWindowsPath
import re
import stat

from .input import InputError, strict_json
from .records import report
from .research import assess


def _problem(message):
    return InputError(message, 40)


def _reject_links(path):
    for component in (*reversed(path.parents), path):
        try:
            observed = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _problem('Cannot inspect evidence path component: ' + str(component)) from exc
        if stat.S_ISLNK(observed.st_mode) or getattr(observed, 'st_file_attributes', 0) & 0x400:
            raise _problem('Symlink or reparse component in evidence path: ' + str(component))


def _inside(root, name):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise _problem('Invalid evidence path')
    relative = name.replace('\\', '/')
    parts = relative.split('/')
    if (Path(relative).is_absolute() or PureWindowsPath(name).drive or
            any(part in ('', '.', '..') or ':' in part for part in parts)):
        raise _problem('Evidence path escapes run directory: ' + name)
    candidate = root / relative
    _reject_links(candidate)
    path = candidate.resolve()
    if path == root or not path.is_relative_to(root):
        raise _problem('Evidence path escapes run directory: ' + name)
    return path, relative


def _digest(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _json(path):
    try:
        with path.open('rb') as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise _problem('Evidence metadata JSON exceeds 4 MiB: ' + path.name)
        value = strict_json(raw)
    except (InputError, OSError, ValueError, TypeError) as exc:
        raise _problem('Cannot read strict evidence JSON ' + path.name + ': ' + str(exc)) from exc
    if not isinstance(value, dict):
        raise _problem('Evidence JSON must be an object: ' + path.name)
    return value, {'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _host_failure(record, blocked_context=False):
    observation = record.get('observation') or {}
    if not isinstance(observation, dict):
        raise _problem('Host observation must be an object')
    status = record.get('status')
    reason = record.get('termination_reason') or observation.get('reason')
    container_code = record.get('container_exit_code', observation.get('container_exit_code'))
    service_code = record.get('service_exit_code')
    terminal = ('TIMEOUT', 'TIMED_OUT', 'CANCELLED', 'CANCELED', 'FAILED', 'OOM_KILLED')
    infrastructure_failure = (bool(record.get('collection_error')) or reason == 'UNKNOWN' or
                              observation.get('oom_killed') is True or record.get('oom_killed') is True or
                              bool(observation.get('engine_error')) or reason in terminal)
    blocked = ((status == 'BLOCKED' or blocked_context or service_code == 20) and
               service_code in (None, 20) and container_code in (None, 20) and not infrastructure_failure)
    failed = not blocked and (status in terminal or (isinstance(status, str) and status.startswith('FAIL')) or
              reason in terminal or observation.get('oom_killed') is True or
              infrastructure_failure or
              (type(service_code) is int and service_code != 0) or
              (type(container_code) is int and container_code != 0))
    incomplete = not failed and not blocked and status not in ('PASS', 'COMPLETED')
    return {'failed': failed, 'blocked': blocked, 'incomplete': incomplete, 'reason': reason,
            'service_exit_code': service_code, 'container_exit_code': container_code,
            'host_exit_code': record.get('host_exit_code'),
            'container_exit_code_source': ('host-execution.json.container_exit_code'
                if 'container_exit_code' in record else 'host-execution.json.observation.container_exit_code')}


def read_run_report(run_directory):
    """Return markdown and a conservative derived summary of local evidence.

    MATCHED means only that a local manifest matches local bytes. It proves no
    reviewer authority, scientific acceptance, source provenance, or permission.
    Missing evidence is rendered as UNVERIFIED (report_exit_code 40); corrupt or
    escaping evidence raises InputError(40). A read of a complete failed run can
    return 0 without changing that run's scientific failure or original exit.
    """
    candidate = Path(run_directory).absolute()
    _reject_links(candidate)
    root = candidate.resolve()
    if not root.is_dir():
        raise _problem('Run directory does not exist: ' + str(root))
    sources, missing, issues, documents = {}, [], [], {}
    manifest_names = [name for name in ('run-manifest.json', 'manifest.json')
                      if (root / name).exists()]
    manifest_records = {}
    declared = set()
    declared_case = {}
    for name in manifest_names:
        path, _ = _inside(root, name)
        document, stamp = _json(path)
        manifest_records[name] = document
        sources[name] = {**stamp, 'integrity': 'MANIFEST',
                         'role': 'local hash registry; authority not established'}
        files = document.get('files')
        if not isinstance(files, dict) or not files:
            issues.append('MANIFEST_FILE_LIST_MISSING: ' + name)
            continue
        if len(files) > 10000:
            raise _problem('Evidence manifest exceeds 10000 files')
        local_names = set()
        for relative, entry in files.items():
            target, normalized = _inside(root, relative)
            if normalized.casefold() in local_names:
                raise _problem('Duplicate normalized manifest path: ' + normalized)
            local_names.add(normalized.casefold())
            if (not isinstance(entry, dict) or type(entry.get('size_bytes')) is not int or
                    entry['size_bytes'] < 0 or not isinstance(entry.get('sha256'), str) or
                    not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
                raise _problem('Invalid manifest size/hash: ' + normalized)
            declared.add(normalized)
            folded = normalized.casefold()
            if folded in declared_case and declared_case[folded] != normalized:
                raise _problem('Conflicting manifest path case: ' + normalized)
            declared_case[folded] = normalized
            if len(declared) > 10000:
                raise _problem('Evidence manifests exceed 10000 files')
            if not target.is_file():
                missing.append(normalized)
                issues.append('MANIFEST_FILE_MISSING: ' + normalized)
                sources[normalized] = {'size_bytes': None, 'sha256': None,
                                       'integrity': 'MISSING', 'role': 'missing manifest-listed evidence'}
                continue
            try:
                actual_size, actual_digest = _digest(target)
            except OSError as exc:
                raise _problem('Cannot verify manifest file: ' + normalized) from exc
            if actual_size != entry['size_bytes'] or actual_digest != entry['sha256']:
                raise _problem('Manifest byte mismatch: ' + normalized)
            sources[normalized] = {'size_bytes': actual_size, 'sha256': actual_digest,
                                   'integrity': 'MATCHED', 'role': 'manifest-listed evidence'}
    if not manifest_names:
        issues.append('MANIFEST_MISSING')
        missing.append('run-manifest.json or manifest.json')

    def read(name):
        path, relative = _inside(root, name)
        if not path.exists():
            return None
        document, stamp = _json(path)
        entry = sources.get(relative)
        if entry is not None and (entry['size_bytes'] != stamp['size_bytes'] or entry['sha256'] != stamp['sha256']):
            raise _problem('Evidence changed during report read: ' + relative)
        if relative not in declared:
            issues.append('FILE_NOT_MANIFESTED: ' + relative)
        sources[relative] = {**stamp,
                             'integrity': 'MATCHED' if relative in declared else 'UNVERIFIED',
                             'role': 'read JSON evidence'}
        documents[relative] = document
        return document

    raw_result = read('result.json')
    preflight = read('preflight.json')
    error = read('error.json')
    host = read('host-execution.json')
    execution = read('execution.json')
    progress = read('runtime-progress.json')
    service_request = read('input/request.normalized.json')
    original_request = read('input/request.original.json')
    acceptance_request = read('request.acceptance.json')
    host_state = (_host_failure(host, (raw_result or {}).get('execution_status') == 'BLOCKED') if host else
                  {'failed': False, 'blocked': False, 'incomplete': False, 'reason': None,
                   'service_exit_code': None, 'container_exit_code': None, 'host_exit_code': None,
                   'container_exit_code_source': None})
    terminal_host, host_reason = host_state['failed'], host_state['reason']
    acceptance = bool(raw_result and ('status' in raw_result or 'checks' in raw_result)
                      and 'execution_status' not in raw_result)
    record_kind = ('acceptance' if acceptance else 'service-result' if raw_result else
                   'service-error' if error else 'host-failure' if terminal_host else
                   'service-preflight' if preflight else 'host-incomplete' if host_state['incomplete'] else
                   'host-blocked' if host_state['blocked'] else 'unknown')
    if record_kind == 'unknown':
        raise _problem('No supported result, preflight, error, or failed host record')
    request = acceptance_request if acceptance else service_request
    expected_absence = []
    if request is None and (raw_result or preflight):
        issues.append('REQUEST_SNAPSHOT_MISSING')
        missing.append('request.acceptance.json' if acceptance else 'input/request.normalized.json')
    elif request is None:
        expected_absence.append('input/request.normalized.json (input parsing did not produce a snapshot)')
    record = copy.deepcopy(raw_result or preflight or {})
    raw_statuses = {key: record.get(key) for key in
                    ('input_status', 'execution_status', 'numerical_status', 'research_status',
                     'method_status', 'method_review_status', 'status')}
    if host:
        raw_statuses['host_status'] = host.get('status')
    manifest = manifest_records.get('run-manifest.json', manifest_records.get('manifest.json', {}))
    for value in manifest_records.values():
        if 'host' in value:
            if host is None:
                issues.append('MANIFEST_HOST_RECORD_MISSING')
            elif value['host'] != host:
                raise _problem('Manifest host record conflicts with host-execution.json')
    identities = {}
    identity_records = [(name, value.get('identities') or {}) for name, value in
                        (('record', record), ('preflight', preflight or {}), ('manifest', manifest))]
    if record.get('identity') is not None:
        identity_records.append(('record identity', record['identity']))
    if execution:
        identity_records.append(('execution', execution.get('identity') or {}))
    if host:
        identity_records.append(('host', host.get('identities') or host.get('identity') or {}))
        host_bindings = {key: host[key] for key in ('image_id', 'science_commit', 'runtime_build_commit')
                         if key in host}
        for source, target in (('original_geometry_sha256', 'geometry_sha256'),
                               ('original_request_sha256', 'source_request_sha256' if acceptance else 'request_sha256')):
            if source in host:
                host_bindings[target] = host[source]
        identity_records.append(('host fields', host_bindings))
    for origin, values in identity_records:
        if not isinstance(values, dict):
            raise _problem('Invalid identities object in ' + origin)
        for key, value in values.items():
            if key in identities and identities[key] is not None and value is not None and identities[key] != value:
                raise _problem('Conflicting run identity: ' + key)
            if value is not None or key not in identities:
                identities[key] = value
    request_name = 'request.acceptance.json' if acceptance else 'input/request.normalized.json'
    binding_name = 'acceptance_request_sha256' if acceptance else 'normalized_sha256'
    if request and identities.get(binding_name) and identities[binding_name] != sources[request_name]['sha256']:
        raise _problem('Request snapshot identity mismatch: ' + binding_name)
    if original_request and identities.get('request_sha256') and identities['request_sha256'] != sources['input/request.original.json']['sha256']:
        raise _problem('Original request snapshot identity mismatch')
    for identity_key, filename in (('geometry_sha256', 'molecule.xyz'),
                                   ('geometry_sha256', 'input/molecule.xyz'),
                                   ('profile_sha256', 'profile.unchanged.json')):
        if (filename in sources and sources[filename]['integrity'] == 'MATCHED' and
                identities.get(identity_key) and identities[identity_key] != sources[filename]['sha256']):
            raise _problem('Evidence identity mismatch: ' + identity_key)

    states = {}
    failed_metrics = []
    if acceptance:
        for name in ('ordinary-tested', 'conditional-single', 'conditional-copy', 'conditional-reference'):
            value = read(name + '.json')
            if value is not None:
                states[name] = value
        resource = read('resource-candidate.json')
        if resource is not None:
            raw_statuses['resource_scientific_qualification'] = resource.get('scientific_qualification')
        checks = record.get('checks') or []
        if not isinstance(checks, list) or any(not isinstance(check, dict) for check in checks):
            raise _problem('Acceptance checks must be an array of objects')
        failed_metrics = list(record.get('failed_metric_ids') or [])
        if any(not isinstance(metric, str) for metric in failed_metrics):
            raise _problem('Invalid failed metric identifiers')
        failed_metrics.extend(check.get('metric_id', 'UNKNOWN') for check in checks
                              if check.get('required') is True and check.get('pass') is False)
        failed_metrics = list(dict.fromkeys(failed_metrics))
        record['ordinary'] = states.get('ordinary-tested')
        record['conditional'] = states.get('conditional-single')
    else:
        for name in ('ordinary', 'conditional'):
            state = record.get(name)
            if state is not None and not isinstance(state, dict):
                raise _problem('Invalid molecular state object: ' + name)
            if state:
                states[name] = state

    checked_only = (record_kind == 'service-preflight' and not error and not terminal_host and
                    not host_state['blocked'] and not host_state['incomplete'])
    try:
        qualification = ({'method_status': 'NOT_REVIEWED', 'research_status': 'NOT_REVIEWED',
                          'reasons': ['NUMERICAL_COMPARISON_NOT_EXECUTED']}
                         if checked_only else assess(record, (request or {}).get('calculation_profile')))
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise _problem('Invalid evidence structure for qualification: ' + str(exc)) from exc
    input_status = record.get('input_status', (preflight or {}).get('input_status', 'UNKNOWN'))
    execution_status = record.get('execution_status', manifest.get('execution_status', 'UNKNOWN'))
    numerical_status = record.get('numerical_status', manifest.get('numerical_status', 'UNKNOWN'))
    if input_status not in ('VALID', 'INVALID', 'UNSUPPORTED'):
        input_status = 'UNKNOWN'
    if execution_status not in ('NOT_EXECUTED', 'COMPLETED', 'FAILED', 'BLOCKED'):
        execution_status = 'UNKNOWN'
    if numerical_status not in ('NOT_EXECUTED', 'NUMERICALLY_QUALIFIED', 'NOT_QUALIFIED'):
        numerical_status = 'UNKNOWN'
    if numerical_status == 'NUMERICALLY_QUALIFIED' and qualification['research_status'] == 'NOT_QUALIFIED':
        numerical_status = 'NOT_QUALIFIED'
    research_status = qualification['research_status']
    reasons = list(record.get('reasons') or [])
    scientific_execution = ('NOT_EXECUTED' if checked_only or numerical_status == 'NOT_EXECUTED' else
                            'EXECUTED' if raw_result and numerical_status in ('NUMERICALLY_QUALIFIED', 'NOT_QUALIFIED') else 'UNKNOWN')
    exit_code, exit_source = None, None
    for origin, value in (('error.json.exit_code', (error or {}).get('exit_code')),
                          ('host-execution.json.service_exit_code', host_state['service_exit_code']),
                          ('execution.json.container_exit_code', (execution or {}).get('container_exit_code')),
                          (host_state['container_exit_code_source'], host_state['container_exit_code']),
                          ('run-manifest.json.exit_code', manifest.get('exit_code'))):
        if type(value) is int:
            exit_code, exit_source = value, origin
            break
    if checked_only:
        completed_host = 'COMPLETED' if (host or {}).get('status') in ('COMPLETED', 'PASS') else 'UNKNOWN'
        execution_status = manifest.get('execution_status', completed_host)
        numerical_status = 'NOT_EXECUTED'
    if acceptance:
        raw_status = record.get('status')
        observed_failure = (isinstance(raw_status, str) and raw_status.startswith('FAIL')) or bool(failed_metrics)
        if observed_failure:
            execution_status, numerical_status, research_status = 'FAILED', 'NOT_QUALIFIED', 'NOT_QUALIFIED'
            scientific_execution = 'EXECUTED' if raw_status == 'FAIL_NUMERICAL_GATES' or record.get('phases') else 'UNKNOWN'
            reasons.append('RECORDED_ACCEPTANCE_FAILURE: ' + str(raw_status))
        else:
            issues.append('ACCEPTANCE_SUCCESS_NOT_ASSESSED_BY_REPORT')
            execution_status, numerical_status, research_status = 'UNKNOWN', 'UNKNOWN', 'NOT_QUALIFIED'
    if error or terminal_host:
        execution_status, research_status = 'FAILED', 'NOT_QUALIFIED'
        if numerical_status == 'NUMERICALLY_QUALIFIED':
            numerical_status = 'NOT_QUALIFIED'
        if (progress or {}).get('scf_executed') is False:
            numerical_status, scientific_execution = 'NOT_EXECUTED', 'NOT_EXECUTED'
        elif (progress or {}).get('scf_executed') is True:
            numerical_status, scientific_execution = 'NOT_QUALIFIED', 'EXECUTED'
        else:
            numerical_status, scientific_execution = 'UNKNOWN', 'UNKNOWN'
        reasons.append('ERROR_RECORD: ' + str(error.get('message', 'UNKNOWN')) if error else
                       'HOST_TERMINAL_FAILURE: ' + str(host_reason or (host or {}).get('status', 'UNKNOWN')))
    elif host_state['blocked']:
        execution_status, research_status = 'BLOCKED', 'NOT_QUALIFIED'
    elif host_state['incomplete']:
        execution_status, numerical_status, research_status, scientific_execution = 'UNKNOWN', 'UNKNOWN', 'NOT_QUALIFIED', 'UNKNOWN'
        issues.append('HOST_NONTERMINAL_OR_UNKNOWN')
    integrity = 'UNVERIFIED' if issues else 'MATCHED'
    available = (integrity == 'MATCHED' and not acceptance and not error and not terminal_host and
                 record.get('comparison_available') is True and
                 qualification['research_status'] in ('TECHNICAL_ONLY', 'NOT_REVIEWED'))
    if integrity != 'MATCHED' and not checked_only:
        research_status = 'NOT_QUALIFIED'
        if raw_statuses['numerical_status'] == 'NUMERICALLY_QUALIFIED':
            numerical_status = 'UNKNOWN'
    raw_eligibility = (preflight or record).get('compute_eligible')
    eligibility = (False if error or terminal_host or host_state['blocked'] else
                   raw_eligibility if integrity == 'MATCHED' and type(raw_eligibility) is bool else None)
    summary = {'record_integrity': integrity, 'record_integrity_scope': 'LOCAL_MANIFEST_BYTES_ONLY',
               'report_exit_code': 40 if issues else 0, 'input_status': input_status,
               'execution_status': execution_status, 'scientific_execution_status': scientific_execution,
               'numerical_status': numerical_status, 'research_status': research_status,
               'method_status': 'NOT_REVIEWED', 'compute_eligible': eligibility,
               'raw_compute_eligible': raw_eligibility,
               'comparison_available': available,
               'delta_hartree': record.get('delta_hartree') if available else None,
               'delta_kcal_mol': record.get('delta_kcal_mol') if available else None,
               'identities': identities, 'original_exit_code': exit_code,
               'host_service_exit_code': host_state['service_exit_code'],
               'container_exit_code': host_state['container_exit_code'],
               'host_exit_code': host_state['host_exit_code'],
               'original_exit_code_source': exit_source, 'termination_reason': host_reason,
               'raw_statuses': raw_statuses, 'failed_metric_ids': failed_metrics,
               'reasons': reasons, 'qualification_reasons': qualification['reasons'],
               'evidence_issues': list(dict.fromkeys(issues)), 'missing_files': list(dict.fromkeys(missing)),
               'expected_absence': expected_absence,
               'raw_state_labels': {name: {key: value[key] for key in
                   ('molecular_acceptance', 'research_acceptance', 'research_status', 'state_comparability',
                    'solver_candidate_status', 'molecular_execution') if key in value}
                    for name, value in states.items()},
               'state_diagnostics': states, 'checked_only': checked_only}
    record['identities'] = identities
    return {'markdown': report(record, request, summary=summary), 'summary': summary,
            'source_files': sources, 'record_kind': record_kind}
