"""Read ELF .comment compiler strings; these are hints, not source attestations."""
import hashlib
import json
from pathlib import Path
import struct


def comments(data):
    if data[:5] != b'\x7fELF\x02' or data[5] != 1:
        return []
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, strings = struct.unpack_from('<HHH', data, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size) for i in range(count)]
    names = data[sections[strings][4]:sections[strings][4] + sections[strings][5]]
    result = []
    for section in sections:
        name = names[section[0]:].split(b'\0', 1)[0]
        if name == b'.comment':
            result.extend(x.decode('utf-8', errors='replace') for x in data[section[4]:section[4]+section[5]].split(b'\0') if x)
    return sorted(set(result))


records = []
for path in Path('/opt/venv/lib/python3.12/site-packages').rglob('*.so*'):
    if path.is_file() and any(s in path.name.lower() for s in ['openblas', 'gfortran', 'quadmath', 'gomp', 'hdf5', 'aec', 'libsz', 'libxc', 'libcint']):
        data = path.read_bytes()
        try:
            compiler = comments(data)
        except (IndexError, struct.error):
            compiler = []
        records.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                        'elf_compiler_comments': compiler, 'exact_source_build': 'UNKNOWN'})
print(json.dumps({'libraries': records, 'scope': 'Compiler strings alone do not establish runtime source version, patches or build options'}))
