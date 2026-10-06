"""Isolated V2 seed policy over the unchanged prepared operator bridge.

The inherited identity contract belongs to the operator bridge only.  The
separate V2 contract describes the actual initialization used by this class.
No inherited scientific source, threshold, budget or result is rewritten.
"""
from __future__ import annotations

import copy
import json
import math

import numpy as np
from scipy.linalg import eigh

from . import residual_candidate
from .residual_bridge import (PreparedResidualBridge, BridgeRefusal,
                              array_identity, _array, _scalar,
                              INITIALIZATION_GAP_MINIMUM_HARTREE)
from .seed_v2 import POLICY_ID, prepare_seed_v2


BRIDGE_ID = "P09_PREPARED_RESIDUAL_SEED_V2"
METHOD_STATUS = "EXTERNAL_REVIEW_CANCELLED_BY_USER_INTERNAL_METHOD_VALIDATION_PENDING"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class PreparedResidualSeedBridgeV2(PreparedResidualBridge):
    """Single-use V2 initialization with frozen ordinary-MO ancestry.

    ``frozen_ordinary_mo_identities`` uses the existing ``array_identity``
    format.  Binding those metadata to the original NPZ/JSON is the caller's
    preparation responsibility; this class checks the supplied arrays and
    detects their subsequent mutation.  Shared seeds require independent
    local construction plus all unchanged production admission checks.
    """

    def __init__(self, *, mo_coefficients, mo_occupations,
                 frozen_ordinary_mo_identities, shared_seed_density=None,
                 **operator_bridge_kwargs):
        self._v2_ready = False
        self._capture_initial_diagnostic = False
        self._initial_diagnostic = None
        # This is the actual legacy contract for source/array preparation.
        # Its run method is never used to perform the V2 initialization.
        super().__init__(**operator_bridge_kwargs)
        if self.initialization_policy != "REQUIRE_EXISTING_MASKED_PROJECTOR":
            raise BridgeRefusal("V2_OPERATOR_CONTRACT_POLICY_MISMATCH",
                "V2 requires an explicit REQUIRE_EXISTING_MASKED_PROJECTOR operator-preparation contract; it does not execute that legacy initialization")
        self._seed_mo_callers = {"mo_coefficients": mo_coefficients,
                                 "mo_occupations": mo_occupations}
        if not isinstance(frozen_ordinary_mo_identities, dict) or set(frozen_ordinary_mo_identities) != set(self._seed_mo_callers):
            raise BridgeRefusal("V2_MO_IDENTITIES_REQUIRED", "Exact ordinary coefficients/occupations metadata identities are required")
        self._seed_mo_identities = copy.deepcopy(frozen_ordinary_mo_identities)
        self._seed_mo_arrays = {}
        for name, value in self._seed_mo_callers.items():
            actual = array_identity(value)
            if actual != self._seed_mo_identities[name]:
                raise BridgeRefusal("V2_MO_IDENTITY_MISMATCH", "Ordinary MO bytes differ from supplied frozen metadata: " + name)
            self._seed_mo_arrays[name] = _array(value, name).copy()
            self._seed_mo_arrays[name].setflags(write=False)
        prepared = prepare_seed_v2(density=self.arrays["ordinary_density"],
            physical_overlap=self.arrays["physical_overlap"], masked_overlap=self.overlap,
            mo_coefficients=self._seed_mo_arrays["mo_coefficients"],
            mo_occupations=self._seed_mo_arrays["mo_occupations"], electrons=self.electrons)
        self.seed_receipt = copy.deepcopy(prepared["receipt"])
        self.computed_seed_density = prepared["density"]
        self.seed_coefficients = prepared["coefficients"]
        self._shared_seed_caller = shared_seed_density
        self._shared_seed_identity = None
        if shared_seed_density is None:
            self.seed_density = self.computed_seed_density.copy()
            self.seed_receipt["shared_seed_admission"] = {"status": "NOT_APPLICABLE_LOCAL_SEED_USED"}
        else:
            shared = _array(shared_seed_density, "Shared V2 seed").copy()
            self._shared_seed_identity = array_identity(shared_seed_density)
            self.seed_receipt["shared_seed_admission"] = self._admit_shared_seed(shared)
            self.seed_density = shared
        self.seed_density.setflags(write=False)
        self._seed_owned_identities = {
            "seed_density": array_identity(self.seed_density),
            "computed_seed_density": array_identity(self.computed_seed_density),
            "seed_coefficients": array_identity(self.seed_coefficients),
        }
        self.v2_contract = {
            "bridge_id": BRIDGE_ID, "initialization_policy": POLICY_ID,
            "operator_identity_contract": copy.deepcopy(self.contract),
            "operator_preparation_policy_is_v2_initialization": False,
            "ordinary_mo_identities": copy.deepcopy(self._seed_mo_identities),
            "ordinary_density_id": residual_candidate.density_id(self.arrays["ordinary_density"]),
            "seed_identity": array_identity(self.seed_density),
            "seed_density_id": residual_candidate.density_id(self.seed_density),
            "computed_seed_identity": array_identity(self.computed_seed_density),
            "shared_seed_used": shared_seed_density is not None,
            "seed_receipt": copy.deepcopy(self.seed_receipt),
            "initial_gap_role": "DIAGNOSTIC_ONLY_NO_INITIAL_F_ORBITAL_SELECTION",
            "final_gap_minimum_hartree": INITIALIZATION_GAP_MINIMUM_HARTREE,
            "production_activation": False, "scientific_approval": False,
        }
        self._v2_contract_identity = _canonical(self.v2_contract)
        self._seed_receipt_identity = _canonical(self.seed_receipt)
        self._v2_ready = True
        self._assert_frozen()

    def _admit_shared_seed(self, shared):
        """Recheck the actually used shared density; no projection or repair."""
        if shared.shape != self.computed_seed_density.shape or not np.allclose(shared, shared.T, rtol=0, atol=1e-12):
            raise BridgeRefusal("V2_SHARED_SEED_INVALID", "Shared seed must have the same finite real shape and absolute symmetry")
        checks = {}
        def check(name, measured, threshold, metric, denominator=None):
            observed = float(measured)
            checks[name] = {"observed": observed if math.isfinite(observed) else None,
                           "threshold": threshold, "metric": metric,
                           "pass": math.isfinite(observed) and observed <= threshold}
            if denominator is not None:
                checks[name]["denominator"] = float(denominator) if math.isfinite(float(denominator)) else None
            if not checks[name]["pass"]:
                raise BridgeRefusal("V2_SHARED_SEED_ADMISSION_FAILED", "Shared seed fails " + name)
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                denominator = max(float(np.linalg.norm(self.computed_seed_density)), 1.0)
                check("local_seed_agreement", np.linalg.norm(shared-self.computed_seed_density)/denominator,
                      1e-10, "Frobenius(shared-local)/max(Frobenius(local),1)", denominator)
                values, vectors = np.linalg.eigh(self.overlap)
                half = (vectors*np.sqrt(values)) @ vectors.T
                inverse = (vectors/np.sqrt(values)) @ vectors.T
                p = .5*half @ shared @ half
                if not all(np.isfinite(a).all() for a in (half, inverse, p)):
                    raise BridgeRefusal("V2_SHARED_SEED_NONFINITE", "Shared seed whitening must be finite")
                occupied = self.electrons//2
                check("whitened_trace", abs(float(np.trace(p))-occupied), 1e-10,
                      "abs(Tr(Pshared)-nocc); absolute")
                check("whitened_idempotency", np.linalg.norm(p@p-p), 1e-10,
                      "Frobenius(Pshared@Pshared-Pshared); absolute")
                check("masked_electron_count", abs(float(np.trace(self.overlap@shared))-self.electrons),
                      1e-7, "abs(Tr(S_tilde Dshared)-N)")
                twice = 2*shared
                denom_twice = max(float(np.linalg.norm(twice)), 1.0)
                check("masked_idempotency_relative", np.linalg.norm(shared@self.overlap@shared-twice)/denom_twice,
                      1e-10, "Frobenius(D S_tilde D-2D)/max(Frobenius(2D),1)", denom_twice)
                pe, u = np.linalg.eigh((p+p.T)*.5)
                occupied_vectors = u[:, np.argsort(pe)[::-1]][:, :occupied]
                reconstructed = 2*inverse @ occupied_vectors @ occupied_vectors.T @ inverse.T
                denom_shared = max(float(np.linalg.norm(shared)), 1.0)
                check("production_density_reconstruction", np.linalg.norm(reconstructed-shared)/denom_shared,
                      1e-10, "Frobenius(Drec-Dshared)/max(Frobenius(Dshared),1)", denom_shared)
        except (FloatingPointError, np.linalg.LinAlgError, OverflowError) as error:
            raise BridgeRefusal("V2_SHARED_SEED_NUMERICAL_REFUSAL", type(error).__name__ + ": " + str(error)) from error
        return {"status": "PASS_SHARED_SEED_PRODUCTION_ADMISSION", "checks": checks,
                "shared_seed_density_id": residual_candidate.density_id(shared),
                "local_seed_density_id": residual_candidate.density_id(self.computed_seed_density),
                "functional_calls": 0, "repairs_performed": False}

    def _assert_frozen(self):
        super()._assert_frozen()
        if not self._v2_ready:
            if hasattr(self, "_v2_contract_identity"):
                raise BridgeRefusal("V2_FROZEN_STATE_DISABLED", "Completed V2 preparation cannot disable its frozen-state checks")
            return
        if _canonical(self.v2_contract) != self._v2_contract_identity or _canonical(self.seed_receipt) != self._seed_receipt_identity:
            raise BridgeRefusal("V2_CONTRACT_OR_RECEIPT_CHANGED", "V2 initialization contract or seed evidence changed")
        for name, identity in self._seed_mo_identities.items():
            if array_identity(self._seed_mo_callers[name]) != identity or array_identity(self._seed_mo_arrays[name]) != identity:
                raise BridgeRefusal("V2_ORDINARY_MO_CHANGED", "Caller or owned ordinary MO bytes changed: " + name)
        for name, identity in self._seed_owned_identities.items():
            if array_identity(getattr(self, name)) != identity:
                raise BridgeRefusal("V2_SEED_CHANGED", "Owned seed initialization arrays changed: " + name)
        if self._shared_seed_caller is not None and array_identity(self._shared_seed_caller) != self._shared_seed_identity:
            raise BridgeRefusal("V2_SHARED_SEED_CALLER_CHANGED", "Caller-owned common seed changed")

    def evaluate(self, density, phase="SOLVER_CALLBACK"):
        evaluated = super().evaluate(density, phase=phase)
        if self._capture_initial_diagnostic and self._initial_diagnostic is None:
            if evaluated["density_id"] != residual_candidate.density_id(self.seed_density):
                raise BridgeRefusal("V2_INITIAL_CALLBACK_DENSITY_MISMATCH", "First solver callback must evaluate the admitted V2 seed")
            spectrum, orbitals = eigh(evaluated["fock"], self.overlap, check_finite=True)
            occupied = self.electrons//2
            gap = float(spectrum[occupied]-spectrum[occupied-1])
            if not np.isfinite(spectrum).all() or not np.isfinite(orbitals).all() or not math.isfinite(gap):
                raise BridgeRefusal("V2_INITIAL_DIAGNOSTIC_NONFINITE", "Initial seed spectrum must be finite")
            self._initial_diagnostic = {
                "raw_aufbau_spectrum_hartree": spectrum.tolist(),
                "raw_aufbau_gap_hartree": gap,
                "raw_aufbau_fock_id": residual_candidate.density_id(evaluated["fock"]),
                "raw_aufbau_spectrum_identity": array_identity(spectrum),
                "diagnostic_callback_count": self.ledger[-1]["global_evaluation_count"],
                "initial_gap_is_admission_or_endpoint_pass": False,
            }
            self.ledger[-1]["v2_initial_gap_diagnostic_hartree"] = gap
            self.ledger[-1]["v2_initial_gap_role"] = "DIAGNOSTIC_ONLY_NO_ADDITIONAL_CALLBACK"
        return evaluated

    def run(self, *, maximum_iterations=8, finite_difference_step=1e-5,
            trust_radius=0.25, maximum_backtracks=8):
        if self._used:
            raise BridgeRefusal("BRIDGE_ALREADY_USED", "No automatic retry or budget reset is permitted")
        self._used = True
        initialized = {
            "policy": POLICY_ID, "status": "NOT_EXECUTED",
            "ordinary_density_id": residual_candidate.density_id(self.arrays["ordinary_density"]),
            "initial_density_id": residual_candidate.density_id(self.seed_density),
            "computed_seed_density_id": residual_candidate.density_id(self.computed_seed_density),
            "seed_receipt": copy.deepcopy(self.seed_receipt),
            "ordinary_mo_identities": copy.deepcopy(self._seed_mo_identities),
            "raw_aufbau_spectrum_hartree": None, "raw_aufbau_gap_hartree": None,
            "initial_gap_role": "DIAGNOSTIC_ONLY_NO_INITIAL_F_ORBITAL_SELECTION",
            "final_gap_minimum_hartree": INITIALIZATION_GAP_MINIMUM_HARTREE,
            "evaluation_count_before": len(self.ledger),
        }
        solved, failure, reason = None, None, "NOT_EXECUTED"
        try:
            for name, value in (("maximum_iterations", maximum_iterations), ("maximum_backtracks", maximum_backtracks)):
                if type(value) is not int or not 1 <= value <= 100:
                    raise BridgeRefusal("INVALID_SOLVER_CONFIGURATION", name + " must be an integer in [1,100]")
            fd, radius = _scalar(finite_difference_step, "Finite-difference step"), _scalar(trust_radius, "Trust radius")
            if not 0 < fd <= radius <= 1:
                raise BridgeRefusal("INVALID_SOLVER_CONFIGURATION", "Require 0 < finite_difference_step <= trust_radius <= 1")
            self._assert_frozen()
            remaining = self.limit-len(self.ledger)
            if remaining < 1:
                raise BridgeRefusal("EVALUATION_BUDGET_EXHAUSTED", "No remaining global callback allowance")
            initialized.update(status="PREPARED_ENGINEERING_V2_SEED",
                ordinary_density_metrics=self._projector_metrics(self.arrays["ordinary_density"]),
                initial_density_metrics=self._projector_metrics(self.seed_density))
            self._capture_initial_diagnostic = True
            offset = len(self.ledger)
            solved = residual_candidate.solve_residual_candidate(initial_density=self.seed_density,
                overlap=self.overlap, electrons=self.electrons, evaluate=self.evaluate,
                maximum_iterations=maximum_iterations, maximum_evaluations=remaining,
                finite_difference_step=fd, trust_radius=radius,
                maximum_backtracks=maximum_backtracks, matrix_delete_mask=self.mask)
            for index, inner in enumerate(solved["evaluation_ledger"]):
                if offset+index < len(self.ledger):
                    self.ledger[offset+index]["solver_evaluation_count"] = inner["evaluation_count"]
                    self.ledger[offset+index]["solver_phase"] = inner["phase"]
            reason = solved["stop_reason"]
            self._assert_frozen()
        except BridgeRefusal as error:
            reason, failure = error.reason, {"reason": error.reason, "detail": error.detail}
            if initialized["status"] == "NOT_EXECUTED":
                initialized["status"] = "REFUSED"
        except (ValueError, TypeError, OSError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as error:
            reason, failure = "V2_INITIALIZATION_OR_SOLVER_REFUSED", {
                "reason": "V2_INITIALIZATION_OR_SOLVER_REFUSED", "exception_type": type(error).__name__, "detail": str(error)}
            if initialized["status"] == "NOT_EXECUTED":
                initialized["status"] = "REFUSED"
        finally:
            self._capture_initial_diagnostic = False
            self._settled = True
        if self._initial_diagnostic is not None:
            initialized.update(copy.deepcopy(self._initial_diagnostic))
        initialized["evaluation_count_after"] = len(self.ledger)
        initialized["ordinary_density_preserved"] = array_identity(self._caller_arrays["ordinary_density"]) == self._caller_identities["ordinary_density"]
        real_attempts = len(self.ledger) if self.execution_kind == "PREPARED_MOLECULAR_DIAGNOSTIC" else 0
        last_refusal = next((copy.deepcopy(row) for row in reversed(self.ledger) if row["status"] == "REFUSED"), None)
        return {
            "bridge_id": BRIDGE_ID, "status": "ENGINEERING_CANDIDATE_V2", "initialization_policy": POLICY_ID,
            "stop_reason": reason, "failure": failure, "last_bridge_refusal": last_refusal,
            "execution_kind": self.execution_kind, "identity_contract": copy.deepcopy(self.v2_contract),
            "operator_identity_contract": copy.deepcopy(self.contract), "initialization": initialized,
            "seed_receipt": copy.deepcopy(self.seed_receipt), "solver_result": solved,
            "bridge_ledger": copy.deepcopy(self.ledger), "global_evaluation_count": len(self.ledger),
            "global_evaluation_limit": self.limit, "eri_mode": self.eri_mode,
            "optimize_eri_contractions": self.optimize, "deleted_eri_count": self.deleted_eri_count,
            "total_eri_count": self.n**4, "real_molecular_operator_attempts": real_attempts,
            "molecular_execution": "EXECUTED_DIAGNOSTIC_UNQUALIFIED" if real_attempts else "NOT_EXECUTED",
            "identity_evidence_kind": "LOCAL_BYTES_AND_ENVIRONMENT_DECLARATIONS_NOT_AUTHENTICATION",
            "molecular_metadata_status": "BOUND_CACHED_METADATA_NOT_AUTHENTICATED" if self.execution_kind == "PREPARED_MOLECULAR_DIAGNOSTIC" else "TEST_DOUBLE_NOT_MOLECULAR_EVIDENCE",
            "production_activation": False, "molecular_acceptance": "NOT_EXECUTED",
            "research_acceptance": "NOT_ACCEPTED", "method_review_status": METHOD_STATUS,
            "comparison_available": False, "deltas": None, "delta_hartree": None, "delta_kcal_mol": None,
        }
