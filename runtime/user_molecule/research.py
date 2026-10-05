"""Conservative, read-only research assessment; never activates Compute."""
import hashlib
import json
import math
from pathlib import Path
import re

BINDINGS = ('normalized_sha256', 'geometry_sha256', 'profile_sha256',
            'condition_rules_sha256', 'science_commit', 'image_id')
PROFILES = {'pilot-b3lypg-sto3g-grid2-v1', 'research-b3lypg-631gd-grid3-v1'}
HARTREE_TO_KCAL_MOL = 627.5094740631


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def result_fingerprint(record):
    """Canonical JSON identity, distinct from the raw result.json file hash."""
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _receipt(root, reference):
    root = Path(root).resolve()
    path = (root / reference['path']).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Review evidence escapes its trusted root')
    if not re.fullmatch(r'[0-9a-f]{64}', reference['sha256']):
        raise ValueError('Invalid receipt hash')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Review evidence byte mismatch')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate receipt key')
            result[key] = value
        return result
    def reject(_value):
        raise ValueError('Nonfinite receipt')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject)


def assess(record, profile_id=None, registry=None, evidence_root=None):
    """Exact-scope assessment using operator-maintained hashed review receipts.

    Hashes preserve bytes, not reviewer authority. Caller flags, question text,
    convergence and bare status strings cannot approve research or Compute.
    """
    result = {'method_status': 'NOT_REVIEWED', 'research_status': 'NOT_QUALIFIED',
              'scope_id': None, 'scope_version': None, 'reasons': []}
    valid = record.get('input_status') == 'VALID' and record.get('execution_status') == 'COMPLETED' and record.get('numerical_status') == 'NUMERICALLY_QUALIFIED'
    valid = valid and record.get('comparison_available') is True
    valid = valid and finite(record.get('delta_hartree')) and finite(record.get('delta_kcal_mol'))
    for state in ('ordinary', 'conditional'):
        value, tests = record.get(state) or {}, record.get(state + '_tests')
        valid = valid and value.get('converged') is True and finite(value.get('total_energy_hartree'))
        valid = valid and isinstance(tests, dict) and bool(tests) and all(v is True for v in tests.values())
    if not valid:
        result['reasons'] = ['NUMERICAL_COMPARISON_NOT_QUALIFIED']
        return result
    if record['delta_hartree'] != record['ordinary']['total_energy_hartree'] - record['conditional']['total_energy_hartree']:
        result['reasons'] = ['COMPARISON_ENERGY_IDENTITY_MISMATCH']
        return result
    if record['delta_kcal_mol'] != record['delta_hartree'] * HARTREE_TO_KCAL_MOL:
        result['reasons'] = ['COMPARISON_UNIT_CONVERSION_MISMATCH']
        return result
    if profile_id not in PROFILES:
        result['reasons'] = ['PROFILE_ID_UNKNOWN_OR_UNSUPPORTED']
        return result
    if isinstance(profile_id, str) and profile_id.startswith('pilot-'):
        result.update(research_status='TECHNICAL_ONLY', reasons=['PILOT_HAS_NO_RESEARCH_QUALIFICATION'])
        return result
    if not isinstance(profile_id, str) or not profile_id.startswith('research-'):
        result['reasons'] = ['PROFILE_ID_UNKNOWN_OR_UNSUPPORTED']
        return result
    result['research_status'] = 'NOT_REVIEWED'
    identities = record.get('identities', {})
    try:
        fingerprint = result_fingerprint(record)
    except (ValueError, TypeError):
        result['reasons'] = ['RESULT_CONTENT_NOT_STRICT_JSON']
        return result
    matching = [s for s in (registry or {}).get('scopes', []) if s.get('profile_id') == profile_id and all(
        identities.get(key) and s.get('bindings', {}).get(key) == identities[key] for key in BINDINGS)
        and s.get('bindings', {}).get('result_content_sha256') == fingerprint]
    if not matching:
        result['reasons'] = ['NO_EXACT_REVIEWED_SCOPE_MATCH']
        return result
    if len(matching) != 1 or evidence_root is None:
        result['reasons'] = ['REVIEW_EVIDENCE_MISSING_OR_AMBIGUOUS']
        return result
    scope = matching[0]
    try:
        if not scope.get('scope_id') or not scope.get('scope_version'):
            raise ValueError('Missing scope identity')
        receipts = {key: _receipt(evidence_root, scope[key]) for key in
                    ('method_review', 'acceptance', 'complete_reference', 'resource_review')}
        for key, receipt in receipts.items():
            if receipt.get('status') != 'PASS' or receipt.get('purpose') != key:
                raise ValueError('Evidence purpose or status missing: ' + key)
            if receipt.get('profile_id') != profile_id or receipt.get('bindings') != scope['bindings']:
                raise ValueError('Evidence identity mismatch: ' + key)
        method = receipts['method_review']
        if any(not isinstance(method.get(key), str) or not method[key].strip() for key in
               ('reviewer', 'responsibility', 'approved_at', 'allowed_interpretation')):
            raise ValueError('Real reviewer/responsibility/interpretation required')
        if method.get('interpretation_id') != 'CONDITIONAL_FIXED_POINT_FUNCTIONAL':
            raise ValueError('Unreviewed interpretation')
        criteria = receipts['acceptance'].get('criteria', {})
        if any(criteria.get(f'A{i:02d}') != 'PASS' for i in range(1, 19)):
            raise ValueError('A01-A18 actual applicable acceptance required')
        if len(set(receipts['acceptance'].get('new_systems', []))) < 2:
            raise ValueError('Two reviewed new systems required')
        reference = receipts['complete_reference']
        if reference.get('independent_core_import_audit') != 'PASS' or reference.get('numerical_execution') != 'PASS':
            raise ValueError('Complete independent molecular reference not executed')
        if not reference.get('threshold_version') or not reference.get('reference_commit'):
            raise ValueError('Reference/threshold identities required')
        resource = receipts['resource_review']
        nao = resource.get('request_nao')
        if type(nao) is not int or nao <= 0 or type(resource.get('tested_maximum_nao')) is not int:
            raise ValueError('Actual tested size required')
        if nao > resource['tested_maximum_nao'] or resource.get('peak_calibration') != 'PASS':
            raise ValueError('Resource calibration or size not qualified')
        if resource.get('bounded_budget_authorized') is not True:
            raise ValueError('No acceptance budget authorization')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result['reasons'] = ['REVIEW_EVIDENCE_NOT_QUALIFIED: ' + str(exc)]
        return result
    result.update(method_status='APPROVED_WITHIN_SCOPE', research_status='QUALIFIED_WITHIN_SCOPE',
                  scope_id=scope['scope_id'], scope_version=scope['scope_version'], reasons=[])
    return result
