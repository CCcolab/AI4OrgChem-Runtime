"""Read-only assembly of current matching completed high-cost state records."""
from pathlib import Path
import argparse,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import read_json,save,digest
from runtime.high_cost_cases.assembly import assemble
spec=importlib.util.spec_from_file_location('_high_cost_host',ROOT/'scripts/run-high-cost-case.py');host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
def main():
    p=argparse.ArgumentParser();p.add_argument('--task',choices=['P11','P12'],required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=host.validate_directory(a.output)
    if output.exists():raise ValueError('Fresh external assembly directory required')
    rows={};dirs={};identities={}
    for identifier,name in read_json(a.inputs).items():
        root=host.validate_directory(Path(name));receipt=read_json(root/'worker-receipt.json');execution=read_json(root.parent/'host-execution.json')
        if execution.get('status')!='PASS_SCOPED_HIGH_COST_LIVE' or execution.get('container_removed') is not True or receipt.get('unit')!=identifier or receipt.get('mode')!='live':raise ValueError('Only completed new matching optimisations may be assembled')
        host.verify_outputs(root,receipt['contract']);rows[identifier]=read_json(root/'result.json');dirs[identifier]=root
        identities[identifier]={'result_sha256':digest(root/'result.json'),'worker_receipt_sha256':digest(root/'worker-receipt.json'),'host_receipt_sha256':digest(root.parent/'host-execution.json')}
    result=assemble(a.task,rows,output_dirs=dirs)
    output.mkdir();save(output/'assembly-result.json',result);save(output/'assembly-inputs.json',identities)
    save(output/'run-manifest.json',{'schema':'high-cost-assembly-output-v1','files':{f.name:digest(f) for f in output.iterdir() if f.is_file()},'read_only_inputs':True,'no_new_scf':True})
    print(json.dumps({'status':result.get('status'),'records':str(output)},ensure_ascii=False));return 0 if result.get('status')=='PASS' else 20
if __name__=='__main__':raise SystemExit(main())
