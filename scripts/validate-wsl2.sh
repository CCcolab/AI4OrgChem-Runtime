#!/bin/bash
# Uses only a new candidate venv and verified build source, never sibling science.
set -eu
[ -d "$(dirname -- "${BASH_SOURCE[0]}")/../tests" ] || { printf "%s\n" "LOCAL_TEST_SUITE_REQUIRED: tests are local-only" >&2; exit 2; }
runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python=${1:?pass absolute candidate Python path}
output=${2:?pass absolute persistent output root}
source=${3:?pass absolute verified extracted source root}
locks=${4:?pass the shared host lock directory}
cd "$runtime_root"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
"$python" -m pip check
"$python" -m unittest discover -s tests -v
for task in evidence core-tests p14-smoke; do
    "$python" -m runtime.cli run "$task" --source "$source" --output-root "$output" --lock-root "$locks"
done
