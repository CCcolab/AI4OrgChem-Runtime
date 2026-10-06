"""Array-only masked-metric seed; no operator evaluation or method approval.

The supplied ordinary occupied space is retained.  This preparation neither
repairs an invalid parent density nor qualifies a conditional endpoint.
"""
from __future__ import annotations

import hashlib
import math
import struct

import numpy as np


POLICY_ID = "MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2"
RELATIVE_TOLERANCE = 1e-10
SYMMETRY_TOLERANCE = 1e-12
ELECTRON_TOLERANCE = 1e-7
PROJECTOR_TOLERANCE = 1e-10
CONDITION_LIMIT = 1e6
MAXIMUM_ROTATION_VARIABLES = 64


class SeedV2Error(ValueError):
    """Fail-closed preparation refusal, with a finite JSON evidence receipt."""

    def __init__(self, reason, receipt):
        self.reason = reason
        self.receipt = receipt
        super().__init__(reason)


def _identity(array):
    data = np.ascontiguousarray(array, dtype="<f8")
    header = b"AI4OrgChem-seed-v2-array-v1\0" + struct.pack("<Q", data.ndim)
    header += struct.pack("<" + "Q" * data.ndim, *data.shape)
    return hashlib.sha256(header + data.tobytes(order="C")).hexdigest()


def _density_identity(array):
    data = np.ascontiguousarray(array, dtype="<f8")
    header = b"AI4OrgChem-density-v1\0" + struct.pack("<QQ", *data.shape)
    return hashlib.sha256(header + data.tobytes(order="C")).hexdigest()


