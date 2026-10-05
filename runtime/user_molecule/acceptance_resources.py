"""Acceptance-only persistent budgets and cgroup v2 observations.

This module neither launches calculations nor activates a production profile.
The caller must reserve before launching, then charge wall time through process
termination and output collection. An unresolved reservation remains charged at
its entire timeout after a crash; reopening the ledger never resets it.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile


class ResourceError(ValueError):
    pass


class BudgetBusy(ResourceError):
    pass


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def identity_digest(identity):
    """Bind one exact fixture/profile/dependency/mode identity, including extras."""
    if not isinstance(identity, dict):
        raise ResourceError('identity must be an object')
    for name in ('geometry_sha256', 'profile_sha256', 'dependencies_sha256'):
        if not isinstance(identity.get(name), str) or not re.fullmatch('[0-9a-f]{64}', identity[name]):
            raise ResourceError(name + ' must be a complete lowercase SHA-256')
    if not isinstance(identity.get('mode'), str) or not identity['mode'].strip():
        raise ResourceError('mode is required')
    try:
        return hashlib.sha256(_canonical(identity)).hexdigest()
    except (ValueError, TypeError) as exc:
        raise ResourceError('identity must contain finite JSON values') from exc


def _positive_int(value, name, maximum):
    if type(value) is not int or not 0 < value <= maximum:
        raise ResourceError(f'{name} must be an integer in 1..{maximum}')
    return value


def _name(value, field):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ResourceError(field + ' must be a bounded identifier')
    return value


def _finite_seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ResourceError('observed wall time must be finite and nonnegative')
    return float(value)


@contextmanager
def _lock(path):
    """Nonblocking OS file lock; no automatic deletion of another holder's lock."""
    if path.is_symlink():
        raise ResourceError('budget lock must not be a symlink')
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BudgetBusy('another process holds the batch budget') from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BudgetBusy('another process holds the batch budget') from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _atomic_write(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ResourceError('duplicate ledger JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ResourceError('nonfinite ledger JSON value: ' + value)
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        _canonical(data)
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise ResourceError('budget ledger is unreadable or invalid; it was not reset') from exc


class Budget:
    """Durable sum-of-child-wall budget with reservations before process launch.

    Creating a different batch ID/configuration over an existing path is refused.
    The file is a local accounting record, not proof of reviewer authorization.
    """
    def __init__(self, path, batch_id, total_seconds=7200, max_process_seconds=900,
                 memory_limit_mib=4096, threads=1):
        self.path = Path(path).absolute()
        self.batch_id = _name(batch_id, 'batch_id')
        self.limits = {
            'total_seconds': _positive_int(total_seconds, 'total_seconds', 7200),
            'max_process_seconds': _positive_int(max_process_seconds, 'max_process_seconds', 900),
            'memory_limit_mib': _positive_int(memory_limit_mib, 'memory_limit_mib', 4096),
            'threads': _positive_int(threads, 'threads', 1),
            'swap_allowed': False,
        }
        if max_process_seconds > total_seconds:
            raise ResourceError('process ceiling exceeds total batch budget')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + '.lock')
        with _lock(self.lock_path):
            if self.path.exists() or self.path.is_symlink():
                self._load()
            else:
                self._save({'schema_version': 'acceptance-budget-v1', 'batch_id': self.batch_id,
                            'limits': self.limits, 'created_at_utc': _utc(), 'runs': {}})

    def _load(self):
        if self.path.is_symlink():
            raise ResourceError('budget ledger must not be a symlink')
        data = _strict_load(self.path)
        if not isinstance(data, dict) or data.get('schema_version') != 'acceptance-budget-v1':
            raise ResourceError('unknown ledger format; existing file was not reset')
        checksum = data.pop('integrity_sha256', None)
        if checksum != hashlib.sha256(_canonical(data)).hexdigest():
            raise ResourceError('budget ledger integrity mismatch')
        if data.get('batch_id') != self.batch_id or data.get('limits') != self.limits:
            raise ResourceError('existing batch identity/limits differ; resetting is forbidden')
        if not isinstance(data.get('runs'), dict):
            raise ResourceError('invalid ledger runs')
        for run_id, run in data['runs'].items():
            _name(run_id, 'run_id')
            if not isinstance(run, dict) or run.get('run_id') != run_id:
                raise ResourceError('invalid run record')
            _positive_int(run.get('reserved_seconds'), 'reserved_seconds', self.limits['max_process_seconds'])
            if identity_digest(run.get('identity')) != run.get('identity_sha256'):
                raise ResourceError('run identity mismatch')
            if run.get('state') == 'SETTLED':
                _finite_seconds(run.get('observed_wall_seconds'))
                if not isinstance(run.get('termination_reason'), str) or not run['termination_reason'].strip():
                    raise ResourceError('settled run lacks termination reason')
            elif run.get('state') != 'RESERVED':
                raise ResourceError('unknown reservation state')
        return data

    def _save(self, data):
        data['updated_at_utc'] = _utc()
        data['integrity_sha256'] = hashlib.sha256(_canonical(data)).hexdigest()
        _atomic_write(self.path, data)

    def _snapshot(self, data):
        settled = [run['observed_wall_seconds'] for run in data['runs'].values() if run['state'] == 'SETTLED']
        reserved = sum(run['reserved_seconds'] for run in data['runs'].values() if run['state'] == 'RESERVED')
        consumed = math.fsum(settled)
        return {**data, 'consumed_seconds': consumed, 'unresolved_reserved_seconds': reserved,
                'remaining_seconds': max(0.0, self.limits['total_seconds'] - consumed - reserved),
                'over_budget': consumed + reserved > self.limits['total_seconds'],
                'production_activation': False}

    def snapshot(self):
        with _lock(self.lock_path):
            return self._snapshot(self._load())

    def reserve(self, run_id, timeout_seconds, identity):
        run_id = _name(run_id, 'run_id')
        timeout_seconds = _positive_int(timeout_seconds, 'timeout_seconds', self.limits['max_process_seconds'])
        digest = identity_digest(identity)
        # Deep-copy strict JSON: later caller mutation cannot change a reservation.
        identity = json.loads(_canonical(identity))
        with _lock(self.lock_path):
            data = self._load()
            if run_id in data['runs']:
                raise ResourceError('run ID already exists; reruns require a new reservation')
            if timeout_seconds > self._snapshot(data)['remaining_seconds']:
                raise ResourceError('insufficient persistent batch wall budget')
            run = {'run_id': run_id, 'state': 'RESERVED', 'reserved_seconds': timeout_seconds,
                   'identity': identity, 'identity_sha256': digest, 'reserved_at_utc': _utc()}
            data['runs'][run_id] = run
            self._save(data)
            return json.loads(_canonical(run))

    def settle(self, run_id, observed_wall_seconds, termination_reason, resource_observation=None):
        run_id = _name(run_id, 'run_id')
        wall = _finite_seconds(observed_wall_seconds)
        if not isinstance(termination_reason, str) or not termination_reason.strip() or len(termination_reason) > 256:
            raise ResourceError('explicit termination reason is required')
        if resource_observation is not None:
            try:
                resource_observation = json.loads(_canonical(resource_observation))
            except (ValueError, TypeError) as exc:
                raise ResourceError('resource observation must contain finite JSON values') from exc
        with _lock(self.lock_path):
            data = self._load()
            run = data['runs'].get(run_id)
            if run is None or run['state'] != 'RESERVED':
                raise ResourceError('only an outstanding reservation can be settled, exactly once')
            run.update(state='SETTLED', observed_wall_seconds=wall, termination_reason=termination_reason,
                       settled_at_utc=_utc(), timeout_exceeded=wall > run['reserved_seconds'],
                       resource_observation=resource_observation)
            self._save(data)
            return self._snapshot(self._load())


def _resolve_v1_paths(cgroup_path='/proc/self/cgroup', mountinfo_path='/proc/self/mountinfo'):
    """Resolve the current process' v1 membership against controller mount roots."""
    memberships = {}
    for line in Path(cgroup_path).read_text(encoding='ascii').splitlines():
        fields = line.split(':', 2)
        if len(fields) != 3:
            raise ResourceError('invalid /proc/self/cgroup record')
        for controller in fields[1].split(','):
            if controller:
                memberships[controller] = fields[2]
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), value)
    mounts = []
    for line in Path(mountinfo_path).read_text(encoding='ascii').splitlines():
        fields = line.split(' - ', 1)
        if len(fields) != 2:
            raise ResourceError('invalid /proc/self/mountinfo record')
        left, right = fields[0].split(), fields[1].split()
        if len(left) < 6 or len(right) < 3:
            raise ResourceError('truncated /proc/self/mountinfo record')
        if right[0] == 'cgroup':
            mounts.append({'mount_root': unescape(left[3]), 'mount_point': unescape(left[4]),
                           'controllers': set(right[2].split(','))})
    resolved = {}
    for controller in ('memory', 'cpu'):
        membership = memberships.get(controller)
        if membership is None:
            raise ResourceError('missing v1 controller membership: ' + controller)
        candidates = []
        for mount in mounts:
            if controller not in mount['controllers']:
                continue
            member, base = PurePosixPath(membership), PurePosixPath(mount['mount_root'])
            if not member.is_absolute() or not base.is_absolute() or '..' in member.parts or '..' in base.parts:
                raise ResourceError('unsafe cgroup membership or mount root')
            try:
                relative = member.relative_to(base)
                resolution = 'MEMBERSHIP_RELATIVE_TO_MOUNT_ROOT'
            except ValueError:
                # A cgroup namespace can expose its membership as / while the
                # mount root retains the host hierarchy's absolute path.
                if membership != '/':
                    continue
                relative = PurePosixPath('.')
                resolution = 'CGROUP_NAMESPACE_ROOT'
            candidates.append({**{key: mount[key] for key in ('mount_root', 'mount_point')},
                               'membership_path': membership, 'path_resolution': resolution,
                               'resolved_path': str(Path(mount['mount_point']) / str(relative))})
        if not candidates:
            raise ResourceError('controller membership cannot be resolved: ' + controller)
        # Prefer the most specific mounted hierarchy; never fall back to a
        # parent cgroup just because a child counter cannot be read.
        resolved[controller] = max(candidates, key=lambda item: len(PurePosixPath(item['mount_root']).parts))
    return resolved


