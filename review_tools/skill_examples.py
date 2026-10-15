"""Small reproducible examples of selected instruction checks, not an Agent.

Only saved/synthetic arrays, fixed public input and RDKit graph parsing are used.
These examples neither implement every Skill instruction nor qualify a molecule.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def array(value):
    raw = np.asarray(value)
    require(raw.dtype.kind in 'fciu' and np.isfinite(raw).all(), 'finite numeric array required')
    return raw.astype(complex if np.iscomplexobj(raw) else float)


def metric(value):
    s = array(value)
    require(s.ndim == 2 and s.shape[0] == s.shape[1], 'square metric required')
    require(np.linalg.norm(s-s.conj().T) <= 1e-12, 'Hermitian metric required')
    require(np.linalg.eigvalsh(s).min() > 1e-10, 'positive metric required')
    return s


def evaluate(name, data):
    if name == 'rhf-single-point':
        from runtime.molecular_service.input import parse_request, strict_json
        import tempfile
        request = strict_json((ROOT/'examples/molecular-service/water/request.json').read_bytes())
        request.update(data.get('changes', {}))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            xyz = (ROOT/'examples/molecular-service/water/molecule.xyz').read_bytes()
            (p/'molecule.xyz').write_bytes(xyz)
            (p/'request.json').write_text(json.dumps(request), encoding='utf-8')
            parsed = parse_request(p/'request.json')
        require(parsed['scientific_execution_performed'] is False, 'input-only path required')
        return {'electrons': parsed['electron_count'], 'scf_calls': 0}
    if name == 'table-fitting-residuals':
        x, y = array(data['x']), array(data['y'])
        require(x.ndim == y.ndim == 1 and len(x) == len(y) >= 3, 'paired samples required')
        design = np.column_stack((np.ones(len(x)), x))
        require(np.linalg.matrix_rank(design) == 2, 'rank-deficient fit')
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        return {'coefficients': beta.tolist(), 'rss': float(np.linalg.norm(y-design@beta)**2)}
    if name == 'orbital-localization-density':
        c, u, occ = array(data['C']), array(data['U']), array(data['occupations'])
        require(np.linalg.norm(u.conj().T@u-np.eye(len(occ))) < 1e-12, 'unitary rotation required')
        require(np.linalg.norm(u@np.diag(occ)@u.conj().T-np.diag(occ)) < 1e-12, 'rotation mixes unequal occupations')
        d = (c*occ)@c.conj().T
        rotated = c@u
        return {'density_residual': float(np.linalg.norm(d-(rotated*occ)@rotated.conj().T))}
    if name == 'molecular-graph-energy-ledger':
        from rdkit import Chem
        mol = Chem.MolFromSmiles(data['smiles'])
        query = Chem.MolFromSmarts(data['query'])
        require(mol is not None and query is not None, 'invalid graph input')
        require(len(Chem.GetMolFrags(mol)) == 1, 'explicit fragment policy required for salts')
        return {'matches': len(mol.GetSubstructMatches(query)), 'quantum_energy_generated': False}
    if name == 'same-hamiltonian-path-closure':
        rows = data['edges']
        require(len({r['protocol'] for r in rows}) == 1, 'incompatible Hamiltonian/protocol')
        require(all(rows[i]['to'] == rows[(i+1) % len(rows)]['from'] for i in range(len(rows))), 'path has a missing bridge')
        return {'closure': float(sum(r['energy'] for r in rows)), 'independent_evidence': False}
    if name == 'nonorthogonal-subspace':
        s, b, v = metric(data['S']), array(data['B']), array(data['v'])
        gram = b.conj().T@s@b
        projected = b@np.linalg.pinv(gram, rcond=1e-12)@b.conj().T@s@v
        residual = v-projected
        return {'rank': int(np.linalg.matrix_rank(gram)), 'squared_leakage': float(np.real(residual.conj().T@s@residual))}
    if name == 'partition-mask-audit':
        a, mask = array(data['matrix']), array(data['mask'])
        require(a.shape == mask.shape and np.all((mask == 0) | (mask == 1)), 'binary same-shape mask required')
        b = a*mask
        require(np.linalg.norm(b-b.conj().T) <= 1e-12, 'mask breaks Hermitian symmetry')
        minimum = float(np.linalg.eigvalsh(b).min())
        if data['requires_positive_metric']:
            require(minimum > 1e-10, 'mask destroys positive metric')
        return {'minimum_eigenvalue': minimum}
    if name == 'reflection-parity':
        s, r, b = metric(data['S']), array(data['R']), array(data['B'])
        require(np.linalg.norm(r@r-np.eye(len(s))) < 1e-12, 'reflection must square to identity')
        require(np.linalg.norm(r.conj().T@s@r-s) < 1e-12, 'reflection must preserve metric')
        projected = b@np.linalg.pinv(b.conj().T@s@b, rcond=1e-12)@b.conj().T@s@r@b
        residual = float(np.linalg.norm(r@b-projected))
        require(residual < 1e-12, 'subspace is not reflection-closed')
        return {'closure_residual': residual}
    if name == 'fragment-working-basis':
        b = array(data['B']); s = metric(data['S'])
        require(np.linalg.matrix_rank(b) == data['required_rank'], 'working-basis coverage/rank failure')
        for col, allowed in enumerate(data['supports']):
            outside = sorted(set(range(len(s)))-set(allowed))
            require(np.linalg.norm(b[outside, col]) <= 1e-12, 'fragment support changed')
        return {'rank': int(np.linalg.matrix_rank(b)), 'gram': (b.conj().T@s@b).tolist()}
    if name == 'nuclear-repulsion-response':
        # Synthetic point-charge oracle only, coordinates explicitly in Bohr.
        require(data['unit'] == 'bohr', 'explicit Bohr input required in this example')
        z, xyz = array(data['charges']), array(data['coordinates'])
        require(xyz.shape == (len(z), 3), 'coordinate shape mismatch')
        energy = 0.; gradient = np.zeros_like(xyz)
        for i in range(len(z)):
            for j in range(i):
                delta = xyz[i]-xyz[j];distance = float(np.linalg.norm(delta))
                require(distance > 1e-8, 'coincident synthetic charges')
                energy += z[i]*z[j]/distance
                g = -z[i]*z[j]*delta/distance**3
                gradient[i] += g;gradient[j] -= g
        return {'energy_hartree': float(energy), 'gradient_hartree_per_bohr': gradient.tolist()}
    if name == 'scan-energy-curvature':
        x, y = array(data['x']), array(data['energy'])
        require(len(set(data['state_ids'])) == 1, 'state discontinuity')
        require(len(x) >= 3 and len(np.unique(x)) == len(x), 'distinct scan coordinates required')
        if data['unit'] == 'degree':x = np.deg2rad(x)
        else:require(data['unit'] in ('radian', 'bohr'), 'explicit scan unit required')
        beta = np.linalg.lstsq(np.column_stack((np.ones(len(x)), x, x*x)), y, rcond=None)[0]
        return {'curvature': float(2*beta[2]), 'unit': 'hartree/'+('bohr2' if data['unit'] == 'bohr' else 'radian2')}
    if name == 'fixed-protocol-energy-review':
        states = data['states']
        require(len({(r['protocol'], r['geometry']) for r in states}) == 1, 'incompatible fixed-protocol states')
        require(all(r['qualified'] for r in states), 'unqualified endpoint')
        return {'difference_hartree': states[1]['energy']-states[0]['energy'], 'physical_bond_energy_claimed': False}
    if name == 'constrained-optimization-response':
        j, g = array(data['jacobian']), array(data['cartesian_gradient'])
        reduced = j.conj().T@g
        require(not data.get('claim_full_minimum', False), 'restricted gradient cannot prove full minimum')
        return {'reduced_gradient': reduced.tolist(), 'cartesian_norm': float(np.linalg.norm(g)), 'molecular_optimization_calls': 0}
    if name == 'multistate-size-comparison':
        required = set(data['required']); rows = data['states']
        require(set(rows) == required, 'missing or extra registered state')
        require(all(r['qualified'] for r in rows.values()), 'unqualified state cannot enter assembly')
        return {'assembled_energy': sum(rows[k]['weight']*rows[k]['energy'] for k in required), 'new_state_calculations': 0}
    if name == 'runtime-usage-assistant':
        # Validate an explicit service choice; this is not natural-language routing.
        spec = importlib.util.spec_from_file_location('_review_capabilities', ROOT/'scripts/local-runtime-capabilities.py')
        m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        registry = m.load_capabilities(ROOT/'configs/runtime-capabilities-v2.json')
        selected = [r for r in registry['capabilities'] if r['id'] == data['service']]
        require(len(selected) == 1 and selected[0]['execution_enabled'], 'service is not enabled')
        require(data['service'] != 'user-compute', 'conditional Compute remains closed')
        return {'profile': selected[0]['profile'], 'execution_authorized': False, 'docker_calls': 0}
    raise ValueError('unknown instruction example')


def run_fixture(name, data, output, *, unavailable_input=None):
    """Exercise refusal and I/O recording without dispatching a calculation.

    Refusing an existing output directory must not append to or alter it.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    if unavailable_input is not None:
        try:
            Path(unavailable_input).read_bytes()
        except OSError as exc:
            result = {'status':'EXECUTION_ERROR', 'type':type(exc).__name__, 'scientific_calls':0}
            (output/'result.json').write_text(json.dumps(result), encoding='utf-8')
            (output/'stderr.log').write_text(str(exc), encoding='utf-8')
            return 2, result
        raise ValueError('I/O failure fixture unexpectedly exists')
    try:
        value = evaluate(name, data)
        result = {'status':'CHECK_COMPLETED', 'value':value, 'scientific_calls':0}
        code = 0
    except ValueError as exc:
        result = {'status':'EXPECTED_REFUSAL', 'message':str(exc), 'scientific_calls':0}
        code = 2
    except Exception as exc:
        result = {'status':'UNEXPECTED_ERROR', 'type':type(exc).__name__, 'message':str(exc), 'scientific_calls':0}
        code = 2
    (output/'result.json').write_text(json.dumps(result, allow_nan=False), encoding='utf-8')
    return code, result
