"""Bounded candidate solver: frozen P09 equations, stricter endpoint acceptance.

This opt-in runtime adapter does not replace the frozen scientific kernel or
activate a production profile.  Global 2/0 Aufbau occupancy is retained.  A
small DIIS step is only a *candidate* stop, never evidence of a true fixed point.
The returned raw-F orbitals are diagnostics and are not silently substituted
for an unqualified returned density.  All qualification thresholds retain the
existing profile/acceptance-contract values; none is relaxed by this strategy.
"""
from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any

import numpy as np
from scipy.linalg import eigh


SOLVER_ID = "P09_RUNTIME_ENDPOINT_CHECKED_SOLVER_CANDIDATE_V2"
ENDPOINT_THRESHOLDS = MappingProxyType({
    "commutator_frobenius": 1.0e-5,
    "electron_count_abs": 1.0e-7,
    "idempotency_relative": 1.0e-7,
    "energy_closure_hartree": 1.0e-9,
    "mask_max_abs": 1.0e-12,
    "mapped_density_relative": 2.0e-8,
    "final_non_diis_gap_minimum_hartree": 1.0e-6,
})
RAW_REFINEMENT_CYCLES = 2


def _subspace_change(left: np.ndarray | None, right: np.ndarray,
                     overlap: np.ndarray, occupied: int) -> float | None:
    """Distance of metric occupied projectors; invariant to MO signs/rotations."""
    if left is None:
        return None
    cross = left[:, :occupied].T @ overlap @ right[:, :occupied]
    squared = 2.0 * occupied - 2.0 * float(np.sum(cross * cross))
    return float(np.sqrt(max(squared, 0.0)))


