"""Guarded V2 seed readiness on the existing full cache; zero true F calls."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path('/workspace')
sys.path[:0] = [str(ROOT), '/opt/ai4orgchem/software/src']


def main():
    import numpy as np
    from pyscf import gto, scf
    from pyscf.dft import gen_grid, numint
    forbidden = {'SCF': 0, 'GRID': 0, 'INTEGRAL': 0, 'NR_RKS': 0}
    def guard(key):
        def refuse(*args, **kwargs):
            forbidden[key] += 1
            raise AssertionError('Seed readiness forbids '+key)
        return refuse
    scf.hf.SCF.kernel = scf.hf.SCF.scf = scf.hf.kernel = guard('SCF')
    gen_grid.Grids.build = guard('GRID')
    gto.Mole.intor = gto.Mole.intor_by_shell = guard('INTEGRAL')
    numint.NumInt.nr_rks = numint.nr_rks = guard('NR_RKS')
    from reference.ordinary_molecule import ReferenceResult
    from reference.residual_seed_v2 import PreparedResidualSeedReferenceV2
    from runtime.user_molecule.residual_seed_v2 import PreparedResidualSeedBridgeV2
    from runtime.user_molecule.residual_bridge import array_identity
    from runtime.user_molecule.residual_seed_preparation import prepare_cached_context, create_seed_bridge_preparation
    from runtime.user_molecule.seed_v2 import POLICY_ID
    proposal = json.loads((ROOT/'validation/user-molecule/residual-diagnostic/contract-v1.json').read_bytes())
    identity = dict(proposal, profile_sha256=hashlib.sha256((ROOT/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json').read_bytes()).hexdigest(),
        source_manifest_sha256=hashlib.sha256((ROOT/'locks/source-user-molecule-files.sha256.json').read_bytes()).hexdigest())
    cached = prepare_cached_context(runtime_root=ROOT, science_root=Path('/opt/ai4orgchem'), ordinary_dir=Path('/saved-ordinary'), identity=identity)
    def no_metadata_energy(*args, **kwargs):
        raise AssertionError('No nuclear evaluation during readiness')
    cached['context'].mol.energy_nuc = no_metadata_energy
    prepared = create_seed_bridge_preparation(runtime_root=ROOT, science_root=Path('/opt/ai4orgchem'), cached=cached,
        runtime_test_commit=os.environ['AI4ORGCHEM_RUNTIME_TEST_COMMIT'], image_id=os.environ['AI4ORGCHEM_IMAGE_ID'],
        image_build_commit=os.environ['AI4ORGCHEM_IMAGE_BUILD_COMMIT'], execution_kind='ENGINEERING_FAKE')
    copy_engine = PreparedResidualSeedBridgeV2(**prepared['bridge_kwargs'], eri_mode='COPY_MASK', optimize_eri_contractions=True)
    shared = copy_engine.seed_density.copy()
    owned_engine = PreparedResidualSeedBridgeV2(**prepared['bridge_kwargs'], eri_mode='INPLACE_OWNED', optimize_eri_contractions=False)
    ref_engine = PreparedResidualSeedReferenceV2(ordinary=ReferenceResult(cached['record'], cached['arrays'], cached['context']),
        rule_path=Path('/opt/ai4orgchem/configs/qm/p09_exchange_integral_classes_v0.1.yaml'),
        expected_sha256=cached['lock']['condition_rules_sha256'], shared_seed_density=shared)
    denominator = max(float(np.linalg.norm(shared)), 1.)
    reference_difference = float(np.linalg.norm(ref_engine.reference_seed_density-shared))/denominator
    engines = {'production_copy': copy_engine, 'production_owned': owned_engine, 'independent_reference': ref_engine}
    same = len({array_identity(engine.seed_density)['sha256'] for engine in engines.values()}) == 1
    if not same or reference_difference > 1e-10 or any(forbidden.values()) or any(engine.ledger for engine in engines.values()):
        raise ValueError('Seed equivalence/readiness/zero-F guard failed')
    source_paths = ('runtime/user_molecule/seed_v2.py', 'reference/seed_v2.py',
                    'runtime/user_molecule/residual_seed_v2.py', 'reference/residual_seed_v2.py',
                    'runtime/user_molecule/residual_seed_preparation.py')
    result = {'schema_version': 'seed-v2-cached-readiness-v1', 'status': 'PASS_SEED_V2_CACHED_PREPARATION_ONLY',
        'runtime_test_commit': os.environ['AI4ORGCHEM_RUNTIME_TEST_COMMIT'], 'policy': POLICY_ID,
        'ordinary_D0_identity': array_identity(cached['arrays']['density']),
        'ordinary_mo_coefficients_identity': array_identity(cached['arrays']['mo_coefficients']),
        'ordinary_mo_occupations_identity': array_identity(cached['arrays']['mo_occupations']),
        'seed_density_identity': array_identity(shared), 'three_used_seeds_byte_identical': same,
        'reference_constructed_seed_identity': array_identity(ref_engine.reference_seed_density),
        'reference_constructed_to_common_seed_relative_frobenius': reference_difference,
        'reference_difference_threshold': 1e-10, 'reference_difference_denominator': 'max(||commonseed||F,1)',
        'source_file_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
        'receipts': {name: engine.seed_receipt for name, engine in engines.items()},
        'forbidden_operation_counts': forbidden, 'new_functional_calls': 0,
        'scientific_execution': 'NOT_EXECUTED', 'production_activation': False,
        'initial_gap_qualification': 'NOT_APPLICABLE_TO_SEED; FIRST_F_GAP_DIAGNOSTIC_ONLY',
        'final_gap_minimum_hartree': 1e-6, 'final_endpoint_gates': 'UNCHANGED_NOT_EXECUTED',
        'research_acceptance': 'NOT_ACCEPTED', 'deltas': None,
        'common_seed_scope': 'PRODUCTION_CANONICAL_BYTES_AFTER_INDEPENDENT_SEED_EQUIVALENCE_AND_ENTRY_CHECKS',
        'basis_representation_receipt': cached['basis_receipt']}
    output = Path('/output'); output.mkdir(exist_ok=True)
    with (output/'seed-readiness.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    with (output/'shared-seed.npz').open('xb') as stream:
        np.savez_compressed(stream, density=shared)
    print(json.dumps({'status': result['status'], 'new_functional_calls': 0, 'reference_seed_relative_error': reference_difference}), flush=True)


if __name__ == '__main__':
    main()
