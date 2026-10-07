"""Read current local capability declarations; never grant computation rights."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load_capabilities(path):
    record=json.loads(Path(path).read_bytes())
    if (record.get('schema_version')!='local-runtime-capabilities-v1'
            or record.get('compute_enabled') is not False
            or record.get('declaration_grants_execution_authorization') is not False):
        raise ValueError('Current declaration cannot authorize user Compute')
    rows=record.get('capabilities')
    if not isinstance(rows,list) or not rows:
        raise ValueError('Nonempty capability declarations required')
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or any(not isinstance(row.get(key),str) or not row[key].strip()
                for key in ('id','name','status','scope')) or row['id'] in seen):
            raise ValueError('Invalid or duplicated capability declaration')
        seen.add(row['id'])
    return record


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    record=load_capabilities(ROOT/'validation/local-runtime-capabilities-v1.json')
    if args.json:print(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    else:
        print('AI4OrgChem Runtime：本地工程候选 / Local engineering candidate')
        print('该声明只介绍能力；来源与科学资格由实际运行记录分别核验。')
        for row in record['capabilities']:
            print(f"{row['name']}: {row['status']} — {row['scope']}")
        print('入口 / Entry: start-local-runtime.ps1 -Action List|Show|Review|Check|Report')
        print('登记P14计算 / Registered P14: start-runtime.ps1; fixed protocol only')
    return 0


if __name__=='__main__':raise SystemExit(main())
