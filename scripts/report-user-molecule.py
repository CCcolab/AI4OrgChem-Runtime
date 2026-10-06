"""Host-side read-only reports; uses only Python's standard library."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.user_molecule.__main__ import main

if __name__ == '__main__':
    if sys.argv[1:] in (['-h'], ['--help']):
        sys.argv.insert(1, 'report')
    elif not sys.argv[1:] or sys.argv[1] != 'report':
        print('This read-only host entry accepts report only; no Check or Compute was started.', file=sys.stderr)
        raise SystemExit(40)
    raise SystemExit(main())
