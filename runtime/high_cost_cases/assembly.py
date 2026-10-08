"""Read-only assembly of current P11/P12 state results; never invoke QM.

The host must verify real worker receipts before calling this API. This module
checks current/live result identity, source gates and frozen arithmetic. Printed
source comparisons are not external experimental validation. Engineering doubles
can exercise arithmetic only with explicit opt-in and can never become science.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import re

from . import ASSETS, units as registered_units
from . import p11, p12


KCAL = 627.5094740631
_IDENTITY = ("source_sha256", "dependencies_sha256", "profile_sha256", "image_id")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A finite recorded energy or diagnostic is required")
    return float(value)


def _fake(row):
    return (row.get("evidence_identity") == "ENGINEERING_FAKE"
        or row.get("engineering_test_double") is True
        or any(isinstance(row.get(key), dict) and row[key].get("engineering_test_double") is True
               for key in ("source_result", "source_record")))


def _identity_errors(row):
    errors = []
    for key in _IDENTITY:
        pattern = r"sha256:[0-9a-f]{64}" if key == "image_id" else r"[0-9a-f]{64}"
        if not isinstance(row.get(key), str) or re.fullmatch(pattern, row[key]) is None:
            errors.append("MISSING_OR_INVALID_" + key.upper())
    return errors


def _row_errors(identifier, row, unit, engineering_test):
    errors = []
    if not isinstance(row, dict):
        return ["RESULT_IS_NOT_AN_OBJECT"]
    try:
        json.dumps(row, allow_nan=False)
    except (TypeError, ValueError):
        errors.append("NONFINITE_OR_NON_JSON_RESULT")
    if row.get("unit_id", row.get("unit")) != identifier:
        errors.append("UNIT_IDENTITY_DIFFERS")
    if row.get("case") != unit["case"]:
        errors.append("CASE_IDENTITY_DIFFERS")
    if row.get("status") != "PASS":
        errors.append("STATE_NOT_PASS")
    if row.get("execution_mode") != "live":
        errors.append("NOT_A_CURRENT_LIVE_RESULT")
    if not (row.get("new_optimization_executed") is True
            or row.get("geometry_optimization_performed") is True):
        errors.append("NEW_OPTIMIZATION_NOT_RECORDED")
    if _fake(row) and not engineering_test:
        errors.append("ENGINEERING_FAKE_NOT_SCIENTIFIC")
    if row.get("method_id") != unit["method_id"]:
        errors.append("FROZEN_METHOD_DIFFERS")
    if "operator_id" in row and row["operator_id"] != unit["operator_id"]:
        errors.append("FROZEN_OPERATOR_DIFFERS")
    if "dependencies" in row and row["dependencies"] != unit["dependencies"]:
        errors.append("FROZEN_DEPENDENCY_GRAPH_DIFFERS")
    expected_protocol = "runtime-high-cost-" + unit["case"].lower() + "/0.1"
    if row.get("runtime_protocol_id") != expected_protocol:
        errors.append("RUNTIME_PROTOCOL_DIFFERS")
    checks = row.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        errors.append("ORIGINAL_ADAPTER_CHECKS_NOT_ALL_PASS")
    errors.extend(_identity_errors(row))
    return errors


def _sub_result(expected, eligible):
    missing = sorted(set(expected) - set(eligible))
    return {"required_units": expected, "missing_or_rejected_units": missing,
        "status": "BLOCKED_INCOMPLETE" if missing else "READY",
        "new_scientific_acceptance": False}


def _p11_a(rows, root):
    protocol = p11._protocols(root)[0]
    checks, energies = {}, {}
    for state in ("G", "GL", "GE1", "GE2"):
        row = rows["P11A-furan-" + state]
        checks.update(p11._a_state_checks(state, row, protocol))
        checks[state + "_source_protocol"] = row.get("protocol_id") == p11.A_PROTOCOL
        energies[state] = _number(row["state"]["total_energy_hartree"])
    delta, first, second = (energies[state] - energies["GL"] for state in ("G", "GE1", "GE2"))
    summed, lde = first + 2.0*second, delta-(first+2.0*second)
    direction = _number(protocol["acceptance"]["strict_direction_tolerance_hartree"])
    checks.update(delta_EA_positive=delta > direction, delta_EA1_positive=first > direction,
        delta_EA2_positive=second > direction, sum_increments_exceeds_delta_EA=summed > delta+direction,
        LDE_negative=lde < -direction,
        LDE_identity_closes=abs(lde-(energies["G"]-(energies["GL"]+summed)))
            <= _number(protocol["acceptance"]["energy_identity_hartree"]))
    reference = _number(protocol["source_claim"]["public_furan_LDE_kcal_mol"])
    tolerance = _number(protocol["source_claim"]["quantitative_tolerance_kcal_mol"])
    difference = lde*KCAL-reference
    values = {"delta_EA_hartree": delta, "delta_EA1_hartree": first, "delta_EA2_hartree": second,
        "sum_delta_EAm_hartree": summed, "LDE_hartree": lde}
    return {"status": "PASS" if all(checks.values()) else "NOT_QUALIFIED",
        "numerical_status": "PASS" if all(checks.values()) else "NOT_QUALIFIED", "checks": checks,
        "protocol_id": p11.A_PROTOCOL, "state_energies_hartree": energies, **values,
        **{key.replace("_hartree", "_kcal_mol"): value*KCAL for key, value in values.items()},
        "GE2_multiplicity": 2, "GE3": "C2v_SYMMETRY_EQUIVALENT_TO_GE2",
        "aromatic_ESE_label": False,
        "printed_reference_comparison": {"status": "PASS" if abs(difference) <= tolerance else "OUTSIDE_FROZEN_TOLERANCE",
            "reference_LDE_kcal_mol": reference, "tolerance_kcal_mol": tolerance,
            "difference_kcal_mol": difference, "source_value_is_fit_target": False,
            "external_experimental_validation": False}}


def _p11_b(rows, root):
    protocol = p11._protocols(root)[1]
    checks, energies, records = {}, {}, {}
    tolerance = protocol["acceptance"]
    for system, state in p11._B_STATES:
        identifier = "P11B-"+system+"-"+state
        row, source = rows[identifier], rows[identifier]["source_record"]
        name = system+"_"+state
        records[name] = source
        energies[name] = _number(source["final_energy_hartree"])
        checks[name+"_source_protocol"] = row.get("protocol_id") == p11.B_PROTOCOL
        checks[name+"_state_identity"] = source.get("system") == system and source.get("state") == state
        checks[name+"_optimizer_converged"] = source.get("optimizer_converged") is True
        checks[name+"_final_scf_converged"] = source.get("final_scf_converged") is True
        checks[name+"_source_gate"] = source.get("pass") is True
        checks[name+"_hard_planarity"] = _number(source["geometry"]["maximum_absolute_z_angstrom"]) <= _number(tolerance["maximum_absolute_z_angstrom"])
        checks[name+"_physical_hcore_retained"] = source.get("one_electron_matrix_masked") is False
        expected = "ordinary_RKS" if state == "G" else "interfragment_pi_Fock_and_overlap_zeroed_each_SCF_iteration"
        checks[name+"_operator_semantics"] = source.get("conditional_semantics") == expected
    e = energies
    whole_delta = e["cyanobenzene_G"]-e["cyanobenzene_GL_I"]
    whole_terms = {state: e["cyanobenzene_"+state]-e["cyanobenzene_GL_I"] for state in ("GE1", "GE2", "GE3")}
    benzene_delta = e["benzene_G"]-e["benzene_GL"]
    benzene_term = e["benzene_GE1"]-e["benzene_GL"]
    phenyl_terms = {state: e["cyanobenzene_"+state]-e["cyanobenzene_GL_II"] for state in ("GE4", "GE5", "GE6", "GE7")}
    sb, bz = whole_delta-sum(whole_terms.values()), benzene_delta-3.0*benzene_term
    ph = phenyl_terms["GE7"]-sum(phenyl_terms[state] for state in ("GE4", "GE5", "GE6"))
    values = {"ESE_cyanobenzene_whole_system_hartree": sb, "ESE_benzene_hartree": bz,
        "ESE_cyanobenzene_isolated_phenyl_hartree": ph,
        "conjugative_effect_hartree": sb-ph, "inductive_effect_hartree": ph-bz}
    checks.update(whole_system_ESE_negative=sb < 0.0, conjugative_effect_positive=sb-ph > 0.0,
                  isolated_phenyl_less_stabilizing_than_benzene=ph > bz, inductive_effect_positive=ph-bz > 0.0)
    comparisons = {}
    reference_keys = {"ESE_cyanobenzene_whole_system_hartree": "cyanobenzene_whole_system_ESE",
        "ESE_benzene_hartree": "benzene_ESE",
        "ESE_cyanobenzene_isolated_phenyl_hartree": "cyanobenzene_isolated_phenyl_ESE",
        "conjugative_effect_hartree": "conjugative_effect", "inductive_effect_hartree": "inductive_effect"}
    for key, value in values.items():
        ref = _number(tolerance[reference_keys[key]+"_reference_kcal_mol"])
        threshold = _number(tolerance["ESE_tolerance_kcal_mol" if key.startswith("ESE_") else key.replace("_hartree", "_tolerance_kcal_mol")])
        difference = value*KCAL-ref
        comparisons[key.replace("_hartree", "_kcal_mol")] = {"reference": ref, "difference": difference,
            "tolerance": threshold, "within_frozen_tolerance": abs(difference) <= threshold}
    drift = max(max(abs(math.dist(source["initial_atoms_angstrom"][i][1:4], source["initial_atoms_angstrom"][(i+1)%6][1:4])
        - _number(source["geometry"]["ring_bonds_angstrom"][i])) for i in range(6)) for source in records.values())
    return {"status": "PASS" if all(checks.values()) else "NOT_QUALIFIED",
        "numerical_status": "PASS" if all(checks.values()) else "NOT_QUALIFIED", "checks": checks,
        "protocol_id": p11.B_PROTOCOL, "state_energies_hartree": energies,
        "cyanobenzene_delta_EA_hartree": whole_delta, "cyanobenzene_SB_increments_hartree": whole_terms,
        "benzene_delta_EA_hartree": benzene_delta, "benzene_delta_EA1_hartree": benzene_term,
        "cyanobenzene_ph_increments_hartree": phenyl_terms, **values,
        **{key.replace("_hartree", "_kcal_mol"): value*KCAL for key, value in values.items()},
        "source_start_diagnostic": {"observed_maximum_ring_bond_change_angstrom": drift,
            "registered_threshold_angstrom": _number(tolerance["maximum_source_heavy_bond_change_angstrom"]),
            "within_registered_threshold": drift <= _number(tolerance["maximum_source_heavy_bond_change_angstrom"]),
            "disposition": "NONBLOCKING_SOURCE_START_DIAGNOSTIC", "threshold_relaxed": False},
        "printed_reference_comparison": {"status": "PASS" if all(value["within_frozen_tolerance"] for value in comparisons.values()) else "OUTSIDE_FROZEN_TOLERANCE",
            "values": comparisons, "source_values_are_fit_targets": False, "external_experimental_validation": False},
        "historical_fixed_geometry_proxy_status": "PRESERVED_HISTORICAL_SUPERSEDED_DIAGNOSTIC"}


def _safe_artifact(directory, relative, hashes):
    if not isinstance(relative, str):
        raise ValueError("Artifact path must be relative text")
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or ":" in relative or "\\" in relative:
        raise ValueError("Artifact path escapes output")
    base = Path(directory).resolve()
    path = base / part
    if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(base)
            or any(parent.is_symlink() for parent in path.parents if parent != base.parent)):
        raise ValueError("Artifact is missing, symbolic or outside output")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if hashes.get(part.as_posix()) != digest:
        raise ValueError("Current geometry/source artifact hash differs")
    return path, digest


def _current_xyz(identifier, row, output_dirs, source_root):
    if identifier not in output_dirs:
        raise ValueError("Current N12 geometry output was not provided: "+identifier)
    directory = Path(output_dirs[identifier]).resolve()
    if directory.is_relative_to(Path(source_root).resolve()):
        raise ValueError("Frozen source XYZ cannot be current optimization evidence")
    source = row["source_result"]
    hashes = row.get("artifacts")
    if not isinstance(hashes, dict):
        raise ValueError("Current P12 artifacts need verified hash entries")
    path, source_digest = _safe_artifact(directory, row["source_result_path"], hashes)
    if p12._json_file(path) != source:
        raise ValueError("Saved current source result differs from supplied row")
    relative = (Path("work") / source["optimized_xyz"]).as_posix()
    xyz_path, xyz_digest = _safe_artifact(directory, relative, hashes)
    atoms = p12._xyz(xyz_path)
    if [atom[0] for atom in atoms] != ["C"]*12+["H"]*12:
        raise ValueError("N12 current XYZ atom order changed")
    if max(abs(_number(atom[3])) for atom in atoms) > 1.0e-8:
        raise ValueError("N12 current XYZ is not planar")
    return atoms, {"unit_id": identifier, "source_result_sha256": source_digest, "xyz_sha256": xyz_digest}


def _distance_residual(reference, control, shift):
    permutation = [(i+shift)%12 for i in range(12)] + [12+(i+shift)%12 for i in range(12)]
    return max(abs(math.dist(reference[i][1:], reference[j][1:])
        - math.dist(control[permutation[i]][1:], control[permutation[j]][1:]))
        for i in range(24) for j in range(24))


def _n12_weighting(rows, root, output_dirs):
    manifest = p12._json(root, p12.STATE_DIR+"/N12_GE_pair_orbits.json")
    tolerance = _number(manifest["acceptance_tolerance_angstrom"])
    energy_tolerance = _number(manifest["symmetry_control"]["maximum_energy_difference_kcal_mol"])
    control_tolerance = _number(manifest["symmetry_control"]["maximum_mapped_distance_matrix_residual_angstrom"])
    expected_pairs = p12.N12_PAIRS
    members = []
    for pair in expected_pairs:
        orbit = {tuple(sorted(((pair[0]+shift)%6, (pair[1]+shift)%6))) for shift in (0, 2, 4)}
        if len(orbit) != 3:
            raise ValueError("N12 orbit weight is not three")
        members.extend(orbit)
    checks = {"all_15_pairs_covered_once": sorted(members) == list(itertools.combinations(range(6), 2)),
        "frozen_symmetry_thresholds": tolerance == .002 and energy_tolerance == .02 and control_tolerance == .002,
        "control_excluded_from_weighted_energy": True}
    result = {"status": "BLOCKED_NOT_VERIFIED", "checks": checks,
        "representative_weight": 3, "control_weight": 0, "weighted_pair_count": 15,
        "geometry_tolerance_angstrom": tolerance, "control_energy_tolerance_kcal_mol": energy_tolerance,
        "failure_action": "STOP_NO_WEIGHTED_LEDGER", "new_GL_geometry_required": True}
    if output_dirs is None:
        result["reason"] = "Current verified GL and representative/control XYZ are required; row dictionaries cannot prove geometric symmetry"
        return result
    identifiers = ("P12-N12-GL", "P12-N12-GE-g01-g02", "P12-N12-GE-g03-g04-control")
    try:
        geometry, evidence = {}, []
        for identifier in identifiers:
            geometry[identifier], provenance = _current_xyz(identifier, rows[identifier], output_dirs, root)
            evidence.append(provenance)
        gl = geometry[identifiers[0]]
        gl_residuals = {str(shift): _distance_residual(gl, gl, shift) for shift in (4, 8)}
        control_residual = _distance_residual(geometry[identifiers[1]], geometry[identifiers[2]], 4)
        energy_difference = abs(_number(rows[identifiers[1]]["source_result"]["final_energy_hartree"])
            - _number(rows[identifiers[2]]["source_result"]["final_energy_hartree"]))*KCAL
        checks.update(new_GL_C3_geometry=all(value <= tolerance for value in gl_residuals.values()),
            independent_control_geometry=control_residual <= control_tolerance,
            independent_control_energy=energy_difference <= energy_tolerance)
        result.update(status="PASS" if all(checks.values()) else "NOT_QUALIFIED",
            GL_distance_matrix_residuals_angstrom=gl_residuals,
            control_distance_matrix_residual_angstrom=control_residual,
            control_energy_difference_kcal_mol=energy_difference, current_geometry_artifacts=evidence)
    except (KeyError, ValueError, OSError, TypeError) as error:
        result.update(status="BLOCKED_NOT_VERIFIED", reason=str(error))
    return result


def _p12_system(n, rows, root, output_dirs):
    base, _ = p12._contracts(root)
    selected = [unit for unit in registered_units() if unit["case"] == "P12" and unit["system"] == f"N{n}"]
    checks, energies = {}, {}
    for unit in selected:
        source = rows[unit["id"]]["source_result"]
        key = unit["id"]
        energies[key] = _number(source["final_energy_hartree"])
        checks[key+"_source_pass"] = source.get("pass") is True and source.get("optimizer_converged") is True
        checks[key+"_configuration_identity"] = (source.get("N") == n and source.get("configuration") == p12.CONFIGURATIONS[n]
            and source["geometry"].get("configuration_identity_preserved") is True)
        checks[key+"_hard_planarity"] = _number(source["geometry"]["maximum_absolute_z_angstrom"]) <= _number(base["geometry_contract"]["maximum_absolute_z_angstrom"])
        checks[key+"_source_protocol"] = source.get("protocol_id") == unit["source_protocol_id"]
        if unit["state"] == "G":
            checks[key+"_source_method"] = source.get("method") == p12.METHOD
            checks[key+"_SCF"] = source.get("final_scf_converged") is True
        else:
            checks[key+"_source_method"] = source.get("geometry_method") == source.get("energy_method") == p12.METHOD
            checks[key+"_SCF"] = source.get("geometry_scf_converged") is True and source.get("energy_scf_converged") is True
            checks[key+"_pair_identity"] = source.get("pair_zero_based") == unit["pair"]
    prefix = f"P12-N{n}"
    eg, egl = energies[prefix+"-G"], energies[prefix+"-GL"]
    pair_rows, adjacent, nonadjacent = [], [], []
    for unit in selected:
        if unit["state"] != "GE" or unit.get("symmetry_control"):
            continue
        first, second = unit["pair"]
        distance = min(second-first, n//2-(second-first))
        pair_class = "adjacent" if distance == 1 else "nonadjacent"
        increment = energies[unit["id"]]-egl
        weight = 3 if n == 12 else 1
        if unit["multiplicity"] != weight:
            raise ValueError("Frozen pair multiplicity differs")
        (adjacent if distance == 1 else nonadjacent).append(increment*weight)
        pair_rows.append({"unit_id": unit["id"], "pair_zero_based": unit["pair"], "pair_class": pair_class,
            "multiplicity": weight, "GE_energy_hartree": energies[unit["id"]],
            "delta_pair_hartree": increment, "delta_pair_kcal_mol": increment*KCAL})
    weight_total = sum(row["multiplicity"] for row in pair_rows)
    checks["all_pairs_and_original_weights"] = weight_total == math.comb(n//2, 2)
    delta, adjacent_total, nonadjacent_total = eg-egl, math.fsum(adjacent), math.fsum(nonadjacent)
    ese, cese = delta-adjacent_total, delta-adjacent_total-nonadjacent_total
    expanded = eg-math.fsum(row["GE_energy_hartree"]*row["multiplicity"] for row in pair_rows)+(weight_total-1)*egl
    checks["expanded_CESE_identity"] = abs(cese-expanded) <= 1.0e-10
    values = {"delta_EA_kcal_mol": delta*KCAL, "sum_delta_EAm_kcal_mol": adjacent_total*KCAL,
        "ESE_kcal_mol": ese*KCAL, "sum_delta_EnAm_kcal_mol": nonadjacent_total*KCAL,
        "CESE_kcal_mol": cese*KCAL, "CESE_per_pi_kcal_mol_electron": cese*KCAL/n}
    printed = p12._json(root, f"data/processed/p12_source2011_same_basis_n{n}_ledger_v0.2.json")["source_printed_values"]
    differences = {key: value-_number(printed[key]) for key, value in values.items()}
    result = {"system": f"N{n}", "configuration": p12.CONFIGURATIONS[n], "checks": checks,
        "source_protocol_id": p12.N16_PROTOCOL if n == 16 else p12.BASE_PROTOCOL,
        "state_energies_hartree": energies, "pair_rows": pair_rows, "weighted_pair_count": weight_total,
        "ledger_hartree": {"E_G": eg, "E_GL": egl, "delta_EA": delta,
            "sum_delta_EAm": adjacent_total, "sum_delta_EnAm": nonadjacent_total, "ESE": ese, "CESE": cese},
        "candidate_ledger": values,
        "printed_reference_comparison": {"status": "DIFFERENCES_DISCLOSED_NO_FROZEN_EXACT_MATCH_TOLERANCE",
            "source_printed_values": printed, "current_minus_source": differences,
            "same_CESE_direction": cese*_number(printed["CESE_kcal_mol"]) > 0.0,
            "source_values_are_fit_targets": False, "exact_numeric_reproduction_claimed": False,
            "external_experimental_validation": False}}
    if n == 12:
        weighting = _n12_weighting(rows, root, output_dirs)
        result["N12_weighting"] = weighting
        result["weighted_ledger_accepted"] = weighting["status"] == "PASS"
        if weighting["status"] != "PASS":
            result["candidate_ledger_scope"] = "UNACCEPTED_ARITHMETIC_PREVIEW_UNTIL_CURRENT_GEOMETRY_SYMMETRY_IS_VERIFIED"
        result["numerical_status"] = "PASS" if all(checks.values()) and weighting["status"] == "PASS" else weighting["status"] if all(checks.values()) else "NOT_QUALIFIED"
    else:
        result["numerical_status"] = "PASS" if all(checks.values()) else "NOT_QUALIFIED"
    if n == 16:
        denominator = abs(adjacent_total+nonadjacent_total)
        relative = abs(cese)/denominator if denominator > 0.0 else None
        checks["relative_CESE_denominator_nonzero"] = denominator > 0.0
        if denominator == 0.0:
            result["numerical_status"] = "NOT_QUALIFIED"
        result["N16_relative_CESE"] = {"value": relative, "frozen_boundary_threshold": .10,
            "below_registered_threshold": relative is not None and relative <= .10,
            "scope": "SCOPED_BOUNDARY_DIAGNOSTIC_NOT_UNIVERSAL_ONSET_LAW"}
    result["status"] = result["numerical_status"]
    return result


def assemble(case, rows, *, output_dirs=None, source_root=ASSETS, engineering_test=False):
    """Assemble only a fixed case's complete current/live state subset.