def collect_cgroup_v1(memory_root, cpu_root, phase=None):
    """Native v1 counters, preserving their definitions and actual file paths.

    memory.failcnt counts limit failures, not OOM events. under_oom is a current
    flag, not a history. oom_kill is reported only when the kernel supplies it.
    memory.memsw.limit_in_bytes is combined memory+swap; swap allowance below is
    its difference from the memory limit, never the combined value itself.
    """
    memory_root, cpu_root = Path(memory_root), Path(cpu_root)
    files = {name: str(memory_root / name) for name in (
        'memory.usage_in_bytes', 'memory.max_usage_in_bytes', 'memory.limit_in_bytes',
        'memory.memsw.limit_in_bytes', 'memory.failcnt', 'memory.oom_control')}
    files.update({name: str(cpu_root / name) for name in ('cpu.cfs_quota_us', 'cpu.cfs_period_us')})
    observation = {'schema_version': 'cgroup-resource-observation-v1', 'source': 'CGROUP_V1',
                   'root': {'memory': str(memory_root), 'cpu': str(cpu_root)}, 'files': files,
                   'observed_at_utc': _utc(), 'phase': phase, 'memory_current_bytes': None,
                   'memory_peak_bytes': None, 'memory_limit_bytes': None, 'memory_limit_unbounded': None,
                   'memory_memsw_limit_bytes': None, 'memory_memsw_limit_unbounded': None,
                   'memory_swap_limit_bytes': None, 'memory_swap_limit_unbounded': None,
                   'memory_events': None, 'cpu_quota_us': None, 'cpu_period_us': None,
                   'cpu_limit_unbounded': None, 'errors': [],
                   'peak_scope': 'CUMULATIVE_CONTAINER_CGROUP_NOT_PER_PHASE', 'peak_reset_performed': False,
                   'oom_counter_semantics': 'V1_FAILCNT_IS_LIMIT_FAILURES_UNDER_OOM_IS_CURRENT_FLAG'}
    def read(name):
        try:
            path = Path(files[name])
            if path.stat().st_size > 65536:
                raise ValueError('counter file exceeds size bound')
            text = path.read_text(encoding='ascii').strip()
            if len(text) > 65536:
                raise ValueError('counter file exceeds size bound')
            return text
        except (OSError, ValueError, UnicodeError) as exc:
            observation['errors'].append({'file': files[name], 'error_type': type(exc).__name__, 'message': str(exc)})
            return None
    def integer(name, signed=False):
        text = read(name)
        if text is None:
            return None
        if not re.fullmatch('-?[0-9]+' if signed else '[0-9]+', text):
            observation['errors'].append({'file': files[name], 'error_type': 'InvalidCounter', 'message': 'invalid integer'})
            return None
        return int(text)
    for name, field in (('memory.usage_in_bytes', 'memory_current_bytes'),
                        ('memory.max_usage_in_bytes', 'memory_peak_bytes'),
                        ('memory.limit_in_bytes', 'memory_limit_bytes'),
                        ('memory.memsw.limit_in_bytes', 'memory_memsw_limit_bytes')):
        observation[field] = integer(name)
    for prefix in ('memory_limit', 'memory_memsw_limit'):
        value = observation[prefix + '_bytes']
        observation[prefix + '_unbounded'] = value >= 2 ** 60 if value is not None else None
    memory_limit, memsw_limit = observation['memory_limit_bytes'], observation['memory_memsw_limit_bytes']
    if memory_limit is not None and memsw_limit is not None:
        if observation['memory_memsw_limit_unbounded']:
            observation['memory_swap_limit_unbounded'] = True
        elif observation['memory_limit_unbounded'] or memsw_limit < memory_limit:
            observation['errors'].append({'file': files['memory.memsw.limit_in_bytes'], 'error_type': 'InvalidCounter',
                                          'message': 'combined memory/swap limit cannot determine swap allowance'})
        else:
            observation['memory_swap_limit_bytes'] = memsw_limit - memory_limit
            observation['memory_swap_limit_unbounded'] = False
    events = {'limit_failures': integer('memory.failcnt'), 'oom_kill': None,
              'under_oom': None, 'oom_kill_disable': None}
    text = read('memory.oom_control')
    if text is not None:
        parsed = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) != 2 or parts[0] in parsed or not re.fullmatch('[0-9]+', parts[1]):
                observation['errors'].append({'file': files['memory.oom_control'], 'error_type': 'InvalidCounter',
                                              'message': 'invalid or duplicate OOM control entry'})
                parsed = {}
                break
            parsed[parts[0]] = int(parts[1])
        for key in ('oom_kill', 'under_oom', 'oom_kill_disable'):
            events[key] = parsed.get(key)
    observation['memory_events'] = events
    observation['cpu_quota_us'] = integer('cpu.cfs_quota_us', signed=True)
    observation['cpu_period_us'] = integer('cpu.cfs_period_us')
    quota = observation['cpu_quota_us']
    observation['cpu_limit_unbounded'] = quota == -1 if quota is not None else None
    if quota == -1:
        observation['cpu_quota_us'] = None
    observation['status'] = ('COMPLETE' if not observation['errors'] else
                             'UNKNOWN' if observation['memory_current_bytes'] is None and observation['memory_peak_bytes'] is None else 'PARTIAL')
    observation['oom_kill_counter_available'] = type(events['oom_kill']) is int
    return observation