def prepare_seed_v2(*, density, physical_overlap, masked_overlap,
                    mo_coefficients, mo_occupations, electrons):
    """Return read-only ``density``, ``coefficients`` and an evidence receipt.

    Inputs must be a complete finite ordinary MO matrix and exact 2/0
    occupations.  Parent file/source/profile binding belongs to the calling
    preparation factory.  Every check here precedes any functional callback;
    there is no callback parameter, engine import, clipping or regularization.
    """
    receipt = {
        "schema_version": "user-molecule-seed-v2-v1",
        "policy_id": POLICY_ID,
        "status": "PREPARING",
        "definition_checks": {},
        "solver_admission_checks": {},
        "input_identities": {},
        "diagnostics": {},
        "functional_calls": 0,
        "scientific_execution": "NOT_EXECUTED",
        "endpoint_qualification": "NOT_EXECUTED",
        "production_activation": False,
        "scientific_approval": False,
        "parent_identity_binding": "REQUIRED_FROM_CALLER_NOT_ESTABLISHED_BY_ARRAY_PREPARATION",
        "repairs_performed": False,
    }

    def refuse(reason):
        receipt.update(status="REFUSED", reason=reason)
        raise SeedV2Error(reason, receipt)

    def array(value, name, dimensions):
        try:
            raw = np.asarray(value)
            if raw.dtype.kind not in "iuf" or raw.ndim != dimensions or not raw.size:
                refuse(name + " must be a real nonempty array of the required rank")
            result = np.array(raw, dtype=np.float64, copy=True)
        except SeedV2Error:
            raise
        except (TypeError, ValueError, OverflowError) as error:
            refuse(name + " cannot be converted to a real finite array: " + type(error).__name__)
        if not np.isfinite(result).all():
            refuse(name + " must be finite")
        receipt["input_identities"][name] = {
            "sha256": _identity(result), "shape": list(result.shape),
            "encoding": "AI4OrgChem-seed-v2-array-v1; little-endian binary64",
        }
        return result

    def check(name, observed, threshold, *, layer="definition_checks", metric, denominator=None):
        measured = float(observed)
        row = {"metric": metric, "observed": measured if math.isfinite(measured) else None,
               "threshold": float(threshold), "pass": math.isfinite(measured) and measured <= threshold}
        if denominator is not None:
            row["denominator"] = float(denominator) if math.isfinite(float(denominator)) else None
        receipt[layer][name] = row
        if not row["pass"]:
            refuse(name + " failed its unchanged preparation/admission threshold")

    def relative(name, actual, expected, *, layer="definition_checks"):
        difference = float(np.linalg.norm(actual - expected, ord="fro"))
        denominator = max(float(np.linalg.norm(expected, ord="fro")), 1.0)
        if not math.isfinite(difference) or not math.isfinite(denominator):
            receipt[layer][name] = {"metric": "relative Frobenius", "observed": None,
                "denominator": None, "threshold": RELATIVE_TOLERANCE, "pass": False}
            refuse(name + " produced a nonfinite norm")
        check(name, difference / denominator, RELATIVE_TOLERANCE,
              layer=layer, metric="Frobenius(actual-expected)/max(Frobenius(expected),1)",
              denominator=denominator)

    def symmetric(value, name, *, layer="definition_checks"):
        check(name + "_symmetry", np.max(np.abs(value - value.T)), SYMMETRY_TOLERANCE,
              layer=layer, metric="max(abs(A-A.T)); absolute")

    def spectrum(value, name):
        symmetric(value, name)
        values, vectors = np.linalg.eigh(value)
        if not np.isfinite(values).all() or not np.isfinite(vectors).all():
            refuse(name + " eigendecomposition must be finite")
        minimum, maximum = float(values[0]), float(values[-1])
        receipt["diagnostics"][name + "_minimum_eigenvalue"] = minimum
        receipt["diagnostics"][name + "_maximum_eigenvalue"] = maximum
        if minimum <= 0:
            receipt["definition_checks"][name + "_positive_definite"] = {
                "metric": "minimum eigenvalue strictly > 0", "observed": minimum, "pass": False}
            refuse(name + " must be strictly positive definite; no metric repair is permitted")
        receipt["definition_checks"][name + "_positive_definite"] = {
            "metric": "minimum eigenvalue strictly > 0", "observed": minimum, "pass": True}
        condition = maximum / minimum
        check(name + "_condition_number", condition, CONDITION_LIMIT,
              metric="largest/smallest eigenvalue")
        return values, vectors

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            d0 = array(density, "ordinary_density", 2)
            s = array(physical_overlap, "physical_overlap", 2)
            sm = array(masked_overlap, "masked_overlap", 2)
            coefficients = array(mo_coefficients, "mo_coefficients", 2)
            occupations = array(mo_occupations, "mo_occupations", 1)
            n = d0.shape[0]
            if d0.shape != (n, n) or s.shape != d0.shape or sm.shape != d0.shape:
                refuse("Density and both overlaps must be same-size square matrices")
            if coefficients.shape != (n, n) or occupations.shape != (n,):
                refuse("Complete ordinary MO coefficients and occupations must match the AO dimension")
            if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2 * n:
                refuse("Require integer positive closed-shell electron count and at least one virtual orbital")
            nocc = electrons // 2
            variables = nocc * (n - nocc)
            receipt["diagnostics"].update(n_ao=n, electrons=electrons, n_occupied=nocc,
                                          rotation_variables=variables)
            if variables > MAXIMUM_ROTATION_VARIABLES:
                refuse("Occupied-virtual rotation variables exceed the unchanged ceiling of 64")
            if not np.all((occupations == 0.0) | (occupations == 2.0)) or np.count_nonzero(occupations == 2.0) != nocc:
                refuse("Ordinary occupations must be exact global closed-shell 2/0 with the requested electron count")
            symmetric(d0, "ordinary_density")
            spectrum(s, "physical_overlap")
            sm_values, sm_vectors = spectrum(sm, "masked_overlap")
            c0 = coefficients[:, occupations == 2.0].copy()
            identity = np.eye(nocc)
            relative("ordinary_occupied_physical_orthonormality", c0.T @ s @ c0, identity)
            relative("ordinary_density_reconstruction", 2.0 * c0 @ c0.T, d0)
            check("ordinary_physical_electron_count", abs(float(np.trace(s @ d0)) - electrons),
                  ELECTRON_TOLERANCE, metric="abs(Tr(S D0)-N)")

            gram = c0.T @ sm @ c0
            b_values, b_vectors = spectrum(gram, "occupied_masked_gram")
            inverse_half = (b_vectors / np.sqrt(b_values)) @ b_vectors.T
            cseed = c0 @ inverse_half
            dseed = 2.0 * cseed @ cseed.T
            if not np.isfinite(cseed).all() or not np.isfinite(dseed).all():
                refuse("Prepared seed and coefficients must be finite")
            symmetric(dseed, "seed_density")
            relative("seed_masked_orthonormality", cseed.T @ sm @ cseed, identity)
            relative("seed_masked_idempotency", dseed @ sm @ dseed, 2.0 * dseed)
            q0, _ = np.linalg.qr(c0, mode="reduced")
            qseed, _ = np.linalg.qr(cseed, mode="reduced")
            relative("seed_occupied_column_space", qseed @ qseed.T, q0 @ q0.T)
            masked_count = float(np.trace(sm @ dseed))
            physical_count = float(np.trace(s @ dseed))
            if not math.isfinite(masked_count) or not math.isfinite(physical_count):
                refuse("Prepared seed electron diagnostics must be finite")
            receipt["diagnostics"].update(masked_seed_electron_count=masked_count,
                physical_seed_electron_count=physical_count,
                physical_seed_count_is_guaranteed_by_masked_count=False,
                grid_seed_electron_count=None,
                grid_seed_electron_count_status="NOT_EXECUTED_NO_FUNCTIONAL_CALLBACK")
            check("seed_masked_electron_count", abs(masked_count - electrons),
                  ELECTRON_TOLERANCE, metric="abs(Tr(S_tilde Dseed)-N)")

            half = (sm_vectors * np.sqrt(sm_values)) @ sm_vectors.T
            inverse = (sm_vectors / np.sqrt(sm_values)) @ sm_vectors.T
            pseed = 0.5 * half @ dseed @ half
            if not all(np.isfinite(a).all() for a in (half, inverse, pseed)):
                refuse("Masked whitening and seed projector must be finite")
            symmetric(dseed, "seed_density", layer="solver_admission_checks")
            symmetric(sm, "masked_overlap", layer="solver_admission_checks")
            check("whitened_trace", abs(float(np.trace(pseed)) - nocc), PROJECTOR_TOLERANCE,
                  layer="solver_admission_checks", metric="abs(Tr(Pseed)-nocc); absolute")
            check("whitened_idempotency", np.linalg.norm(pseed @ pseed - pseed, ord="fro"),
                  PROJECTOR_TOLERANCE, layer="solver_admission_checks",
                  metric="Frobenius(Pseed@Pseed-Pseed); absolute")
            pe, u = np.linalg.eigh((pseed + pseed.T) * 0.5)
            u = u[:, np.argsort(pe)[::-1]][:, :nocc]
            reconstructed = 2.0 * inverse @ u @ u.T @ inverse.T
            if not np.isfinite(reconstructed).all():
                refuse("Production admission density reconstruction must be finite")
            relative("production_density_reconstruction", reconstructed, dseed,
                     layer="solver_admission_checks")
            receipt.update(status="ADMITTED_SEED_ONLY", definition_status="PASS_SEED_DEFINITION",
                solver_admission_status="PASS_PRODUCTION_SEED_ADMISSION",
                ordinary_density_id=_density_identity(d0), seed_density_id=_density_identity(dseed),
                seed_coefficients_sha256=_identity(cseed), occupied_parent_sha256=_identity(c0))
            dseed.setflags(write=False)
            cseed.setflags(write=False)
            return {"density": dseed, "coefficients": cseed, "receipt": receipt}
    except SeedV2Error:
        raise
    except (FloatingPointError, np.linalg.LinAlgError, OverflowError) as error:
        refuse("Numerical seed preparation failed without repair: " + type(error).__name__)
