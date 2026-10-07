"""Standard-library local proposition navigation; no scientific execution."""
import argparse
import json
import sys
from .core import CatalogError, list_propositions, show_proposition, review_proposition, _summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    children = parser.add_subparsers(dest='action', required=True)
    listing = children.add_parser('list')
    listing.add_argument('--json', action='store_true', dest='as_json')
    for action in ('show', 'review'):
        child = children.add_parser(action)
        child.add_argument('proposition_id')
        child.add_argument('--source-dir', help='Explicit offline source/cache directory; never guessed/downloaded')
        child.add_argument('--json', action='store_true', dest='as_json')
        if action == 'review':
            child.add_argument('--output-dir', required=True, help='Fresh directory outside source/runtime')
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        if args.action == 'list':
            result = list_propositions()
            text = '\n'.join(case['id'] + '  ' + case['title'] for case in result['cases'])
            code = 0
        elif args.action == 'show':
            result = show_proposition(args.proposition_id, source_dir=args.source_dir)
            text, code = _summary(result), result['exit_code']
        else:
            result = review_proposition(args.proposition_id, source_dir=args.source_dir, output_dir=args.output_dir)
            text, code = _summary(result), result['exit_code']
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) if args.as_json else text)
        return code
    except (CatalogError, OSError, KeyError, TypeError, ValueError) as error:
        result = {'status': 'REFUSED', 'exit_code': 40, 'error': str(error),
                  'scientific_validation': 'NOT_EXECUTED', 'runtime_task_execution': 'NOT_EXECUTED'}
        print(json.dumps(result, ensure_ascii=False) if args.as_json else '读取被拒绝：' + str(error), file=sys.stderr)
        return 40


if __name__ == '__main__':
    raise SystemExit(main())
