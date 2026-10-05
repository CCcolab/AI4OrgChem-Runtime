"""V2 molecular bridge; ordinary v1 unchanged, conditional independently v2."""
import json
import math
import numpy as np
from scipy.linalg import eigvalsh
from reference import user_molecule_v2 as conditional
from reference import user_molecule as raw_reference
from reference.ordinary_molecule import (run_ordinary, ReferenceResult, array_identity,
    FINAL_OPERATOR, _metric)

def run_conditional(ordinary, rule_path, expected_sha256, settings=None, progress=lambda phase: None):
    """Independent complete molecular fixed point from frozen ordinary D.

    This does not reuse the tested implementation's AO mask, operators, energy,
    occupation or iteration helpers. Shared raw integral/XC errors remain out
    of scope. Stopping criteria do not establish research qualification.
    """
    context, arrays = ordinary.context, ordinary.arrays
    profile = context.profile
    entries = raw_reference.load_rules(rule_path, expected_sha256)
    for key in ("density", "hcore", "overlap", "eri", "grid_coords", "grid_weights"):
        if array_identity(arrays[key]) != ordinary.record["array_identities"][key]:
            raise ValueError("Frozen ordinary array changed: " + key)
    if (array_identity(context.mean_field.grids.coords) != ordinary.record["array_identities"]["grid_coords"]
            or array_identity(context.mean_field.grids.weights) != ordinary.record["array_identities"]["grid_weights"]):
        raise ValueError("Original frozen grid changed before conditional reference")
    xc, hybrid = raw_reference.original_grid_xc(context.mean_field)
    progress("CONDITIONAL_REFERENCE")
    evaluated = conditional.fixed_point(density=arrays["density"], h=arrays["hcore"], overlap=arrays["overlap"],
        eri=arrays["eri"], aos=context.aos, entries=entries, electrons=int(context.mol.nelectron), hybrid=hybrid,
        nuclear=float(context.mol.energy_nuc()), xc=xc, settings=profile["conditional"] if settings is None else settings, progress=progress)
    exported_arrays = {key: value for key, value in evaluated.items() if isinstance(value, np.ndarray)}
    record = {key: value for key, value in evaluated.items() if not isinstance(value, np.ndarray)}
    progress("CONDITIONAL_RECOMPUTE")
    count = context.mol.nelectron // 2
    final_energies = eigvalsh(exported_arrays["Fcond"], exported_arrays["masked_overlap"], check_finite=True)
    exported_arrays["final_non_diis_eigenvalues_hartree"] = final_energies
    record.update({"final_non_diis_gap_hartree": float(final_energies[count] - final_energies[count-1])
            if count < len(final_energies) else None,
        "final_non_diis_gap_operator_source": FINAL_OPERATOR,
        "initial_density_identity": ordinary.record["array_identities"]["density"],
        "rules_sha256": expected_sha256, "metadata": context.metadata,
        "settings_effective": dict(profile["conditional"] if settings is None else settings),
        "molecular_execution": "EXECUTED_DIAGNOSTIC_NOT_ACCEPTED",
        "molecular_acceptance": "PENDING_ACCEPTANCE_EVALUATION", "research_status": "NOT_QUALIFIED",
        "undefined_diagnostics": [{"field": "history[0].energy_change_hartree", "reason": "NO_PREVIOUS_CYCLE_ENERGY"}],
        "stability_analysis": "NOT_EXECUTED",
        "array_identities": {key: array_identity(value) for key, value in exported_arrays.items()}})
    forbidden = np.array([[left.kind == right.kind == "pi" and left.group != right.group
                           for right in context.aos] for left in context.aos], dtype=bool)
    record["masked_overlap_cross_pi_max_abs"] = float(np.max(np.abs(exported_arrays["masked_overlap"][forbidden]), initial=0))
    record["conditional_fock_cross_pi_max_abs"] = float(np.max(np.abs(exported_arrays["Fcond"][forbidden]), initial=0))
    threshold = profile["thresholds"]
    record["qualification_tests"].update({
        "converged": bool(record["converged"]), "energy_finite": math.isfinite(record["total_energy_hartree"]),
        "electron_count": abs(record["masked_metric_electron_count"] - context.mol.nelectron) <= threshold["electron_count_abs"],
        "commutator": record["final_commutator_frobenius_norm"] <= threshold["commutator_frobenius"],
        "idempotency": record["closed_shell_idempotency_relative_residual"] <= threshold["idempotency_relative"],
        "energy_closure": abs(record["energy_component_closure_residual_hartree"]) <= threshold["energy_closure_hartree"],
        "masked_overlap_positive": record["masked_overlap_minimum_eigenvalue"] > 0,
        "overlap_mask": record["masked_overlap_cross_pi_max_abs"] <= threshold["mask_max_abs"],
        "fock_mask": record["conditional_fock_cross_pi_max_abs"] <= threshold["mask_max_abs"],
        "occupation_electron_count": bool(abs(float(exported_arrays["mo_occupations"].sum()) - context.mol.nelectron) <= 1e-12),
        "closed_shell_occupation": bool(np.isin(exported_arrays["mo_occupations"], [0., 2.]).all())})
    descriptions = {
        "masked_metric_electron_count": ("COND_NE", "Tr(S_tilde D)", "electrons", threshold["electron_count_abs"], True, "MASKED_OVERLAP"),
        "physical_metric_electron_count": ("COND_PHYSICAL_NE", "Tr(S D)", "electrons", None, False, "PHYSICAL_OVERLAP"),
        "grid_electron_count": ("COND_GRID_NE", "original_grid nr_rks electron integral", "electrons", None, False, "ORIGINAL_AO_GRID"),
        "final_commutator_frobenius_norm": ("COND_COMM", "||F_cond D S_tilde - S_tilde D F_cond||F", "AO_matrix_units", threshold["commutator_frobenius"], True, FINAL_OPERATOR),
        "closed_shell_idempotency_relative_residual": ("COND_IDEMP", "||D S_tilde D - 2 D||F / max(||D||F,1)", "AO_density_relative", threshold["idempotency_relative"], True, "MASKED_OVERLAP"),
        "energy_component_closure_residual_hartree": ("COND_CLOSE", "abs(sum(five components) - returned functional energy)", "hartree", threshold["energy_closure_hartree"], True, "CONDITIONAL_FIXED_POINT_FUNCTIONAL"),
        "masked_overlap_cross_pi_max_abs": ("COND_S_MASK", "max(abs(S_tilde[forbidden_pi_blocks]))", "dimensionless_AO_overlap", threshold["mask_max_abs"], True, "MASKED_OVERLAP"),
        "conditional_fock_cross_pi_max_abs": ("COND_F_MASK", "max(abs(F_cond[forbidden_pi_blocks]))", "hartree_AO_matrix", threshold["mask_max_abs"], True, FINAL_OPERATOR),
        "masked_overlap_minimum_eigenvalue": ("COND_S_MIN", "min(eigvalsh(S_tilde))", "dimensionless_AO_overlap", 0., True, "MASKED_OVERLAP"),
        "masked_overlap_condition_number": ("COND_S_KAPPA", "cond_2(S_tilde)", "dimensionless", None, False, "MASKED_OVERLAP"),
        "occupied_virtual_gap_hartree": ("COND_GAP_RETURNED_RAW", "eig(F_cond at returned D,S_tilde)[N/2] - eig(F_cond at returned D,S_tilde)[N/2-1]", "hartree", None, False, record["gap_operator_source"]),
        "final_non_diis_gap_hartree": ("COND_GAP_FINAL", "eig(F_cond,S_tilde)[N/2] - eig(F_cond,S_tilde)[N/2-1]", "hartree", None, False, FINAL_OPERATOR)}
    record["metric_metadata"] = {name: _metric(metric_id, record[name], formula, units, bound, required, operator, profile)
        for name, (metric_id, formula, units, bound, required, operator) in descriptions.items()}
    record["undefined_diagnostics"] = [] if count < len(final_energies) else [
        {"field": "occupied_virtual_gap_hartree", "reason": "NO_VIRTUAL_ORBITALS"},
        {"field": "final_non_diis_gap_hartree", "reason": "NO_VIRTUAL_ORBITALS"}]
    json.dumps(record, allow_nan=False)
    return ReferenceResult(record, exported_arrays, context)
