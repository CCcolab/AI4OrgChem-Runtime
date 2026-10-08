"""Captured P11 state optimizers; ledger and preflight never execute QM.

P11-A retains its historical h/F/S mask. P11-B v0.2 retains physical hcore
and ERIs and masks F/S only. A unit PASS is a single state qualification,
not a new P11 scientific conclusion. No original scientific tree is executed.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys


KCAL = 627.5094740631
A_PROTOCOL = "p11-furan-lde/0.1"
B_PROTOCOL = "p11-source2007-planar-recalculation/0.2"
_PREPARED = {}
_B_STATES = (
    ("benzene", "G"), ("benzene", "GL"), ("benzene", "GE1"),
    ("cyanobenzene", "G"), ("cyanobenzene", "GL_I"),
    ("cyanobenzene", "GE1"), ("cyanobenzene", "GE2"),
    ("cyanobenzene", "GE3"), ("cyanobenzene", "GL_II"),
    ("cyanobenzene", "GE4"), ("cyanobenzene", "GE5"),
    ("cyanobenzene", "GE6"), ("cyanobenzene", "GE7"),
)
_STATE_FILES = (
    "data/processed/p11_source2007_planar_optimized_v0.2/benzene_G.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/benzene_GL.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/benzene_GE1.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_G.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GL_I.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE1.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE2.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE3.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GL_II.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE4.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE5.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE6.json",
    "data/processed/p11_source2007_planar_optimized_v0.2/cyanobenzene_GE7.json",
)
_ASSETS = {
    "scripts/__init__.py", "src/ai4orgchem/__init__.py",
    "src/ai4orgchem/qm/__init__.py",
    "src/ai4orgchem/qm/p09_ao_classification.py",
    "src/ai4orgchem/qm/p09_conditional_scf.py",
    "src/ai4orgchem/qm/p09_energy_assembly.py",
    "src/ai4orgchem/qm/p09_eri_mask.py",
    "src/ai4orgchem/qm/p11_source2007_rks.py",
    "scripts/run_p11_furan_lde.py",
    "scripts/run_p11_source2007_planar_optimization.py",
    "scripts/run_p11_benzene_2007_anchor.py",
    "scripts/run_p11_cyanobenzene_effect.py",
    "scripts/assemble_p11_source2007_planar_recalculation.py",
    "scripts/run_p11_source2007_gradient_pilot.py",
    "configs/qm/p11_furan_lde_v0.1.yaml",
    "configs/qm/p11_substituted_benzene_effect_v0.1.yaml",
    "configs/qm/p11_benzene_2007_anchor_v0.1.yaml",
    "configs/qm/p11_source2007_planar_recalculation_v0.2.yaml",
    "configs/qm/p11_benzene_all_atom_planar.constraints",
    "configs/qm/p11_cyanobenzene_all_atom_planar.constraints",
    "docs/theory/p11_furan_lde_protocol_v0.1.md",
    "docs/theory/p11_source2007_planar_recalculation_protocol_v0.2.md",
    "docs/theory/p11_substituted_benzene_effect_protocol_v0.1.md",
    "docs/theory/p11_source_claim_mapping_v0.1.md",
    "configs/resources/local_wsl.yaml", "environment.yml",
    "data/processed/p11_furan_lde_v0.1.json",
    "data/processed/p11_scoped_furan_LDE_conclusion_v0.1.json",
    "data/processed/p11_source2007_planar_recalculation_v0.2.json",
    "data/processed/p11_source2007_gradient_pilot_v0.2.json",
    "data/processed/p11_scoped_substituent_effect_conclusion_v0.1.json",
    "data/processed/p11_cyanobenzene_effect_v0.1.json",
    "data/processed/p11_benzene_2007_anchor_v0.1.json",
    "data/processed/p11_cyanobenzene_source2007_fs_only_fixed_v0.2.json",
    "data/processed/p11_benzene_source2007_fs_only_fixed_v0.2.json",
    *_STATE_FILES,
}


def assets():
    return set(_ASSETS)


def units():
    rows = []
    for state, deps in (("G", []), ("GL", ["G"]),
                        ("GE1", ["G", "GL"]), ("GE2", ["G", "GL"])):
        rows.append({"id": "P11A-furan-" + state, "case": "P11",
            "subcase": "P11-A", "system": "furan", "state": state,
            "pair": None, "dependencies": ["P11A-furan-" + dep for dep in deps],
            "method_id": ("B3LYPG/6-31g(d);grid=3;ordinary-RKS" if state == "G" else
                "B3LYPG/6-31g(d);grid=3;source2007-h/F/S-mask;no-ERI-deletion")})
    for system, state in _B_STATES:
        rows.append({"id": "P11B-" + system + "-" + state, "case": "P11",
            "subcase": "P11-B", "system": system, "state": state,
            "pair": None, "dependencies": [],
            "method_id": ("B3LYPG/6-31g(d);grid=3;ordinary-RKS" if state == "G" else
                "B3LYPG/6-31g(d);grid=3;source2007-F/S-mask;physical-hcore-and-ERI")})
    return rows


def _unit(value):
    unit_id = value.get("id") if isinstance(value, dict) else value
    for row in units():
        if row["id"] == unit_id:
            if isinstance(value, dict):
                for key in row:
                    if key in value and value[key] != row[key]:
                        raise ValueError("Unit metadata differs from frozen registry: " + key)
            return row
    raise ValueError("Unknown P11 optimization unit")


def _file(root, relative):
    base = Path(root).resolve()
    path = base / relative
    if relative not in _ASSETS or not path.is_file() or path.is_symlink():
        raise ValueError("Missing, unregistered or symbolic captured asset: " + relative)
    if not path.resolve().is_relative_to(base):
        raise ValueError("Captured asset escapes source root")
    return path


def _normalize(value, path=(), changes=None):
    if changes is None:
        changes = []
    if isinstance(value, float) and not math.isfinite(value):
        if value == math.inf and path[-3:] == ("history", 0, "energy_change_hartree"):
            changes.append("/".join(map(str, path)))
            return None
        raise ValueError("Nonfinite scientific value: " + str(path))
    if isinstance(value, dict):
        return {key: _normalize(item, path + (key,), changes) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, path + (index,), changes) for index, item in enumerate(value)]
    return value


def _read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return _normalize(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs))


def _json(root, relative):
    return _read(_file(root, relative))


def _yaml(root, relative):
    import yaml
    value = yaml.safe_load(_file(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Captured protocol must be an object")
    return value


def _protocols(root):
    a = _yaml(root, "configs/qm/p11_furan_lde_v0.1.yaml")
    b = _yaml(root, "configs/qm/p11_source2007_planar_recalculation_v0.2.yaml")
    cyano = _yaml(root, "configs/qm/p11_substituted_benzene_effect_v0.1.yaml")
    benzene = _yaml(root, "configs/qm/p11_benzene_2007_anchor_v0.1.yaml")
    if (a["protocol_id"] != A_PROTOCOL or b["protocol_id"] != B_PROTOCOL
            or cyano["protocol_id"] != "p11-substituted-benzene-effect/0.1"
            or benzene["protocol_id"] != "p11-benzene-2007-anchor/0.1"):
        raise ValueError("Captured P11 protocol identity differs")
    for record in (a, cyano, benzene):
        electronic = record["electronic_structure"]
        for key, expected in {"pyscf_xc": "B3LYPG", "basis": "6-31g(d)",
                "grid_level": 3, "scf_tolerance_hartree": 1.0e-10,
                "maximum_memory_mb": 6000}.items():
            if electronic[key] != expected:
                raise ValueError("Captured electronic parameter differs: " + key)
    if (b["source_method"]["eri_deletion"] is not False
            or b["source_method"]["physical_one_electron_operator_retained"] is not True
            or b["geometry_optimization"]["all_atom_z_angstrom"] != 0.0):
        raise ValueError("P11-B F/S-only or planar contract differs")
    return a, b, cyano, benzene


def _base(mode, unit=None):
    result = {"case": "P11", "mode": mode, "production_label": False,
        "training_eligible": False, "arbitrary_molecule_inputs": False,
        "historical_scientific_verdict_changed": False,
        "new_scientific_conclusion_generated": False,
        "scientific_method_approval_claimed": False, "automatic_retry": False,
        "source_scope": "FROZEN_P11A_FURAN_AND_P11B_SINGLE_CYANOBENZENE_WITH_BENZENE_ANCHOR"}
    if unit is not None:
        result.update(unit_id=unit["id"], subcase=unit["subcase"],
                      system=unit["system"], state=unit["state"], method_id=unit["method_id"])
    return result


def _finish(result, checks):
    result["checks"] = {key: bool(value) for key, value in checks.items()}
    result["failed_checks"] = [key for key, value in result["checks"].items() if not value]
    result["status"] = "PASS" if all(result["checks"].values()) else "NOT_QUALIFIED"
    result = _normalize(result)
    json.dumps(result, allow_nan=False)
    return result


def _a_state_checks(name, record, protocol, *, historical=False):
    optimizer, state = record["optimizer"], record["state"]
    checks = {name + "_optimizer_success": optimizer["success"],
        name + "_gradient_within_tolerance": float(optimizer["gradient_max_abs_hartree_per_angstrom"])
            <= float(protocol["optimizer"]["gradient_tolerance_hartree_per_angstrom"]),
        name + "_no_active_bound": len(optimizer["active_bounds"]) == 0,
        name + "_SCF_converged": state["converged"]}
    if name != "G":
        tol = protocol["acceptance"]
        for label, field, threshold in (
            ("cross_pi_overlap_zero", "masked_overlap_cross_pi_max_abs", "matrix_zero_tolerance"),
            ("cross_pi_fock_zero", "conditional_fock_cross_pi_max_abs", "matrix_zero_tolerance"),
            ("components_close", "energy_component_closure_residual_hartree", "energy_component_closure_hartree"),
            ("commutator_closed", "final_commutator_frobenius_norm", "commutator_frobenius_tolerance"),
            ("density_idempotent", "closed_shell_idempotency_relative_residual", "idempotency_relative_tolerance")):
            checks[name + "_" + label] = abs(float(state[field])) <= float(tol[threshold])
        checks[name + "_36_electrons"] = abs(float(state["masked_metric_electron_count"])
            - float(tol["electron_count"])) <= float(tol["electron_count_tolerance"])
        checks[name + "_no_ERI_deletion"] = int(state["deleted_eri_count"]) == 0
        if "one_electron_matrix_masked" in state:
            checks[name + "_hcore_mask_retained"] = state["one_electron_matrix_masked"] is True
        elif not historical:
            raise ValueError("New conditional state did not report its hcore-mask contract")
    return checks


def ledger(root):
    """Recalculate formulas from captured historical energies without imports of QM."""
    a_protocol, b_protocol, _, _ = _protocols(root)
    a = _json(root, "data/processed/p11_furan_lde_v0.1.json")
    b = _json(root, "data/processed/p11_source2007_planar_recalculation_v0.2.json")
    checks = {"historical_protocols_identified": a["protocol_id"] == A_PROTOCOL
        and b["protocol_id"] == B_PROTOCOL,
        "A_recorded_hFS_implementation_contract": a["implementation_semantics"]
            == a_protocol["state_contract"]["implementation_semantics"]}
    for state in ("G", "GL", "GE1", "GE2"):
        checks.update(_a_state_checks(state, a[state], a_protocol, historical=True))
    energies = {state: float(a[state]["state"]["total_energy_hartree"])
                for state in ("G", "GL", "GE1", "GE2")}
    da = energies["G"] - energies["GL"]
    d1, d2 = energies["GE1"] - energies["GL"], energies["GE2"] - energies["GL"]
    summed, lde = d1 + 2.0*d2, da - d1 - 2.0*d2
    a_values = {"delta_EA_hartree": da, "delta_EA1_hartree": d1,
                "delta_EA2_hartree": d2, "sum_delta_EAm_hartree": summed, "LDE_hartree": lde}
    for key, value in a_values.items():
        checks["A_" + key + "_recomputed"] = abs(value - float(a[key])) <= 1.0e-12
        kcal_key = key.replace("_hartree", "_kcal_mol")
        checks["A_" + kcal_key + "_recomputed"] = abs(value*KCAL - float(a[kcal_key])) <= 1.0e-10
    direction = float(a_protocol["acceptance"]["strict_direction_tolerance_hartree"])
    checks["A_directions"] = da > direction and d1 > direction and d2 > direction and summed > da + direction and lde < -direction
    checks["A_published_LDE_tolerance"] = abs(lde*KCAL - float(a_protocol["source_claim"]["public_furan_LDE_kcal_mol"])) <= float(a_protocol["source_claim"]["quantitative_tolerance_kcal_mol"])
    checks["A_nonproduction_LDE_only"] = a["aromatic_ESE_label"] is False and a["production_label"] is False and a["training_eligible"] is False
    b_energies, states = {}, {}
    sources = [{"path": relative, "sha256": hashlib.sha256(_file(root, relative).read_bytes()).hexdigest()}
        for relative in ("configs/qm/p11_furan_lde_v0.1.yaml",
            "configs/qm/p11_source2007_planar_recalculation_v0.2.yaml",
            "configs/qm/p11_substituted_benzene_effect_v0.1.yaml",
            "configs/qm/p11_benzene_2007_anchor_v0.1.yaml",
            "data/processed/p11_furan_lde_v0.1.json",
            "data/processed/p11_source2007_planar_recalculation_v0.2.json")]
    for relative in _STATE_FILES:
        record = _json(root, relative)
        name = Path(relative).stem
        states[name] = record
        b_energies[name] = float(record["final_energy_hartree"])
        checks[name + "_historical_optimization"] = record["optimizer_converged"] and record["final_scf_converged"] and record["pass"]
        checks[name + "_planar"] = float(record["geometry"]["maximum_absolute_z_angstrom"]) <= float(b_protocol["acceptance"]["maximum_absolute_z_angstrom"])
        checks[name + "_physical_hcore"] = record["one_electron_matrix_masked"] is False
        checks[name + "_assembly_energy_identity"] = abs(b_energies[name] - float(b["state_energies_hartree"][name])) <= 1.0e-12
        digest = hashlib.sha256(_file(root, relative).read_bytes()).hexdigest()
        checks[name + "_historical_input_hash"] = b["input_sha256"].get(relative) == digest
        sources.append({"path": relative, "sha256": digest})
    e = b_energies
    sb = (e["cyanobenzene_G"]-e["cyanobenzene_GL_I"]) - sum(e["cyanobenzene_"+s]-e["cyanobenzene_GL_I"] for s in ("GE1", "GE2", "GE3"))
    bz = (e["benzene_G"]-e["benzene_GL"]) - 3.0*(e["benzene_GE1"]-e["benzene_GL"])
    ph = (e["cyanobenzene_GE7"]-e["cyanobenzene_GL_II"]) - sum(e["cyanobenzene_"+s]-e["cyanobenzene_GL_II"] for s in ("GE4", "GE5", "GE6"))
    b_values = {"ESE_cyanobenzene_whole_system_hartree": sb, "ESE_benzene_hartree": bz,
        "ESE_cyanobenzene_isolated_phenyl_hartree": ph,
        "conjugative_effect_hartree": sb-ph, "inductive_effect_hartree": ph-bz}
    for key, value in b_values.items():
        checks["B_"+key+"_recomputed"] = abs(value-float(b[key])) <= 1.0e-12
        kcal_key = key.replace("_hartree", "_kcal_mol")
        checks["B_"+kcal_key+"_recomputed"] = abs(value*KCAL-float(b[kcal_key])) <= 1.0e-10
        reference_key = {"ESE_cyanobenzene_whole_system_hartree": "cyanobenzene_whole_system_ESE_reference_kcal_mol",
            "ESE_benzene_hartree": "benzene_ESE_reference_kcal_mol",
            "ESE_cyanobenzene_isolated_phenyl_hartree": "cyanobenzene_isolated_phenyl_ESE_reference_kcal_mol",
            "conjugative_effect_hartree": "conjugative_effect_reference_kcal_mol",
            "inductive_effect_hartree": "inductive_effect_reference_kcal_mol"}[key]
        tolerance_key = "ESE_tolerance_kcal_mol" if key.startswith("ESE_") else key.replace("_hartree", "_tolerance_kcal_mol")
        checks["B_"+kcal_key+"_source_tolerance"] = abs(value*KCAL-float(b_protocol["acceptance"][reference_key])) <= float(b_protocol["acceptance"][tolerance_key])
    checks["B_directions"] = sb < 0.0 and sb-ph > 0.0 and ph > bz
    drift = max(max(abs(math.dist(record["initial_atoms_angstrom"][i][1:4], record["initial_atoms_angstrom"][(i+1)%6][1:4])-float(record["geometry"]["ring_bonds_angstrom"][i])) for i in range(6)) for record in states.values())
    checks["B_source_start_diagnostic_recomputed"] = abs(drift-float(b["maximum_ring_bond_change_from_source_start_angstrom"])) <= 1.0e-12
    checks["B_diagnostic_threshold_not_relaxed"] = b["nonblocking_geometry_diagnostic"]["registered_maximum_ring_bond_change_angstrom"] == b_protocol["acceptance"]["maximum_source_heavy_bond_change_angstrom"] == 1.0e-3
    result = _base("ledger")
    result.update(scope="HISTORICAL_ENERGY_LEDGER_ARITHMETIC_NO_NEW_QM", new_optimization_executed=False,
        observed_new_scf_kernel_calls=0, observed_new_integral_calls=0,
        furan={**a_values, "LDE_kcal_mol": lde*KCAL}, substituted_benzene={**b_values,
            "conjugative_effect_kcal_mol": (sb-ph)*KCAL, "inductive_effect_kcal_mol": (ph-bz)*KCAL},
        source_start_diagnostic={"observed_maximum_ring_bond_change_angstrom": drift,
            "within_registered_threshold": drift <= 1.0e-3, "disposition": "NONBLOCKING_SOURCE_START_DIAGNOSTIC"},
        historical_A_per_state_hcore_mask_flags="NOT_RECORDED_IN_2026_A_ARTIFACT;TOP_LEVEL_hFS_CONTRACT_CHECKED",
        first_history_absent_energy_delta_normalization="POSITIVE_INFINITY_TO_NULL_IN_LOADED_COPY_ONLY_ORIGINAL_BYTES_PRESERVED",
        historical_fixed_geometry_status="HISTORICAL_SUPERSEDED_DIAGNOSTIC", sources=sources)
    return _finish(result, checks)


def _execution_root(root):
    base = Path(root).resolve()
    if tuple(part.lower() for part in base.parts[-3:]) != ("reference", "high_cost_cases", "source_tree"):
        raise ValueError("Execution requires the isolated reference/high_cost_cases/source_tree capture")
    return base


def prepare(root):
    """Load captured source helpers only; no SCF, integral or optimizer call."""
    base = _execution_root(root)
    key = str(base)
    if key in _PREPARED:
        return
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for entry in (str(base), str(base / "src")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        names = ("ai4orgchem", "ai4orgchem.qm", "scripts",
            "ai4orgchem.qm.p09_eri_mask", "ai4orgchem.qm.p09_ao_classification",
            "ai4orgchem.qm.p09_energy_assembly", "ai4orgchem.qm.p09_conditional_scf",
            "ai4orgchem.qm.p11_source2007_rks", "scripts.run_p11_furan_lde",
            "scripts.run_p11_cyanobenzene_effect", "scripts.run_p11_benzene_2007_anchor",
            "scripts.run_p11_source2007_planar_optimization")
        loaded = {}
        for name in names:
            relative = (("src/" if name.startswith("ai4orgchem") else "")
                + name.replace(".", "/") + ("/__init__.py" if name in ("ai4orgchem", "ai4orgchem.qm", "scripts") else ".py"))
            expected = _file(base, relative).resolve()
            cached = sys.modules.get(name)
            if cached is not None and Path(cached.__file__).resolve() != expected:
                raise ValueError("Scientific import belongs to another source tree: " + name)
            module = importlib.import_module(name)
            if Path(module.__file__).resolve() != expected:
                raise ValueError("Scientific import escapes captured source: " + name)
            loaded[name.rsplit(".", 1)[-1]] = module
        _PREPARED[key] = loaded
    finally:
        sys.dont_write_bytecode = previous


def _modules(root):
    base = _execution_root(root)
    if str(base) not in _PREPARED:
        raise ValueError("prepare(root) must run before entering the scientific guard")
    return _PREPARED[str(base)]


def _a_fragments(state):
    return {"GL": {0: "O", 1: "A", 2: "A", 3: "B", 4: "B"},
        "GE1": {0: "O", 1: "AB", 2: "AB", 3: "AB", 4: "AB"},
        "GE2": {0: "OA", 1: "OA", 2: "OA", 3: "B", 4: "B"}}.get(state)


def _b_geometry(unit, protocols, modules):
    _, _, cyano, benzene = protocols
    if unit["system"] == "cyanobenzene":
        helper = modules["run_p11_cyanobenzene_effect"]
        atoms, _ = helper.cyanobenzene_atoms(cyano["geometry"]["states"][unit["state"]], cyano["geometry"])
        return atoms, cyano, helper
    helper = modules["run_p11_benzene_2007_anchor"]
    geometry = benzene["geometry"][unit["state"]]
    atoms = (helper.regular_benzene(geometry["regular_CC_angstrom"], geometry["common_CH_angstrom"])
        if unit["state"] == "G" else helper.chain_ring(geometry["chain_CC_angstrom"], geometry["chain_angles_degrees"], geometry["CH_angstrom"])[0])
    return atoms, benzene, helper


def preflight(unit, root):
    unit = _unit(unit)
    modules, protocols = _modules(root), _protocols(root)
    if unit["subcase"] == "P11-A":
        helper, protocol = modules["run_p11_furan_lde"], protocols[0]
        historical = _json(root, "data/processed/p11_furan_lde_v0.1.json")
        initial = (protocol["geometry"]["initial_parameters_angstrom"] if unit["state"] == "G"
            else historical["G" if unit["state"] == "GL" else "GL"]["parameters_angstrom"])
        atoms = helper.furan_atoms(initial)
        fragments, expected = _a_fragments(unit["state"]), 36
        geometry_origin = "FROZEN_START_OR_HISTORICAL_DEPENDENCY_GEOMETRY_METADATA_ONLY"
    else:
        atoms, protocol, helper = _b_geometry(unit, protocols, modules)
        runner = modules["run_p11_source2007_planar_optimization"]
        fragments = (runner.BENZENE_FRAGMENT_MAPS if unit["system"] == "benzene" else runner.CYANO_FRAGMENT_MAPS)[unit["state"]]
        expected = 42 if unit["system"] == "benzene" else 54
        geometry_origin = "ORIGINAL_STATE_SPECIFIC_FIGURE7_OR_SI_START"
    molecule = helper.build_molecule(atoms, protocol)
    descriptors = modules["p09_ao_classification"].classify_planar_pyscf_aos(molecule,
        fragments if fragments is not None else {index: "FULL" for index, row in enumerate(atoms) if row[0] != "H"})
    ao_count = int(molecule.nao_nr())
    pi_count = sum(descriptor.kind == "pi" for descriptor in descriptors)
    explicit_eri = ((unit["subcase"] == "P11-A" and fragments is not None)
        or (unit["system"] == "cyanobenzene" and unit["state"].startswith("GE")))
    result = _base("preflight", unit)
    result.update(scope="ACTUAL_MOLE_BUILD_AND_AO_METADATA_NO_INTEGRALS_OR_SCF",
        geometry_origin=geometry_origin, atoms_angstrom=atoms, actual_ao_count=ao_count,
        actual_atom_count=int(molecule.natm), actual_electron_count=int(molecule.nelectron),
        actual_pi_ao_count=pi_count, actual_sigma_ao_count=ao_count-pi_count,
        explicit_eri_tensor_required=explicit_eri,
        explicit_eri_tensor_bytes_per_copy=8*ao_count**4 if explicit_eri else None,
        explicit_physical_plus_masked_eri_bytes_lower_bound=16*ao_count**4 if explicit_eri else None,
        dense_eri_role=("FURAN_CONDITIONAL_OBJECTIVE" if unit["subcase"] == "P11-A" else
                       "ORIGINAL_CYANOBENZENE_FIXED_GL_SEED") if explicit_eri else None,
        source_pyscf_max_memory_mb=int(protocol["electronic_structure"]["maximum_memory_mb"]),
        new_optimization_executed=False, observed_new_scf_kernel_calls=0,
        observed_new_integral_calls=0, energy_nuc_called=False,
        live_memory_and_duration="UNMEASURED", guaranteed_convergence=False)
    return _finish(result, {"neutral_closed_shell": molecule.charge == 0 and molecule.spin == 0,
        "electron_count": int(molecule.nelectron) == expected,
        "ao_classification_complete": len(descriptors) == ao_count and pi_count > 0,
        "input_all_atom_planarity": max(abs(float(row[3])) for row in atoms) <= 1.0e-10})


def _output(root, output):
    base, target = Path(root).resolve(), Path(output).resolve()
    if target.is_relative_to(base) or base.is_relative_to(target):
        raise ValueError("Live output must remain outside captured source")
    if Path(output).is_symlink():
        raise ValueError("Symbolic live output is forbidden")
    target.mkdir(parents=True, exist_ok=True)
    if any((target / name).exists() for name in ("p11-state.json", "density.npy", "optimized.xyz")):
        raise ValueError("Previous P11 live artifacts must never be overwritten")
    work = target / "work"
    work.mkdir(exist_ok=False)
    return target, work


def _dependency(unit_id, inputs):
    import numpy as np
    if unit_id not in inputs:
        raise ValueError("Missing verified live dependency: " + unit_id)
    directory = Path(inputs[unit_id]).resolve()
    for name in ("p11-state.json", "density.npy"):
        path = directory / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory):
            raise ValueError("Missing or symbolic live dependency artifact")
    record = _read(directory / "p11-state.json")
    if record.get("unit_id") != unit_id or record.get("status") != "PASS" or record.get("mode") != "live":
        raise ValueError("Dependency is not a qualified new P11 state")
    parameters = np.asarray(record["parameters_angstrom"], dtype=float)
    density = np.load(directory / "density.npy", allow_pickle=False)
    if parameters.shape != (8,) or density.ndim != 2 or density.shape[0] != density.shape[1] or not np.isfinite(parameters).all() or not np.isfinite(density).all():
        raise ValueError("Malformed live dependency parameters or density")
    return parameters, density


def _save(target, unit, result, atoms, density, checkpoint):
    import numpy as np
    density = np.asarray(density, dtype=float)
    if density.ndim != 2 or density.shape[0] != density.shape[1] or not np.isfinite(density).all():
        raise ValueError("Final observed density is not finite and square")
    result["density_shape"] = list(density.shape)
    result["artifact_files"] = ["p11-state.json", "density.npy", "optimized.xyz", "work/"]
    np.save(target / "density.npy", density, allow_pickle=False)
    xyz = [str(len(atoms)), unit["id"] + " observed optimized geometry"]
    xyz += [str(row[0]) + " " + " ".join(format(float(value), ".16g") for value in row[1:4]) for row in atoms]
    (target / "optimized.xyz").write_text("\n".join(xyz) + "\n", encoding="utf-8")
    (target / "p11-state.json").write_text(json.dumps(_normalize(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint({"unit_id": unit["id"], "stage": "FINAL_ARTIFACTS_SAVED", "saved_path": str(target / "p11-state.json")})
    return result


def _live_a(unit, root, target, work, inputs, checkpoint):
    import numpy as np
    helper, protocol = _modules(root)["run_p11_furan_lde"], _protocols(root)[0]
    state = unit["state"]
    if state == "G":
        initial = np.asarray(protocol["geometry"]["initial_parameters_angstrom"], dtype=float)
        bounds = [tuple(map(float, pair)) for pair in protocol["geometry"]["initial_bounds_angstrom"]]
        seed = None
    else:
        g_parameters, g_density = _dependency("P11A-furan-G", inputs)
        windows = np.asarray(protocol["geometry"]["conditional_half_windows_angstrom"], dtype=float)
        bounds = [(float(value-window), float(value+window)) for value, window in zip(g_parameters, windows, strict=True)]
        initial, seed = (g_parameters, g_density) if state == "GL" else _dependency("P11A-furan-GL", inputs)
        nao = helper.build_molecule(helper.furan_atoms(initial), protocol).nao_nr()
        if seed.shape != (nao, nao):
            raise ValueError("Dependency density shape differs from frozen AO basis")
    evaluator = (lambda parameters: helper.ordinary_state(helper.furan_atoms(parameters), protocol)) if state == "G" else (lambda parameters: helper.conditional_state(helper.furan_atoms(parameters), _a_fragments(state), seed, protocol))
    original_write = helper.write_json
    def write_progress(path, value):
        original_write(path, value)
        checkpoint({"unit_id": unit["id"], "stage": "SOURCE_OPTIMIZER_PROGRESS_SAVED", "saved_path": str(path), "evaluations": len(value.get("evaluations", []))})
    helper.write_json = write_progress
    try:
        optimized, evaluations = helper.optimize_state(name=state, initial=initial, bounds=bounds,
            evaluator=evaluator, protocol=protocol, checkpoint=work / "source-progress.json")
    finally:
        helper.write_json = original_write
    parameters = np.asarray(optimized.x, dtype=float)
    atoms = helper.furan_atoms(parameters)
    raw = evaluator(parameters)
    if not raw["converged"]:
        raise RuntimeError("Final furan " + state + " SCF did not converge")
    source = {"parameters_angstrom": parameters.tolist(), "atoms_angstrom": atoms,
        "geometry_metrics_angstrom": helper.geometry_metrics(atoms),
        "state": helper.compact_state(raw), "optimizer": helper.optimizer_record(optimized, bounds, evaluations)}
    result = _base("live", unit)
    result.update(source, scope="ONE_FROZEN_FURAN_STATE_OPTIMIZATION_ONLY",
        protocol_id=A_PROTOCOL, new_optimization_executed=True,
        source_capture_root=str(Path(root).resolve()),
        original_state_optimizer_called=True, dependencies=list(unit["dependencies"]),
        initialization="ORIGINAL_G_BOUNDS_AND_G_OR_GL_DENSITY_DEPENDENCY_CHAIN",
        one_electron_matrix_masked=state != "G", final_P11A_LDE_not_assembled=True)
    result = _finish(result, _a_state_checks(state, source, protocol))
    return _save(target, unit, result, atoms, raw["density"], checkpoint)


def _live_b(unit, root, target, work, checkpoint):
    runner = _modules(root)["run_p11_source2007_planar_optimization"]
    original = {name: getattr(runner, name) for name in ("ROOT", "OUTPUT_DIR", "REPORT_DIR",
        "write_json", "_configure", "build_benzene_mean_field", "build_cyanobenzene_mean_field")}
    ordinary, conditional = [], []
    def observe_builder(builder):
        def observed(*args, **kwargs):
            mf = builder(*args, **kwargs)
            ordinary.append(mf)
            return mf
        return observed
    def observe_configure(*args, **kwargs):
        mf = original["_configure"](*args, **kwargs)
        conditional.append(mf)
        return mf
    def write_progress(path, value):
        original["write_json"](path, value)
        checkpoint({"unit_id": unit["id"], "stage": "SOURCE_STATE_RECORD_SAVED", "saved_path": str(path), "trajectory_length": len(value.get("trajectory", []))})
    runner.ROOT, runner.OUTPUT_DIR, runner.REPORT_DIR = work, work / "states", work / "reports"
    runner.write_json, runner._configure = write_progress, observe_configure
    runner.build_benzene_mean_field = observe_builder(original["build_benzene_mean_field"])
    runner.build_cyanobenzene_mean_field = observe_builder(original["build_cyanobenzene_mean_field"])
    try:
        source = runner.run_one(unit["system"], unit["state"], maxsteps=50)
        observed = ordinary if unit["state"] == "G" else conditional
        if not observed:
            raise RuntimeError("Original optimizer did not expose its final mean field")
        density = observed[-1].make_rdm1()
    finally:
        for name, value in original.items():
            setattr(runner, name, value)
    checks = {"original_optimizer_converged": source["optimizer_converged"],
        "original_final_scf_converged": source["final_scf_converged"],
        "all_atom_z_hard_constraint": float(source["geometry"]["maximum_absolute_z_angstrom"]) <= 1.0e-10,
        "original_single_state_gate": source["pass"],
        "physical_hcore_retained": source["one_electron_matrix_masked"] is False}
    result = _base("live", unit)
    result.update(protocol_id=B_PROTOCOL, scope="ONE_ORIGINAL_SOURCE2007_PLANAR_OPTIMIZATION_ONLY",
        source_record=source, new_optimization_executed=True, original_run_one_called=True,
        source_capture_root=str(Path(root).resolve()),
        frozen_state_specific_initialization_retained=True, optimized_dependency_seed_substitution=False,
        one_electron_matrix_masked=False, final_P11B_CE_IE_not_assembled=True,
        unexecuted_checks=["Independent AO electron count/idempotency/component-closure audit",
                           "Whole thirteen-state ESE/CE/IE assembly"])
    result = _finish(result, checks)
    return _save(target, unit, result, source["optimized_atoms_angstrom"], density, checkpoint)


def live(unit, root, output, inputs, checkpoint):
    """Run exactly one registered optimizer under the caller's held resource guard."""
    unit = _unit(unit)
    _modules(root)
    _protocols(root)
    if not callable(checkpoint):
        raise ValueError("A durable engineering checkpoint callback is required")
    if not isinstance(inputs, dict) or set(inputs) != set(unit["dependencies"]):
        raise ValueError("Live dependencies must match the frozen unit graph exactly")
    target, work = _output(root, output)
    if unit["subcase"] == "P11-A":
        return _live_a(unit, root, target, work, inputs, checkpoint)
    return _live_b(unit, root, target, work, checkpoint)
