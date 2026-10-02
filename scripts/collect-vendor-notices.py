"""Read vendor notices in the existing image (run inside read-only container)."""
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re


def family(text):
    labels = []
    if 'permission is hereby granted, free of charge' in text.lower():
        labels.append('MIT')
    if 'Apache License' in text and 'Version 2.0' in text:
        labels.append('Apache-2.0')
    if 'Mozilla Public License' in text and '2.0' in text:
        labels.append('MPL-2.0')
    if 'Redistribution and use in source and binary forms' in text:
        labels.append('BSD-family; exact clauses preserved in text')
    if 'PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2' in text:
        labels.append('PSF-2.0 and any retained historical clauses')
    if 'GNU LESSER GENERAL PUBLIC LICENSE' in text and 'Version 3, 29 June 2007' in text:
        labels.append('LGPL-3.0 text; or-later grant needs source header/metadata confirmation')
    return labels or ['Text retained; exact expression needs review']


notices, components, source_hashes = {}, [], {}
for environment in ['/opt/venv/lib/python3.12/site-packages', '/usr/local/lib/python3.12/site-packages']:
    for parent in ['pip', 'setuptools']:
        root = Path(environment) / parent / '_vendor'
        if not root.exists():
            continue
        for path in root.rglob('*.py'):
            if path.is_file():
                source_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*'):
            if path.is_file() and re.match(r'^(LICENSE|COPYING|NOTICE)', path.name, re.I):
                data = path.read_bytes()
                text = data.decode('utf-8', errors='replace')
                notices[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(),
                                      'text': text, 'license_families': family(text)}
        if parent == 'pip':
            for line in (root / 'vendor.txt').read_text().splitlines():
                match = re.match(r'\s*([\w.-]+)==([^\s#]+)', line)
                if not match:
                    continue
                name, version = match.groups()
                directory = 'pkg_resources' if name.lower() == 'setuptools' else name.lower().replace('-', '_')
                files = [p for p in notices if p.startswith(str(root / directory) + '/')
                         or p == str(root / (directory + '.LICENSE'))]
                components.append({'parent': parent, 'environment': environment, 'name': name,
                                   'version': version, 'transitive_in_vendor_txt': line.startswith(' '),
                                   'license_files': files, 'license_families': sorted({f for p in files for f in notices[p]['license_families']}),
                                   'status': 'NOTICE_FOUND' if files else 'NOTICE_NOT_FOUND'})
        else:
            for info in sorted(root.glob('*.dist-info')):
                metadata = Parser().parsestr((info / 'METADATA').read_text())
                files = [p for p in notices if p.startswith(str(info) + '/')]
                components.append({'parent': parent, 'environment': environment, 'name': metadata['Name'],
                                   'version': metadata['Version'], 'metadata_license': metadata['License'],
                                   'license_files': files, 'license_families': sorted({f for p in files for f in notices[p]['license_families']}),
                                   'status': 'NOTICE_FOUND' if files else 'NOTICE_NOT_FOUND'})
print(json.dumps({'components': components, 'notices': notices, 'python_source_hashes': source_hashes,
                  'scope': 'Exact installed vendor version and notice paths; textual families are not a complete per-file SPDX expression'}, ensure_ascii=True))
