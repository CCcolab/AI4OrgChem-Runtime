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
from pathlib import Path
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


def collect_cgroup(root='/sys/fs/cgroup', phase=None):
    """Read cgroup v2 counters without resetting peaks or substituting process RSS.

    A private container cgroup's memory.peak includes startup and earlier phases;
    its value is a conservative whole-container peak, not a per-phase peak.
    Missing/unsupported counters are explicit unknowns. Hard limits are observed,
    never inferred from requested Docker arguments.
    """
    root = Path(root)
    observation = {'schema_version': 'cgroup-resource-observation-v1', 'source': 'CGROUP_V2',
                   'root': str(root), 'observed_at_utc': _utc(), 'phase': phase,
                   'memory_current_bytes': None, 'memory_peak_bytes': None,
                   'memory_limit_bytes': None, 'memory_limit_unbounded': None,
                   'memory_swap_limit_bytes': None, 'memory_swap_limit_unbounded': None,
                   'memory_events': None, 'cpu_quota_us': None, 'cpu_period_us': None,
                   'cpu_limit_unbounded': None, 'errors': [],
                   'peak_scope': 'CUMULATIVE_CONTAINER_CGROUP_NOT_PER_PHASE',
                   'peak_reset_performed': False}
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


def qualify_exact_fixture(identity, n_ao, observations, memory_limit_mib=4096, threads=1):
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
        if not isinstance(sample, dict) or sample.get('source') != 'CGROUP_V2':
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
        if not isinstance(events, dict) or any(type(events.get(name)) is not int for name in ('oom', 'oom_kill')):
            reasons.append(prefix + 'UNKNOWN_OOM_COUNTERS')
        elif events['oom'] != 0 or events['oom_kill'] != 0:
            reasons.append(prefix + 'OOM_OBSERVED')
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
            'scientific_qualification': 'NOT_REVIEWED'}
