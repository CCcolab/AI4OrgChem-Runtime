"""Read current scoped services or an explicit historical capability snapshot."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'configs/runtime-capabilities-v2.json'
STATUS_LABELS={
    'AVAILABLE_SCOPED_LOCAL_RHF':'可用：受限本地RHF服务',
    'AVAILABLE_FIXED_CASE':'可用：登记固定示例',
    'AVAILABLE_FIXED_PROTOCOL':'可用：登记专题协议',
    'PARTIAL_SINGLE_STATE_ACCEPTANCE':'部分验收：只有一态完成',
    'HISTORICAL_LOCAL_DOCKER_ACCEPTANCE':'已有历史本地Docker验收',
    'BLOCKED':'当前未开放：无合格条件端点',
    'EXECUTED_INCOMPLETE_NO_FORMAL_ENDPOINT':'已执行研究诊断：未得到正式端点',
}


def load_capabilities(path):
    record=json.loads(Path(path).read_bytes())
    version=record.get('schema_version')
    if version not in ('local-runtime-capabilities-v1','runtime-capabilities-v2'):
        raise ValueError('Unsupported capability schema')
    if record.get('declaration_grants_execution_authorization') is not False:
        raise ValueError('A capability declaration cannot grant execution authorization')
    if version=='local-runtime-capabilities-v1' and record.get('compute_enabled') is not False:
        raise ValueError('Historical conditional Compute declaration differs')
    if version=='runtime-capabilities-v2' and 'compute_enabled' in record:
        raise ValueError('Current services require per-service execution scope')
    rows=record.get('capabilities')
    if not isinstance(rows,list) or not rows:
        raise ValueError('Nonempty capability declarations required')
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or any(not isinstance(row.get(key),str) or not row[key].strip()
                for key in ('id','name','status','scope')) or row['id'] in seen):
            raise ValueError('Invalid or duplicated capability declaration')
        seen.add(row['id'])
        if version=='runtime-capabilities-v2':
            if (not isinstance(row.get('execution_enabled'),bool)
                    or not isinstance(row.get('execution_enabled_scope'),str)
                    or any(not isinstance(row.get(key),dict) for key in ('input','source','build','image','qualification'))
                    or any(not isinstance(row.get(key),str) or not row[key].strip() for key in ('profile','protocol'))
                    or any(not isinstance(row.get(key),list) for key in ('accepted_runs','evidence'))
                    or any(not isinstance(row['qualification'].get(key),str) or not row['qualification'][key].strip()
                           for key in ('engineering','numerical','science'))):
                raise ValueError('Incomplete current service identity or qualification')
            if row['status']=='BLOCKED' and row['execution_enabled']:
                raise ValueError('Blocked service cannot be declared enabled')
            if row['id']=='user-compute' and (row['status']!='BLOCKED' or row['execution_enabled']):
                raise ValueError('Legacy conditional Compute remains blocked')
            for evidence in row['evidence']:
                if not isinstance(evidence,dict) or not isinstance(evidence.get('path'),str) or not evidence['path']:
                    raise ValueError('Evidence reference required')
    return record


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--historical',action='store_true',help='Read an explicitly supplied local historical v1 snapshot')
    parser.add_argument('--historical-file',type=Path,help='Local archive JSON path; required together with --historical')
    args=parser.parse_args(argv)
    if args.historical and args.historical_file is None:
        parser.error('LOCAL_ARCHIVE_ONLY: --historical requires an explicit --historical-file local archive path')
    if args.historical_file is not None and not args.historical:
        parser.error('LOCAL_ARCHIVE_ONLY: --historical-file requires --historical')
    try:
        record=load_capabilities(args.historical_file if args.historical else CURRENT)
    except (OSError,ValueError) as exc:
        parser.error(str(exc))
    if args.historical and record['schema_version']!='local-runtime-capabilities-v1':
        parser.error('LOCAL_ARCHIVE_ONLY: historical mode requires the original local v1 schema, not a public projection')
    if args.json:print(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    else:
        print('AI4OrgChem Runtime：历史能力快照' if args.historical else 'AI4OrgChem Runtime：当前计算与复核服务')
        print('能力表不是执行授权；运行仍须核对当前安装、输入、来源、资源与预算。')
        if not args.historical:
            print(f"源码：{record['publication']['source']['url']}")
            print(f"静态指南：{record['publication']['guide']['url']}")
            print(f"GitHub Actions：已记录提交 {record['ci']['commit'][:8]} 的 {record['ci']['successful_jobs']} 个既有 job 成功；范围：{record['ci']['scope']}")
        for row in record['capabilities']:
            status=row['status'] if args.historical else STATUS_LABELS.get(row['status'],row['status'])
            print(f"{row['name']}: {status}")
            if args.historical:print(f"  {row['scope']}")
        print('当前专业矩阵 / Service matrix: docs/CURRENT_PROFESSIONAL_SERVICES_zh-CN.md')
        print('源码安装 / Source installation: docs/SOURCE_INSTALLATION_zh-CN.md')
    return 0


if __name__=='__main__':raise SystemExit(main())