``rows`` contains parsed current result.json dictionaries. The caller verifies
worker receipts. ``output_dirs`` additionally supplies current artifact roots
for the N12 geometric weighting gate. This function writes no files.
    """
    if case not in ("P11", "P12") or not isinstance(rows, dict):
        raise ValueError("A fixed P11/P12 case and unitID-to-result mapping are required")
    if type(engineering_test) is not bool or (output_dirs is not None and not isinstance(output_dirs, dict)):
        raise ValueError("Explicit engineering boolean and optional artifact mapping required")
    registry = {unit["id"]: unit for unit in registered_units()}
    expected = [identifier for identifier, unit in registry.items() if unit["case"] == case]
    unknown = sorted(str(identifier) for identifier in rows if identifier not in registry)
    present = {identifier: row for identifier, row in rows.items() if identifier in expected}
    rejected, eligible, identity_mismatches = {}, {}, {}
    engineering = engineering_test or any(isinstance(row, dict) and _fake(row) for row in present.values())
    baseline = None
    for identifier, row in present.items():
        errors = _row_errors(identifier, row, registry[identifier], engineering_test)
        if isinstance(row, dict) and not _identity_errors(row):
            identity = {key: row[key] for key in _IDENTITY}
            if baseline is None:
                baseline = identity
            changed = [key for key in _IDENTITY if identity[key] != baseline[key]]
            if changed:
                errors.append("MIXED_SOURCE_DEPENDENCIES_PROFILE_OR_IMAGE")
                identity_mismatches[identifier] = changed
        if errors:
            rejected[identifier] = errors
        else:
            eligible[identifier] = row
    result = {"schema": "high-cost-current-state-assembly-v1", "case": case,
        "required_unit_count": len(expected), "registered_total_unit_count": len(registry),
        "present_unit_count": len(present), "eligible_current_unit_count": len(eligible),
        "missing_units": sorted(set(expected)-set(present)), "rejected_units": rejected,
        "unknown_units": unknown, "identity_mismatches": identity_mismatches,
        "shared_execution_identity": baseline, "engineering_test": engineering,
        "source_scope": "CURRENT_FIXED_P11_17_STATES" if case == "P11" else "CURRENT_SAME_BASIS_N12_N14_N16_61_STATES",
        "receipts_verification": "HOST_CALLER_MUST_VERIFY_REAL_WORKER_RECEIPTS_BEFORE_THIS_API",
        "operators": {identifier: {"method_id": registry[identifier]["method_id"],
            "operator_id": registry[identifier]["operator_id"], "dependencies": registry[identifier]["dependencies"],
            "operator_identity_authority": "FIXED_PROFILE_AND_CALLER_VERIFIED_WORKER_RECEIPT"} for identifier in present},
        "new_optimization_executed_by_assembly": False, "new_quantum_computation_executed_by_assembly": False,
        "external_experimental_validation": False, "historical_scientific_verdict_changed": False,
        "classification_change_allowed": False, "public_classification_changed": False,
        "production_label": False, "training_eligible": False, "new_scientific_acceptance": False,
        "new_numerical_assembly_accepted": False, "subcases": {}}
    groups = ([("P11-A", [identifier for identifier in expected if identifier.startswith("P11A-")]),
               ("P11-B", [identifier for identifier in expected if identifier.startswith("P11B-")])]
              if case == "P11" else [(f"N{n}", [identifier for identifier in expected if registry[identifier]["system"] == f"N{n}"]) for n in (12, 14, 16)])
    for name, identifiers in groups:
        value = _sub_result(identifiers, eligible)
        if value["status"] == "READY" and not unknown and not identity_mismatches:
            try:
                value.update(_p11_a(eligible, source_root) if name == "P11-A" else
                    _p11_b(eligible, source_root) if name == "P11-B" else
                    _p12_system(int(name[1:]), eligible, source_root, output_dirs))
            except (KeyError, ValueError, TypeError, OSError) as error:
                value.update(status="NOT_QUALIFIED", numerical_status="NOT_QUALIFIED", error=str(error))
        result["subcases"][name] = value
    complete = not result["missing_units"] and not rejected and not unknown and not identity_mismatches
    numerical = complete and all(value.get("numerical_status") == "PASS" for value in result["subcases"].values())
    source_comparison = (case == "P11" and numerical and all(value["printed_reference_comparison"]["status"] == "PASS" for value in result["subcases"].values()))
    result["complete_current_case"] = complete
    result["numerical_status"] = "PASS" if numerical else "BLOCKED_INCOMPLETE" if not complete else "NOT_QUALIFIED"
    result["scientific_status"] = "NOT_EXECUTED" if engineering else "SCOPED_P11_ACCEPTED" if source_comparison else "SCOPED_SAME_BASIS_LEDGER_ONLY" if case == "P12" and numerical else "NOT_QUALIFIED"
    result["new_numerical_assembly_accepted"] = numerical and not engineering
    result["new_scientific_acceptance"] = source_comparison and not engineering
    result["status"] = ("ENGINEERING_ONLY" if engineering and numerical else "PASS" if numerical and (case == "P12" or source_comparison)
                        else "BLOCKED_INCOMPLETE" if not complete else "NOT_QUALIFIED")
    if case == "P12":
        result.update(historical_2011_method_alignment="NOT_ESTABLISHED",
            electronic_state_continuity="NOT_PROVEN_BY_CURRENT_RUNNER",
            universal_annulene_boundary_claim=False,
            full_six_size_source_panel_completed=False)
    if engineering:
        result["new_scientific_acceptance"] = False
        result["new_numerical_assembly_accepted"] = False
    json.dumps(result, allow_nan=False)
    return result
