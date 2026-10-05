"""New-service resource/identity observations; no legacy threshold changes."""
import os
from pathlib import Path
from runtime.resources import memory_snapshot
from .records import load, file_hash


def cpu_snapshot(proc=Path('/proc/self')):
    samples, errors = [], []
    try:
        memberships = (proc / 'cgroup').read_text().splitlines()
        mounts = (proc / 'mountinfo').read_text().splitlines()
        for membership in memberships:
            _, controllers, relative = membership.split(':', 2)
            version = 2 if not controllers else 1
            if version == 1 and 'cpu' not in controllers.split(','):
                continue
            for mount in mounts:
                left, right = mount.split(' - ', 1)
                fields, fs = left.split(), right.split()
                if fs[0] != ('cgroup2' if version == 2 else 'cgroup'):
                    continue
                if version == 1 and 'cpu' not in fs[2].split(','):
                    continue
                mount_path = Path(fields[4].replace('\\040', ' '))
                mount_root = Path(fields[3])
                member = Path(relative)
                suffix = member.relative_to(mount_root) if member.is_relative_to(mount_root) else Path('.')
                leaf = mount_path / suffix
                while True:
                    if version == 2 and (leaf / 'cpu.max').exists():
                        quota, period = (leaf / 'cpu.max').read_text().split()
                        samples.append(None if quota == 'max' else int(quota)/int(period))
                    if version == 1 and (leaf / 'cpu.cfs_quota_us').exists():
                        quota = int((leaf / 'cpu.cfs_quota_us').read_text())
                        period = int((leaf / 'cpu.cfs_period_us').read_text())
                        samples.append(None if quota < 0 else quota/period)
                    if leaf == mount_path:
                        break
                    leaf = leaf.parent
                break
        # A hybrid host can list an unused v2 hierarchy while CPU is controlled
        # by v1. Missing counters in that unused hierarchy do not invalidate
        # the quota read from the actual CPU controller.
        if not samples:
            errors.append('CPU hierarchy counters unavailable')
    except (OSError, ValueError, ZeroDivisionError) as exc:
        errors.append(type(exc).__name__)
    affinity = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count()
    known = [x for x in samples if x is not None]
    return {'affinity_cpus': affinity, 'quota_cpus': min(known) if known else None,
            'quota_samples': samples,
            'effective_cpus': min([affinity] + known) if affinity is not None and not errors else None,
            'errors': errors}


def observations():
    return {'memory': memory_snapshot(), 'cpu': cpu_snapshot()}


def verify_source(root, source):
    lock = load(root / 'locks/source.user-molecule.lock.json')
    expected = load(root / 'locks/source-user-molecule-files.sha256.json')
    actual = {p.relative_to(source).as_posix(): p for p in source.rglob('*')
              if p.is_file() and '.git' not in p.relative_to(source).parts}
    if set(actual) != set(expected):
        raise ValueError('new scientific source file set mismatch')
    for name, expected_hash in expected.items():
        if file_hash(actual[name]) != expected_hash:
            raise ValueError('new scientific source byte mismatch: '+name)
    return lock


def identity(root, bundle, profile_path, source_lock):
    return {'request_sha256': bundle['request_sha256'], 'normalized_sha256': bundle['normalized_sha256'],
        'geometry_sha256': bundle['xyz_sha256'], 'profile_sha256': file_hash(profile_path),
        'request_schema_sha256': file_hash(root/'schemas/user-molecule-request-v1.json'),
        'science_commit': source_lock['source_commit'], 'science_baseline_commit': source_lock['baseline_commit'],
        'source_manifest_sha256': file_hash(root/'locks/source-user-molecule-files.sha256.json'),
        'runtime_build_commit': os.environ.get('AI4ORGCHEM_RUNTIME_COMMIT'),
        'image_id': os.environ.get('AI4ORGCHEM_IMAGE_ID'),
        'condition_rules_sha256': source_lock['condition_rules_sha256']}
