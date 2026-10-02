"""Create a small verified summary; keep raw outputs outside Git."""
import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.cli import digest, load, save

parser = argparse.ArgumentParser()
parser.add_argument('run_root', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
rows = []
for manifest_path in sorted(args.run_root.glob('*/run-manifest.json')):
    manifest = load(manifest_path)
    for name, expected in manifest.get('output_sha256', {}).items():
        output = (manifest_path.parent / name).resolve()
        if not output.is_relative_to(manifest_path.parent.resolve()) or digest(output) != expected:
            raise ValueError('summary refused: output hash/path mismatch')
    row = {key: manifest.get(key, 'UNKNOWN') for key in (
        'run_id','task','status','source_commit','runtime_commit','runtime_code_sha256',
        'process_exit_code','runtime_exit_code','numerical_qualification','scientific_comparison',
        'wall_time_seconds','threads','source_readonly','resource_peak','image_digest','image_id')}
    row['manifest_sha256'] = digest(manifest_path)
    if 'error' in manifest:
        row['error'] = manifest['error']
    if manifest['task'] == 'p14-smoke' and (manifest_path.parent / 'result.json').exists():
        result = load(manifest_path.parent / 'result.json')
        frozen = load(root / '.build/source/evidence/P01-P14/P14/processed/p14_benzotricyclobutadiene_fixed_geometry_smoke_v0.1.json')
        row.update(technical_endpoint_kcal_mol=result['technical_endpoint_kcal_mol'],
                   frozen_technical_endpoint_kcal_mol=frozen['technical_endpoint_kcal_mol'],
                   absolute_technical_residual_kcal_mol=abs(result['technical_endpoint_kcal_mol']-frozen['technical_endpoint_kcal_mol']))
    if manifest['task'] == 'p14-equivalence' and (manifest_path.parent / 'result.json').exists():
        row['differences'] = load(manifest_path.parent / 'result.json')['differences']
    rows.append(row)
summary = {'date':'2026-10-02','scope':'independent WSL2 candidate, not OCI/WSLc acceptance',
           'raw_logs_relative_location':'../ai4orgchem-runtime-runs/20261002-wsl2',
           'oci_build':'BLOCKED','oci_tests':'NOT_EXECUTED','wslc_acceptance':'BLOCKED','wslc_tests':'NOT_EXECUTED',
           'p14_fixed':'NOT_EXECUTED','p14_optimize':'NOT_EXECUTED','new_four_input_classification':'NOT_EXECUTED',
           'runs':rows}
save(root / 'validation/summary.json', summary)
print(json.dumps({'summarized_runs':len(rows),'all_listed_output_hashes_verified':True}))