def collect_cgroup(root='/sys/fs/cgroup', phase=None):
    """Read native v1/v2 counters without resetting peaks or substituting RSS.

    A private container cgroup's memory.peak includes startup and earlier phases;
    its value is a conservative whole-container peak, not a per-phase peak.
    Missing/unsupported counters are explicit unknowns. Hard limits are observed,
    never inferred from requested Docker arguments.
    """
    root = Path(root)
    if root == Path('/sys/fs/cgroup') and not (root / 'memory.current').exists():
        try:
            paths = _resolve_v1_paths()
            observation = collect_cgroup_v1(paths['memory']['resolved_path'], paths['cpu']['resolved_path'], phase)
            observation['discovery'] = paths
            return observation
        except (OSError, ValueError, UnicodeError) as exc:
            return {'schema_version': 'cgroup-resource-observation-v1', 'source': 'CGROUP_UNRESOLVED',
                    'root': str(root), 'phase': phase, 'observed_at_utc': _utc(), 'status': 'UNKNOWN',
                    'memory_current_bytes': None, 'memory_peak_bytes': None, 'memory_limit_bytes': None,
                    'memory_events': None, 'errors': [{'file': '/proc/self/cgroup;/proc/self/mountinfo',
                                                      'error_type': type(exc).__name__, 'message': str(exc)}],
                    'peak_reset_performed': False}
    observation = {'schema_version': 'cgroup-resource-observation-v1', 'source': 'CGROUP_V2',
                   'root': str(root), 'observed_at_utc': _utc(), 'phase': phase,
                   'memory_current_bytes': None, 'memory_peak_bytes': None,
                   'memory_limit_bytes': None, 'memory_limit_unbounded': None,
                   'memory_swap_limit_bytes': None, 'memory_swap_limit_unbounded': None,
                   'memory_events': None, 'cpu_quota_us': None, 'cpu_period_us': None,
                   'cpu_limit_unbounded': None, 'errors': [],
                   'peak_scope': 'CUMULATIVE_CONTAINER_CGROUP_NOT_PER_PHASE',
                   'peak_reset_performed': False}
    observation['files'] = {name: str(root / name) for name in (
        'memory.current', 'memory.peak', 'memory.max', 'memory.swap.max', 'memory.events', 'cpu.max')}
    def read(name):
        try:
            path = root / name
            if path.stat().st_size > 65536:
                raise ValueError('counter file exceeds size bound')
            text = path.read_text(encoding='ascii')
            if len(text) > 65536:
                raise ValueError('counter file exceeds size bound')
            return text.strip()
        except (OSError, ValueError, UnicodeError) as exc:
            observation['errors'].append({'file': name, 'error_type': type(exc).__name__, 'message': str(exc)})
            return None
    def integer(text, name):
        if text is None:
            return None
        if not re.fullmatch('[0-9]+', text):
            observation['errors'].append({'file': name, 'error_type': 'InvalidCounter', 'message': 'expected nonnegative integer'})
            return None
        return int(text)
    for filename, field in (('memory.current', 'memory_current_bytes'), ('memory.peak', 'memory_peak_bytes')):
        observation[field] = integer(read(filename), filename)
    for filename, field in (('memory.max', 'memory_limit'), ('memory.swap.max', 'memory_swap_limit')):
        value = read(filename)
        observation[field + '_unbounded'] = value == 'max' if value is not None else None
        observation[field + '_bytes'] = None if value == 'max' else integer(value, filename)
    value = read('memory.events')
    if value is not None:
        events = {}
        for line in value.splitlines():
            parts = line.split()
            if len(parts) != 2 or parts[0] in events:
                observation['errors'].append({'file': 'memory.events', 'error_type': 'InvalidCounter', 'message': 'invalid or duplicate event'})
                events = None
                break
            counter = integer(parts[1], 'memory.events')
            if counter is None:
                events = None
                break
            events[parts[0]] = counter
        observation['memory_events'] = events
    value = read('cpu.max')
    if value is not None:
        parts = value.split()
        if len(parts) == 2:
            observation['cpu_limit_unbounded'] = parts[0] == 'max'
            observation['cpu_quota_us'] = None if parts[0] == 'max' else integer(parts[0], 'cpu.max')
            observation['cpu_period_us'] = integer(parts[1], 'cpu.max')
        else:
            observation['errors'].append({'file': 'cpu.max', 'error_type': 'InvalidCounter', 'message': 'expected quota and period'})
    observation['status'] = ('COMPLETE' if not observation['errors'] else
                             'UNKNOWN' if observation['memory_current_bytes'] is None and observation['memory_peak_bytes'] is None else 'PARTIAL')
    return observation


