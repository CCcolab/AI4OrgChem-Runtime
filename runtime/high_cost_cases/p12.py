"""Frozen P12 same-basis planar optimizations in a fresh, bounded workspace.

Preparation and preflight never evaluate an integral or an SCF kernel.  Historical
ledgers remain arithmetic evidence; only live calls invoke the original single
state optimization runners.  Source files and source protocol bytes stay frozen.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import sys

METHOD = "B3LYPG/6-311g(2df,p)"
RUNTIME_PROTOCOL = "runtime-high-cost-p12/0.1"
BASE_PROTOCOL = "p12-source2011-planar-cese-recalculation/0.2"
N16_PROTOCOL = "p12-source2011-same-basis-n16-execution/0.1"
BASE = "configs/qm/p12_source2011_planar_cese_recalculation_v0.2.yaml"
N16_CONTRACT = "configs/qm/p12_source2011_same_basis_n16_execution_v0.1.yaml"
BASE_SHA = "734658d90f5d7ab4408f8b1b05732717ad241aaf3a60e8e264be59646c4a57a5"
N16_SHA = "2baeb7813ea058c1412f86bc8f07600b3453cc6c9f0ad5fc7d41dca48d334a82"
SEEDS = "data/inputs/p12_source2011_planar_seeds_v0.1"
G_DIR = "data/processed/p12_source2011_same_basis_planar_g_v0.2"
STATE_DIR = "data/processed/p12_source2011_same_basis_planar_states_v0.2"
KCAL = 627.5094740631
CONFIGURATIONS = {12: "[12]-555", 14: "[14]-665", 16: "[16]-5555"}
INNER = {12: [0, 4, 8], 14: [0, 5, 10], 16: [0, 4, 8, 12]}
SEED_NAMES = {12: "N12_555_seed.xyz", 14: "N14_665_seed.xyz", 16: "N16_5555_seed.xyz"}
N12_PAIRS = [(0, 1), (0, 2), (0, 3), (0, 5), (1, 3)]
_PREPARED = {}
_ASSETS = {
    "src/ai4orgchem/__init__.py", "src/ai4orgchem/qm/__init__.py",
    "src/ai4orgchem/qm/p09_ao_classification.py", "src/ai4orgchem/qm/p09_eri_mask.py",
    "src/ai4orgchem/qm/p09_conditional_scf.py", "src/ai4orgchem/qm/p09_energy_assembly.py",
    "src/ai4orgchem/qm/p12_direct_source2011.py",
    "src/ai4orgchem/qm/p12_direct_conditional_scf.py",
    "src/ai4orgchem/qm/p12_source2011_rks.py", "scripts/__init__.py",
    "scripts/prepare_p12_planar_configuration_seeds.py",
    "scripts/p12_n16_execution_contract.py", "scripts/run_p12_planar_g_optimization.py",
    "scripts/run_p12_planar_source_state_optimization.py", BASE, N16_CONTRACT,
    "configs/qm/p12_source2011_planar_cese_recalculation_v0.1.yaml",
    "configs/qm/p09_exchange_integral_classes_v0.1.yaml",
    "configs/data/p12_annulene_boundary_source_freeze_v0.1.yaml",
    SEEDS + "/manifest.json", STATE_DIR + "/N12_GE_pair_orbits.json",
    STATE_DIR + "/N12_GL_optimized.xyz", STATE_DIR + "/N12_GE_g01_g02_optimized.xyz",
    STATE_DIR + "/N12_GE_g03_g04_optimized.xyz",
    *[SEEDS + "/" + SEED_NAMES[n] for n in CONFIGURATIONS],
    *[SEEDS + f"/N{n}_all_atom_planar.constraints" for n in CONFIGURATIONS],
    *[f"data/processed/p12_source2011_same_basis_n{n}_ledger_v0.2.json" for n in CONFIGURATIONS],
}


def assets():
    return set(_ASSETS)


def units():
    result = []
    for n in CONFIGURATIONS:
        prefix = f"P12-N{n}"
        common = {"case": "P12", "system": f"N{n}", "method_id": METHOD,
                  "source_protocol_id": N16_PROTOCOL if n == 16 else BASE_PROTOCOL,
                  "max_geometry_steps": 80, "geometry_optimization": True}
        result.append({**common, "id": prefix + "-G", "state": "G", "pair": None,
                       "dependencies": []})
        result.append({**common, "id": prefix + "-GL", "state": "GL", "pair": None,
                       "dependencies": [prefix + "-G"]})
        pairs = N12_PAIRS if n == 12 else list(itertools.combinations(range(n // 2), 2))
        for pair, control in [(p, False) for p in pairs] + ([( (2, 3), True)] if n == 12 else []):
            identifier = prefix + f"-GE-g{pair[0]+1:02d}-g{pair[1]+1:02d}"
            result.append({**common, "id": identifier + ("-control" if control else ""),
                           "state": "GE", "pair": list(pair), "symmetry_control": control,
                           "multiplicity": 0 if control else 3 if n == 12 else 1,
                           "dependencies": [prefix + "-G"] + ([prefix + "-GL"] if n == 16 else [])})
    return result


def _unit(unit):
    identifier = unit if isinstance(unit, str) else unit.get("id")
    expected = next((row for row in units() if row["id"] == identifier), None)
    if expected is None:
        raise ValueError("Unregistered P12 optimization unit")
    if isinstance(unit, dict):
        for key, value in expected.items():
            if key in unit and unit[key] != value:
                raise ValueError("Changed P12 scientific/unit field: " + key)
    return expected


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _under(path, root):
    path, root = Path(path), Path(root).resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError("Path escapes or aliases its declared artifact root")
    return resolved


def _file(root, relative):
    if relative not in _ASSETS:
        raise ValueError("Unregistered P12 source asset: " + relative)
    path = _under(Path(root) / relative, root)
    if not path.is_file():
        raise ValueError("Missing frozen P12 source asset: " + relative)
    return path


def _json_file(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Nonfinite JSON value: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid)


def _json(root, relative):
    return _json_file(_file(root, relative))


def _contracts(root):
    import yaml
    if _sha(_file(root, BASE)) != BASE_SHA or _sha(_file(root, N16_CONTRACT)) != N16_SHA:
        raise ValueError("Frozen P12 base or N16 contract SHA-256 changed")
    base = yaml.safe_load(_file(root, BASE).read_text(encoding="utf-8"))
    n16 = yaml.safe_load(_file(root, N16_CONTRACT).read_text(encoding="utf-8"))
    geometry, energy = base["geometry_contract"], base["energy_contract"]
    required_g = {"method": "B3LYPG", "basis": "6-311g(2df,p)", "charge": 0,
                  "multiplicity": 1, "dimensionality": "fully_planar",
                  "hard_constraint": "all_atomic_z_coordinates_equal_zero_throughout_optimization",
                  "maximum_absolute_z_angstrom": 1e-8}
    required_e = {"engine": "PySCF", "pyscf_version": "2.14.0", "method": "B3LYPG",
                  "basis": "6-311g(2df,p)", "grid_level": 3, "density_fitting": False,
                  "spherical_basis": True, "scf_tolerance_hartree": 1e-10,
                  "maximum_scf_cycles": 150}
    if (base["protocol_id"] != BASE_PROTOCOL or n16["protocol_id"] != N16_PROTOCOL
            or any(geometry.get(k) != v for k, v in required_g.items())
            or any(energy.get(k) != v for k, v in required_e.items())
            or n16["base_protocol_sha256"] != BASE_SHA):
        raise ValueError("P12 frozen same-basis scientific contract differs")
    return base, n16


def _source_root(root):
    root = Path(root).resolve()
    if root.name != "source_tree" or root.parent.name != "high_cost_cases":
        raise ValueError("P12 executes only a captured high_cost_cases/source_tree")
    return root


def prepare(root):
    """Import frozen implementation only; no molecular or solver calls."""
    root = _source_root(root)
    _contracts(root)
    for relative in _ASSETS:
        _file(root, relative)
    if str(root) not in _PREPARED:
        sys.dont_write_bytecode = True  # frozen source remains read-only
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts.") or name == "ai4orgchem" or name.startswith("ai4orgchem."):
                module_file = getattr(sys.modules[name], "__file__", None)
                if module_file and not Path(module_file).resolve().is_relative_to(root):
                    del sys.modules[name]
        sys.path[:0] = [str(root / "src"), str(root)]
        modules = {key: importlib.import_module(name) for key, name in {
            "contract": "scripts.p12_n16_execution_contract",
            "g": "scripts.run_p12_planar_g_optimization",
            "conditional": "scripts.run_p12_planar_source_state_optimization",
            "classification": "ai4orgchem.qm.p09_ao_classification",
        }.items()}
        for module in modules.values():
            if not Path(module.__file__).resolve().is_relative_to(root):
                raise ValueError("P12 import escaped the captured implementation")
        _PREPARED[str(root)] = modules
    return _PREPARED[str(root)]


def _xyz(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    count = int(lines[0])
    if len(lines) != count + 2:
        raise ValueError("XYZ atom count differs from file")
    atoms = [[row.split()[0], *[float(x) for x in row.split()[1:]]] for row in lines[2:]]
    if any(len(row) != 4 or any(not math.isfinite(x) for x in row[1:]) for row in atoms):
        raise ValueError("Malformed/nonfinite XYZ")
    return atoms


def _seed(root, n):
    manifest = _json(root, SEEDS + "/manifest.json")
    record = next(row for row in manifest["records"] if row["N"] == n)
    if (record["configuration"] != CONFIGURATIONS[n]
            or record["inner_hydrogen_carbon_indices_zero_based"] != INNER[n]
            or record["inner_hydrogen_topology_verified"] is not True):
        raise ValueError("P12 configuration/inner-hydrogen identity changed")
    seed = _file(root, record["path"])
    constraint = _file(root, record["constraint_path"])
    if (_sha(seed) != record["sha256"] or _sha(constraint) != record["constraint_sha256"]
            or constraint.read_text(encoding="utf-8") != f"$freeze\nz 1-{2*n}\n"):
        raise ValueError("P12 seed or hard planar constraint hash/content differs")
    atoms = _xyz(seed)
    if ([row[0] for row in atoms] != ["C"] * n + ["H"] * n
            or max(abs(row[3]) for row in atoms) > 1e-8):
        raise ValueError("P12 seed atom order or planarity differs")
    return record, atoms


def preflight(unit, root):
    unit = _unit(unit)
    root = _source_root(root)
    base, _ = _contracts(root)
    modules = prepare(root)
    n = int(unit["system"][1:])
    record, atoms = _seed(root, n)
    if n == 16:
        modules["contract"].preflight(root / N16_CONTRACT)
    molecule = modules["g"].build_molecule(atoms, base)
    mapping = modules["conditional"].fragment_map(n, tuple(unit["pair"]) if unit["pair"] else None)
    descriptors = modules["classification"].classify_planar_pyscf_aos(molecule, mapping)
    geometry = modules["g"].geometry_summary(molecule, n, INNER[n])
    checks = {"seed_hash_and_constraint_verified": True, "configuration_identity": geometry["configuration_identity_preserved"],
              "fully_planar": geometry["maximum_absolute_z_angstrom"] <= 1e-8,
              "AO_count": molecule.nao_nr() == 36 * n, "electron_count": molecule.nelectron == 7 * n,
              "AO_classification_complete": len(descriptors) == molecule.nao_nr()}
    return {"status": "PASS" if all(checks.values()) else "FAIL", "unit": unit["id"], "checks": checks,
            "configuration": record["configuration"], "nao": molecule.nao_nr(), "atom_count": molecule.natm,
            "method_id": METHOD, "integrals_evaluated": False, "scf_performed": False,
            "geometry_optimization_performed": False, "runtime_protocol_id": RUNTIME_PROTOCOL}


def _distance_residual(reference, control, shift):
    import numpy as np
    a = np.asarray([row[1:] for row in reference])
    b = np.asarray([row[1:] for row in control])
    perm = [(i + shift) % 12 for i in range(12)] + [12 + (i + shift) % 12 for i in range(12)]
    da = np.linalg.norm(a[:, None] - a[None, :], axis=2)
    db = np.linalg.norm(b[:, None] - b[None, :], axis=2)
    return float(np.max(np.abs(da - db[np.ix_(perm, perm)])))


def _ledger_one(root, n):
    relative = f"data/processed/p12_source2011_same_basis_n{n}_ledger_v0.2.json"
    record = _json(root, relative)
    rows = record["pair_rows"]
    expected = N12_PAIRS if n == 12 else list(itertools.combinations(range(n//2), 2))
    pair_key = "pair_zero_based" if n == 16 else "representative_zero_based"
    if [tuple(row[pair_key]) for row in rows] != expected:
        raise ValueError("Historical P12 GE enumeration/order changed")
    multiplicity = 3 if n == 12 else 1
    if any(row["multiplicity"] != multiplicity for row in rows):
        raise ValueError("Historical P12 pair weight changed")
    if n == 16:
        eg, egl = record["ledger_hartree"]["E_G"], record["ledger_hartree"]["E_GL"]
    else:
        audit = record["state_audits"]
        eg = audit["G"].get("energy_hartree", audit["G"].get("recorded_energy_hartree"))
        egl = audit["GL"]["recorded_energy_hartree"]
    increments = {"adjacent": [], "nonadjacent": []}
    for row in rows:
        a, b = row[pair_key]
        group_distance = min(b-a, n//2-(b-a))
        kind = "adjacent" if group_distance == 1 else "nonadjacent"
        if row["pair_class"] != kind:
            raise ValueError("Historical P12 adjacent/nonadjacent class changed")
        delta = row["GE_energy_hartree"] - egl
        recorded_delta = row.get("delta_pair_kcal_mol", row.get("delta_EA_pair_kcal_mol"))
        if not math.isfinite(delta) or abs(recorded_delta / KCAL - delta) > 1e-10:
            raise ValueError("Historical P12 pair increment does not close")
        increments[kind].append(delta * multiplicity)
    da = eg - egl
    adjacent, nonadjacent = map(math.fsum, (increments["adjacent"], increments["nonadjacent"]))
    ese, cese = da - adjacent, da - adjacent - nonadjacent
    computed = {"delta_EA_kcal_mol": da*KCAL, "sum_delta_EAm_kcal_mol": adjacent*KCAL,
                "ESE_kcal_mol": ese*KCAL, "sum_delta_EnAm_kcal_mol": nonadjacent*KCAL,
                "CESE_kcal_mol": cese*KCAL, "CESE_per_pi_kcal_mol_electron": cese*KCAL/n}
    checks = {"all_pairs_and_weights": sum(row["multiplicity"] for row in rows) == math.comb(n//2, 2),
              "no_exact_numeric_replication_claim": record["exact_numeric_reproduction_claimed"] is False}
    for key, value in computed.items():
        checks["identity_" + key] = abs((record["ledger"][key] - value) / KCAL) <= 1e-10
        checks["disclosed_difference_" + key] = abs(record["recalculation_minus_source"][key] -
                                                          (record["ledger"][key]-record["source_printed_values"][key])) <= 1e-10
    if n == 12:
        orbit = _json(root, STATE_DIR + "/N12_GE_pair_orbits.json")
        members = [tuple(p) for row in orbit["orbits"] for p in row["members"]]
        checks["C3_pair_coverage"] = sorted(members) == list(itertools.combinations(range(6), 2))
        checks["C3_reference_geometric_gate"] = max(orbit["distance_matrix_residuals_angstrom"].values()) <= .002
        gl = _xyz(_file(root, STATE_DIR + "/N12_GL_optimized.xyz"))
        checks["C3_reference_geometry_recomputed"] = all(_distance_residual(gl, gl, shift) <= .002 for shift in (4, 8))
        reference = _xyz(_file(root, STATE_DIR + "/N12_GE_g01_g02_optimized.xyz"))
        control = _xyz(_file(root, STATE_DIR + "/N12_GE_g03_g04_optimized.xyz"))
        control_energy = record["state_audits"]["N12_GE_g03_g04_symmetry_control"]["recorded_energy_hartree"]
        checks["symmetry_control_energy"] = abs(control_energy-rows[0]["GE_energy_hartree"])*KCAL <= .02
        checks["symmetry_control_geometry"] = _distance_residual(reference, control, 4) <= .002
        checks["historical_control_pass_preserved"] = all(record["checks"][key] is True for key in
            ("symmetry_control_state_passed", "symmetry_control_energy_close", "symmetry_control_geometry_close"))
    if n == 16:
        checks["boundary_threshold_unchanged"] = record["N16_relative_CESE_threshold"] == .10
        checks["relative_CESE_identity"] = abs(record["ledger"]["relative_CESE"] - abs(cese)/abs(adjacent+nonadjacent)) <= 1e-10
    return {"system": f"N{n}", "checks": checks, "computed": computed, "historical_verdict": record["verdict"],
            "numeric_difference": record["recalculation_minus_source"], "source_printed_values": record["source_printed_values"],
            "exact_numeric_reproduction_claimed": False, "sha256": _sha(_file(root, relative))}


def ledger(root):
    _contracts(root)
    results = [_ledger_one(root, n) for n in CONFIGURATIONS]
    checks = {row["system"]: all(row["checks"].values()) for row in results}
    return {"status": "PASS" if all(checks.values()) else "FAIL", "case": "P12", "checks": checks,
            "systems": results, "scope": "HISTORICAL_ARITHMETIC_AND_SYMMETRY_ONLY",
            "quantum_calculation_performed": False, "geometry_optimization_performed": False,
            "new_scientific_acceptance": False, "classification_change_allowed": False,
            "historical_2011_method_alignment": "NOT_ESTABLISHED"}


def _dependency(unit_id, root, output):
    output = Path(output).resolve()
    if output.is_relative_to(Path(root).resolve()):
        raise ValueError("Frozen historical outputs cannot be optimization dependencies")
    wrapper = _json_file(_under(output / "result.json", output))
    if (wrapper.get("status") != "PASS" or wrapper.get("unit", wrapper.get("unit_id")) != unit_id
            or wrapper.get("runtime_protocol_id") != RUNTIME_PROTOCOL
            or wrapper.get("geometry_optimization_performed") is not True
            or wrapper.get("evidence_identity") == "ENGINEERING_FAKE"
            or wrapper.get("dependencies_inputs_scope") != "CURRENT_RUN_VERIFIED_OPTIMIZATION_OUTPUTS_ONLY"):
        raise ValueError("Dependency is not a passing current-run P12 optimization")
    artifacts = wrapper["artifacts"]
    path = _under(output / wrapper["source_result_path"], output)
    if artifacts.get(path.relative_to(output).as_posix()) != _sha(path):
        raise ValueError("Dependency source result hash differs")
    result = _json_file(path)
    if result.get("engineering_test_double") is True:
        raise ValueError("Engineering fake is not a scientific optimization dependency")
    if result != wrapper["source_result"]:
        raise ValueError("Dependency payload differs from saved source result")
    work = _under(output / "work", output)
    xyz = _under(work / result["optimized_xyz"], work)
    if artifacts.get(xyz.relative_to(output).as_posix()) != _sha(xyz):
        raise ValueError("Dependency optimized geometry hash differs")
    expected = _unit(unit_id)
    n = int(expected["system"][1:])
    if (result.get("pass") is not True or result.get("optimizer_converged") is not True
            or result.get("N") != n or result.get("configuration") != CONFIGURATIONS[n]
            or result.get("protocol_id") != expected["source_protocol_id"]
            or not result.get("trajectory") or len(result["trajectory"]) > 80
            or result.get("geometry", {}).get("configuration_identity_preserved") is not True
            or result["geometry"]["maximum_absolute_z_angstrom"] > 1e-8):
        raise ValueError("Dependency source optimization qualification differs")
    if expected["state"] == "G":
        if result.get("method") != METHOD or result.get("final_scf_converged") is not True:
            raise ValueError("Dependency G method/SCF differs")
    elif (result.get("state") != expected["state"] or result.get("geometry_method") != METHOD
          or result.get("energy_method") != METHOD or result.get("geometry_scf_converged") is not True
          or result.get("energy_scf_converged") is not True):
        raise ValueError("Dependency conditional state/method/SCF differs")
    return result, xyz, _sha(path)


@contextmanager
def _routing(modules, work, checkpoint):
    changes = []
    def replace(module, name, value):
        changes.append((module, name, getattr(module, name)))
        setattr(module, name, value)
    for key in ("contract", "g", "conditional"):
        replace(modules[key], "ROOT", work)
    replace(modules["contract"], "N16_CONTRACT", work / N16_CONTRACT)
    for key in ("g", "conditional"):
        original = modules[key].write_json
        def writer(path, payload, original=original):
            _under(path, work)
            original(path, payload)
            if checkpoint:
                checkpoint({"event": "P12_SOURCE_CHECKPOINT", "path": Path(path).relative_to(work).as_posix(),
                            "sha256": _sha(path), "state": payload.get("state_id", payload.get("N")),
                            "trajectory_length": len(payload.get("trajectory", []))})
        replace(modules[key], "write_json", writer)
    try:
        yield
    finally:
        for module, name, value in reversed(changes):
            setattr(module, name, value)


def live(unit, root, output, inputs=None, checkpoint=None):
    """One fresh original optimization; caller supplies OS memory/wall guard."""
    if not callable(checkpoint):
        raise ValueError("A durable engineering checkpoint callback is required")
    unit, root = _unit(unit), _source_root(root)
    base, n16 = _contracts(root)
    modules = prepare(root)
    n, inputs = int(unit["system"][1:]), inputs or {}
    if set(inputs) != set(unit["dependencies"]):
        raise ValueError("Exactly the current unit's verified predecessor outputs are required")
    verified = {key: _dependency(key, root, value) for key, value in inputs.items()}
    output = Path(output).resolve()
    if output.is_relative_to(root):
        raise ValueError("P12 output cannot write the frozen source tree")
    work = output / "work"
    if work.exists():
        raise ValueError("P12 requires a fresh work directory; resume/force/already_complete forbidden")
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir()
    for relative in sorted(_ASSETS):
        if relative.startswith("configs/") or relative.startswith(SEEDS + "/"):
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_file(root, relative), target)
            if _sha(target) != _sha(_file(root, relative)):
                raise ValueError("Frozen protocol/input routing copy hash differs")
    _seed(work, n)
    for dependency_id, (result, xyz, _) in verified.items():
        state = _unit(dependency_id)["state"]
        directory = G_DIR if state == "G" else STATE_DIR
        result_path = work / directory / f"N{n}_{state}.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        target = _under(work / result["optimized_xyz"], work)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(xyz, target)
    source_protocol = N16_CONTRACT if n == 16 else BASE
    review = {"runtime_protocol_id": RUNTIME_PROTOCOL, "unit": unit["id"], "source_protocol_id": unit["source_protocol_id"],
              "engineering_routing": "MODULE_ROOT_TO_FRESH_WORK_COPY_WITH_UNCHANGED_SOURCE_PROTOCOL_BYTES",
              "source_base_sha256": BASE_SHA, "source_n16_contract_sha256": N16_SHA,
              "scientific_parameter_changes": [], "max_geometry_steps": 80,
              "resume": False, "force": False, "new_states_per_invocation": 1,
              "dependencies_inputs_scope": "CURRENT_RUN_VERIFIED_OPTIMIZATION_OUTPUTS_ONLY",
              "dependency_source_result_sha256": {key: value[2] for key, value in verified.items()},
              "N16_GE_gate": "CURRENT_G_GL_RESULTS_REVIEWED_UNDER_CURRENT_USER_AUTHORIZATION" if n == 16 and unit["state"] == "GE" else "NOT_APPLICABLE",
              "historical_review_files_reused": False, "public_classification_mutation": False}
    (output / "source-routing-review.json").write_text(json.dumps(review, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    old_token = os.environ.get("AI4ORGCHEM_N16_QUEUE_CONTRACT_SHA256")
    if n == 16:
        os.environ["AI4ORGCHEM_N16_QUEUE_CONTRACT_SHA256"] = N16_SHA
    try:
        with _routing(modules, work, checkpoint):
            # The frozen loader still checks exact contract path, unchanged base
            # hash, all-28 enumeration, single-state and original science gates.
            if n == 16:
                modules["contract"].preflight(work / N16_CONTRACT)
            args = {"maxsteps": 80, "resume": False, "force": False,
                    "protocol_path": work / source_protocol, "n16_execute": n == 16}
            if unit["state"] == "G":
                result = modules["g"].run_one(n, **args)
                source_result_path = work / G_DIR / f"N{n}_G.json"
            else:
                pair = tuple(unit["pair"]) if unit["pair"] else None
                result = modules["conditional"].run_one(n, pair, **args)
                source_result_path = work / STATE_DIR / (modules["conditional"].state_id(n, pair) + ".json")
    finally:
        if old_token is None:
            os.environ.pop("AI4ORGCHEM_N16_QUEUE_CONTRACT_SHA256", None)
        else:
            os.environ["AI4ORGCHEM_N16_QUEUE_CONTRACT_SHA256"] = old_token
    geometry = result.get("geometry", {})
    checks = {"source_pass": result.get("pass") is True, "optimizer_converged": result.get("optimizer_converged") is True,
              "new_optimization_trajectory": 0 < len(result.get("trajectory", [])) <= 80,
              "source_protocol_identity": result.get("protocol_id") == unit["source_protocol_id"],
              "source_system_identity": result.get("N") == n and result.get("configuration") == CONFIGURATIONS[n],
              "source_method_identity": (result.get("method") == METHOD if unit["state"] == "G" else
                                         result.get("geometry_method") == METHOD and result.get("energy_method") == METHOD),
              "configuration_identity": geometry.get("configuration_identity_preserved") is True,
              "fully_planar": geometry.get("maximum_absolute_z_angstrom", math.inf) <= 1e-8,
              "saved_source_result_matches": source_result_path.is_file() and _json_file(source_result_path) == result}
    checks["final_SCF"] = (result.get("final_scf_converged") is True if unit["state"] == "G" else
                            result.get("geometry_scf_converged") is True and result.get("energy_scf_converged") is True)
    artifacts = {path.relative_to(output).as_posix(): _sha(path) for path in work.rglob("*") if path.is_file()}
    artifacts["source-routing-review.json"] = _sha(output / "source-routing-review.json")
    scientific_run = result.get("engineering_test_double") is not True
    return {"status": "PASS" if all(checks.values()) else "FAIL", "unit": unit["id"], "case": "P12", "checks": checks,
            "runtime_protocol_id": RUNTIME_PROTOCOL, "source_protocol_id": unit["source_protocol_id"],
            "method_id": METHOD, "source_result": result, "source_result_path": source_result_path.relative_to(output).as_posix(),
            "artifacts": artifacts, "geometry_optimization_performed": scientific_run, "quantum_calculation_performed": scientific_run,
            "evidence_identity": "SOURCE_P12_PLANAR_OPTIMIZATION_EXECUTION" if scientific_run else "ENGINEERING_FAKE",
            "dependencies_inputs_scope": "CURRENT_RUN_VERIFIED_OPTIMIZATION_OUTPUTS_ONLY",
            "electronic_state_continuity": "NOT_PROVEN_BY_CURRENT_RUNNER", "historical_2011_method_alignment": "NOT_ESTABLISHED",
            "CESE_assembled": False, "classification_change_allowed": False,
            "resource_policy": {"pyscf_memory_setting_mib": 12000, "external_memory_hard_limit_gib": 14,
                                "maximum_threads": 16, "external_wall_limit_seconds": 43200}}
