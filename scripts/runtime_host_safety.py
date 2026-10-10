"""Owned Docker creation recovery and stdlib-only output admission.

No scientific libraries, kernel dispatch, retry, permission mutation or global
configuration occurs here. Unknown daemon state quarantines the owning run.
"""
import json
from pathlib import Path
import re
import uuid

CID = re.compile(r'[0-9a-f]{64}\Z')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')


class HostSafetyError(RuntimeError):
    def __init__(self, message, *, cleanup_unknown=False):
        super().__init__(message)
        self.cleanup_unknown = bool(cleanup_unknown)


def confirmed_absence(result, identity):
    message = result.stderr.decode('utf-8', 'replace').strip()
    return result.returncode == 1 and bool(re.fullmatch(
        r'(?:Error(?: response from daemon)?:\s*)?No such (?:object|container):\s*'+re.escape(identity),
        message, re.I))


def owned_row(result, *, name, image_id, label_key, token):
    if result.returncode != 0:
        raise HostSafetyError('Container identity unavailable', cleanup_unknown=True)
    try:
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError('One actual container inspection required')
        row = rows[0]
        if (not CID.fullmatch(str(row.get('Id'))) or row.get('Image') != image_id
                or row.get('Name') != '/'+name
                or (row.get('Config', {}).get('Labels') or {}).get(label_key) != token):
            raise ValueError('Container name/image/label/ID does not match owned intent')
        return row
    except (ValueError, TypeError, AttributeError) as exc:
        raise HostSafetyError(str(exc), cleanup_unknown=True) from exc


def recover_created_container(docker, *, name, image_id, label_key, token):
    """Return a current identity/absence observation, not pending-request closure."""
    try:
        result = docker('inspect', name, timeout=3, allow_failure=True)
    except Exception as exc:
        raise HostSafetyError('Owned creation outcome unknown: '+str(exc), cleanup_unknown=True) from exc
    if confirmed_absence(result, name):
        return None
    return owned_row(result, name=name, image_id=image_id, label_key=label_key, token=token)['Id']


def probe_output_writable(docker, *, image_id, output_path, token, label_key, timeout=10,
                          python_executable='/opt/venv/bin/python'):
    """Create/remove one owned file as UID10001 before a science worker starts."""
    if not IMAGE.fullmatch(str(image_id)) or not re.fullmatch(r'[0-9a-f]{32}', str(token)):
        raise HostSafetyError('Complete immutable image and execution token required')
    output_path = Path(output_path).absolute()
    if not output_path.is_dir() or output_path.is_symlink() or ',' in str(output_path):
        raise HostSafetyError('Existing isolated bind directory required')
    owner = uuid.uuid4().hex
    name = 'ai4orgchem-output-probe-'+owner
    probe_label = label_key+'.output-probe'
    intent = {'name': name, 'image_id': image_id, 'label_key': probe_label, 'token': owner,
              'parent_execution_id': token, 'scientific_calls': 0}
    journal_root = getattr(docker, 'output', None)
    if journal_root is not None:
        with (Path(journal_root)/('output-probe-intent-'+owner+'.json')).open('x', encoding='utf-8', newline='\n') as out:
            out.write(json.dumps(intent, sort_keys=True)+'\n')
    program = """import json,os,sys
owner=OWNER;parent=PARENT
assert os.geteuid()==10001
path='/output/.runtime-write-probe-'+owner
created=False
try:
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 created=True
 with os.fdopen(fd,'wb') as stream: stream.write(owner.encode('ascii'))
finally:
 if created: os.unlink(path)
print(json.dumps({'owner':owner,'parent_execution_id':parent,'uid':os.geteuid(),'scientific_calls':0,'status':'CREATED_AND_REMOVED'}))
""".replace('OWNER', repr(owner)).replace('PARENT', repr(token))
    command = ['create', '--name', name, '--label', probe_label+'='+owner,
               '--network', 'none', '--read-only', '--user', '10001:10001',
               '--cpus', '1', '--memory', '134217728', '--memory-swap', '134217728',
               '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--mount', 'type=bind,source='+str(output_path)+',target=/output',
               '--entrypoint', python_executable, image_id, '-I', '-c', program]
    cid, error = None, None
    try:
        result = docker(*command, timeout=timeout)
        cid = result.stdout.decode('ascii').strip()
        if not CID.fullmatch(cid):
            cid = None
            raise HostSafetyError('Output probe create did not return a complete ID')
        row = owned_row(docker('inspect', cid, timeout=3), name=name, image_id=image_id,
                        label_key=probe_label, token=owner)
        config, host = row.get('Config', {}), row.get('HostConfig', {})
        if config.get('User') != '10001:10001' or host.get('NetworkMode') != 'none' or host.get('ReadonlyRootfs') is not True:
            raise HostSafetyError('Actual output probe confinement differs')
        process = docker('start', '--attach', cid, timeout=timeout, allow_failure=True)
        row = owned_row(docker('inspect', cid, timeout=3), name=name, image_id=image_id,
                        label_key=probe_label, token=owner)
        state = row.get('State', {})
        if state.get('Running') is not False or type(state.get('ExitCode')) is not int:
            raise HostSafetyError('Output probe process state unknown', cleanup_unknown=True)
        if process.returncode != 0 or state['ExitCode'] != 0:
            raise HostSafetyError('UID10001 output write/readiness probe failed; see preserved command stderr')
        receipt = json.loads(process.stdout)
        if receipt != {'owner': owner, 'parent_execution_id': token, 'uid': 10001,
                       'scientific_calls': 0, 'status': 'CREATED_AND_REMOVED'}:
            raise HostSafetyError('Output probe receipt does not match actual intent')
    except Exception as exc:
        error = exc
    finally:
        try:
            # Always resolve the registered name, including a timed-out create
            # or malformed stdout. Ownership is checked before any rm.
            recovered = recover_created_container(docker, name=name, image_id=image_id,
                                                  label_key=probe_label, token=owner)
            if recovered is None and cid is None:
                raise HostSafetyError('Probe creation may complete after this absence query', cleanup_unknown=True)
            if recovered is not None:
                if cid is not None and recovered != cid:
                    raise HostSafetyError('Output probe CID/name changed', cleanup_unknown=True)
                docker('rm', '--force', recovered, timeout=3)
                absent = docker('inspect', recovered, timeout=3, allow_failure=True)
                if not confirmed_absence(absent, recovered):
                    raise HostSafetyError('Output probe removal unconfirmed', cleanup_unknown=True)
        except Exception as exc:
            raise HostSafetyError('Output probe cleanup unknown: '+str(exc), cleanup_unknown=True) from exc
    if error is not None:
        # Successful owned removal closes cleanup even if the original probe
        # failed. The numerical worker still must not run after this refusal.
        raise HostSafetyError(str(error), cleanup_unknown=False) from error
