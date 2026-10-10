"""Add project-specific license/source materials to a completed local backup."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def make_archive(target, roots):
    records = []
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as archive:
        for prefix, root in roots:
            if not root.is_dir():
                raise RuntimeError('Required material directory absent: ' + str(root))
            for path in sorted(root.rglob('*')):
                if path.is_file() and not path.is_symlink():
                    name = prefix + '/' + path.relative_to(root).as_posix()
                    archive.write(path, name)
                    records.append({'path': name, 'sha256': digest(path), 'bytes': path.stat().st_size})
        archive.writestr('material-files.sha256.json', json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    with zipfile.ZipFile(target) as archive:
        for record in records:
            with archive.open(record['path']) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                    raise RuntimeError('Material archive mismatch: ' + record['path'])
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    destination = args.directory.resolve()
    repo = Path(__file__).resolve().parents[1]
    delivery = repo.parent / 'ai4orgchem-runtime-deliveries'
    backup = json.loads((destination/'backup-manifest.json').read_text(encoding='utf-8-sig'))
    for name in ['source-materials.zip', 'third-party-materials-supplement.zip', 'package-manifest.json']:
        if (destination/name).exists():
            raise RuntimeError('Refusing to replace existing candidate material: ' + name)
    source_count = make_archive(destination/'source-materials.zip', [
        ('corresponding-sources', delivery/'20261003-corresponding-sources'),
        ('native-source-candidates', delivery/'20261003-native-source-candidates'),
        ('upstream-license-and-source-candidates', delivery/'20261003-license-materials/upstream')])
    notice_count = make_archive(destination/'third-party-materials-supplement.zip', [
        ('original-image-notices', delivery/'20261003-license-materials/image-notices'),
        ('vendor-notice-supplement-and-mapping', delivery/'20261003-vendor-mapping')])
    readme = (repo/'docs/PUBLICATION_BOUNDARIES_zh-CN.md').read_text(encoding='utf-8')
    (destination/'CANDIDATE_README_zh-CN.md').write_text(readme, encoding='utf-8')
    files = [{'path':p.name,'bytes':p.stat().st_size,'sha256':digest(p)}
             for p in sorted(destination.iterdir()) if p.is_file()]
    record = {'schema_version':1,'kind':'Local candidate and same-disk backup; not a Release',
              'runtime_source_commit':backup['runtime_repository_commit'],
              'image_id':backup['image_id'],'image_runtime_commit':backup['image_runtime_commit'],
              'source_material_files':source_count,'notice_and_mapping_files':notice_count,
              'files':files,'public_source':'NOT_PUBLISHED','public_image':'BLOCKED',
              'CI_execution':'NOT_EXECUTED',
              'L4_resume_supported':False,'scientific_runs_repeated':False,
              'restore_execution':'NOT_EXECUTED','independent_storage_copy':'NOT_EXECUTED',
              'open_items':'runtime-source.zip: docs/PUBLICATION_BOUNDARIES_zh-CN.md and validation/source-materials-final-review.public.json'}
    (destination/'package-manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (destination/'package-manifest.sha256.txt').write_text(digest(destination/'package-manifest.json')+'  package-manifest.json\n', encoding='utf-8')
    for file in files:
        if digest(destination/file['path']) != file['sha256']:
            raise RuntimeError('Package mismatch: '+file['path'])
    process = subprocess.run(['git','bundle','verify',str(destination/'runtime-history.bundle')], cwd=repo,
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
    (destination/'package-bundle-verify.log').write_text(process.stdout+process.stderr, encoding='utf-8')
    if process.returncode:
        raise RuntimeError('Git bundle verification failed')
    result = {'status':'PASS','package_files_verified':len(files), 'source_material_files':source_count,
              'notice_and_mapping_files':notice_count,'git_bundle':'PASS','archive_material_hashes':'PASS',
              'source_commit':record['runtime_source_commit'],'image_id':record['image_id'],
              'scope':'Content integrity only; no reload, restoration, scientific computation or release'}
    (destination/'package-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
