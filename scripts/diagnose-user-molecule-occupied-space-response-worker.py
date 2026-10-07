"""Four immutable occupied-space densities, three single-F paths, no solve.

Preparation checks actual cached source, basis, metric, labels and the exact
saved array recipe without reserving a scientific callback journal.  A live
process permits at most twelve precharged original-grid NR calls.  No ordinary
SCF, new grid/integral, optimizer, Jacobian or mapped-density recheck is allowed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
import traceback


PATHS = ('production_copy', 'production_owned', 'independent_reference')
LIVE_KIND = 'PREPARED_OCCUPIED_SPACE_SINGLE_RESPONSE_DIAGNOSTIC'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())


def shared_helpers(root):
    """Reuse only retained resource/array-output definitions, never its main."""
    spec = importlib.util.spec_from_file_location('retained_seed_worker_helpers',
        root/'scripts/diagnose-user-molecule-seed-v2-worker.py')
    if spec is None or spec.loader is None:
        raise ValueError('Retained worker helpers unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def platform_preflight(*, roots, mountinfo_text=None, ipv4_route_text=None,
                       ipv6_interfaces_text=None, euid=None, egid=None):
    """Read local Linux facts before importing any scientific library.

    Optional text/identity inputs support pure fixture tests.  The worker uses
    actual proc files and effective IDs.  Route/interface snapshots are a local
    isolation check, not network security authentication or an access attempt.
    """
    reasons, observations = [], {}
    for name, value, getter in (('euid', euid, 'geteuid'), ('egid', egid, 'getegid')):
        if value is None:
            function = getattr(os, getter, None)
            value = function() if callable(function) else None
        observations[name] = value
        if type(value) is not int or value != 10001:
            reasons.append('EFFECTIVE_'+name.upper()+'_10001_NOT_CONFIRMED')
    def text_or_proc(value, path, label):
        if value is not None:
            if not isinstance(value, str):
                reasons.append(label+'_TEXT_INVALID'); return None
            return value
        try:
            return Path(path).read_text(encoding='ascii')
        except (OSError, UnicodeError):
            reasons.append(label+'_UNAVAILABLE'); return None
    mountinfo = text_or_proc(mountinfo_text, '/proc/self/mountinfo', 'ACTUAL_MOUNTINFO')
    ipv4 = text_or_proc(ipv4_route_text, '/proc/net/route', 'IPV4_ROUTE_SNAPSHOT')
    ipv6 = text_or_proc(ipv6_interfaces_text, '/proc/net/if_inet6', 'IPV6_INTERFACE_SNAPSHOT')
    mounts, readonly = [], {}
    if mountinfo is not None:
        try:
            for line in mountinfo.splitlines():
                before, after = line.split(' - ', 1)
                fields, filesystem = before.split(), after.split()
                if len(fields) < 6 or len(filesystem) < 3:
                    raise ValueError('Incomplete mountinfo row')
                point = PurePosixPath(fields[4].replace('\\040', ' ').replace('\\134', '\\'))
                if not point.is_absolute():
                    raise ValueError('Nonabsolute mount point')
                mounts.append((point, fields[5].split(','), filesystem[0]))
        except (ValueError, IndexError):
            reasons.append('ACTUAL_MOUNTINFO_MALFORMED'); mounts = []
    if not isinstance(roots, dict) or not roots:
        reasons.append('READONLY_TARGETS_MISSING')
    else:
        for name, raw_path in roots.items():
            path = PurePosixPath(os.fspath(raw_path))
            candidates = [entry for entry in mounts if path.is_absolute() and path.is_relative_to(entry[0])]
            if not candidates:
                readonly[name] = {'path': str(path), 'read_only': None}
                reasons.append('ACTUAL_READONLY_MOUNT_UNKNOWN_'+name.upper()); continue
            longest = max(len(row[0].parts) for row in candidates)
            covering = [row for row in candidates if len(row[0].parts) == longest]
            if len({('ro' in row[1], 'rw' in row[1]) for row in covering}) != 1:
                readonly[name] = {'path': str(path), 'read_only': None}
                reasons.append('ACTUAL_READONLY_MOUNT_AMBIGUOUS_'+name.upper()); continue
            point, options, filesystem = covering[-1]
            is_readonly = 'ro' in options and 'rw' not in options
            readonly[name] = {'path': str(path), 'mount_point': str(point),
                'mount_options': options, 'filesystem': filesystem, 'read_only': is_readonly}
            if not is_readonly:
                reasons.append('ACTUAL_READONLY_MOUNT_REFUSED_'+name.upper())
    ipv4_interfaces, ipv6_interfaces = [], []
    if ipv4 is not None:
        lines = ipv4.splitlines()
        if not lines or lines[0].split()[:3] != ['Iface', 'Destination', 'Gateway']:
            reasons.append('IPV4_ROUTE_SNAPSHOT_MALFORMED')
        else:
            for line in lines[1:]:
                if not line.strip(): continue
                fields = line.split()
                if len(fields) < 11:
                    reasons.append('IPV4_ROUTE_SNAPSHOT_MALFORMED'); continue
                ipv4_interfaces.append(fields[0])
            if any(name != 'lo' for name in ipv4_interfaces):
                reasons.append('NONLOOPBACK_IPV4_ROUTE_OBSERVED')
    if ipv6 is not None:
        for line in ipv6.splitlines():
            if not line.strip(): continue
            fields = line.split()
            if len(fields) != 6:
                reasons.append('IPV6_INTERFACE_SNAPSHOT_MALFORMED'); continue
            ipv6_interfaces.append(fields[-1])
        if any(name != 'lo' for name in ipv6_interfaces):
            reasons.append('NONLOOPBACK_IPV6_INTERFACE_OBSERVED')
    return {'status': 'PASS_ACTUAL_PLATFORM_PREFLIGHT' if not reasons else 'BLOCKED_PLATFORM_PREFLIGHT',
        'observed_effective_ids': observations, 'read_only_paths': readonly,
        'ipv4_route_interfaces': ipv4_interfaces, 'ipv6_interfaces': ipv6_interfaces,
        'proc_snapshot_sha256': {'mountinfo': None if mountinfo is None else sha(mountinfo.encode('ascii')),
            'ipv4_routes': None if ipv4 is None else sha(ipv4.encode('ascii')),
            'ipv6_interfaces': None if ipv6 is None else sha(ipv6.encode('ascii'))},
        'reasons': reasons, 'new_scientific_calls': 0, 'scientific_callback_journal_created': False,
        'scope': 'LOCAL_EFFECTIVE_IDS_MOUNT_FLAGS_AND_ROUTE_SNAPSHOT_NOT_NETWORK_SECURITY_AUTHENTICATION'}


def load_saved_family(record, archive_raw):
    """Restore exact saved NPY bytes, not a replacement computed density."""
    import numpy as np
    arrays, used = {}, set()
    with np.load(io.BytesIO(archive_raw), allow_pickle=False) as archive:
        for name in archive.files:
            value = archive[name].copy()
            if value.dtype.kind != 'f' or value.dtype.str != '<f8' or not np.isfinite(value).all():
                raise ValueError('Prepared family requires finite little-endian binary64 arrays')
            value.setflags(write=False)
            arrays[name] = value
    def restore(value):
        if isinstance(value, dict) and 'npz_member' in value:
            name = value['npz_member']
            if name not in arrays or name in used:
                raise ValueError('Prepared NPY member is missing or used more than once')
            array = arrays[name]
            if (list(array.shape) != value['shape'] or array.dtype.str != value['dtype']
                    or sha(np.ascontiguousarray(array).tobytes()) != value['sha256']):
                raise ValueError('Prepared NPY bytes differ from saved member metadata')
            used.add(name)
            return array
        if isinstance(value, dict):
            return {key: restore(item) for key, item in value.items() if key != 'raw_array_archive'}
        if isinstance(value, list):
            return [restore(item) for item in value]
        return value
    family = restore(record)
    if used != set(arrays) or len(arrays) != 10:
        raise ValueError('Exactly ten registered prepared-family NPY members required')
    return family


def scientific_worker(args, output, contract, contract_sha):
    import numpy as np
    from pyscf import dft, gto, scf
    from pyscf.dft import numint
    from reference.ordinary_molecule import ReferenceResult
    from reference.residual_molecule import PreparedResidualReference
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    from runtime.user_molecule.input import strict_json
    from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
    from runtime.user_molecule.residual_bridge import PreparedResidualBridge, array_identity
    from runtime.user_molecule.residual_candidate import density_id
    from runtime.user_molecule.residual_seed_preparation import prepare_cached_context
    from runtime.user_molecule.residual_preparation import create_bridge_contract
    from runtime.user_molecule.occupied_space_response import (
        preflight_occupied_space_response, run_occupied_space_response)
    from runtime.user_molecule.occupied_space_response_contract import execution_identity, validate_seed_binding
    from runtime.user_molecule import residual_candidate, solver_candidate
    from reference import residual_candidate as reference_solver, user_molecule as reference_equations
    from reference import user_molecule_v2 as reference_equations_v2
    from ai4orgchem.qm import p09_conditional_scf as source_equations
    import scipy.optimize
    import scipy.optimize._numdiff

    helpers, started = shared_helpers(args.runtime_root), time.monotonic()
    forbidden, bindings = [], []
    def install(owner, attribute, label):
        if not hasattr(owner, attribute):
            raise ValueError('Required forbidden API unavailable: '+label)
        def refuse(*_args, **_kwargs):
            forbidden.append(label)
            raise RuntimeError('Forbidden in occupied-space single-response: '+label)
        setattr(owner, attribute, refuse)
        bindings.append((owner, attribute, refuse, label))

    original_nr, original_nuc = numint.NumInt.nr_rks, gto.Mole.energy_nuc
    for owner, attribute, label in (
        (scf.hf.SCF, 'kernel', 'SCF.kernel'), (scf.hf.SCF, 'scf', 'SCF.scf'),
        (scf.hf, 'kernel', 'hf.kernel'), (scf.hf.RHF, 'kernel', 'RHF.kernel'),
        (scf.uhf.UHF, 'kernel', 'UHF.kernel'), (scf.rohf.ROHF, 'kernel', 'ROHF.kernel'),
        (dft.rks.RKS, 'kernel', 'RKS.kernel'), (dft.uks.UKS, 'kernel', 'UKS.kernel'),
        (dft.roks.ROKS, 'kernel', 'ROKS.kernel'), (dft.gen_grid.Grids, 'build', 'Grids.build'),
        (gto.Mole, 'intor', 'Mole.intor'), (gto.Mole, 'intor_by_shell', 'Mole.intor_by_shell'),
        (numint.NumInt, 'nr_rks', 'NumInt.nr_rks outside charged instance'),
        (numint, 'nr_rks', 'numint.nr_rks outside charged instance'),
        (residual_candidate, 'solve_residual_candidate', 'production residual solve'),
        (solver_candidate, 'iterate_candidate', 'production candidate iterate'),
        (solver_candidate, 'run_candidate_conditional_rks', 'production candidate SCF driver'),
        (reference_solver, 'solve', 'reference solve'),
        (reference_equations, 'fixed_point', 'reference fixed_point'),
        (reference_equations_v2, 'fixed_point', 'reference v2 fixed_point'),
        (source_equations, 'run_p09_conditional_rks', 'frozen scientific SCF driver'),
        (scipy.optimize, 'least_squares', 'scipy least_squares'),
        (scipy.optimize._numdiff, 'approx_derivative', 'scipy numerical Jacobian'),
        (PreparedResidualBridge, 'run', 'production bridge.run'),
        (PreparedResidualReference, 'run', 'reference bridge.run')):
        install(owner, attribute, label)

    def changed_guards():
        return [label for owner, name, guard, label in bindings if getattr(owner, name) is not guard]
    def observe(phase):
        value = {'phase': phase, 'elapsed_seconds': time.monotonic()-started,
            'cgroup': collect_cgroup(phase=phase), 'vm_memory': helpers.vm_memory()}
        with (output/'resources.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(value, allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
        if helpers.resource_reasons(value['cgroup']):
            raise RuntimeError('Actual native hard limits or resource events refused')
        available = value['vm_memory']['available_bytes']
        if available is None or available < 2147483648:
            raise RuntimeError('At least 2GiB VM MemAvailable required')
        if forbidden or changed_guards():
            raise RuntimeError('Forbidden call or changed scientific guard binding')
        return value

    versions = {name: importlib.metadata.version(name) for name in contract['expected_dependencies']}
    loaded = {name: getattr(importlib.import_module(name), '__version__', None) for name in versions}
    save(output/'dependency-identity.json', {'expected': contract['expected_dependencies'],
        'actual_distributions': versions, 'loaded_module_versions': loaded})
    if versions != contract['expected_dependencies'] or loaded != contract['expected_dependencies']:
        raise ValueError('Pinned dependency mismatch before any F')
    for name, digest in contract['source_file_sha256'].items():
        if sha((args.runtime_root/name).read_bytes()) != digest:
            raise ValueError('Actual tested runtime source bytes changed: '+name)
    observe('BEFORE_PREPARATION')
    cached = prepare_cached_context(runtime_root=args.runtime_root, science_root=args.science_root,
        ordinary_dir=args.ordinary_dir, identity=contract)
    save(output/'legacy-basis-representation.json', cached['basis_receipt'])
    context = cached['context']
    install(gto.Mole, 'energy_nuc', 'Mole.energy_nuc outside charged instance')

    source_raw = (args.seed_input_dir/'SOURCE.json').read_bytes()
    source_arrays_raw = (args.seed_input_dir/'source-arrays.npz').read_bytes()
    seed_record_raw = (args.seed_input_dir/'prepared-seed-family.json').read_bytes()
    seed_arrays_raw = (args.seed_input_dir/'prepared-seed-family.npz').read_bytes()
    binding = validate_seed_binding(contract, source_raw, seed_record_raw, seed_arrays_raw,
        source_arrays_bytes=source_arrays_raw)
    save(output/'seed-byte-binding.json', binding)
    source = strict_json(source_raw)
    family = load_saved_family(strict_json(seed_record_raw), seed_arrays_raw)
    source_arrays = {}
    with np.load(io.BytesIO(source_arrays_raw), allow_pickle=False) as archive:
        if set(archive.files) != set(source['arrays']):
            raise ValueError('Source-input NPY set differs')
        for name, metadata in source['arrays'].items():
            array = archive[name].copy()
            if (list(array.shape) != metadata['shape'] or array.dtype.str != metadata['dtype']
                    or not np.isfinite(array).all() or sha(np.ascontiguousarray(array).tobytes()) != metadata['sha256']):
                raise ValueError('Actual source-input NPY bytes differ: '+name)
            array.setflags(write=False); source_arrays[name] = array
    for name, field in (('base_density', 'source_density'), ('masked_overlap', 'source_masked_overlap'),
                         ('occupied_anchor', 'source_occupied_anchor'), ('virtual_anchor', 'source_virtual_anchor')):
        if not np.array_equal(source_arrays[name], family[field]):
            raise ValueError('Source-input and prepared-family bytes differ: '+name)
    if not np.array_equal(source_arrays['physical_overlap'], cached['arrays']['overlap']):
        raise ValueError('Actual cached physical S differs from saved source-input S')

    mapping = source['source_mapping']
    if (mapping['ao_labels'] != context.metadata['ao_labels'] or
            mapping['ao_descriptors'] != context.metadata['ao_descriptors'] or
            mapping['geometry_sha256'] != cached['prepared_input']['bundle']['xyz_sha256']):
        raise ValueError('Saved source geometry/AO labels or fragment mapping differ from actual cached context')
    for index, atom, component in ((4, 0, 'z'), (9, 1, 'z'), (2, 0, 'x'), (7, 1, 'x')):
        if mapping['ao_labels'][index] != [atom, 'C', '2p', component]:
            raise ValueError('Frozen pi/sigma anchor labels differ')
    if (not np.array_equal(np.flatnonzero(source_arrays['occupied_anchor']), [4, 9]) or
            not np.array_equal(np.flatnonzero(source_arrays['virtual_anchor']), [2, 7])):
        raise ValueError('Frozen pi-sum/sigma-sum anchor supports differ')
    pi = [index for index, row in enumerate(mapping['ao_descriptors']) if row['kind'] == 'pi']
    sigma = [index for index, row in enumerate(mapping['ao_descriptors']) if row['kind'] == 'sigma']
    if pi != [4, 9] or set(pi+sigma) != set(range(14)):
        raise ValueError('This candidate is restricted to the frozen 14-AO planar ethene labels')
    u, v = family['directions']['occupied_white_direction'], family['directions']['virtual_white_direction']
    directions = {'u_sigma_norm': float(np.linalg.norm(u[sigma])), 'v_pi_norm': float(np.linalg.norm(v[pi])),
        'scope': 'NUMERICAL_PARITY_OF_THIS_SAVED_FIXTURE_NOT_GLOBAL_OPERATOR_SYMMETRY'}
    if directions['u_sigma_norm'] > 1e-10 or directions['v_pi_norm'] > 1e-10:
        raise ValueError('Saved occupied/virtual directions do not match the declared pi/sigma fixture scope')

    journal = None
    active = {'path': None, 'seed_index': None, 'angle_rad': None, 'density_id': None, 'slot_id': None, 'phase': None}
    counts = {path: {name: 0 for name in ('nr_rks_attempts', 'nr_rks_completed', 'nr_rks_failed',
        'energy_nuc_attempts', 'energy_nuc_completed', 'energy_nuc_failed')} for path in PATHS}
    slot_counts = {}
    seed_by_id = {row['density_id']: row for row in family['seeds']}
    def event(kind, detail=None):
        value = {'kind': kind, 'active': dict(active), 'elapsed_seconds': time.monotonic()-started,
            'counts': copy.deepcopy(counts), 'detail': detail}
        with (output/'native-callbacks.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(value, allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
    def pending(kind):
        if journal is None:
            raise RuntimeError('No scientific callback journal exists during preparation')
        path = active['path']; snapshot = journal.snapshot()
        rows = [row for row in snapshot['slots'] if row['slot_id'] == active['slot_id']]
        if len(rows) != 1 or path not in PATHS:
            raise RuntimeError('Native call outside an explicit precharged occupied-space slot')
        row = rows[0]; seed = seed_by_id.get(active['density_id'])
        if (row['status'] != 'PENDING' or row['path_id'] != path or row['density_id'] != active['density_id']
                or row['phase'] != active['phase'] or seed is None or
                seed['seed_index'] != active['seed_index'] or seed['angle_rad'] != active['angle_rad'] or
                density_id(seed['density']) != active['density_id']):
            raise RuntimeError('Native PENDING slot/path/angle/source-D binding differs')
        if snapshot['charged_slots'] > 12 or snapshot['path_charged_slots'][path] > 4:
            raise RuntimeError('Native twelve/four callback ceiling exceeded')
        slot = slot_counts.setdefault(row['slot_id'], {'NR_RKS': 0, 'NR_RKS_COMPLETED': 0,
            'NR_RKS_FAILED': 0, 'ENERGY_NUC': 0})
        if slot[kind] or (kind == 'ENERGY_NUC' and
                (path == 'independent_reference' or slot['NR_RKS_COMPLETED'] != 1)):
            raise RuntimeError('Additional or out-of-order native call in the same slot refused')
        return path, slot
    def counted_nr(*values, **settings):
        path, slot = pending('NR_RKS')
        native_d = settings.get('dms', values[3] if len(values) > 3 else None)
        if (len(values) < 3 or values[0] is not context.mol or values[1] is not context.mean_field.grids
                or values[2] != context.mean_field.xc or native_d is None or density_id(native_d) != active['density_id']):
            raise RuntimeError('Actual NR molecule/grid/XC/D differs from the charged source')
        if sum(row['nr_rks_attempts'] for row in counts.values()) >= 12 or counts[path]['nr_rks_attempts'] >= 4:
            raise RuntimeError('Actual NR hard ceiling exhausted')
        slot['NR_RKS'] += 1; counts[path]['nr_rks_attempts'] += 1; event('NR_RKS_ENTERED')
        try:
            value = original_nr(context.mean_field._numint, *values, **settings)
        except BaseException as error:
            slot['NR_RKS_FAILED'] += 1; counts[path]['nr_rks_failed'] += 1
            event('NR_RKS_FAILED', type(error).__name__+': '+str(error)); raise
        slot['NR_RKS_COMPLETED'] += 1; counts[path]['nr_rks_completed'] += 1
        event('NR_RKS_COMPLETED'); return value
    def counted_nuc(*values, **settings):
        path, slot = pending('ENERGY_NUC')
        slot['ENERGY_NUC'] += 1; counts[path]['energy_nuc_attempts'] += 1; event('ENERGY_NUC_ENTERED')
        try:
            value = original_nuc(context.mol, *values, **settings)
        except BaseException as error:
            counts[path]['energy_nuc_failed'] += 1; event('ENERGY_NUC_FAILED', type(error).__name__+': '+str(error)); raise
        counts[path]['energy_nuc_completed'] += 1; event('ENERGY_NUC_COMPLETED'); return value
    context.mean_field._numint.nr_rks, context.mol.energy_nuc = counted_nr, counted_nuc
    def prohibited(*_args, **_kwargs):
        forbidden.append('Prepared ordinary SCF/one-electron integral instance')
        raise RuntimeError('Ordinary SCF/one-electron integral evaluation forbidden')
    context.mean_field.get_hcore = context.mean_field.get_ovlp = prohibited
    context.mean_field.kernel = context.mean_field.scf = prohibited
    prepared = create_bridge_contract(runtime_root=args.runtime_root, science_root=args.science_root,
        prepared_input=cached['prepared_input'], context=context, arrays=cached['arrays'], ordinary_record=cached['record'],
        runtime_test_commit=contract['runtime_test_commit'], image_id=contract['image_id'],
        image_build_commit=contract['image_build_runtime_commit'], execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC',
        initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR', ordinary_record_path=cached['record_path'],
        ordinary_arrays_path=cached['arrays_path'], maximum_evaluations=4)
    save(output/'preparation-contract.json', prepared['contract']); save(output/'prepared-mapping.json', prepared['mapping_receipt'])
    if mapping['atom_mapping'] != prepared['mapping_receipt']['atom_mapping']:
        raise ValueError('Saved atom/fragments differ from the actual original XYZ mapping')
    if (mapping['profile_sha256'] != contract['profile_canonical_sha256'] or
            prepared['mapping_receipt']['profile_canonical_sha256'] != contract['profile_canonical_sha256']):
        raise ValueError('Saved canonical profile alias differs from the explicit new contract')
    engines = {
        'production_copy': PreparedResidualBridge(**prepared['bridge_kwargs'], eri_mode='COPY_MASK', optimize_eri_contractions=True),
        'production_owned': PreparedResidualBridge(**prepared['bridge_kwargs'], eri_mode='INPLACE_OWNED', optimize_eri_contractions=False),
        'independent_reference': PreparedResidualReference(
            ordinary=ReferenceResult(record=cached['record'], arrays=cached['arrays'], context=context),
            rule_path=args.science_root/'configs/qm/p09_exchange_integral_classes_v0.1.yaml',
            expected_sha256=prepared['contract']['condition_rules_sha256'], initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
            maximum_evaluations=4, execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC')}
    for path, engine in engines.items():
        if not np.array_equal(engine.overlap, source_arrays['masked_overlap']) or not np.array_equal(engine.mask, source_arrays['matrix_delete_mask']):
            raise ValueError('Actual prepared masked-S/source-mask differ from saved recipe: '+path)
    admissions = preflight_occupied_space_response(prepared_seeds=family, overlap=engines['production_copy'].overlap,
        electrons=16, matrix_delete_mask=engines['production_copy'].mask)
    ordered_ids = [row['density_id'] for row in family['seeds']]
    if list(admissions['density_ids']) != ordered_ids:
        raise ValueError('Actual regenerated recipe changes the exact ordered saved seed identities')
    helpers.pack_record(output, 'actual-seed-admissions', admissions)
    helpers.pack_record(output, 'prepared-masks', {path: {'masked_overlap': engine.overlap.copy(),
        'masked_hcore': engine.hcore.copy(), 'masked_eri': engine.masked_eri.copy(), 'matrix_mask': engine.mask.copy()}
        for path, engine in engines.items()})
    observe('PREPARED_BEFORE_F')
    if args.prepare_only:
        changed = changed_guards()
        if context.mean_field._numint.nr_rks is not counted_nr or context.mol.energy_nuc is not counted_nuc:
            changed.append('Prepared charged native wrapper')
        if (forbidden or changed or any(any(row.values()) for row in counts.values()) or
                any(engine.ledger for engine in engines.values()) or journal is not None):
            raise RuntimeError('Zero-F preparation guard/counter/journal integrity failed')
        for engine in engines.values(): engine._used = engine._settled = True
        final = observe('PREPARATION_END')
        save(output/'seed-readiness.json', {'status': 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_PREPARATION_ONLY',
            'runtime_test_commit': contract['runtime_test_commit'], 'contract_sha256': contract_sha,
            'seed_input_source_sha256': sha(source_raw), 'seed_input_record_sha256': sha(seed_record_raw),
            'seed_input_archive_sha256': sha(seed_arrays_raw), 'source_file_sha256': contract['source_file_sha256'],
            'ordered_seed_density_ids': ordered_ids, 'source_metric_matches_all_three_paths': True,
            'directions': directions, 'native_counts': counts, 'real_F_NR_SCF_grid_integral_calls': 0,
            'scientific_budget': None, 'scientific_callback_reservation_created': False,
            'guarded_operations': [row[3] for row in bindings], 'forbidden_attempts': forbidden,
            'changed_guard_bindings': changed, 'resource_end': final, 'scientific_execution': 'NOT_EXECUTED',
            'Compute': False, 'method_approval': False})
        return 0

    journal_identity = execution_identity(contract, contract_sha)
    journal = ConditionalCallbackBudget(path=output/'callbacks.json', batch_id=contract['batch_id'],
        identity=journal_identity, path_limits={path: 4 for path in PATHS}, total_limit=12)
    native_leaf = output/'source-captures'; native_leaf.mkdir()
    callbacks = {}
    for path in PATHS:
        engine = engines[path]
        def callback(density, phase, *, path=path, engine=engine):
            did = density_id(density); seed = seed_by_id.get(did)
            rows = [row for row in journal.snapshot()['slots'] if row['status'] == 'PENDING']
            if (seed is None or len(rows) != 1 or rows[0]['path_id'] != path or rows[0]['density_id'] != did
                    or rows[0]['phase'] != phase):
                raise RuntimeError('Response callback requires one exact saved/precharged seed')
            active.update(path=path, seed_index=seed['seed_index'], angle_rad=seed['angle_rad'],
                density_id=did, slot_id=rows[0]['slot_id'], phase=phase)
            try:
                if path == 'independent_reference':
                    value = engine.evaluate(density); raw = copy.deepcopy(engine.last_evaluation)
                    if density_id(raw['density']) != did:
                        raise ValueError('Independent raw evaluation belongs to another D')
                    value = dict(value, raw_fock=raw['Fraw'], coulomb_matrix=raw['J'], exchange_matrix=raw['K'],
                        xc_potential=raw['Vxc'], grid_electron_count=raw['grid_electron_count'],
                        masked_metric_electron_count=raw['masked_metric_electron_count'],
                        physical_metric_electron_count=raw['physical_metric_electron_count'],
                        electronic_energy=raw['total_energy_hartree']-raw['components_hartree']['nuclear_repulsion'])
                else:
                    value = engine.evaluate(density, phase=phase)
                helpers.pack_record(native_leaf, f'slot-{active["slot_id"]:02d}', {'requested_density': density.copy(),
                    'requested_density_id': did, 'path': path, 'seed_index': seed['seed_index'],
                    'angle_rad': seed['angle_rad'], 'phase': phase, 'value': copy.deepcopy(value),
                    'prepared_ledger_row': copy.deepcopy(engine.ledger[-1])})
                observe('AFTER_SLOT_'+str(active['slot_id'])); return value
            finally:
                active.update(path=None, seed_index=None, angle_rad=None, density_id=None, slot_id=None, phase=None)
        callbacks[path] = callback
    result = None
    try:
        result = run_occupied_space_response(prepared_seeds=family, callbacks=callbacks,
            overlap=engines['production_copy'].overlap, electrons=16, matrix_delete_mask=engines['production_copy'].mask,
            journal=journal, execution_kind=LIVE_KIND, scientific_execution_authorized=True)
    finally:
        for engine in engines.values(): engine._used = engine._settled = True
        changed = changed_guards()
        if context.mean_field._numint.nr_rks is not counted_nr or context.mol.energy_nuc is not counted_nuc:
            changed.append('Prepared charged native wrapper')
        save(output/'native-counts.json', {'counts': counts,
            'total_NR_attempts': sum(row['nr_rks_attempts'] for row in counts.values()),
            'total_NR_completed': sum(row['nr_rks_completed'] for row in counts.values()),
            'total_NR_failed': sum(row['nr_rks_failed'] for row in counts.values()),
            'per_slot_counts': slot_counts, 'native_counter_proof': 'INSTRUMENTED_WRAPPER_ENTRY_COMPLETION_FAILURE',
            'conservative_slots_are_not_native_calls': True})
        save(output/'prepared-callback-ledgers.json', {'paths': {
            path: copy.deepcopy(engine.ledger) for path, engine in engines.items()},
            'scope': 'PREPARED_EVALUATOR_ENTRY_AND_VALIDATION_NOT_NATIVE_NR_EXECUTION_COUNT'})
        save(output/'guard-status.json', {'guarded_operations': [row[3] for row in bindings],
            'forbidden_attempts': forbidden, 'changed_bindings': changed,
            'status': 'PASS' if not changed and not forbidden else 'FAIL',
            'solver_and_SCF_iterations': 0, 'new_grid_or_integral_builds': 0})
    helpers.pack_record(output, 'response-result', result)
    final, snapshot = observe('END'), journal.snapshot()
    good = (result['status'] == 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE'
        and result['failure'] is None and len(result['snapshots']) == 12 and not changed and not forbidden
        and snapshot['charged_slots'] == 12 and snapshot['pending_slots'] == snapshot['failed_slots'] == 0
        and all(row['state'] == 'CLOSED' for row in snapshot['paths'].values())
        and all(counts[path]['nr_rks_attempts'] == counts[path]['nr_rks_completed'] == 4 for path in PATHS)
        and all(counts[path]['nr_rks_failed'] == counts[path]['energy_nuc_failed'] == 0 for path in PATHS)
        and all(counts[path]['energy_nuc_attempts'] == counts[path]['energy_nuc_completed'] == 4
            for path in ('production_copy', 'production_owned'))
        and counts['independent_reference']['energy_nuc_attempts'] == counts['independent_reference']['energy_nuc_completed'] == 0)
    save(output/'response-summary.json', {'status': 'EXECUTED_OCCUPIED_SPACE_SINGLE_RESPONSE_ONLY' if good else 'FAILED_OR_REFUSED_OCCUPIED_SPACE_RESPONSE',
        'source_identity': journal_identity, 'native_counts': counts, 'charged_slots': snapshot['charged_slots'],
        'resource_end': final, 'scientific_processes': 1, 'SCF_iterations': 0, 'Compute': False,
        'full_endpoint_qualification': 'NOT_EXECUTED', 'UM_P12_UM_P13_T06': 'NOT_EXECUTED',
        'research_delta_hartree': None, 'production_activation': False, 'method_approval': False, 'automatic_retry': False})
    return 0 if good else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=Path('/execution-contract.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('/output'))
    parser.add_argument('--ordinary-dir', type=Path, default=Path('/saved-ordinary'))
    parser.add_argument('--seed-input-dir', type=Path, default=Path('/seed-input'))
    parser.add_argument('--runtime-root', type=Path, default=Path('/workspace'))
    parser.add_argument('--science-root', type=Path, default=Path('/opt/ai4orgchem'))
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(); args.runtime_root = args.runtime_root.resolve(); args.science_root = args.science_root.resolve()
    sys.path[:0] = [str(args.runtime_root), str(args.science_root/'software/src')]
    from runtime.user_molecule.occupied_space_response_contract import load_execution_contract
    contract = load_execution_contract(args.contract)
    if not args.prepare_only and contract['scientific_execution_authorized'] is not True:
        raise ValueError('This contract grants no scientific execution')
    for key, name in (('runtime_test_commit', 'AI4ORGCHEM_RUNTIME_TEST_COMMIT'),
                     ('image_id', 'AI4ORGCHEM_IMAGE_ID'), ('image_build_runtime_commit', 'AI4ORGCHEM_IMAGE_BUILD_COMMIT')):
        if contract[key] != os.environ.get(name):
            raise ValueError('Actual execution environment identity differs: '+key)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()): raise ValueError('Fresh output leaf required; no retry or overwrite')
    raw_contract = args.contract.read_bytes(); contract_sha = sha(raw_contract)
    save(output/'WORKER_STARTED.json', {'pid': os.getpid(), 'contract_sha256': contract_sha,
        'runtime_test_commit': contract['runtime_test_commit'], 'mode': contract['execution_kind'],
        'prepare_only': args.prepare_only, 'authorization': contract['authorization_basis'], 'production_activation': False})
    try:
        platform = platform_preflight(roots={'root_filesystem': '/', 'runtime_source': args.runtime_root,
            'science_source': args.science_root, 'ordinary_cache': args.ordinary_dir.resolve(),
            'seed_input': args.seed_input_dir.resolve(), 'execution_contract': args.contract.resolve()})
        save(output/'platform-preflight.json', platform)
        if platform['status'] != 'PASS_ACTUAL_PLATFORM_PREFLIGHT':
            save(output/'response-summary.json', {'status': 'BLOCKED_PLATFORM_PREFLIGHT',
                'scientific_execution': 'NOT_EXECUTED_DUE_TO_PLATFORM_PREFLIGHT',
                'reasons': platform['reasons'], 'new_real_F_NR_calls': 0, 'Compute': False,
                'scientific_callback_reservation_created': False, 'automatic_retry': False})
            return 20
        return scientific_worker(args, output, contract, contract_sha)
    except BaseException as error:
        save(output/'worker-fatal-error.json', {'status': 'FATAL_NOT_QUALIFIED', 'type': type(error).__name__,
            'message': str(error), 'traceback': traceback.format_exc(), 'Compute': False, 'automatic_retry': False})
        traceback.print_exc(); return 2


if __name__ == '__main__':
    raise SystemExit(main())
