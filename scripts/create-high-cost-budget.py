"""Create one new explicit state-budget; never resets an existing ledger."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import units,unit,digest,SOURCE_LOCK,DEPENDENCY_LOCK,PROFILE
from runtime.high_cost_cases.budget import new_budget
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--unit',action='append',required=True);p.add_argument('--ceiling-seconds',type=int,required=True);a=p.parse_args()
    for identifier in a.unit:unit(identifier)
    v=new_budget(a.output,a.unit,digest(PROFILE),digest(SOURCE_LOCK),digest(DEPENDENCY_LOCK),a.ceiling_seconds)
    print(json.dumps(v,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
