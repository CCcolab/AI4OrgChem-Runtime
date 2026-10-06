"""Host-side read-only reports; uses only Python's standard library."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.user_molecule.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