def _aufbau(fock: np.ndarray, overlap: np.ndarray, electrons: int):
    energies, coefficients = eigh(fock, overlap, check_finite=True)
    occupations = np.zeros(len(energies))
    occupations[:electrons // 2] = 2.0
    mapped = (coefficients * occupations) @ coefficients.T
    mapped = (mapped + mapped.T) * 0.5
    return energies, coefficients, occupations, mapped


def endpoint_gate(*, density: np.ndarray, fock: np.ndarray, overlap: np.ndarray,
                  electrons: int, energy_closure_hartree: float,
                  overlap_mask_max_abs: float = 0.0,
                  fock_mask_max_abs: float = 0.0) -> dict[str, Any]:
    """Pure array endpoint check using the *true*, freshly evaluated F(D).

    No DIIS operator is accepted here.  A commuting excited determinant is
    rejected when its density disagrees with raw-F global Aufbau occupation.
    Nonfinite/indefinite inputs return an explicit failed gate, never PASS.
    """
    d, f, s = [np.asarray(value, dtype=float) for value in (density, fock, overlap)]
    n = d.shape[0] if d.ndim == 2 else 0
    if type(electrons) is not int or electrons < 2 or electrons % 2:
        raise ValueError("Candidate requires a positive even closed-shell electron count")
    if d.shape != (n, n) or f.shape != d.shape or s.shape != d.shape or electrons > 2*n:
        raise ValueError("Endpoint array/electron dimensions differ")
    names = ("finite", "overlap_positive", "commutator", "electron_count", "idempotency",
             "energy_closure", "overlap_mask", "fock_mask", "mapped_density", "raw_gap")
    checks = dict.fromkeys(names, False)
    result = {"qualified": False, "checks": checks, "reasons": [],
        "operator_source": "RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS",
        "thresholds": dict(ENDPOINT_THRESHOLDS),
        "final_commutator_frobenius_norm": None,
        "masked_metric_electron_count": None,
        "closed_shell_idempotency_relative_residual": None,
        "energy_component_closure_residual_hartree": None,
        "mapped_density_relative_residual": None,
        "final_non_diis_gap_hartree": None,
        "raw_mo_energies_hartree": None, "raw_mo_coefficients": None,
        "raw_mo_occupations": None, "mapped_density": None}
    scalar_inputs = [energy_closure_hartree, overlap_mask_max_abs, fock_mask_max_abs]
    if not all(np.isfinite(matrix).all() for matrix in (d, f, s)) or not np.isfinite(scalar_inputs).all():
        result["reasons"] = ["NONFINITE_ENDPOINT"]
        return result
    checks["finite"] = True
    if any(not np.allclose(matrix, matrix.T, rtol=0, atol=1.0e-12) for matrix in (d, f, s)):
        result["reasons"] = ["NONSYMMETRIC_ENDPOINT"]
        return result
    try:
        minimum = float(np.linalg.eigvalsh(s).min())
        if minimum <= 0:
            result["reasons"] = ["MASKED_OVERLAP_NOT_POSITIVE"]
            return result
        checks["overlap_positive"] = True
        energies, coefficients, occupations, mapped = _aufbau(f, s, electrons)
    except np.linalg.LinAlgError:
        result["reasons"] = ["RAW_GENERALIZED_EIGENSOLVE_FAILED"]
        return result
    commutator = float(np.linalg.norm(f @ d @ s - s @ d @ f, ord="fro"))
    count = float(np.sum(s*d.T))
    idempotency = float(np.linalg.norm(d @ s @ d - 2*d, ord="fro") / max(np.linalg.norm(d, ord="fro"), 1.0))
    mapped_residual = float(np.linalg.norm(mapped-d, ord="fro") / max(np.linalg.norm(mapped, ord="fro"), 1.0))
    occupied = electrons // 2
    gap = float(energies[occupied]-energies[occupied-1]) if occupied < n else None
    result.update({"final_commutator_frobenius_norm": commutator,
        "masked_metric_electron_count": count,
        "closed_shell_idempotency_relative_residual": idempotency,
        "energy_component_closure_residual_hartree": abs(float(energy_closure_hartree)),
        "mapped_density_relative_residual": mapped_residual,
        "final_non_diis_gap_hartree": gap,
        "raw_mo_energies_hartree": energies, "raw_mo_coefficients": coefficients,
        "raw_mo_occupations": occupations, "mapped_density": mapped})
    derived = [commutator, count, idempotency, mapped_residual, *energies]
    if gap is not None:
        derived.append(gap)
    if not np.isfinite(derived).all() or not np.isfinite(coefficients).all() or not np.isfinite(mapped).all():
        checks["finite"] = False
        result["reasons"] = ["NONFINITE_DERIVED_ENDPOINT"]
        return result
    limits = ENDPOINT_THRESHOLDS
    checks.update({"commutator": commutator <= limits["commutator_frobenius"],
        "electron_count": abs(count-electrons) <= limits["electron_count_abs"],
        "idempotency": idempotency <= limits["idempotency_relative"],
        "energy_closure": abs(energy_closure_hartree) <= limits["energy_closure_hartree"],
        "overlap_mask": abs(overlap_mask_max_abs) <= limits["mask_max_abs"],
        "fock_mask": abs(fock_mask_max_abs) <= limits["mask_max_abs"],
        "mapped_density": mapped_residual <= limits["mapped_density_relative"],
        "raw_gap": gap is not None and gap >= limits["final_non_diis_gap_minimum_hartree"]})
    result["qualified"] = all(checks.values())
    result["reasons"] = [key.upper()+"_FAILED" for key, passed in checks.items() if not passed]
    if gap is None:
        result["reasons"].append("NO_VIRTUAL_ORBITAL_RAW_GAP_UNDEFINED")
    if not checks["raw_gap"]:
        result["reasons"].append("ROOT_AMBIGUOUS")
    return result


def _endpoint_record(gate: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in gate.items()
            if key not in {"raw_mo_energies_hartree", "raw_mo_coefficients", "raw_mo_occupations", "mapped_density"}}


def _component_closure(value: dict[str, Any]) -> float:
    return abs(sum(float(value[key]) for key in ("one_electron_energy", "coulomb_energy",
        "exact_exchange_energy", "semilocal_xc_energy", "nuclear_repulsion")) - float(value["total_energy"]))


def iterate_candidate(*, initial_density: np.ndarray, overlap: np.ndarray, electrons: int,
                      evaluate: Callable, diis_factory: Callable,
                      maximum_cycles: int = 100, density_tolerance: float = 2.0e-8,
                      energy_tolerance: float = 1.0e-9, diis_start_cycle: int = 2,
                      diis_space: int = 8, damping_cycles: int = 2, damping: float = 0.20,
                      matrix_delete_mask: np.ndarray | None = None,
                      progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Bounded generic iteration; toy evaluators make false-stop tests possible.

    Only a legacy small-step *and* a qualified fresh endpoint can stop.  A false
    plateau or arithmetic DIIS refusal clears DIIS; when iteration continues,
    the next two cycles use raw F.  There is
    no MOM, fractional occupancy, fragment electron constraint or level shift.
    Evaluation bound is two per cycle plus one final check, at most 201.
    """
    if type(maximum_cycles) is not int or not 1 <= maximum_cycles <= 100:
        raise ValueError("Candidate cycle bound must be an integer in [1, 100]")
    if type(diis_start_cycle) is not int or diis_start_cycle < 1 or type(diis_space) is not int or diis_space < 1:
        raise ValueError("Invalid DIIS settings")
    if type(damping_cycles) is not int or damping_cycles < 0 or not np.isfinite(damping) or not 0 <= damping < 1:
        raise ValueError("Invalid frozen damping settings")
    if not np.isfinite(density_tolerance) or not 0 < density_tolerance <= 2e-8:
        raise ValueError("Density tolerance cannot relax the frozen criterion")
    if not np.isfinite(energy_tolerance) or not 0 < energy_tolerance <= 1e-9:
        raise ValueError("Energy tolerance cannot relax the frozen criterion")
    s = np.asarray(overlap, dtype=float)
    d = np.asarray(initial_density, dtype=float).copy()
    if d.ndim != 2 or d.shape[0] != d.shape[1] or d.shape != s.shape or not np.isfinite(d).all():
        raise ValueError("Invalid initial density")
    if not np.isfinite(s).all() or float(np.linalg.eigvalsh(s).min()) <= 0:
        raise ValueError("Masked metric is not finite positive definite")
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons > 2*len(d):
        raise ValueError("Global closed-shell 2/0 occupancy required")
    mask = np.zeros(d.shape, dtype=bool) if matrix_delete_mask is None else np.asarray(matrix_delete_mask, dtype=bool)
    if mask.shape != d.shape:
        raise ValueError("Matrix deletion mask dimensions differ")
    d = 0.5*(d+d.T)
    diis = diis_factory(diis_space)
    history, evaluations, resets, raw_remaining = [], 0, 0, 0
    arithmetic_resets, plateau_resets = 0, 0
    previous_energy, previous_coefficients, last_candidate_energy = None, None, None
    last_coefficients = last_energies = last_occupations = None
    converged, stop_reason = False, "MAXIMUM_CYCLES_EXHAUSTED"
    def assessed(candidate, value):
        return endpoint_gate(density=candidate, fock=value["fock"], overlap=s,
            electrons=electrons, energy_closure_hartree=_component_closure(value),
            overlap_mask_max_abs=float(np.max(np.abs(s[mask]), initial=0.0)),
            fock_mask_max_abs=float(np.max(np.abs(np.asarray(value["fock"])[mask]), initial=0.0)))
    def do_evaluate(value):
        nonlocal evaluations
        if evaluations >= 2*maximum_cycles+1:
            raise RuntimeError("Candidate evaluation bound exceeded")
        evaluations += 1
        return evaluate(value.copy())
    for cycle in range(1, maximum_cycles+1):
        if progress is not None:
            progress(f"SOLVER_CANDIDATE_V2_CYCLE_{cycle:03d}")
        evaluated = do_evaluate(d)
        f = np.asarray(evaluated["fock"], dtype=float)
        if not np.isfinite(f).all() or not np.isfinite(float(evaluated["total_energy"])):
            stop_reason = "NONFINITE_CURRENT_EVALUATION"
            history.append({"cycle": cycle, "legacy_stop_candidate": False, "endpoint_qualified": False,
                "evaluation_count": evaluations, "reason": stop_reason})
            break
        commutator = f @ d @ s - s @ d @ f
        if not np.isfinite(commutator).all():
            stop_reason = "NONFINITE_CURRENT_COMMUTATOR"
            history.append({"cycle": cycle, "legacy_stop_candidate": False, "endpoint_qualified": False,
                "evaluation_count": evaluations, "reason": stop_reason})
            break
        raw_cycle = raw_remaining > 0
        update_failure = None
        if raw_cycle:
            diagonalized, operator = f, "RAW_F_REFINEMENT"
            raw_remaining -= 1
        elif cycle >= diis_start_cycle:
            try:
                diagonalized = np.asarray(diis.update(f, xerr=commutator), dtype=float)
                operator = "PULAY_DIIS"
            except (np.linalg.LinAlgError, ValueError) as error:
                # Invalid API/shape/configuration errors must remain errors.
                # Only arithmetic solve failure or a specifically unusable
                # extrapolation is recoverable with a finite unchanged raw F.
                if isinstance(error, ValueError) and not isinstance(error, np.linalg.LinAlgError) and str(error) not in {
                    "Unusable affine DIIS coefficients",
                }:
                    raise
                update_failure = {"exception_type": type(error).__name__, "message": str(error)}
                diis, resets = diis_factory(diis_space), resets+1
                arithmetic_resets += 1
                raw_remaining = RAW_REFINEMENT_CYCLES
                diagonalized, operator = f, "RAW_F_DIIS_ARITHMETIC_REFUSAL"
        else:
            diagonalized, operator = f, "RAW_F_BEFORE_DIIS"
        if not np.isfinite(diagonalized).all():
            stop_reason = "NONFINITE_DIAGONALIZATION_OPERATOR"
            history.append({"cycle": cycle, "legacy_stop_candidate": False, "endpoint_qualified": False,
                "evaluation_count": evaluations, "reason": stop_reason})
            break
        energies, coefficients, occupations, candidate = _aufbau(diagonalized, s, electrons)
        residual = float(np.linalg.norm(candidate-d, ord="fro") / max(np.linalg.norm(candidate, ord="fro"), 1.0))
        energy_change = None if previous_energy is None else abs(float(evaluated["total_energy"])-previous_energy)
        legacy_stop = energy_change is not None and residual <= density_tolerance and energy_change <= energy_tolerance
        candidate_value = do_evaluate(candidate)
        last_candidate_energy = float(candidate_value["total_energy"])
        gate = assessed(candidate, candidate_value)
        candidate_energy_change = abs(float(candidate_value["total_energy"])-float(evaluated["total_energy"]))
        reset = bool(legacy_stop and (not gate["qualified"] or not np.isfinite(candidate_energy_change)
                                     or candidate_energy_change > energy_tolerance))
        history.append({"cycle": cycle, "total_energy_hartree": float(evaluated["total_energy"]),
            "candidate_total_energy_hartree": float(candidate_value["total_energy"]),
            "energy_change_hartree": energy_change, "candidate_energy_change_hartree": candidate_energy_change,
            "density_residual": residual, "commutator_frobenius_norm": float(np.linalg.norm(commutator, ord="fro")),
            "masked_metric_electron_count": float(np.sum(s*d.T)),
            "physical_metric_electron_count": evaluated.get("physical_metric_electron_count"),
            "diagonalization_operator": operator, "legacy_stop_candidate": bool(legacy_stop),
            "endpoint_qualified": gate["qualified"], "endpoint": _endpoint_record(gate),
            "true_stop": bool(legacy_stop and gate["qualified"] and candidate_energy_change <= energy_tolerance),
            "diis_reset": bool(reset or update_failure is not None),
            "false_stop_rejected": reset, "diis_update_failure": update_failure,
            "diis_reset_count": resets + int(reset and update_failure is None),
            "evaluation_count": evaluations,
            "occupied_subspace_change_frobenius": _subspace_change(previous_coefficients, coefficients, s, electrons//2),
            "raw_mapped_occupied_subspace_change_frobenius": _subspace_change(coefficients, gate["raw_mo_coefficients"], s, electrons//2)
                if gate["raw_mo_coefficients"] is not None else None})
        last_coefficients, last_energies, last_occupations = coefficients, energies, occupations
        previous_coefficients = coefficients
        if history[-1]["true_stop"]:
            d, converged, stop_reason = candidate, True, "QUALIFIED_TRUE_ENDPOINT"
            break
        if not gate["checks"]["finite"]:
            d, stop_reason = candidate, "NONFINITE_CANDIDATE_ENDPOINT"
            break
        if reset:
            plateau_resets += 1
            if update_failure is None:
                diis, resets = diis_factory(diis_space), resets+1
            raw_remaining = RAW_REFINEMENT_CYCLES
        previous_energy = float(evaluated["total_energy"])
        weight = damping if cycle <= damping_cycles else 0.0
        d = (1-weight)*candidate + weight*d
        d = 0.5*(d+d.T)
    final = do_evaluate(d)
    gate = assessed(d, final)
    final_energy_recheck = abs(float(final["total_energy"])-last_candidate_energy) if converged and last_candidate_energy is not None else None
    if converged and (not gate["qualified"] or not np.isfinite(final_energy_recheck) or final_energy_recheck > energy_tolerance):
        converged, stop_reason = False, "FINAL_RECHECK_FAILED"
    result = {"converged": bool(converged and gate["qualified"]), "cycles": len(history),
        "density": d, "final_evaluation": final, "endpoint_gate": _endpoint_record(gate),
        "history": history, "stop_reason": stop_reason, "solver_id": SOLVER_ID,
        "final_candidate_energy_recheck_hartree": final_energy_recheck,
        "solver_strategy": "TRUE_ENDPOINT_PLATEAU_AND_ARITHMETIC_DIIS_REFUSAL_RAW_TWO_CYCLES_V2_1",
        "solver_revision": "V2.1_ARITHMETIC_DIIS_REFUSAL",
        "diis_implementation": "PYSCF_LIB_DIIS", "diis_reset_count": resets,
        "solver_reset_count": resets, "diis_arithmetic_reset_count": arithmetic_resets,
        "plateau_reset_count": plateau_resets,
        "false_stop_count": sum(bool(row.get("false_stop_rejected")) for row in history),
        "evaluation_count": evaluations, "evaluation_limit": 2*maximum_cycles+1,
        "maximum_cycles": maximum_cycles, "raw_refinement_cycles_after_reset": RAW_REFINEMENT_CYCLES,
        "final_operator_source": "RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS",
        "gap_operator_source": "RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS",
        "mo_diagnostic_role": "FINAL_RAW_F_SPECTRUM_NOT_A_REPLACEMENT_DENSITY",
        "raw_mo_density_matches_returned_density": gate["checks"]["mapped_density"],
        "mapped_density_relative_residual": gate["mapped_density_relative_residual"],
        "final_non_diis_gap_hartree": gate["final_non_diis_gap_hartree"],
        "state_comparability": "ROOT_AMBIGUOUS" if not gate["checks"]["raw_gap"] else
            ("QUALIFIED_RAW_FIXED_POINT" if converged and gate["qualified"] else "NOT_QUALIFIED"),
        "occupied_virtual_gap_hartree": gate["final_non_diis_gap_hartree"],
        "mo_coefficients": gate["raw_mo_coefficients"], "mo_energies_hartree": gate["raw_mo_energies_hartree"],
        "mo_occupations": gate["raw_mo_occupations"], "mapped_density": gate["mapped_density"],
        "last_diagonalization_mo_coefficients": last_coefficients,
        "last_diagonalization_mo_energies_hartree": last_energies,
        "last_diagonalization_mo_occupations": last_occupations,
        "research_status": "NOT_REVIEWED" if converged and gate["qualified"] else "NOT_QUALIFIED",
        "method_review_status": "PENDING_REAL_REVIEW", "production_activation": False,
        "variational_status": "NOT_ESTABLISHED", "stability_status": "NOT_EXECUTED"}
    for key in ("final_commutator_frobenius_norm", "masked_metric_electron_count",
                "closed_shell_idempotency_relative_residual", "energy_component_closure_residual_hartree"):
        result[key] = gate[key]
    result["qualification_tests"] = dict(gate["checks"], converged=result["converged"],
        final_energy_recheck=bool(final_energy_recheck is not None and np.isfinite(final_energy_recheck)
                                  and final_energy_recheck <= energy_tolerance))
    return result


def run_candidate_conditional_rks(mean_field, descriptors, source_entries, *, initial_density,
                                 maximum_cycles=100, density_tolerance=2.0e-8,
                                 energy_tolerance=1.0e-9, diis_start_cycle=2, diis_space=8,
                                 damping_cycles=2, damping=0.20, memory_controlled_eri=False,
                                 progress=None):
    """Opt-in production candidate using the unchanged frozen P09 evaluator.

    ERI preparation and contractions retain both existing storage modes.  The
    frozen source directory is imported read-only; no original file is patched.
    """
    from pyscf import lib
    from ai4orgchem.qm.p09_conditional_scf import _evaluate_density
    from ai4orgchem.qm.p09_ao_classification import (apply_interfragment_pi_matrix_mask,
                                                   interfragment_pi_delete_mask)
    from ai4orgchem.qm.p09_energy_assembly import (apply_eri_tensor_mask,
                                                 apply_eri_tensor_mask_inplace_by_category)
    mol = mean_field.mol
    if mol.spin != 0 or mol.cart:
        raise ValueError("Candidate is limited to spherical closed-shell molecules")
    physical_s = np.asarray(mean_field.get_ovlp(), dtype=float)
    physical_h = np.asarray(mean_field.get_hcore(), dtype=float)
    s = apply_interfragment_pi_matrix_mask(physical_s, descriptors)
    h = apply_interfragment_pi_matrix_mask(physical_h, descriptors)
    eigenvalues = np.linalg.eigvalsh(s)
    if float(eigenvalues.min()) <= 0:
        raise ValueError("Masked metric is not positive definite; no repair permitted")
    physical_eri = np.asarray(mol.intor("int2e_sph", aosym="s1"), dtype=float)
    total_count = int(physical_eri.size)
    if memory_controlled_eri:
        masked_eri = physical_eri
        deleted = apply_eri_tensor_mask_inplace_by_category(masked_eri, descriptors, source_entries)
        storage = "single_tensor_inplace_category_mask"
    else:
        masked_eri, deletion = apply_eri_tensor_mask(physical_eri, descriptors, source_entries)
        deleted = int(np.count_nonzero(deletion))
        del deletion, physical_eri
        storage = "reference_copy_plus_boolean_mask"
    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(mean_field.xc, spin=mol.spin)
    if abs(float(omega)) > 1e-14 or abs(float(alpha)-float(hybrid)) > 1e-14:
        raise ValueError("Only the frozen global hybrid form is supported")
    if getattr(mean_field.grids, "coords", None) is None:
        raise ValueError("Caller must explicitly freeze/build the original grid before acceptance")
    nuclear = float(mol.energy_nuc())
    def evaluator(density):
        value = _evaluate_density(mean_field=mean_field, density=density,
            masked_hcore=h, masked_overlap=s, physical_overlap=physical_s,
            masked_eri=masked_eri, descriptors=descriptors, exact_exchange_fraction=float(hybrid),
            optimize_eri_contractions=not memory_controlled_eri)
        value["nuclear_repulsion"] = nuclear
        return value
    def diis_factory(space):
        instance = lib.diis.DIIS()
        instance.space = space
        return instance
    matrix_mask = interfragment_pi_delete_mask(descriptors)
    value = iterate_candidate(initial_density=initial_density, overlap=s, electrons=int(mol.nelectron),
        evaluate=evaluator, diis_factory=diis_factory, maximum_cycles=maximum_cycles,
        density_tolerance=density_tolerance, energy_tolerance=energy_tolerance,
        diis_start_cycle=diis_start_cycle, diis_space=diis_space,
        damping_cycles=damping_cycles, damping=damping,
        matrix_delete_mask=matrix_mask, progress=progress)
    final = value.pop("final_evaluation")
    value.update({"total_energy_hartree": float(final["total_energy"]),
        "electronic_energy_hartree": float(final["electronic_energy"]),
        "nuclear_repulsion_hartree": nuclear,
        "grid_electron_count": float(final["grid_electron_count"]),
        "physical_metric_electron_count": float(final["physical_metric_electron_count"]),
        "masked_overlap_minimum_eigenvalue": float(eigenvalues.min()),
        "masked_overlap_condition_number": float(np.linalg.cond(s)),
        "masked_overlap_cross_pi_max_abs": float(np.max(np.abs(s[matrix_mask]), initial=0.0)),
        "conditional_fock_cross_pi_max_abs": float(np.max(np.abs(final["fock"][matrix_mask]), initial=0.0)),
        "deleted_eri_count": int(deleted), "total_eri_count": total_count,
        "deleted_eri_fraction": int(deleted)/total_count, "eri_storage_mode": storage,
        "exact_exchange_fraction": float(hybrid), "acceptance_final_F": np.asarray(final["fock"]),
        "frozen_equations": "P09_SOURCE_EVALUATE_DENSITY_UNCHANGED",
        "molecular_acceptance": "NOT_EXECUTED"})
    for key in ("one_electron_energy", "coulomb_energy", "exact_exchange_energy", "semilocal_xc_energy"):
        value[key+"_hartree"] = float(final[key])
    return value
