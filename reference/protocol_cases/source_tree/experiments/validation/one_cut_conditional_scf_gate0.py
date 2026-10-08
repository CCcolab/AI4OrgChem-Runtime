"""Run the first non-production one-cut conditional-SCF candidate."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from types import MethodType
from typing import Any

import numpy as np
import yaml

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

from ai4orgchem.lfmo.conditional_scf import (
    fixed_group_occupations,
    grouped_generalized_eigh,
    nonorthogonal_closed_shell_density,
)
from ai4orgchem.lfmo.kost import bounded_alternating_kost
from ai4orgchem.lfmo.reflection import adapt_reflection_blocks
from ai4orgchem.lfmo.subspaces import (
    metric_projector,
    projector_diagnostics,
    subspace_leakage,
)
from experiments.validation.kost_single_step_gate0 import build_input_spaces
from experiments.validation.kost_vacant_loop_gate0 import occupation_partition


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "qm" / "one_cut_conditional_scf_v0.1.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def build_reflection_adapted_working_basis(config: dict[str, Any]) -> dict[str, Any]:
    working_config = load_yaml(ROOT / config["working_basis_config"])
    scheduler_config = load_yaml(ROOT / working_config["scheduler_config"])
    rotation_config = load_yaml(ROOT / scheduler_config["rotation_config"])
    spaces = build_input_spaces(rotation_config)
    occupations = spaces["fragment"]["natural_occupations"]
    membership = scheduler_config["membership"]
    target, occupied, vacant = occupation_partition(
        occupations,
        membership["target_occupation_window"],
        membership["occupied_auxiliary_window"],
        membership["vacant_auxiliary_window"],
    )
    classes = ["vacant"] * len(occupations)
    classes[target] = "cut_single"
    for index in occupied:
        classes[index] = "occupied"

    molecule = spaces["fragment"]["molecule"]
    odd_components = set(
        spaces["fragment_config"]["classification"]["odd_ao_components"]
    )
    parity_signs = [
        -1.0
        if str(label[3]).lower().replace(" ", "") in odd_components
        else 1.0
        for label in molecule.ao_labels(fmt=False)
    ]
    adaptation_config = config["reflection_adaptation"]
    adaptation = adapt_reflection_blocks(
        spaces["fragment"]["natural_coefficients"],
        spaces["fragment"]["overlap"],
        parity_signs,
        occupations,
        classes,
        occupation_tolerance=float(adaptation_config["occupation_clustering_tolerance"]),
        parity_tolerance=float(adaptation_config["parity_tolerance"]),
        anchor_tolerance=float(adaptation_config["anchor_tolerance"]),
    )
    embedded = np.zeros_like(spaces["fragment_coefficients"])
    embedded[spaces["fragment_indices"], :] = adaptation["coefficients"]
    ordered = [target, *occupied, *vacant]
    initial_ch3 = embedded[:, ordered]
    scheduler = bounded_alternating_kost(
        initial_ch3[:, [0]],
        initial_ch3[:, 1 : 1 + len(occupied)],
        initial_ch3[:, 1 + len(occupied) :],
        spaces["probe"],
        spaces["overlap"],
        occupied_labels=occupied,
        vacant_labels=vacant,
        tolerance=float(scheduler_config["scheduler"]["trigger_tolerance"]),
        maximum_cycles=int(scheduler_config["scheduler"]["maximum_cycles"]),
        occupied_maximum_sweeps=int(
            scheduler_config["convergence"]["occupied_maximum_sweeps"]
        ),
        monotonic_tolerance=float(
            scheduler_config["convergence"]["monotonic_tolerance"]
        ),
    )
    reference = spaces["reference"]
    reference_somo = int(reference["candidate_indices"][0])
    reference_vacant = next(
        index
        for index in range(reference["natural_coefficients"].shape[1])
        if index != reference_somo
    )
    reference_embedded = np.zeros((spaces["overlap"].shape[0], 2))
    reference_embedded[spaces["reference_indices"], :] = reference["natural_coefficients"][
        :, [reference_somo, reference_vacant]
    ]

    current = scheduler["current_block"]
    occupied_vacant = np.column_stack(
        (current[:, 1 : 1 + len(occupied)], current[:, 1 + len(occupied) :])
    )
    cut_reference = np.column_stack((current[:, 0], reference_embedded[:, 0]))
    working_basis = np.column_stack(
        (occupied_vacant, cut_reference, reference_embedded[:, 1])
    )
    return {
        "spaces": spaces,
        "occupations": occupations,
        "classes": classes,
        "target": target,
        "occupied": occupied,
        "vacant": vacant,
        "adaptation": adaptation,
        "scheduler": scheduler,
        "working_basis": working_basis,
        "group_sizes": [len(occupied) + len(vacant), 2, 1],
    }


def run_conditional_scf(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    from pyscf import lib, scf

    molecule = inputs["spaces"]["composite"]
    overlap = inputs["spaces"]["overlap"]
    working_basis = inputs["working_basis"]
    group_sizes = [int(value) for value in config["conditional_blocks"]["group_sizes"]]
    occupied_counts = [
        int(value)
        for value in config["conditional_blocks"]["fixed_doubly_occupied_roots"]
    ]
    if group_sizes != inputs["group_sizes"]:
        raise RuntimeError("configured conditional groups do not match constructed groups")
    fixed_occupations = fixed_group_occupations(group_sizes, occupied_counts)
    expected_electrons = int(np.sum(fixed_occupations))
    if expected_electrons != molecule.nelectron:
        raise RuntimeError("fixed conditional occupations do not match molecular electrons")

    mf = scf.RHF(molecule)
    scf_config = config["scf"]
    mf.conv_tol = float(scf_config["convergence_tolerance"])
    mf.conv_tol_grad = float(scf_config["convergence_tolerance_gradient"])
    mf.max_cycle = int(scf_config["max_cycles"])
    mf.init_guess = str(scf_config["initial_guess"])
    mf.damp = float(scf_config["damping"])
    mf.diis = False
    mf.verbose = 0
    eig_history: list[dict[str, Any]] = []
    previous_occupied: list[np.ndarray | None] = [None] * len(group_sizes)
    inverse_working_basis = np.linalg.inv(working_basis)
    conditional_mask = np.zeros((sum(group_sizes), sum(group_sizes)))
    offset = 0
    for size in group_sizes:
        conditional_mask[offset : offset + size, offset : offset + size] = 1.0
        offset += size
    working_metric = working_basis.T @ overlap @ working_basis
    masked_working_metric = working_metric * conditional_mask
    conditional_diis = lib.diis.DIIS(mf)
    conditional_diis.space = int(scf_config["conditional_diis_space"])
    diis_start = int(scf_config["conditional_diis_start_cycle"])
    conditional_residual_history: list[float] = []
    forbidden_residual_history: list[float] = []

    def conditional_get_fock(
        self: Any,
        h1e: np.ndarray | None = None,
        s1e: np.ndarray | None = None,
        vhf: np.ndarray | None = None,
        dm: np.ndarray | None = None,
        cycle: int = -1,
        diis: Any = None,
        **_kwargs: Any,
    ) -> np.ndarray:
        if h1e is None:
            h1e = self.get_hcore()
        if dm is None:
            dm = self.make_rdm1()
        if vhf is None:
            vhf = self.get_veff(self.mol, dm)
        physical_fock = np.asarray(h1e) + np.asarray(vhf)
        masked_fock = (working_basis.T @ physical_fock @ working_basis) * conditional_mask
        density_working = inverse_working_basis @ dm @ inverse_working_basis.T
        full_error = (
            masked_fock @ density_working @ masked_working_metric
            - masked_working_metric @ density_working @ masked_fock
        )
        error = full_error * conditional_mask
        forbidden_error = full_error * (1.0 - conditional_mask)
        error_norm = float(np.linalg.norm(error, ord="fro"))
        conditional_residual_history.append(error_norm)
        forbidden_residual_history.append(float(np.linalg.norm(forbidden_error, ord="fro")))
        if cycle >= diis_start:
            masked_fock = conditional_diis.update(masked_fock, xerr=error)
            masked_fock = 0.5 * (masked_fock + masked_fock.T)
        return inverse_working_basis.T @ masked_fock @ inverse_working_basis

    def conditional_eig(
        self: Any,
        fock: np.ndarray,
        metric: np.ndarray,
        **_kwargs: Any,
    ):
        fock_working = working_basis.T @ fock @ working_basis
        metric_working = working_basis.T @ metric @ working_basis
        result = grouped_generalized_eigh(fock_working, metric_working, group_sizes)
        coefficients = working_basis @ result["transform"]
        offsets = np.cumsum([0, *group_sizes])
        root_singular_values: list[list[float]] = []
        for group, count in enumerate(occupied_counts):
            region = slice(offsets[group], offsets[group] + count)
            occupied_block = coefficients[:, region]
            previous = previous_occupied[group]
            if previous is None or count == 0:
                singular_values = np.ones(count)
            else:
                singular_values = np.linalg.svd(
                    previous.T @ overlap @ occupied_block,
                    compute_uv=False,
                )
            root_singular_values.append(singular_values.tolist())
            previous_occupied[group] = occupied_block.copy()
        eig_history.append(
            {
                "maximum_generalized_residual": result[
                    "maximum_block_generalized_residual"
                ],
                "masked_metric_condition_number": result["metric_diagnostics"][
                    "condition_number"
                ],
                "occupied_root_singular_values": root_singular_values,
            }
        )
        return result["energies"], coefficients

    def conditional_get_occ(
        self: Any, mo_energy: np.ndarray | None = None, mo_coeff: np.ndarray | None = None
    ) -> np.ndarray:
        return fixed_occupations.copy()

    mf.eig = MethodType(conditional_eig, mf)
    mf.get_occ = MethodType(conditional_get_occ, mf)
    mf.get_fock = MethodType(conditional_get_fock, mf)
    density_reconstruction = str(
        scf_config.get("density_reconstruction", "orthonormal_mo_sum")
    )
    if density_reconstruction == "physical_metric_nonorthogonal_occupied_projector":
        def conditional_make_rdm1(
            self: Any,
            mo_coeff: np.ndarray | None = None,
            mo_occ: np.ndarray | None = None,
            **_kwargs: Any,
        ) -> np.ndarray:
            coefficients = self.mo_coeff if mo_coeff is None else mo_coeff
            occupations = self.mo_occ if mo_occ is None else mo_occ
            if coefficients is None or occupations is None:
                raise RuntimeError("MO coefficients and occupations are required")
            return nonorthogonal_closed_shell_density(
                coefficients, overlap, occupations
            )

        mf.make_rdm1 = MethodType(conditional_make_rdm1, mf)
    elif density_reconstruction != "orthonormal_mo_sum":
        raise ValueError(f"unknown density reconstruction: {density_reconstruction}")
    cycle_history: list[dict[str, float]] = []

    def callback(environment: dict[str, Any]) -> None:
        density = environment.get("dm")
        cycle_history.append(
            {
                "cycle": int(environment.get("cycle", len(cycle_history))) + 1,
                "total_energy": float(environment.get("e_tot", float("nan"))),
                "energy_change": float(environment.get("de", float("nan"))),
                "gradient_norm": float(environment.get("norm_gorb", float("nan"))),
                "electron_trace": float(np.einsum("ij,ji->", density, overlap))
                if density is not None
                else float("nan"),
            }
        )

    mf.callback = callback
    energy = float(mf.kernel())
    density = mf.make_rdm1()
    electron_trace = float(np.einsum("ij,ji->", density, overlap))
    idempotency = float(
        np.linalg.norm(density @ overlap @ density - 2.0 * density, ord="fro")
        / max(float(np.linalg.norm(density, ord="fro")), 1.0)
    )
    root_values = [
        value
        for item in eig_history[1:]
        for group in item["occupied_root_singular_values"]
        for value in group
    ]
    return {
        "mean_field": mf,
        "converged": bool(mf.converged),
        "cycles": len(cycle_history),
        "experimental_conditional_scf_energy_hartree": energy,
        "electron_trace": electron_trace,
        "density_physical_metric_idempotency_residual": idempotency,
        "fixed_occupations": fixed_occupations.tolist(),
        "eig_history": eig_history,
        "cycle_history": cycle_history,
        "maximum_generalized_residual": max(
            (item["maximum_generalized_residual"] for item in eig_history), default=float("inf")
        ),
        "maximum_masked_metric_condition_number": max(
            (item["masked_metric_condition_number"] for item in eig_history), default=float("inf")
        ),
        "minimum_root_subspace_singular_value": min(root_values, default=1.0),
        "conditional_commutator_residual_history": conditional_residual_history,
        "final_conditional_commutator_residual": conditional_residual_history[-1]
        if conditional_residual_history
        else float("inf"),
        "density_reconstruction": density_reconstruction,
        "final_forbidden_rotation_commutator_residual": forbidden_residual_history[-1]
        if forbidden_residual_history
        else float("inf"),
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version

    started = time.perf_counter()
    inputs = build_reflection_adapted_working_basis(config)
    conditional = run_conditional_scf(config, inputs)
    acceptance = config["acceptance"]
    adaptation = inputs["adaptation"]
    scheduler = inputs["scheduler"]
    support_ch3 = float(
        np.max(
            np.abs(
                inputs["working_basis"][inputs["spaces"]["reference_indices"], :19]
            )
        )
    )
    optimized_fragment_orbitals = conditional["mean_field"].mo_coeff[:, :19]
    localized_cut_single = inputs["scheduler"]["current_block"][:, [0]]
    final_sub_lfmo = np.column_stack((optimized_fragment_orbitals, localized_cut_single))
    fragment_indices = inputs["spaces"]["fragment_indices"]
    reference_indices = inputs["spaces"]["reference_indices"]
    local_coefficients = final_sub_lfmo[fragment_indices, :]
    local_overlap = inputs["spaces"]["fragment"]["overlap"]
    odd_components = set(
        inputs["spaces"]["fragment_config"]["classification"]["odd_ao_components"]
    )
    parity_signs = np.array(
        [
            -1.0
            if str(label[3]).lower().replace(" ", "") in odd_components
            else 1.0
            for label in inputs["spaces"]["fragment"]["molecule"].ao_labels(fmt=False)
        ]
    )
    local_reflection = np.diag(parity_signs)
    reflection_expectations = np.array(
        [
            float(
                (
                    local_coefficients[:, [index]].T
                    @ local_overlap
                    @ local_reflection
                    @ local_coefficients[:, [index]]
                )[0, 0]
            )
            / float(
                (
                    local_coefficients[:, [index]].T
                    @ local_overlap
                    @ local_coefficients[:, [index]]
                )[0, 0]
            )
            for index in range(local_coefficients.shape[1])
        ]
    )
    pi_weights = 0.5 * (1.0 - reflection_expectations)

    parity_by_source: dict[int, str] = {}
    for block in adaptation["blocks"]:
        parity_by_source.update(
            {
                int(index): str(parity)
                for index, parity in zip(
                    block["indices"], block["adapted_parities"], strict=True
                )
            }
        )
    adapted_embedded = np.zeros_like(inputs["spaces"]["fragment_coefficients"])
    adapted_embedded[fragment_indices, :] = adaptation["coefficients"]
    sigma_reference = adapted_embedded[
        :, [index for index in range(20) if parity_by_source[index] == "sigma"]
    ]
    pi_reference = adapted_embedded[
        :, [index for index in range(20) if parity_by_source[index] == "pi"]
    ]
    physical_overlap = inputs["spaces"]["overlap"]
    sigma_projector = metric_projector(physical_overlap, sigma_reference)
    pi_projector = metric_projector(physical_overlap, pi_reference)
    b_ov_projector = metric_projector(physical_overlap, optimized_fragment_orbitals)
    b_ov_occupied = optimized_fragment_orbitals[
        :, np.asarray(conditional["mean_field"].mo_occ[:19]) > 0.0
    ]
    b_ov_occupied_projector = metric_projector(physical_overlap, b_ov_occupied)
    target_norm = float(
        (localized_cut_single.T @ physical_overlap @ localized_cut_single)[0, 0]
    )
    target_sigma_weight = float(
        (
            localized_cut_single.T
            @ physical_overlap
            @ sigma_projector
            @ localized_cut_single
        )[0, 0]
        / target_norm
    )
    target_pi_weight = float(
        (
            localized_cut_single.T
            @ physical_overlap
            @ pi_projector
            @ localized_cut_single
        )[0, 0]
        / target_norm
    )
    b_ov_sigma_dimension = float(np.trace(b_ov_projector @ sigma_projector))
    b_ov_pi_dimension = float(np.trace(b_ov_projector @ pi_projector))
    occupied_sigma_dimension = float(
        np.trace(b_ov_occupied_projector @ sigma_projector)
    )
    occupied_pi_dimension = float(np.trace(b_ov_occupied_projector @ pi_projector))
    occupied_pi_leakage = subspace_leakage(
        physical_overlap, b_ov_occupied, pi_reference
    )
    expected_occupied_sigma = sum(
        parity_by_source[int(index)] == "sigma" for index in inputs["occupied"]
    )
    expected_occupied_pi = sum(
        parity_by_source[int(index)] == "pi" for index in inputs["occupied"]
    )
    projector_tolerance = float(acceptance["subspace_projector_residual_tolerance"])
    projector_state_residuals = {
        "sigma_conservation": abs(
            b_ov_sigma_dimension + target_sigma_weight - sigma_reference.shape[1]
        ),
        "pi_conservation": abs(
            b_ov_pi_dimension + target_pi_weight - pi_reference.shape[1]
        ),
        "b_ov_dimension": abs(
            b_ov_sigma_dimension + b_ov_pi_dimension
            - optimized_fragment_orbitals.shape[1]
        ),
        "target_weight": abs(target_sigma_weight + target_pi_weight - 1.0),
    }
    parity_tolerance = float(acceptance["sigma_pi_leakage_tolerance"])
    measured_types = [
        "sigma"
        if abs(weight) <= parity_tolerance
        else "pi"
        if abs(1.0 - weight) <= parity_tolerance
        else "mixed"
        for weight in pi_weights
    ]
    optimized_types = measured_types[:19]
    final_metric = final_sub_lfmo.T @ inputs["spaces"]["overlap"] @ final_sub_lfmo
    final_metric_eigenvalues = np.linalg.eigvalsh(final_metric)
    final_support = float(np.max(np.abs(final_sub_lfmo[reference_indices, :])))
    checks = {
        "reflection_adaptation": adaptation["maximum_parity_residual"]
        <= float(acceptance["reflection_parity_residual_tolerance"]),
        "adapted_orthonormality": adaptation["orthonormality_after_residual"]
        <= float(acceptance["orthonormality_residual_tolerance"]),
        "adapted_subspace_preserved": adaptation["full_subspace_projector_residual"]
        <= float(acceptance["subspace_projector_residual_tolerance"]),
        "kost_scheduler_quiescent": bool(scheduler["scheduler_quiescent"]),
        "working_basis_square_full_rank": inputs["working_basis"].shape == (22, 22)
        and np.linalg.matrix_rank(inputs["working_basis"]) == 22,
        "strict_fragment_support": support_ch3
        <= float(acceptance["coefficient_support_tolerance"]),
        "conditional_scf_converged": conditional["converged"],
        "electron_trace": abs(conditional["electron_trace"] - 10.0)
        <= float(acceptance["electron_trace_tolerance"]),
        "physical_density_idempotency": conditional[
            "density_physical_metric_idempotency_residual"
        ]
        <= float(acceptance["physical_density_idempotency_tolerance"]),
        "masked_metric_conditioned": conditional[
            "maximum_masked_metric_condition_number"
        ]
        <= float(acceptance["metric_condition_number_limit"]),
        "generalized_eigen_residual": conditional["maximum_generalized_residual"]
        <= float(acceptance["generalized_eigen_residual_tolerance"]),
        "conditional_commutator_residual": conditional[
            "final_conditional_commutator_residual"
        ]
        <= float(acceptance["conditional_commutator_residual_tolerance"]),
        "root_continuity": conditional["minimum_root_subspace_singular_value"]
        >= float(acceptance["root_subspace_minimum_singular_value"]),
        "final_sub_lfmo_full_rank": np.linalg.matrix_rank(final_sub_lfmo) == 20
        and float(final_metric_eigenvalues[0]) > 0.0,
        "final_sub_lfmo_strict_support": final_support
        <= float(acceptance["coefficient_support_tolerance"]),
        "optimized_b_ov_sigma_pi_pure": "mixed" not in optimized_types,
        "mixed_cut_projector_state": max(projector_state_residuals.values())
        <= projector_tolerance,
        "no_production_labels": config["production_labels_allowed"] is False,
    }
    peak_rss = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if resource is not None
        else float("nan")
    )
    return {
        "schema": "ai4orgchem-one-cut-conditional-scf/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production independent conditional-SCF candidate",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf_version,
            "platform": platform.platform(),
        },
        "reflection_adaptation": {
            key: value
            for key, value in adaptation.items()
            if key not in {"coefficients", "transform"}
        },
        "kost": {
            "cycles": scheduler["cycles_completed"],
            "return_edges": scheduler["return_edge_count"],
            "scheduler_quiescent": scheduler["scheduler_quiescent"],
            "maximum_occupied_probe_overlap": scheduler[
                "maximum_occupied_probe_overlap"
            ],
            "maximum_vacant_probe_overlap": scheduler["maximum_vacant_probe_overlap"],
        },
        "conditional_scf": {
            key: value for key, value in conditional.items() if key != "mean_field"
        },
        "basis": {
            "shape": list(inputs["working_basis"].shape),
            "rank": int(np.linalg.matrix_rank(inputs["working_basis"])),
            "group_sizes": inputs["group_sizes"],
            "group_occupied_roots": config["conditional_blocks"][
                "fixed_doubly_occupied_roots"
            ],
            "ch3_outside_support_max": support_ch3,
        },
        "final_sub_lfmo": {
            "shape": list(final_sub_lfmo.shape),
            "rank": int(np.linalg.matrix_rank(final_sub_lfmo)),
            "metric_minimum_eigenvalue": float(final_metric_eigenvalues[0]),
            "metric_maximum_eigenvalue": float(final_metric_eigenvalues[-1]),
            "metric_condition_number": float(
                final_metric_eigenvalues[-1] / final_metric_eigenvalues[0]
            ),
            "outside_ch3_support_max": final_support,
            "reference_occupations": [2.0] * 4 + [0.0] * 15 + [1.0],
            "optimized_b_ov_measured_types": optimized_types,
            "optimized_b_ov_sigma_count": optimized_types.count("sigma"),
            "optimized_b_ov_pi_count": optimized_types.count("pi"),
            "optimized_b_ov_mixed_count": optimized_types.count("mixed"),
            "cut_single_role": "mixed_kost_cut_role",
            "cut_single_measured_reflection_type": measured_types[19],
            "cut_single_pi_weight": float(pi_weights[19]),
            "reflection_expectations": reflection_expectations.tolist(),
            "pi_weights": pi_weights.tolist(),
        },
        "mixed_cut_projector_state": {
            "sigma_reference_dimension": int(sigma_reference.shape[1]),
            "pi_reference_dimension": int(pi_reference.shape[1]),
            "b_ov_effective_sigma_dimension": b_ov_sigma_dimension,
            "b_ov_effective_pi_dimension": b_ov_pi_dimension,
            "occupied_b_ov_dimension": int(b_ov_occupied.shape[1]),
            "occupied_b_ov_effective_sigma_dimension": occupied_sigma_dimension,
            "occupied_b_ov_effective_pi_dimension": occupied_pi_dimension,
            "occupied_b_ov_average_pi_leakage": occupied_pi_leakage,
            "expected_occupied_sigma_dimension": int(expected_occupied_sigma),
            "expected_occupied_pi_dimension": int(expected_occupied_pi),
            "occupied_subspace_reflection_pure": bool(
                abs(occupied_sigma_dimension - expected_occupied_sigma)
                <= projector_tolerance
                and abs(occupied_pi_dimension - expected_occupied_pi)
                <= projector_tolerance
            ),
            "target_sigma_weight": target_sigma_weight,
            "target_pi_weight": target_pi_weight,
            "conservation_residuals": projector_state_residuals,
            "sigma_projector": projector_diagnostics(
                physical_overlap, sigma_reference
            ),
            "pi_projector": projector_diagnostics(physical_overlap, pi_reference),
            "b_ov_projector": projector_diagnostics(
                physical_overlap, optimized_fragment_orbitals
            ),
            "occupied_b_ov_projector": projector_diagnostics(
                physical_overlap, b_ov_occupied
            ),
            "interpretation": "gauge-invariant subspace diagnostic only",
        },
        "provenance": {
            "experiment_id": config["experiment_id"],
            "config_hash": sha256_json(config),
            "geometry_hash": sha256_json(inputs["spaces"]["composite_atoms"]),
            "working_basis_hash": hashlib.sha256(
                np.asarray(inputs["working_basis"], dtype="<f8").tobytes()
            ).hexdigest(),
            "code_commit": git_commit(),
            "resource_profile": config["resources"]["profile"],
        },
        "resources": {
            "wall_time_seconds": time.perf_counter() - started,
            "peak_rss_mib": peak_rss,
            "thread_count": int(os.environ.get("OMP_NUM_THREADS", "1")),
        },
        "boundaries": {
            "one_cut_conditional_scf_run": True,
            "candidate_occupation_rule_used": True,
            "source_faithful_reproduction_claimed": False,
            "two_cut_fragment_run": False,
            "dsi_fud_run": False,
            "scientific_energy_labels_generated": False,
            "prohibited_outputs": config["prohibited_outputs"],
        },
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def render_markdown(report: dict[str, Any]) -> str:
    result = report["conditional_scf"]
    lines = [
        "# Gate 0 one-cut reflection adaptation and conditional-SCF candidate",
        "",
        f"- Date: {report['date']}",
        f"- Disposition: **{report['disposition']}**",
        "- Classification: non-production independent candidate",
        "- DSI/FUD or LFMO energy-component label: not generated",
        "",
        "## Result",
        "",
        "| Diagnostic | Value |",
        "|---|---:|",
        f"| Reflection maximum parity residual | {report['reflection_adaptation']['maximum_parity_residual']:.3e} |",
        f"| Adapted orthonormality residual | {report['reflection_adaptation']['orthonormality_after_residual']:.3e} |",
        f"| Full CH3 subspace projector residual | {report['reflection_adaptation']['full_subspace_projector_residual']:.3e} |",
        f"| Conditional groups / occupied roots | {report['basis']['group_sizes']} / {report['basis']['group_occupied_roots']} |",
        f"| SCF converged / cycles | {result['converged']} / {result['cycles']} |",
        f"| Experimental conditional-SCF energy (Eh) | {result['experimental_conditional_scf_energy_hartree']:.12f} |",
        f"| Electron trace | {result['electron_trace']:.12f} |",
        f"| Maximum generalized residual | {result['maximum_generalized_residual']:.3e} |",
        f"| Maximum masked metric condition | {result['maximum_masked_metric_condition_number']:.6g} |",
        f"| Minimum occupied-root subspace singular value | {result['minimum_root_subspace_singular_value']:.6g} |",
        f"| Physical-metric density idempotency residual | {result['density_physical_metric_idempotency_residual']:.3e} |",
        f"| Final conditional commutator residual | {result['final_conditional_commutator_residual']:.3e} |",
        f"| Final sub-LFMO rank / metric condition | {report['final_sub_lfmo']['rank']} / {report['final_sub_lfmo']['metric_condition_number']:.6g} |",
        f"| Optimized B-ov sigma / pi / mixed | {report['final_sub_lfmo']['optimized_b_ov_sigma_count']} / {report['final_sub_lfmo']['optimized_b_ov_pi_count']} / {report['final_sub_lfmo']['optimized_b_ov_mixed_count']} |",
        f"| Cut-single role / measured type / pi weight | {report['final_sub_lfmo']['cut_single_role']} / {report['final_sub_lfmo']['cut_single_measured_reflection_type']} / {report['final_sub_lfmo']['cut_single_pi_weight']:.6g} |",
        f"| B-ov effective sigma / pi dimensions | {report['mixed_cut_projector_state']['b_ov_effective_sigma_dimension']:.6f} / {report['mixed_cut_projector_state']['b_ov_effective_pi_dimension']:.6f} |",
        f"| Occupied B-ov effective sigma / pi dimensions | {report['mixed_cut_projector_state']['occupied_b_ov_effective_sigma_dimension']:.6f} / {report['mixed_cut_projector_state']['occupied_b_ov_effective_pi_dimension']:.6f} |",
        f"| Occupied B-ov average pi leakage | {report['mixed_cut_projector_state']['occupied_b_ov_average_pi_leakage']:.6f} |",
        f"| Target sigma / pi projector weights | {report['mixed_cut_projector_state']['target_sigma_weight']:.6f} / {report['mixed_cut_projector_state']['target_pi_weight']:.6f} |",
        f"| Projector-state maximum conservation residual | {max(report['mixed_cut_projector_state']['conservation_residuals'].values()):.3e} |",
        "",
        "## Interpretation boundary",
        "",
        "This is the first executed one-cut conditional-SCF candidate. Each iteration",
        "rebuilds the full AO Fock matrix from the current density, transforms F and S",
        "to the reflection-adapted/Kost working basis, and masks the source-shaped",
        "B-ov / cut-reference-single / H-v cross blocks. Fixed group occupations",
        "[4, 1, 0] are an explicit independent candidate. The reported energy is not",
        "a DSI, FUD, conjugation, stabilization, or production LFMO energy.",
        "",
        "## Provenance",
        "",
        f"- Experiment: `{report['provenance']['experiment_id']}`.",
        f"- Geometry SHA-256: `{report['provenance']['geometry_hash']}`.",
        f"- Working-basis SHA-256: `{report['provenance']['working_basis_hash']}`.",
        f"- Config SHA-256: `{report['provenance']['config_hash']}`.",
        f"- Code commit at run: `{report['provenance']['code_commit']}`.",
        f"- Runtime: Python `{report['runtime']['python']}`, PySCF `{report['runtime']['pyscf']}`, NumPy `{report['runtime']['numpy']}`.",
        f"- Wall time / peak RSS / threads: `{report['resources']['wall_time_seconds']:.6f} s` / `{report['resources']['peak_rss_mib']:.3f} MiB` / `{report['resources']['thread_count']}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    config = load_yaml(args.config)
    report = json_safe(run_experiment(config))
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8", newline="\n")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    result = report["conditional_scf"]
    print(
        f"{report['disposition']}: converged={result['converged']} cycles={result['cycles']} "
        f"energy={result['experimental_conditional_scf_energy_hartree']:.12f} "
        f"trace={result['electron_trace']:.12f} root_min={result['minimum_root_subspace_singular_value']:.6g}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