def qualify_exact_fixture(identity, n_ao, observations, memory_limit_mib=4096, threads=1,
                          external_oom_evidence=None):
    """Create a measured candidate envelope for this identity only.

    Success is not approval of a scientific profile, a generic nAO limit, or a
    production activation. Any changed geometry, profile, dependencies or mode
    needs separate observations. Unknown hard-limit/peak/OOM counters refuse it.
    """
    digest = identity_digest(identity)
    _positive_int(n_ao, 'n_ao', 80)
    _positive_int(memory_limit_mib, 'memory_limit_mib', 4096)
    _positive_int(threads, 'threads', 1)
    reasons = []
    if not isinstance(observations, list) or not observations:
        reasons.append('NO_CGROUP_OBSERVATIONS')
        observations = []
    peaks = []
    for index, sample in enumerate(observations):
        prefix = f'OBSERVATION_{index}:'
        if not isinstance(sample, dict) or sample.get('source') not in ('CGROUP_V1', 'CGROUP_V2'):
            reasons.append(prefix + 'UNKNOWN_CGROUP_SOURCE')
            continue
        peak = sample.get('memory_peak_bytes')
        if type(peak) is not int or peak < 0:
            reasons.append(prefix + 'UNKNOWN_MEMORY_PEAK')
        else:
            peaks.append(peak)
        if sample.get('memory_limit_unbounded') is not False or sample.get('memory_limit_bytes') != memory_limit_mib * 1024 ** 2:
            reasons.append(prefix + 'HARD_MEMORY_LIMIT_NOT_CONFIRMED')
        if sample.get('memory_swap_limit_unbounded') is not False or sample.get('memory_swap_limit_bytes') != 0:
            reasons.append(prefix + 'NO_SWAP_LIMIT_NOT_CONFIRMED')
        quota, period = sample.get('cpu_quota_us'), sample.get('cpu_period_us')
        if (sample.get('cpu_limit_unbounded') is not False or type(quota) is not int or type(period) is not int
                or quota <= 0 or period <= 0 or quota > period * threads):
            reasons.append(prefix + 'CPU_LIMIT_NOT_CONFIRMED')
        events = sample.get('memory_events')
        if sample['source'] == 'CGROUP_V2':
            if not isinstance(events, dict) or any(type(events.get(name)) is not int for name in ('oom', 'oom_kill')):
                reasons.append(prefix + 'UNKNOWN_OOM_COUNTERS')
            elif events['oom'] != 0 or events['oom_kill'] != 0:
                reasons.append(prefix + 'OOM_OBSERVED')
        elif not isinstance(events, dict) or any(type(events.get(name)) is not int for name in ('limit_failures', 'under_oom')):
            reasons.append(prefix + 'UNKNOWN_V1_LIMIT_OR_CURRENT_OOM_COUNTERS')
        elif events['limit_failures'] != 0 or events['under_oom'] != 0:
            reasons.append(prefix + 'V1_LIMIT_FAILURE_OR_CURRENT_OOM_OBSERVED')
        elif type(events.get('oom_kill')) is int:
            if events['oom_kill'] != 0:
                reasons.append(prefix + 'OOM_KILL_OBSERVED')
        else:
            evidence = external_oom_evidence
            # This supplements failcnt=0 and under_oom=0. OOMKilled=false alone
            # cannot stand in for an unavailable complete OOM event history.
            valid = (isinstance(evidence, dict) and evidence.get('source') == 'DOCKER_INSPECT'
                     and evidence.get('oom_killed') is False
                     and isinstance(evidence.get('container_id'), str)
                     and bool(re.fullmatch('[0-9a-f]{64}', evidence['container_id']))
                     and isinstance(evidence.get('evidence_sha256'), str)
                     and bool(re.fullmatch('[0-9a-f]{64}', evidence['evidence_sha256']))
                     and evidence.get('resource_identity_sha256') == digest
                     and isinstance(evidence.get('state_finished_at'), str)
                     and evidence['state_finished_at'].strip()
                     and not evidence['state_finished_at'].startswith('0001-'))
            if not valid:
                reasons.append(prefix + 'V1_OOM_KILL_COUNTER_UNKNOWN_AND_NO_BOUND_COMPLETED_INSPECT')
    peak = max(peaks) if peaks else None
    bound = memory_limit_mib * 1024 ** 2
    if peak is not None and peak > bound:
        reasons.append('OBSERVED_PEAK_EXCEEDS_HARD_LIMIT')
    return {'schema_version': 'acceptance-resource-candidate-v1',
            'status': 'BLOCKED' if reasons else 'RESOURCE_CANDIDATE_EXACT_FIXTURE',
            'identity': json.loads(_canonical(identity)), 'identity_sha256': digest,
            'tested_n_ao': n_ao, 'observed_peak_bytes': peak, 'configured_memory_limit_bytes': bound,
            'observed_headroom_bytes': None if peak is None else bound - peak,
            'threads': threads, 'swap_allowed': False, 'reasons': reasons,
            'scope': 'EXACT_GEOMETRY_PROFILE_DEPENDENCIES_AND_MODE_ONLY',
            'n_ao_extrapolation_allowed': False, 'production_activation': False,
            'scientific_qualification': 'NOT_REVIEWED',
            'external_oom_evidence': external_oom_evidence,
            'oom_claim': 'NO_OBSERVED_LIMIT_FAILURE_CURRENT_OOM_OR_RECORDED_OOM_KILL; NOT_PROOF_OOM_NEVER_OCCURRED'}
