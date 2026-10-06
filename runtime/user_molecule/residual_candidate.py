"""Pure-array residual solver candidate for the unchanged conditional operator.

This module has no molecular bridge or CLI registration.  It solves the
occupied--virtual block equation on the masked-metric closed-shell manifold;
it does not minimize the reported energy or approve a scientific method.
Every endpoint still needs the existing true-F/Aufbau/gap qualification gates.
"""
from __future__ import annotations

import hashlib
import math
from numbers import Real
import struct
import time
from typing import Any

import numpy as np
from scipy.linalg import expm

from .solver_candidate import ENDPOINT_THRESHOLDS, endpoint_gate


SOLVER_ID = "P09_RUNTIME_RESIDUAL_ENGINEERING_CANDIDATE_V1"
OPERATOR_SOURCE = "TRUE_CONDITIONAL_AT_REQUESTED_DENSITY"
MAXIMUM_ROTATION_VARIABLES = 64
_COMPONENTS = ("one_electron_energy", "coulomb_energy", "exact_exchange_energy",
               "semilocal_xc_energy", "nuclear_repulsion")


def _matrix(value: Any, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.ndim != 2 or not raw.shape[0] or raw.shape[0] != raw.shape[1]:
        raise ValueError(name + " must be a real nonempty square matrix")
    array = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError(name + " must be finite")
    return array


def density_id(density: Any) -> str:
    """SHA-256 of shape and canonical little-endian binary64 matrix bytes."""
    array = _matrix(density, "Density")
    encoded = np.ascontiguousarray(array, dtype="<f8")
    header = b"AI4OrgChem-density-v1\0" + struct.pack("<QQ", *encoded.shape)
    return hashlib.sha256(header + encoded.tobytes(order="C")).hexdigest()


class _Refusal(Exception):
    def __init__(self, reason: str, detail: str):
        self.reason, self.detail = reason, detail
        super().__init__(detail)


def solve_residual_candidate(*, initial_density, overlap, electrons, evaluate,
                            maximum_iterations=8, maximum_evaluations=201,
                            finite_difference_step=1e-5, trust_radius=0.25,
                            maximum_backtracks=8, matrix_delete_mask=None):
    """Bounded central-difference/trust-radius residual candidate.

    Configuration and a nonmanifold initial density raise ``ValueError`` before
    any callback.  Numerical, budget, callback and provenance refusals return
    an unqualified record.  The initial density is never silently projected.
    ``engine_qualified`` concerns this pure-array endpoint only; research and
    molecular acceptance are never granted here.
    """
    for name, value, ceiling in (("maximum_iterations", maximum_iterations, 100),
                                ("maximum_evaluations", maximum_evaluations, 201),
                                ("maximum_backtracks", maximum_backtracks, 100)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError(f"{name} must be an integer in [1, {ceiling}]")
    for name, value in (("finite_difference_step", finite_difference_step),
                        ("trust_radius", trust_radius)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + " must be finite and positive")
    if not finite_difference_step <= trust_radius <= 1.0:
        raise ValueError("Require finite_difference_step <= trust_radius <= 1 radian")
    if not callable(evaluate):
        raise ValueError("evaluate must be callable")
    d = _matrix(initial_density, "Initial density").copy()
    s = _matrix(overlap, "Masked overlap").copy()
    if d.shape != s.shape or any(not np.allclose(a, a.T, rtol=0, atol=1e-12) for a in (d, s)):
        raise ValueError("Initial density and masked overlap must be same-size symmetric matrices")
    n = len(d)
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*n:
        raise ValueError("Require positive global closed-shell 2/0 occupation and a virtual orbital")
    occupied = electrons // 2
    variables = occupied * (n-occupied)
    if variables > MAXIMUM_ROTATION_VARIABLES:
        raise ValueError("Residual engineering candidate is limited to 64 occupied--virtual variables")
    values, vectors = np.linalg.eigh(s)
    if float(values.min()) <= 0:
        raise ValueError("Masked overlap must be positive definite; no metric repair is allowed")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x = (vectors / np.sqrt(values)) @ vectors.T
            half = (vectors * np.sqrt(values)) @ vectors.T
            p = .5 * half @ d @ half
        if not all(np.isfinite(value).all() for value in (values, x, half, p)):
            raise ValueError("Masked-metric whitening and initial projector must be finite")
    except FloatingPointError as error:
        raise ValueError("Masked-metric whitening or initial projector overflowed") from error
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            initial_idempotency = float(np.linalg.norm(p @ p-p, ord="fro"))
            initial_count = float(np.trace(p))
    except FloatingPointError as error:
        raise ValueError("Initial masked-metric projector diagnostics overflowed") from error
    if (not math.isfinite(initial_idempotency) or not math.isfinite(initial_count) or
            initial_idempotency > 1e-10 or abs(initial_count-occupied) > 1e-10):
        raise ValueError("Initial density is not a masked-metric closed-shell projector; no projection is allowed")
    pe, u = np.linalg.eigh((p+p.T)*.5)
    u = u[:, np.argsort(pe)[::-1]]
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            reconstructed = 2*x @ u[:, :occupied] @ u[:, :occupied].T @ x.T
        if not np.isfinite(reconstructed).all():
            raise ValueError("Initial projector reconstruction must be finite")
    except FloatingPointError as error:
        raise ValueError("Initial projector reconstruction overflowed") from error
    if np.linalg.norm(reconstructed-d) / max(np.linalg.norm(d), 1.0) > 1e-10:
        raise ValueError("Initial density does not represent the required integer occupied subspace")
    if matrix_delete_mask is None:
        mask = np.zeros(d.shape, dtype=bool)
    else:
        mask = np.asarray(matrix_delete_mask)
        if mask.dtype.kind != "b" or mask.shape != d.shape or not np.array_equal(mask, mask.T):
            raise ValueError("Matrix deletion mask must be a same-size symmetric boolean matrix")
        mask = mask.copy()
    parameters = {"maximum_iterations": maximum_iterations,
                  "maximum_evaluations": maximum_evaluations,
                  "finite_difference_step": float(finite_difference_step),
                  "trust_radius": float(trust_radius),
                  "maximum_backtracks": maximum_backtracks,
                  "rotation_variables": variables, "initial_density_id": density_id(d),
                  "jacobian": "CENTRAL_FINITE_DIFFERENCE_LOCAL_ORBITAL_RESIDUAL",
                  "step": "DAMPED_LEAST_SQUARES_FROBENIUS_RADIUS_BACKTRACK",
                  "merit": "OCCUPIED_VIRTUAL_RESIDUAL_NOT_ENERGY",
                  "endpoint_thresholds": dict(ENDPOINT_THRESHOLDS)}
    ledger, history, operators_by_density = [], [], {}
    failure, final_gate, mapped_gate = None, None, None
    reason, qualified = "MAXIMUM_ITERATIONS_EXHAUSTED", False
    current = None

    def assessed(dm, evaluated):
        closure = abs(sum(evaluated[key] for key in _COMPONENTS)-evaluated["total_energy"])
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            return endpoint_gate(density=dm, fock=evaluated["fock"], overlap=s,
                electrons=electrons, energy_closure_hartree=closure,
                overlap_mask_max_abs=float(np.max(np.abs(s[mask]), initial=0)),
                fock_mask_max_abs=float(np.max(np.abs(evaluated["fock"][mask]), initial=0)))

    def call(dm, phase):
        if len(ledger) >= maximum_evaluations:
            raise _Refusal("EVALUATION_BUDGET_EXHAUSTED", "No callback invoked after the hard evaluation ceiling")
        argument = dm.copy()
        identity = density_id(argument)
        row = {"evaluation_count": len(ledger)+1, "phase": phase,
               "density_id": identity, "status": "STARTED", "operator_source": None}
        ledger.append(row)
        start = time.monotonic()
        try:
            value = evaluate(argument)
            if density_id(argument) != identity:
                raise ValueError("Evaluator modified its requested density argument")
            if not isinstance(value, dict):
                raise ValueError("Evaluator must return a dictionary")
            row["returned_density_id"] = value.get("density_id")
            row["operator_source"] = value.get("operator_source")
            if value.get("density_id") != identity or value.get("operator_source") != OPERATOR_SOURCE:
                raise ValueError("Evaluator density identity or true-operator provenance mismatch")
            fock = _matrix(value.get("fock"), "True conditional Fock").copy()
            if fock.shape != d.shape or not np.allclose(fock, fock.T, rtol=0, atol=1e-12):
                raise ValueError("True conditional Fock must have the requested size and symmetry")
            fock_identity = density_id(fock)
            previous_fock = operators_by_density.get(identity)
            row.update({"fock_id": fock_identity, "previous_same_density_fock_id": previous_fock,
                        "same_density_operator_reproducible":
                            None if previous_fock is None else fock_identity == previous_fock})
            if previous_fock is not None and fock_identity != previous_fock:
                raise _Refusal("NONREPRODUCIBLE_SAME_DENSITY_OPERATOR",
                    "The same density identity returned different true-F bytes; this is a callback contract refusal, not an endpoint tolerance")
            checked = {"fock": fock, "density_id": identity, "operator_source": OPERATOR_SOURCE}
            for key in ("total_energy", *_COMPONENTS):
                scalar = value.get(key)
                if isinstance(scalar, (bool, np.bool_)) or not isinstance(scalar, Real) or not math.isfinite(scalar):
                    raise ValueError("Evaluator must provide finite real " + key)
                checked[key] = float(scalar)
            operators_by_density[identity] = fock_identity
            row.update({"status": "VALIDATED",
                        "total_energy_hartree": checked["total_energy"]})
            return checked
        except _Refusal as error:
            row.update({"status": "REFUSED", "reason": error.reason,
                        "exception_type": type(error).__name__, "message": str(error)})
            raise
        except Exception as error:
            row.update({"status": "REFUSED", "exception_type": type(error).__name__, "message": str(error)})
            raise _Refusal("EVALUATOR_REFUSED", type(error).__name__+": "+str(error)) from error
        finally:
            row["elapsed_seconds"] = time.monotonic()-start

    def residual(frame, evaluated):
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            f = x.T @ evaluated["fock"] @ x
            value = (frame[:, occupied:].T @ f @ frame[:, :occupied]).ravel()
        if not np.isfinite(f).all() or not np.isfinite(value).all():
            raise _Refusal("NONFINITE_RESIDUAL", "Whitened true-F matrix or orbital residual is not finite")
        return value

    def rotated(frame, vector):
        block = np.asarray(vector).reshape(n-occupied, occupied)
        generator = np.zeros((n, n))
        generator[occupied:, :occupied] = block
        generator[:occupied, occupied:] = -block.T
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            updated = frame @ expm(generator)
            dm = 2*x @ updated[:, :occupied] @ updated[:, :occupied].T @ x.T
        if not np.isfinite(updated).all() or not np.isfinite(dm).all():
            raise _Refusal("NONFINITE_ROTATED_DENSITY", "Orbital rotation or reconstructed density is not finite")
        return updated, (dm+dm.T)*.5

    def public_gate(gate):
        if gate is None:
            return None
        return {key: value for key, value in gate.items() if key not in
                {"raw_mo_coefficients", "raw_mo_energies_hartree", "raw_mo_occupations", "mapped_density"}}

    try:
        current = call(d, "CURRENT_000")
        for iteration in range(1, maximum_iterations+1):
            r = residual(u, current)
            norm = float(np.linalg.norm(r))
            if not np.isfinite(r).all():
                raise _Refusal("NONFINITE_RESIDUAL", "True-operator orbital residual is not finite")
            current_gate = assessed(d, current)
            if current_gate["qualified"]:
                reason = "QUALIFIED_CURRENT_ENDPOINT_CANDIDATE"
                break
            if norm <= 1e-12:
                reason = "STATIONARY_ENDPOINT_FAILED_ORIGINAL_GATES"
                break
            row = {"iteration": iteration, "density_id": density_id(d),
                   "current_residual_norm": norm, "current_endpoint_qualified": False,
                   "evaluation_count_before": len(ledger), "trial_steps": [], "accepted": False}
            history.append(row)
            # Reserve a trial and two independent final evaluations.  This is
            # an implementation bound, never an inherited molecular budget.
            if len(ledger)+2*variables+3 > maximum_evaluations:
                reason = "INSUFFICIENT_BUDGET_FOR_JACOBIAN_TRIAL_AND_FINAL_RECHECK"
                break
            jacobian = np.empty((variables, variables))
            for column in range(variables):
                perturbation = np.zeros(variables)
                perturbation[column] = finite_difference_step
                up, dp = rotated(u, perturbation)
                um, dm = rotated(u, -perturbation)
                plus = residual(up, call(dp, f"FD_PLUS_{iteration:03d}_{column:03d}"))
                minus = residual(um, call(dm, f"FD_MINUS_{iteration:03d}_{column:03d}"))
                jacobian[:, column] = (plus-minus)/(2*finite_difference_step)
            if not np.isfinite(jacobian).all():
                raise _Refusal("NONFINITE_JACOBIAN", "Central-difference residual Jacobian is not finite")
            damping = max(1e-12, 1e-6*float(np.linalg.norm(jacobian, ord=2))**2)
            augmented = np.vstack((jacobian, np.sqrt(damping)*np.eye(variables)))
            step, _, rank, _ = np.linalg.lstsq(augmented, np.concatenate((-r, np.zeros(variables))), rcond=None)
            step_norm = float(np.linalg.norm(step))
            row.update({"jacobian_rank": int(np.linalg.matrix_rank(jacobian)),
                        "damped_system_rank": int(rank), "damping": damping,
                        "unclipped_step_norm": step_norm})
            if not np.isfinite(step).all() or step_norm <= 1e-14:
                reason = "NO_USABLE_RESIDUAL_STEP"
                break
            step *= min(1.0, trust_radius/step_norm)
            for backtrack in range(maximum_backtracks):
                if len(ledger)+3 > maximum_evaluations:
                    reason = "INSUFFICIENT_BUDGET_FOR_TRIAL_AND_FINAL_RECHECK"
                    break
                scale = 2.0**(-backtrack)
                ut, dt = rotated(u, scale*step)
                trial = call(dt, f"CANDIDATE_{iteration:03d}_{backtrack:03d}")
                trial_norm = float(np.linalg.norm(residual(ut, trial)))
                accepted = bool(math.isfinite(trial_norm) and trial_norm < norm*(1-1e-4*scale))
                row["trial_steps"].append({"density_id": density_id(dt), "scale": scale,
                    "step_norm": float(np.linalg.norm(scale*step)), "residual_norm": trial_norm,
                    "accepted": accepted, "evaluation_count": len(ledger)})
                if accepted:
                    u, d, current = ut, dt, trial
                    row["accepted"] = True
                    break
            row["evaluation_count_after"] = len(ledger)
            if not row["accepted"]:
                if not reason.startswith("INSUFFICIENT_BUDGET"):
                    reason = "RESIDUAL_BACKTRACKS_EXHAUSTED"
                break
        # A terminal check uses a fresh, non-DIIS evaluation at the exact
        # returned candidate.  Its raw Aufbau density is a diagnostic: never
        # silently replace the returned density with it.
        termination_reason = reason
        final = call(d, "FINAL_RETURNED_DENSITY")
        final_gate = assessed(d, final)
        final_gate["raw_map_absolute_frobenius"] = float(np.linalg.norm(final_gate["mapped_density"]-d)) if final_gate["mapped_density"] is not None else None
        final_gate["returned_density_energy_recheck_hartree"] = abs(final["total_energy"]-current["total_energy"])
        absolute = final_gate["raw_map_absolute_frobenius"]
        reproducible = final_gate["returned_density_energy_recheck_hartree"] <= 1e-9
        if final_gate["qualified"] and absolute is not None and absolute <= 2e-8 and reproducible:
            mapped = final_gate["mapped_density"]
            mapped_value = call(mapped, "FINAL_RAW_AUFBAU_DENSITY_RECHECK")
            mapped_gate = assessed(mapped, mapped_value)
            energy_change = abs(mapped_value["total_energy"]-final["total_energy"])
            mapped_absolute = float(np.linalg.norm(mapped_gate["mapped_density"]-mapped)) if mapped_gate["mapped_density"] is not None else None
            mapped_gate["raw_map_absolute_frobenius"] = mapped_absolute
            final_gate["mapped_density_energy_change_hartree"] = energy_change
            final_gate["mapped_density_recheck_qualified"] = mapped_gate["qualified"]
            qualified = bool(mapped_gate["qualified"] and mapped_absolute is not None and mapped_absolute <= 2e-8 and energy_change <= 1e-9)
            reason = "QUALIFIED_TRUE_ARRAY_ENDPOINT" if qualified else "FINAL_RAW_AUFBAU_RECHECK_FAILED"
        else:
            if final_gate["qualified"]:
                reason = "FINAL_ABSOLUTE_RAW_MAP_FAILED" if absolute is None or absolute > 2e-8 else "FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED"
            elif termination_reason == "QUALIFIED_CURRENT_ENDPOINT_CANDIDATE":
                reason = "FINAL_ENDPOINT_FAILED_ORIGINAL_GATES"
    except _Refusal as error:
        reason, failure = error.reason, {"reason": error.reason, "detail": error.detail}
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as error:
        reason, failure = "NUMERICAL_REFUSAL", {"exception_type": type(error).__name__, "detail": str(error)}
    return {"solver_id": SOLVER_ID, "status": "ENGINEERING_CANDIDATE",
        "engine_qualified": qualified, "converged": qualified, "stop_reason": reason,
        "density": d, "endpoint_gate": public_gate(final_gate),
        "mapped_endpoint_gate": public_gate(mapped_gate), "parameters": parameters,
        "iterations": len(history), "history": history, "evaluation_ledger": ledger,
        "evaluation_count": len(ledger), "evaluation_limit": maximum_evaluations,
        "failure": failure, "initial_density_preserved": True,
        "final_operator_source": OPERATOR_SOURCE if final_gate is not None else None,
        "final_density_id": density_id(d), "production_activation": False,
        "solver_candidate_status": "NOT_ACCEPTED", "research_acceptance": "NOT_ACCEPTED",
        "molecular_acceptance": "NOT_EXECUTED", "variational_status": "NOT_ESTABLISHED",
        "stability_status": "NOT_EXECUTED", "comparison_available": False,
        "deltas": None, "delta_hartree": None, "delta_kcal_mol": None}
