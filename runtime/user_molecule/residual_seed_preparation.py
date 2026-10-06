"""V2 cache/MO binding. Metadata and algebra only; never authorizes F calls."""
import copy
import hashlib
import io
from pathlib import Path

import numpy as np

from .input import strict_json
from .residual_bridge import array_identity
from .residual_preparation import (create_bridge_contract, load_preparation_input,
                                  restore_legacy_basis_representation)
from .preflight import verify_source
from .seed_v2 import POLICY_ID

ARRAY_KEYS = ('density', 'overlap', 'hcore', 'eri', 'grid_coords', 'grid_weights',
              'mo_coefficients', 'mo_occupations')


def prepare_cached_context(*, runtime_root, science_root, ordinary_dir, identity):
    """Caller must install SCF/grid/integral/NR guards before calling this API."""
    from pyscf import gto
    from reference.ordinary_molecule import build
    root, science, cache = map(Path, (runtime_root, science_root, ordinary_dir))
    lock = verify_source(root, science)
    if (lock['source_commit'] != identity['science_commit'] or
            lock['baseline_commit'] != identity['science_baseline_commit']):
        raise ValueError('Frozen source identity differs')
    if hashlib.sha256((root/'locks/source-user-molecule-files.sha256.json').read_bytes()).hexdigest() != identity['source_manifest_sha256']:
        raise ValueError('Source manifest identity differs')
    fixture, origin = identity['fixture'], identity['ordinary_origin']
    input_data = load_preparation_input(runtime_root=root, request_path=root/fixture['request_path'])
    if (input_data['bundle']['normalized_sha256'] != fixture['normalized_request_sha256'] or
            input_data['bundle']['xyz_sha256'] != fixture['xyz_sha256'] or
            input_data['profile_sha256'] != identity['profile_sha256']):
        raise ValueError('Frozen request/geometry/profile differs')
    record_path, arrays_path = cache/origin['record_file'], cache/origin['arrays_file']
    raw_record, raw_arrays = record_path.read_bytes(), arrays_path.read_bytes()
    for raw, kind in ((raw_record, 'record'), (raw_arrays, 'arrays')):
        expected = origin[kind]
        if len(raw) != expected['size_bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('Frozen complete ordinary source differs: '+kind)
    record = strict_json(raw_record)
    with np.load(io.BytesIO(raw_arrays), allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in ARRAY_KEYS}
    for name, value in arrays.items():
        actual = array_identity(value)
        if actual != record['array_identities'][name]:
            raise ValueError('Ordinary NPZ/JSON member mismatch: '+name)
        if name in origin['array_identities'] and actual != origin['array_identities'][name]:
            raise ValueError('Frozen old proposal array differs: '+name)
        value.setflags(write=False)
    original_nuc = gto.Mole.energy_nuc
    def no_nuclear(*args, **kwargs):
        raise RuntimeError('No nuclear-energy call permitted during cached metadata build')
    gto.Mole.energy_nuc = no_nuclear
    try:
        context = build(input_data['bundle']['request'], input_data['bundle']['atoms'], input_data['profile'])
    finally:
        gto.Mole.energy_nuc = original_nuc
    basis_receipt = restore_legacy_basis_representation(context=context, ordinary_record=record)
    context.mean_field.grids.coords, context.mean_field.grids.weights = arrays['grid_coords'], arrays['grid_weights']
    return dict(context=context, arrays=arrays, record=record, prepared_input=input_data,
                record_path=record_path, arrays_path=arrays_path, basis_receipt=basis_receipt, lock=lock,
                original_record_bytes=raw_record, original_arrays_bytes=raw_arrays)


def create_seed_bridge_preparation(*, runtime_root, science_root, cached,
                                   runtime_test_commit, image_id, image_build_commit,
                                   execution_kind, shared_seed_density=None):
    """Retain the old operator contract and bind V2 as a separate outer policy."""
    prepared = create_bridge_contract(runtime_root=runtime_root, science_root=science_root,
        prepared_input=cached['prepared_input'], context=cached['context'], arrays=cached['arrays'],
        ordinary_record=cached['record'], runtime_test_commit=runtime_test_commit, image_id=image_id,
        image_build_commit=image_build_commit, execution_kind=execution_kind,
        initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
        ordinary_record_path=cached['record_path'], ordinary_arrays_path=cached['arrays_path'])
    mo = {name: cached['record']['array_identities'][name] for name in ('mo_coefficients', 'mo_occupations')}
    kwargs = prepared['bridge_kwargs']
    kwargs.update(mo_coefficients=cached['arrays']['mo_coefficients'],
                  mo_occupations=cached['arrays']['mo_occupations'],
                  frozen_ordinary_mo_identities=copy.deepcopy(mo), shared_seed_density=shared_seed_density)
    prepared.update(seed_policy=POLICY_ID, verified_mo_members=copy.deepcopy(mo),
        seed_scope='SEPARATE_V2_INITIALIZATION_NOT_LEGACY_D0_PROJECTION',
        scientific_execution_authorized=False)
    return prepared
