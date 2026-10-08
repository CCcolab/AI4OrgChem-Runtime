"""Frozen P09/P10 ledger, preflight and bounded live adapters.

Historical evidence is read, never executed as a scheduling authorization.
P09 live is only the frozen CBD fixed-geometry smoke; P10 live is the five
ordinary RKS BLA points. No optimizer or original driver main is called.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import sys


P09 = "p09-benzene-cyclobutadiene-aromatic-energy/0.1"
P10 = "p10-benzene-nuclear-repulsion/0.1"
KCAL = 627.5094740631
_PREPARED = {}
_ASSETS = (
    "src/ai4orgchem/__init__.py", "src/ai4orgchem/qm/__init__.py",
    "src/ai4orgchem/qm/p09_ao_classification.py",
    "src/ai4orgchem/qm/p09_conditional_scf.py",
    "src/ai4orgchem/qm/p09_energy_assembly.py",
    "src/ai4orgchem/qm/p09_eri_mask.py",
    "scripts/run_p09_cyclobutadiene_smoke.py",
    "scripts/run_p10_benzene_nuclear_repulsion.py",
    "configs/qm/p09_benzene_cyclobutadiene_v0.1.yaml",
    "configs/qm/p09_exchange_integral_classes_v0.1.yaml",
    "configs/qm/p10_benzene_nuclear_repulsion_v0.1.yaml",
    "data/processed/p09_cyclobutadiene_fixed_geometry_smoke_v0.1.json",
    "data/processed/p09_cyclobutadiene_G_DSI_VDE_v0.1.json",
    "data/processed/p09_cyclobutadiene_GL_ADE_v0.1.json",
    "data/processed/p09_benzene_G_DSI3_smoke_v0.1.json",
    "data/processed/p09_benzene_GL_GE1_ESE_v0.1.json",
    "data/processed/p09_scoped_aromatic_energy_conclusion_v0.1.json",
    "data/processed/p10_benzene_nuclear_repulsion_v0.1.json",
    "data/processed/p10_scoped_benzene_D6h_conclusion_v0.1.json",
)


def assets():
    """Complete source-tree read closure; first six files use frozen public bytes."""
    return list(_ASSETS)


def _case(case):
    if case not in ("P09", "P10"):
        raise ValueError("Only P09 and P10 are supported by this adapter")
    return case


def _file(root, relative):
    base = Path(root).resolve()
    path = base / relative
    if relative not in _ASSETS or path.is_symlink() or not path.is_file():
        raise ValueError("Missing, unregistered or symbolic source asset: " + relative)
    if not path.resolve().is_relative_to(base):
        raise ValueError("Source asset escapes frozen root")
    return path


def _yaml(root, relative):
    import yaml
    value = yaml.safe_load(_file(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Protocol must be an object")
    return value


def _normalize(value, path=(), changes=None):
    """Normalize only positive first-cycle absent energy delta; reject all else."""
    if changes is None:
        changes = []
    if isinstance(value, float) and not math.isfinite(value):
        if (value == math.inf and len(path) >= 3
                and path[-3:] == ("history", 0, "energy_change_hartree")):
            changes.append("/".join(str(part) for part in path))
            return None
        raise ValueError("Nonfinite value outside first-cycle absent energy delta: " + str(path))
    if isinstance(value, dict):
        return {key: _normalize(item, path + (key,), changes) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, path + (index,), changes) for index, item in enumerate(value)]
    # Backend scalars must be converted explicitly by the calling adapter.
    return value


def _json(root, relative):
    path = _file(root, relative)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate historical JSON key: " + key)
            result[key] = value
        return result
    changes = []
    value = _normalize(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs), changes=changes)
    if not isinstance(value, dict):
        raise ValueError("Historical record must be an object")
    evidence = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "normalization": "FIRST_HISTORY_ABSENT_ENERGY_DELTA_POSITIVE_INFINITY_TO_NULL",
                "normalized_paths": changes, "original_bytes_preserved": True}
    return value, evidence


def _protocol(case, root):
    relative = ("configs/qm/p09_benzene_cyclobutadiene_v0.1.yaml" if case == "P09"
                else "configs/qm/p10_benzene_nuclear_repulsion_v0.1.yaml")
    protocol = _yaml(root, relative)
    if protocol.get("protocol_id") != (P09 if case == "P09" else P10):
        raise ValueError("Frozen protocol identity differs")
    settings = protocol["electronic_structure"] if case == "P09" else protocol["physical_scan"]
    for key, value in {"pyscf_xc": "B3LYPG", "basis": "6-31g(d)", "grid_level": 3,
                       "charge": 0, "multiplicity": 1,
                       "scf_tolerance_hartree": 1.0e-10}.items():
        if settings.get(key) != value:
            raise ValueError("Frozen electronic setting differs: " + key)
    cycle_key = "max_scf_cycles" if case == "P09" else "maximum_scf_cycles"
    if settings.get(cycle_key) != 100:
        raise ValueError("Frozen SCF cycle limit differs")
    if case == "P09":
        conditional = protocol["smoke_gate"]["conditional_scf"]
        for key, value in {"maximum_cycles": 100, "density_tolerance": 2.0e-8,
                "energy_tolerance_hartree": 1.0e-10, "diis_start_cycle": 2,
                "diis_space": 8, "damping_cycles": 2, "damping": 0.20}.items():
            if conditional.get(key) != value:
                raise ValueError("Frozen conditional setting differs: " + key)
    elif settings.get("delta_angstrom") != [0.0, 0.01, 0.02, 0.04, 0.06]:
        raise ValueError("Frozen five-point BLA coordinate differs")
    return protocol


def _base(case, mode):
    live_caps = {"scf_kernel": 1 if case == "P09" else 5,
                 "conditional_solver": 1 if case == "P09" else 0,
                 "conditional_NR": 101 if case == "P09" else 0,
                 "stability": 1 if case == "P09" else 0,
                 "boys_kernel": 0, "pipek_mezey_kernel": 0, "geometry_optimizer": 0}
    return {"case": case, "mode": mode, "protocol_id": P09 if case == "P09" else P10,
            "source_protocol_context_id": P09 if case == "P09" else P10,
            "runtime_protocol_id": "runtime-" + case.lower() + "-bounded/0.1",
            "production_label": False, "training_eligible": False,
            "arbitrary_molecule_inputs": False, "automatic_retry": False, "resume": False,
            "legacy_conditional_user_compute": "BLOCKED",
            "historical_scientific_verdict_changed": False,
            "scientific_method_approval_claimed": False,
            "count_caps": live_caps if mode == "live" else {key: 0 for key in live_caps},
            "planned_live_count_caps": live_caps,
            "unknown_or_not_executed": ["Independent implementation scientific equivalence",
                                       "Historical environment/version equality"]}


def _finish(result, checks):
    result["checks"] = {key: bool(value) for key, value in checks.items()}
    result["failed_checks"] = [key for key, value in result["checks"].items() if not value]
    result["status"] = "PASS" if all(result["checks"].values()) else "NOT_QUALIFIED"
    json.dumps(result, allow_nan=False)
    return result


def prepare(case, root):
    """Import once before the held guard; live calls cached module attributes."""
    case = _case(case)
    base = Path(root).resolve()
    key = (case, str(base))
    if key in _PREPARED:
        return
    src = str(base / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    loaded = {}
    if case == "P09":
        for name in ("p09_ao_classification", "p09_conditional_scf", "p09_energy_assembly", "p09_eri_mask"):
            module = importlib.import_module("ai4orgchem.qm." + name)
            if Path(module.__file__).resolve() != _file(base, "src/ai4orgchem/qm/" + name + ".py").resolve():
                raise ValueError("Scientific module does not belong to frozen source root: " + name)
            loaded[name] = module
    path = _file(base, "scripts/run_p09_cyclobutadiene_smoke.py" if case == "P09"
                 else "scripts/run_p10_benzene_nuclear_repulsion.py")
    module_name = "_protocol_case_" + case + "_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the frozen source helper")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    loaded["helper"] = helper
    # These modules must be loaded before root's guard patches their attributes.
    from pyscf import gto, dft, lib
    loaded.update(gto=gto, dft=dft, lib=lib)
    _PREPARED[key] = loaded


def _modules(case, root):
    key = (_case(case), str(Path(root).resolve()))
    if key not in _PREPARED:
        raise ValueError("prepare(case, root) is required before the held guard")
    return _PREPARED[key]


def _read_records(root, names):
    records, sources = {}, []
    for short, filename in names.items():
        records[short], source = _json(root, "data/processed/" + filename + ".json")
        sources.append(source)
    return records, sources


def ledger(case, root):
    """Recompute ledger arithmetic only; no scientific backend imports/calls."""
    case = _case(case)
    protocol = _protocol(case, root)
    result = _base(case, "ledger")
    result.update(observed_new_scf_kernel_calls=0, observed_new_conditional_NR_calls=0,
                  scope="HISTORICAL_FROZEN_ENERGY_LEDGER_ARITHMETIC_NO_QM")
    if case == "P09":
        records, sources = _read_records(root, {
            "cbd": "p09_cyclobutadiene_GL_ADE_v0.1", "benzene": "p09_benzene_GL_GE1_ESE_v0.1",
            "conclusion": "p09_scoped_aromatic_energy_conclusion_v0.1"})
        cbd, benzene, conclusion = (records[key] for key in ("cbd", "benzene", "conclusion"))
        g = float(cbd["G_energy_hartree"])
        dsi = float(cbd["DSI_at_G_energy_hartree"])
        gl = float(cbd["GL_state"]["total_energy_hartree"])
        vde, ade, relaxation = g - dsi, g - gl, dsi - gl
        bg = float(benzene["G_energy_hartree"])
        bgl = float(benzene["GL_state"]["total_energy_hartree"])
        bge = float(benzene["GE1_state"]["total_energy_hartree"])
        delta_a, delta_a1 = bg - bgl, bge - bgl
        ese = delta_a - 3.0 * delta_a1
        tol = float(protocol["tolerances"]["energy_path_closure_hartree"])
        checks = {"parent_protocol_identities": cbd["protocol_id"] == benzene["protocol_id"] == P09,
            "historical_calculation_checks_passed": cbd["calculation_gate_verdict"] == "PASS"
                and benzene["calculation_gate_verdict"] == "PASS"
                and all(cbd["acceptance_checks"].values()) and all(benzene["acceptance_checks"].values()),
            "cbd_VDE_recomputed": abs(vde-float(cbd["VDE_hartree"])) <= tol,
            "cbd_ADE_recomputed": abs(ade-float(cbd["ADE_hartree"])) <= tol,
            "cbd_relaxation_recomputed": abs(relaxation-float(cbd["GL_relaxation_from_DSI_hartree"])) <= tol,
            "cbd_identity": abs(ade-vde-relaxation) <= 1.0e-12,
            "benzene_delta_A_recomputed": abs(delta_a-float(benzene["delta_E_A_hartree"])) <= tol,
            "benzene_delta_A1_recomputed": abs(delta_a1-float(benzene["delta_E_A1_hartree"])) <= tol,
            "benzene_ESE_recomputed": abs(ese-float(benzene["ESE_hartree"])) <= tol,
            "historical_units_closed": abs(ese*KCAL-float(benzene["ESE_kcal_mol"])) <= 1.0e-10
                and abs(ade*KCAL-float(cbd["ADE_kcal_mol"])) <= 1.0e-10,
            "historical_conclusion_matches_ledger": conclusion["verdict"] == "P09_SCOPED_PROPOSITION_SUPPORTED"
                and abs(float(conclusion["systems"]["cyclobutadiene"]["ADE_kcal_mol"])-ade*KCAL) <= 1.0e-10
                and abs(float(conclusion["systems"]["benzene"]["ESE_kcal_mol"])-ese*KCAL) <= 1.0e-10,
            "historical_source_direction_and_tolerance": ade > 0.0 and ese < 0.0
                and abs(ade*KCAL-float(protocol["blind_comparison_values"]["cyclobutadiene_ADE_kcal_mol"]))
                    <= float(protocol["tolerances"]["quantitative_source_difference_kcal_mol"])
                and abs(ese*KCAL-float(protocol["blind_comparison_values"]["benzene_ESE_kcal_mol"]))
                    <= float(protocol["tolerances"]["quantitative_source_difference_kcal_mol"]),
            "nonproduction_records": all(record["production_labels_allowed"] is False
                and record["ai_training_allowed"] is False for record in (cbd, benzene))
                and conclusion["production_label"] is False and conclusion["training_eligible"] is False
                and conclusion["universal_aromaticity_law"] is False}
        result.update(cyclobutadiene={"VDE_hartree": vde, "ADE_hartree": ade,
                      "GL_relaxation_hartree": relaxation, "ADE_kcal_mol": ade*KCAL},
                      benzene={"delta_E_A_hartree": delta_a, "delta_E_A1_hartree": delta_a1,
                               "ESE_hartree": ese, "ESE_kcal_mol": ese*KCAL}, sources=sources)
        result["unknown_or_not_executed"].append("No new G/GL optimization or final P09 numerical reproduction")
        return _finish(result, checks)
    records, sources = _read_records(root, {
        "g": "p09_benzene_G_DSI3_smoke_v0.1", "gl": "p09_benzene_GL_GE1_ESE_v0.1",
        "p10": "p10_benzene_nuclear_repulsion_v0.1", "conclusion": "p10_scoped_benzene_D6h_conclusion_v0.1"})
    helper = _load_geometry_helper(root)
    observed = records["p10"]["ordinary_RKS_BLA_scan"]["points"]
    computed = _p10_record(protocol, records["g"], records["gl"], observed, helper)
    checks = dict(computed["acceptance_checks"])
    checks["historical_scan_identity"] = records["p10"]["protocol_id"] == P10 and records["p10"]["calculation_gate_verdict"] == "PASS"
    checks["historical_conclusion_preserved"] = records["conclusion"]["verdict"] == "P10_SCOPED_PROPOSITION_SUPPORTED"
    for component in ("electronic", "nuclear", "total"):
        old = float(records["p10"]["ordinary_RKS_BLA_scan"]["quadratic_curvatures_hartree_per_angstrom2"][component])
        checks[component+"_historical_curvature_recomputed"] = abs(old-computed["ordinary_RKS_BLA_scan"]["quadratic_curvatures_hartree_per_angstrom2"][component]) <= 1.0e-12
    result.update(result=computed, sources=sources)
    result["unknown_or_not_executed"].append("Five ordinary RKS energies reused; not recomputed in ledger mode")
    return _finish(result, checks)


def _load_geometry_helper(root):
    """Import source P10 pure helpers without importing a scientific backend."""
    path = _file(root, "scripts/run_p10_benzene_nuclear_repulsion.py")
    spec = importlib.util.spec_from_file_location("_protocol_p10_ledger_geometry", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load P10 geometry helper")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def _p10_record(protocol, g_record, gl_record, observations, helper):
    """Recompute the original 17 checks from five observed ordinary energies."""
    import numpy as np
    deltas = [float(value) for value in protocol["physical_scan"]["delta_angstrom"]]
    if len(observations) != 5 or [float(row["delta_angstrom"]) for row in observations] != deltas:
        raise ValueError("Exactly the frozen five points in original order are required")
    atoms = g_record["optimized_G_geometry"]["atoms_angstrom"]
    g_total = float(g_record["ordinary_G_state"]["total_energy_hartree"])
    g_nuclear = helper.nuclear_repulsion(atoms)
    gl_state = gl_record["GL_state"]
    gl_total = float(gl_state["total_energy_hartree"])
    gl_nuclear = float(gl_state["nuclear_repulsion_hartree"])
    gl_electronic = float(gl_state["electronic_energy_hartree"])
    de = (g_total-g_nuclear)-gl_electronic
    dn = g_nuclear-gl_nuclear
    dt = g_total-gl_total
    closure = dt-de-dn
    mean_cc, ch = helper.mean_ring_cc_length(atoms), helper.mean_ch_length(atoms)
    points = []
    for row in observations:
        delta = float(row["delta_angstrom"])
        formula = helper.nuclear_repulsion(helper.d3h_atoms(mean_cc, delta, ch))
        total = float(row["total_energy_hartree"])
        pyscf_nuc = float(row["nuclear_repulsion_hartree_pyscf"])
        points.append({"delta_angstrom": delta, "ra_angstrom": mean_cc-delta,
            "rb_angstrom": mean_cc+delta, "converged": bool(row["converged"]),
            "total_energy_hartree": total, "electronic_energy_hartree": total-pyscf_nuc,
            "nuclear_repulsion_hartree_pyscf": pyscf_nuc,
            "nuclear_repulsion_hartree_formula": formula,
            "nuclear_formula_minus_pyscf_hartree": formula-pyscf_nuc,
            "scf_cycles": row.get("scf_cycles")})
    anchor = points[0]
    for row in points:
        for component, field in (("total", "total_energy_hartree"), ("electronic", "electronic_energy_hartree"),
                                 ("nuclear", "nuclear_repulsion_hartree_formula")):
            row["delta_"+component+"_hartree"] = row[field]-anchor[field]
            row["delta_"+component+"_kcal_mol"] = row["delta_"+component+"_hartree"]*KCAL
    x = np.square(np.asarray(deltas, dtype=float))
    curvature = {component: 2.0*float(np.polyfit(x, np.asarray([row["delta_"+component+"_hartree"]
                 for row in points], dtype=float), 1)[0]) for component in ("electronic", "nuclear", "total")}
    symmetry = [abs(helper.nuclear_repulsion(helper.d3h_atoms(mean_cc, delta, ch))
                 -helper.nuclear_repulsion(helper.d3h_atoms(mean_cc, -delta, ch))) for delta in deltas[1:]]
    tol = protocol["acceptance"]
    direction = float(tol["strict_direction_tolerance_hartree"])
    distorted = points[1:]
    checks = {"p09_G_gate_passed": g_record["smoke_gate_verdict"] == "PASS" and g_record["protocol_id"] == P09,
        "p09_GL_gate_passed": gl_record["calculation_gate_verdict"] == "PASS" and gl_record["protocol_id"] == P09,
        "endpoint_energy_identity_closed": abs(closure) <= float(tol["energy_identity_hartree"]),
        "endpoint_delta_Ee_positive": de > direction, "endpoint_delta_EN_negative": dn < -direction,
        "endpoint_nuclear_change_predominates": abs(dn) > de,
        "all_scan_SCF_converged": all(row["converged"] for row in points),
        "delta_zero_matches_p09_G": abs(anchor["total_energy_hartree"]-g_total) <= float(tol["g_anchor_energy_hartree"]),
        "independent_nuclear_formula_matches_pyscf": max(abs(row["nuclear_formula_minus_pyscf_hartree"])
            for row in points) <= float(tol["nuclear_formula_hartree"]),
        "nuclear_energy_minimum_at_equal_bonds": all(row["delta_nuclear_hartree"] > direction for row in distorted),
        "ordinary_electronic_energy_favors_BLA": all(row["delta_electronic_hartree"] < -direction for row in distorted),
        "nuclear_penalty_exceeds_electronic_lowering": all(row["delta_nuclear_hartree"] > abs(row["delta_electronic_hartree"])
            for row in distorted),
        "ordinary_total_energy_minimum_at_equal_bonds": all(row["delta_total_hartree"] > direction for row in distorted),
        "electronic_curvature_negative": curvature["electronic"] < 0.0,
        "nuclear_curvature_positive": curvature["nuclear"] > 0.0,
        "total_curvature_positive": curvature["total"] > 0.0,
        "nuclear_path_even_in_delta": max(symmetry, default=0.0) <= float(tol["nuclear_symmetry_hartree"])}
    return {"protocol_id": P10, "stage": "benzene_D6h_nuclear_repulsion_decomposition",
        "source_aligned_endpoint_decomposition": {"G_total_energy_hartree": g_total,
            "G_electronic_energy_hartree": g_total-g_nuclear, "G_nuclear_repulsion_hartree": g_nuclear,
            "GL_total_energy_hartree": gl_total, "GL_electronic_energy_hartree": gl_electronic,
            "GL_nuclear_repulsion_hartree": gl_nuclear, "delta_electronic_hartree": de,
            "delta_electronic_kcal_mol": de*KCAL, "delta_nuclear_hartree": dn,
            "delta_nuclear_kcal_mol": dn*KCAL, "delta_total_hartree": dt,
            "delta_total_kcal_mol": dt*KCAL, "identity_residual_hartree": closure},
        "ordinary_RKS_BLA_scan": {"mean_CC_angstrom": mean_cc, "fixed_CH_angstrom": ch,
            "points": points, "quadratic_curvatures_hartree_per_angstrom2": curvature,
            "maximum_nuclear_plus_minus_symmetry_error_hartree": max(symmetry, default=0.0)},
        "acceptance_checks": {key: bool(value) for key, value in checks.items()},
        "calculation_gate_verdict": "PASS" if all(checks.values()) else "FAIL",
        "production_label": False, "training_eligible": False, "universal_benzene_symmetry_law": False,
        "nuclear_repulsion_as_independent_first_cause": False}


def preflight(case, root):
    """Build actual AO models and calculate resource lower bounds; no kernel."""
    case = _case(case)
    prepare(case, root)
    modules = _modules(case, root)
    protocol = _protocol(case, root)
    result = _base(case, "preflight")
    if case == "P09":
        mol = modules["helper"].build_molecule(protocol)
        atoms = protocol["smoke_gate"]["initial_atoms"]
        naos = [int(mol.nao_nr())]
        checks = {"frozen_CBD_atom_order": [row[0] for row in atoms] == ["C"]*4+["H"]*4,
                  "frozen_planar_CBD": all(abs(float(row[3])) <= 1.0e-8 for row in atoms),
                  "actual_AO_count": naos == [64], "actual_electron_count": int(mol.nelectron) == 28,
                  "neutral_singlet": mol.charge == 0 and mol.spin == 0,
                  "exact_fifteen_classes": len(_yaml(root, "configs/qm/p09_exchange_integral_classes_v0.1.yaml")["exchange_integral_classes"]) == 15}
        result.update(full_eri_tensor_bytes=8*naos[0]**4, eri_storage="single_tensor_inplace_category_mask",
                      source_pyscf_max_memory_mb=int(protocol["smoke_gate"]["maximum_memory_mb"]))
    else:
        g, source = _json(root, "data/processed/p09_benzene_G_DSI3_smoke_v0.1.json")
        helper = modules["helper"]
        atoms = g["optimized_G_geometry"]["atoms_angstrom"]
        mean_cc, ch = helper.mean_ring_cc_length(atoms), helper.mean_ch_length(atoms)
        scan = protocol["physical_scan"]
        naos = []
        electrons = []
        for delta in scan["delta_angstrom"]:
            mol = modules["gto"].M(atom=helper.d3h_atoms(mean_cc, float(delta), ch), basis=scan["basis"],
                charge=scan["charge"], spin=scan["multiplicity"]-1, unit="Angstrom", symmetry=False, verbose=0)
            naos.append(int(mol.nao_nr()))
            electrons.append(int(mol.nelectron))
        checks = {"five_frozen_models": len(naos) == 5, "actual_AO_counts": naos == [96]*5,
                  "actual_electron_counts": electrons == [42]*5,
                  "frozen_parent_G_passed": g["protocol_id"] == P09 and g["smoke_gate_verdict"] == "PASS"}
        result.update(sources=[source], source_pyscf_max_memory_mb=int(scan["maximum_memory_mb"]),
                      explicit_conditional_eri_tensor_required=False)
    result.update(scope="ACTUAL_MOLECULE_BUILD_NO_SCF", actual_ao_counts=naos,
        observed_new_scf_kernel_calls=0, observed_new_conditional_NR_calls=0,
        resource_profile={"container_memory_bytes": 1073741824, "cpu_threads": 1,
                          "wall_limit_seconds": 120, "soft_stop_seconds": 90},
        planned_live_resource_profile={"container_memory_bytes": 4294967296, "cpu_threads": 2,
                                       "wall_limit_seconds": 900, "soft_stop_seconds": 840},
        memory_advisory_is_not_a_hard_limit=True, guaranteed_convergence=False)
    result["unknown_or_not_executed"].extend(["Runtime peak memory and duration until live observation",
                                           "Source max_memory6000 MB exceeds cgroup4 GiB; cgroup is controlling"])
    return _finish(result, checks)


def live(case, root):
    """Requires separately authorized held native guard and cgroup envelope."""
    case = _case(case)
    modules = _modules(case, root)
    protocol = _protocol(case, root)
    result = _base(case, "live")
    modules["lib"].num_threads(2)
    if case == "P10":
        records, sources = _read_records(root, {"g": "p09_benzene_G_DSI3_smoke_v0.1",
                                               "gl": "p09_benzene_GL_GE1_ESE_v0.1"})
        helper = modules["helper"]
        atoms = records["g"]["optimized_G_geometry"]["atoms_angstrom"]
        mean_cc, ch = helper.mean_ring_cc_length(atoms), helper.mean_ch_length(atoms)
        observations = []
        for delta in protocol["physical_scan"]["delta_angstrom"]:
            observations.append({"delta_angstrom": float(delta),
                **helper.ordinary_rks(helper.d3h_atoms(mean_cc, float(delta), ch), protocol)})
        computed = _p10_record(protocol, records["g"], records["gl"], observations, helper)
        result.update(scope="FIVE_FROZEN_ORDINARY_RKS_BLA_POINTS_PLUS_REUSED_G_GL_LEDGER",
            result=computed, sources=sources, actual_completed_rks_evaluations=len(observations),
            original_driver_main_called=False, p09_reoptimized=False,
            source_pyscf_max_memory_mb=int(protocol["physical_scan"]["maximum_memory_mb"]))
        result["unknown_or_not_executed"].append("No new G/GL optimization; source-aligned endpoint energies reused")
        return _finish(result, computed["acceptance_checks"])
    helper = modules["helper"]
    mol = helper.build_molecule(protocol)
    mf = helper.build_mean_field(mol, protocol)
    ordinary, density = helper.ordinary_state(mf)
    if not ordinary["converged"]:
        return _finish({**result, "scope": "FIXED_GEOMETRY_CBD_G_LIKE_DSI_SMOKE_ONLY", "ordinary": ordinary},
                       {"ordinary_scf_converged": False})
    descriptors = modules["p09_ao_classification"].classify_planar_pyscf_aos(mol, {0: "A", 1: "A", 2: "B", 3: "B"})
    classes = _yaml(root, "configs/qm/p09_exchange_integral_classes_v0.1.yaml")["exchange_integral_classes"]
    options = protocol["smoke_gate"]["conditional_scf"]
    raw = modules["p09_conditional_scf"].run_p09_conditional_rks(mf, descriptors, classes,
        initial_density=density, maximum_cycles=int(options["maximum_cycles"]),
        density_tolerance=float(options["density_tolerance"]), energy_tolerance=float(options["energy_tolerance_hartree"]),
        diis_start_cycle=int(options["diis_start_cycle"]), diis_space=int(options["diis_space"]),
        damping_cycles=int(options["damping_cycles"]), damping=float(options["damping"]), memory_controlled_eri=True)
    changes = []
    conditional = _normalize(helper.compact_conditional(raw), changes=changes)
    import numpy as np
    tol = protocol["smoke_gate"]["acceptance"]
    expected = int(mol.nelectron)
    checks = {"ordinary_scf_converged": ordinary["converged"], "conditional_scf_converged": conditional["converged"],
        "neutral_singlet_and_electron_count": mol.charge == 0 and mol.spin == 0 and expected == 28,
        "ordinary_physical_metric_electron_count": abs(float(ordinary["physical_metric_electron_count"])-expected) <= float(tol["electron_count_tolerance"]),
        "conditional_masked_metric_electron_count": abs(float(conditional["masked_metric_electron_count"])-expected) <= float(tol["electron_count_tolerance"]),
        "cross_fragment_pi_overlap_zero": float(conditional["masked_overlap_cross_pi_max_abs"]) <= float(tol["matrix_zero_tolerance"]),
        "cross_fragment_pi_fock_zero": float(conditional["conditional_fock_cross_pi_max_abs"]) <= float(tol["matrix_zero_tolerance"]),
        "fifteen_class_eri_mask_applied": len(classes) == 15 and int(conditional["deleted_eri_count"]) > 0,
        "independent_energy_components_close": float(conditional["energy_component_closure_residual_hartree"]) <= float(tol["energy_component_closure_hartree"]),
        "conditional_commutator_closed": float(conditional["final_commutator_frobenius_norm"]) <= float(tol["commutator_frobenius_tolerance"]),
        "conditional_density_idempotent": float(conditional["closed_shell_idempotency_relative_residual"]) <= float(tol["idempotency_relative_tolerance"]),
        "wavefunction_stability_reported": ordinary["stability"]["internal_stability_checked"]
            and np.isfinite(float(conditional["occupied_virtual_gap_hartree"]))}
    difference = float(ordinary["total_energy_hartree"])-float(conditional["total_energy_hartree"])
    result.update(scope="FIXED_GEOMETRY_CBD_G_LIKE_DSI_SMOKE_ONLY", ordinary_G_like_state=ordinary,
        conditional_DSI_state=conditional, geometry_sha256=helper.geometry_hash(mol),
        geometry_atoms_angstrom=protocol["smoke_gate"]["initial_atoms"],
        fixed_geometry_diagnostic_difference_hartree=difference,
        fixed_geometry_diagnostic_difference_kcal_mol=difference*KCAL,
        source_pyscf_max_memory_mb=int(protocol["smoke_gate"]["maximum_memory_mb"]),
        actual_completed_rks_evaluations=1, actual_completed_conditional_evaluations=1,
        first_cycle_energy_delta_normalization={"replacement": None, "normalized_paths": changes},
        original_driver_main_called=False, geometry_optimization_executed=False,
        energy_difference_is_final_VDE_ADE_or_ESE=False,
        masked_physical_and_grid_electron_counts_are_distinct_diagnostics=True)
    historical, source = _json(root, "data/processed/p09_cyclobutadiene_fixed_geometry_smoke_v0.1.json")
    result["sources"] = [source]
    rerun_tol = float(protocol["tolerances"]["rerun_energy_difference_hartree"])
    rerun_residuals = {
        "ordinary_total_energy_hartree": abs(float(ordinary["total_energy_hartree"])
            -float(historical["ordinary_G_like_state"]["total_energy_hartree"])),
        "conditional_total_energy_hartree": abs(float(conditional["total_energy_hartree"])
            -float(historical["conditional_DSI_state"]["total_energy_hartree"]))}
    result["historical_rerun_comparison"] = {"scope": "AFTER_FROZEN_CALCULATION_NOT_A_FIT_TARGET",
        "tolerance_hartree": rerun_tol, "absolute_residuals": rerun_residuals,
        "status": "PASS" if all(value <= rerun_tol for value in rerun_residuals.values()) else "NOT_QUALIFIED",
        "same_historical_environment_certified": False}
    result["original_smoke_checks"] = {key: bool(value) for key, value in checks.items()}
    checks["historical_rerun_comparison"] = result["historical_rerun_comparison"]["status"] == "PASS"
    result["unknown_or_not_executed"].extend(["No final optimized VDE/ADE or benzene ESE reproduced",
        "Conditional fixed point is not a proof of energy stationarity or experimental accuracy"])
    return _finish(result, checks)
