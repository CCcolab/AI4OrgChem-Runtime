#!/bin/bash
# One controlled local verification; no global configuration or environment edits.
set -eu
[ -d "$(dirname -- "${BASH_SOURCE[0]}")/../tests" ] || { printf "%s\n" "LOCAL_TEST_SUITE_REQUIRED: tests are local-only" >&2; exit 2; }
runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$runtime_root"
python=${1:?absolute independent candidate Python}
archive=${2:?absolute locked archive}
output=${3:?absolute persistent output root}
lock_root=${4:?absolute shared host lock root}
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
"$python" - <<'PY'
from pathlib import Path
import json
source=Path('/tmp/ai4orgchem-runtime-source-28511f3-20261002')
expected=set(json.loads(Path('locks/source-files.sha256.json').read_text()))
actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
print(json.dumps({'old_source_exists':source.exists(),'missing_count':len(expected-actual),
                  'extra_files':sorted(actual-expected)[:12]}))
PY
# Ext4 under a new dedicated directory survives distribution restarts.
# No prior directories are removed, overwritten or recursively cleaned.
validation_root=$(mktemp -d "$HOME/ai4orgchem-runtime-validation-XXXXXXXX")
source_root="$validation_root/source"
"$python" scripts/fetch-source.py "$source_root" --archive "$archive"
chmod -R a-w "$source_root"
"$python" -m pip check
"$python" -m unittest discover -s tests -v
sh -n container/entrypoint.sh
bash -n scripts/validate-wsl2.sh
"$python" -m runtime.cli run p14-equivalence --source "$source_root" --output-root "$output" --lock-root "$lock_root"
printf 'Retained read-only source: %s\n' "$source_root"
