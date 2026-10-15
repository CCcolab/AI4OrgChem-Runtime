"""Review a saved NPZ without scientific calls or modification of old results.

Exit 0: saved arrays meet the extra policy. Exit 2: rejected/not executed.
Neither exit value certifies wavefunction stability or a complete Runtime run.
"""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--npz',type=Path,required=True)
    parser.add_argument('--electron-count',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New directory; existing directories are refused')
    args=parser.parse_args(argv)
    try:args.output.mkdir(parents=True,exist_ok=False)
    except OSError as exc:
        print('OUTPUT_REFUSED: '+str(exc),file=sys.stderr);return 2
    def refuse(name,*_):
        if name.split('.')[0] in ('pyscf','ai4orgchem'):raise ImportError('Saved-array review forbids '+name)
    class NoBackend:
        def find_spec(self,fullname,path=None,target=None):refuse(fullname)
    guard=NoBackend();sys.meta_path.insert(0,guard)
    try:
        import numpy as np
        from review_tools.canonical_orbitals import review_arrays
        if args.npz.is_symlink() or args.npz.stat().st_size>32*1024*1024:
            raise ValueError('Saved NPZ must be a bounded regular file')
        raw=args.npz.read_bytes()
        with zipfile.ZipFile(args.npz) as z:
            if sum(i.file_size for i in z.infolist())>64*1024*1024:
                raise ValueError('Expanded NPZ exceeds review limit')
        with np.load(args.npz,allow_pickle=False) as saved:
            wanted=('overlap','canonical_coefficients','orbital_energies_hartree','occupations','fock','density')
            arrays={k:saved[k] for k in wanted if k in saved}
        report=review_arrays(arrays,electron_count=args.electron_count)
        report['input_npz_sha256']=hashlib.sha256(raw).hexdigest()
        report['review_tool_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        code=0 if report['full_orbital_qualification']['qualified'] else 2
    except Exception as exc:
        report={'schema':'canonical-mo-array-review-v1','full_orbital_qualification':{'status':'REJECTED_OR_UNREADABLE','qualified':False},'error':type(exc).__name__+': '+str(exc),'scientific_backend_calls':0,'wavefunction_stability':{'status':'NOT_EXECUTED','qualified':False}}
        code=2
    finally:sys.meta_path.remove(guard)
    (args.output/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['full_orbital_qualification']['status'],'scientific_backend_calls':0}))
    return code


if __name__=='__main__':raise SystemExit(main())
