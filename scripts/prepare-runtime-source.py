#!/usr/bin/env python3
"""Prepare/verify runtime-only source snapshots without building or installing."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.distribution import export_source_zip, prepare_runtime_source, verify_prepared_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export", help="Export a clean Git checkout to a new project source ZIP")
    export.add_argument("--source", required=True); export.add_argument("--output", required=True)
    prepare = sub.add_parser("prepare", help="Prepare a new runtime source directory from Git or a project ZIP")
    prepare.add_argument("--source", required=True); prepare.add_argument("--target", required=True)
    verify = sub.add_parser("verify", help="Verify an existing prepared directory; no repairs")
    verify.add_argument("--source", required=True)
    for item in (prepare, verify):
        item.add_argument("--expected-commit"); item.add_argument("--expected-manifest-sha256")
    args = parser.parse_args()
    try:
        if args.action == "export":
            result = export_source_zip(args.source, args.output)
        else:
            kwargs = {"expected_commit": args.expected_commit,
                      "expected_manifest_sha256": args.expected_manifest_sha256}
            result = (prepare_runtime_source(args.source, args.target, **kwargs) if args.action == "prepare"
                      else verify_prepared_source(args.source, **kwargs))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "SOURCE_PREPARATION_REFUSED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
