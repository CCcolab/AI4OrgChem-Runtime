"""Conservative memory preflight, including cgroup hierarchy limits."""
import math
import os
from pathlib import Path, PurePosixPath

UNKNOWN = 'UNKNOWN'


def remaining(limit, usage):
    if limit.strip() == 'max':
        return None
    value = int(limit)
    if value >= 2**60:  # v1 unlimited sentinel
        return None
    return max(0, value - int(usage))


def memory_snapshot(proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    host = None
    try:
        for line in (proc / 'meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                host = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    samples, errors = [], []
    try:
        memberships = (proc / 'self/cgroup').read_text().splitlines()
        mounts = (proc / 'self/mountinfo').read_text().splitlines()
        unmounted_v2 = False
        usable_v1 = False
        for row in memberships:
            _, controllers, relative = row.split(':', 2)
            version = 2 if controllers == '' else 1
            if version == 1 and 'memory' not in controllers.split(','):
                continue
            matched_mount = False
            for mount in mounts:
                left, right = mount.split(' - ', 1)
                fields, fs = left.split(), right.split()
                expected = 'cgroup2' if version == 2 else 'cgroup'
                if fs[0] != expected or (version == 1 and 'memory' not in fs[2].split(',')):
                    continue
                matched_mount = True
                # Tests may remap the standard cgroup mount to a fixture.
                posix_mount = PurePosixPath(fields[4].replace('\\040', ' '))
                mount_path = Path(str(posix_mount))
                if posix_mount.is_relative_to('/sys/fs/cgroup'):
                    mount_path = cgroup / str(posix_mount.relative_to('/sys/fs/cgroup'))
                root = fields[3]
                relative_path = str(PurePosixPath(relative).relative_to(root)) if PurePosixPath(relative).is_relative_to(root) else '..'
                # A private cgroup namespace exposes / as membership even when
                # mount root is a host path. In that case start at visible root.
                if relative_path.startswith('..'):
                    relative_path = '.'
                leaf = mount_path / relative_path
                found_counter = False
                while True:
                    names = ('memory.max', 'memory.current') if version == 2 else ('memory.limit_in_bytes', 'memory.usage_in_bytes')
                    if (leaf / names[0]).exists():
                        found_counter = True
                        samples.append(remaining((leaf / names[0]).read_text(), (leaf / names[1]).read_text()))
                    if leaf == mount_path:
                        break
                    leaf = leaf.parent
                if not found_counter:
                    errors.append('memory controller counters unavailable')
                elif version == 1:
                    usable_v1 = True
                break
            if not matched_mount:
                if version == 2:
                    # Hybrid kernels may list an unused unified hierarchy while
                    # memory is exclusively attached to a visible v1 controller.
                    unmounted_v2 = True
                else:
                    errors.append('memory cgroup mount unavailable')
        if unmounted_v2 and not usable_v1:
            errors.append('memory cgroup mount unavailable')
    except (OSError, ValueError) as exc:
        errors.append(type(exc).__name__)
    values = ([host] if host is not None else []) + [v for v in samples if v is not None]
    return {'host_available_bytes': host if host is not None else UNKNOWN,
            'cgroup_remaining_bytes': [v if v is not None else 'unlimited' for v in samples],
            'effective_available_bytes': min(values) if values and not errors else UNKNOWN,
            'errors': errors}


def require_memory(task, snapshot):
    thresholds = {'p14-fixed': 13000 * 1024**2, 'p14-optimize': 13 * 1024**3}
    required = thresholds.get(task)
    available = snapshot['effective_available_bytes']
    if required and (available == UNKNOWN or available < required):
        raise MemoryError(f'{task} requires {required} bytes effective available memory; found {available}')


def thread_limit(requested):
    if requested < 1:
        raise ValueError('threads must be positive')
    count = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    quota = Path('/sys/fs/cgroup/cpu.max')
    if quota.exists():
        maximum, period = quota.read_text().split()
        if maximum != 'max':
            count = min(count, max(1, math.floor(int(maximum) / int(period))))
    return min(requested, count)
