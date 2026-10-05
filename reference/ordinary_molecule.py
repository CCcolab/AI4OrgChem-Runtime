"""Acceptance-only molecular reference using pinned raw PySCF dependencies.

This module does not import the scientific application's implementation. The
ordinary SCF engine, AO integrals and original-grid semilocal XC are shared
PySCF dependencies; J/K contractions, energy assembly, final metrics and the
conditional fixed point are independent. It cannot approve a budget, enable a
service profile, establish variationality or grant a research interpretation.
The caller must enforce the bounded acceptance process before calling ``run``.
"""
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math

import numpy as np
from scipy.linalg import eigvalsh

from reference import user_molecule as conditional

REFERENCE_VERSION = "MOLECULAR_REFERENCE_V1"
MAXIMUM_REFERENCE_NAO = 40
FINAL_OPERATOR = "RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS"
_ORDINARY_KEYS = {"init_guess", "conv_tol", "conv_tol_grad", "max_cycle", "diis",
    "diis_space", "diis_start_cycle", "damp", "level_shift", "direct_scf",
    "direct_scf_tol", "max_memory_mb"}
_GRID_KEYS = {"level", "prune", "radi_method", "radii_adjust", "atomic_radii",
    "becke_scheme", "alignment", "atom_grid"}
_GRID_FIXED = {"prune": "nwchem_prune", "radi_method": "treutler",
    "radii_adjust": "treutler_atomic_radii_adjust", "atomic_radii": "BRAGG_RADII",
    "becke_scheme": "original_becke", "alignment": 8, "atom_grid": {}}


@dataclass
class MolecularContext:
    mol: object
    mean_field: object
    aos: tuple
    metadata: dict
    profile: dict


@dataclass
class ReferenceResult:
    record: dict
    arrays: dict
    context: MolecularContext


def array_identity(array):
    """Hash shape and canonical little-endian float64 bytes explicitly."""
    value = np.ascontiguousarray(array, dtype="<f8")
    if not np.isfinite(value).all():
        raise ValueError("Nonfinite frozen array")
    raw = value.tobytes(order="C")
    return {"shape": list(value.shape), "dtype": "<f8", "order": "C",
            "sha256": hashlib.sha256(raw).hexdigest()}


def _json_identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _validate_input(request, atoms, profile):
    if (type(request.get("charge")) is not int or request["charge"] != 0
            or type(request.get("multiplicity")) is not int or request["multiplicity"] != 1):
        raise ValueError("Only neutral closed-shell singlet requests supported")
    if request.get("coordinate_unit") != "angstrom":
        raise ValueError("Explicit Angstrom coordinates required")
    if not atoms or any(len(atom) != 2 or atom[0] not in ("C", "H") for atom in atoms):
        raise ValueError("Use the normalized [element, [x,y,z]] C/H atom list")
    coordinates = np.asarray([atom[1] for atom in atoms], dtype=float)
    if coordinates.shape != (len(atoms), 3) or not np.isfinite(coordinates).all():
        raise ValueError("Invalid coordinate array")
    if np.max(np.abs(coordinates[:, 2])) > 1e-8:
        raise ValueError("Fixed xy-plane orientation required")
    if len(set(map(tuple, coordinates))) != len(atoms):
        raise ValueError("Coincident nuclei rejected without geometry edits")
    fragments = request.get("fragments", [])
    if [fragment.get("id") for fragment in fragments] != ["A", "B"]:
        raise ValueError("Exactly two ordered carbon groups A and B required")
    assigned = [index for group in fragments for index in group["carbon_atom_indices_1based"]]
    carbons = {index for index, atom in enumerate(atoms, 1) if atom[0] == "C"}
    if (any(type(index) is not int for index in assigned)
            or len(set(assigned)) != len(assigned) or set(assigned) != carbons
            or any(not group["carbon_atom_indices_1based"] for group in fragments)):
        raise ValueError("Every carbon must be assigned once, with no H assignment")
    threads = request.get("resources", {}).get("threads")
    if type(threads) is not int or threads != 1:
        raise ValueError("Acceptance reference requires exactly one thread")
    if set(profile.get("ordinary", {})) != _ORDINARY_KEYS:
        raise ValueError("Complete frozen ordinary settings required")
    if set(profile.get("grid", {})) != _GRID_KEYS:
        raise ValueError("Complete frozen grid settings required")
    if any(profile["grid"][key] != value for key, value in _GRID_FIXED.items()):
        raise ValueError("Unsupported grid setting; no silent default substitution")
    if type(profile["grid"]["level"]) is not int or not 0 <= profile["grid"]["level"] <= 9:
        raise ValueError("Unsupported grid level")
    if profile.get("xc") != "B3LYPG" or profile.get("basis") not in ("sto-3g", "6-31g(d)"):
        raise ValueError("Only the frozen pilot/research basis and XC are supported")
    if profile["ordinary"]["diis"] is not True:
        raise ValueError("Frozen ordinary profile requires DIIS")
    ordinary = profile["ordinary"]
    for key in ("max_cycle", "diis_space", "diis_start_cycle", "max_memory_mb"):
        if type(ordinary[key]) is not int or ordinary[key] < 1:
            raise ValueError("Invalid positive integer ordinary setting: " + key)
    for key in ("conv_tol", "conv_tol_grad", "direct_scf_tol"):
        if (type(ordinary[key]) not in (int, float) or not math.isfinite(ordinary[key])
                or ordinary[key] <= 0):
            raise ValueError("Invalid finite positive ordinary tolerance: " + key)
    if (ordinary["init_guess"] != "minao" or type(ordinary["direct_scf"]) is not bool
            or type(ordinary["damp"]) not in (int, float) or not math.isfinite(ordinary["damp"])
            or not 0 <= ordinary["damp"] < 1 or type(ordinary["level_shift"]) not in (int, float)
            or not math.isfinite(ordinary["level_shift"]) or ordinary["level_shift"] < 0):
        raise ValueError("Unsupported ordinary initialization or mixing settings")
    return coordinates


def build(request, atoms, profile):
    """Build only raw molecule/configuration; no SCF, grids or full ERI."""
    coordinates = _validate_input(request, atoms, profile)
    from pyscf import dft, gto, lib
    from pyscf.dft import gen_grid, radi
    dependencies = {name: importlib.metadata.version(name) for name in ("pyscf", "numpy", "scipy")}
    if dependencies != profile.get("expected_dependencies"):
        raise ValueError("Reference dependencies differ from the frozen profile")
    lib.num_threads(1)
    molecule = gto.M(atom=atoms, basis=profile["basis"], unit="Angstrom", charge=0,
        spin=0, cart=False, symmetry=False, ecp={}, verbose=0,
        max_memory=profile["ordinary"]["max_memory_mb"])
    nao, electrons = int(molecule.nao_nr()), int(molecule.nelectron)
    if not 1 <= nao <= MAXIMUM_REFERENCE_NAO:
        raise ValueError("Full molecular reference limited to 1..40 AO before ERI allocation")
    if electrons < 2 or electrons % 2 or electrons > 2 * nao:
        raise ValueError("Unsupported closed-shell occupation")
    mean_field = dft.RKS(molecule)
    mean_field.verbose, mean_field.xc = 0, profile["xc"]
    for key, value in profile["ordinary"].items():
        setattr(mean_field, "max_memory" if key == "max_memory_mb" else key, value)
    grids = mean_field.grids
    grids.level = profile["grid"]["level"]
    grids.prune, grids.radi_method = gen_grid.nwchem_prune, radi.treutler
    grids.radii_adjust, grids.atomic_radii = radi.treutler_atomic_radii_adjust, radi.BRAGG_RADII
    grids.becke_scheme, grids.alignment, grids.atom_grid = gen_grid.original_becke, 8, {}
    mean_field.small_rho_cutoff, mean_field.nlc = 0, ""
    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(mean_field.xc, spin=0)
    if (not np.isfinite([omega, alpha, hybrid]).all() or abs(omega) > 1e-14
            or abs(alpha - hybrid) > 1e-14 or not 0 <= hybrid <= 1):
        raise ValueError("Only the locked finite global-hybrid functional is supported")
    labels = [(int(label[0]), *label[1:]) for label in molecule.ao_labels(fmt=False)]
    groups = {group["id"]: group["carbon_atom_indices_1based"] for group in request["fragments"]}
    aos = conditional.classify(labels, coordinates, groups)
    metadata = {"reference_version": REFERENCE_VERSION, "nao": nao, "electron_count": electrons,
        "ao_labels": [list(label) for label in labels],
        "ao_descriptors": [{"kind": ao.kind, "fragment": ao.group} for ao in aos],
        "atom_coordinates_angstrom": coordinates.tolist(), "atom_elements": [atom[0] for atom in atoms],
        "fragments_1based": groups, "atom_order_preserved": True, "coordinate_reorientation": False,
        "molecule_effective": {"basis": profile["basis"], "unit": "Angstrom", "charge": 0,
            "spin": 0, "cart": False, "symmetry": False, "ecp": {}},
        "basis_expansion_sha256": hashlib.sha256(repr(molecule._basis).encode("utf-8")).hexdigest(),
        "dependencies": dependencies, "threads": 1,
        "xc_effective": {"xc": mean_field.xc, "omega": float(omega), "alpha": float(alpha), "hybrid": float(hybrid)},
        "ordinary_effective": {key: getattr(mean_field, "max_memory" if key == "max_memory_mb" else key)
                               for key in profile["ordinary"]},
        "grid_effective": dict(profile["grid"], small_rho_cutoff=0, nlc=""),
        "profile_id": profile["id"], "profile_canonical_sha256": _json_identity(profile),
        "shared_dependencies": ["PySCF ordinary SCF engine", "PySCF raw AO integrals",
            "PySCF original AO/grid semilocal XC", "NumPy/SciPy linear algebra"],
        "independent_components": ["input/configuration driver", "AO parity assignment",
            "full-tensor J/K contractions", "energy assembly", "final metrics", "conditional iteration"],
        "scientific_scope_approval": "NOT_GRANTED", "variational_status": "NOT_ESTABLISHED",
        "stability_analysis": "NOT_EXECUTED"}
    return MolecularContext(molecule, mean_field, aos, metadata, profile)


def ordinary_evaluate(density, hcore, overlap, eri, hybrid, nuclear, xc):
    """Unprojected ordinary functional, with independent chemist-index J/K."""
    density = np.asarray(density, dtype=float)
    hcore, overlap, eri = (np.asarray(value, dtype=float) for value in (hcore, overlap, eri))
    if (density.ndim != 2 or density.shape[0] != density.shape[1]
            or hcore.shape != density.shape or overlap.shape != density.shape
            or eri.shape != (len(density),) * 4
            or any(not np.isfinite(value).all() for value in (density, hcore, overlap, eri))):
        raise ValueError("Invalid finite ordinary arrays")
    grid_electrons, xc_energy, vxc = xc(density.copy())
    vxc = np.asarray(vxc, dtype=float)
    if vxc.shape != density.shape or not np.isfinite(vxc).all():
        raise ValueError("Invalid original-grid XC potential")
    if not np.isfinite([grid_electrons, xc_energy, hybrid, nuclear]).all() or not 0 <= hybrid <= 1:
        raise ValueError("Nonfinite or unsupported ordinary functional component")
    j = np.tensordot(eri, density, axes=([2, 3], [0, 1]))
    k = np.tensordot(eri, density, axes=([1, 3], [0, 1]))
    trace = lambda matrix: float(np.sum(matrix * density.T))
    components = {"one_electron": trace(hcore), "coulomb": .5 * trace(j),
        "exact_exchange": -.25 * hybrid * trace(k), "semilocal_xc": float(xc_energy),
        "nuclear_repulsion": float(nuclear)}
    fock = hcore + j - .5 * hybrid * k + vxc
    return {"density": density.copy(), "J": j, "K": k, "Vxc": vxc, "Fraw": fock,
        "components_hartree": components, "total_energy_hartree": sum(components.values()),
        "physical_metric_electron_count": trace(overlap), "grid_electron_count": float(grid_electrons)}


def _metric(metric_id, value, formula, units, threshold, required, operator, profile):
    return {"metric_id": metric_id, "value": value, "formula_version": REFERENCE_VERSION,
        "formula": formula, "units": units, "threshold": threshold,
        "threshold_version": "CANDIDATE_PROFILE:" + profile["id"], "required": required,
        "operator_source": operator}


def _final_metrics(density, overlap, fock, electrons, energy, components, profile):
    metrics = {"physical_metric_electron_count": float(np.sum(overlap * density.T)),
        "final_commutator_frobenius_norm": float(np.linalg.norm(fock @ density @ overlap - overlap @ density @ fock)),
        "closed_shell_idempotency_relative_residual": float(np.linalg.norm(density @ overlap @ density - 2 * density)
                                                          / max(np.linalg.norm(density), 1.0)),
        "energy_component_closure_residual_hartree": float(sum(components.values()) - energy)}
    if not np.isfinite(list(metrics.values())).all():
        raise ValueError("Nonfinite required final metric")
    threshold = profile["thresholds"]
    metrics["metric_metadata"] = {
        "electron_count": _metric("ORD_NE", metrics["physical_metric_electron_count"], "Tr(S D)", "electrons",
            threshold["electron_count_abs"], True, "PHYSICAL_OVERLAP", profile),
        "commutator": _metric("ORD_COMM", metrics["final_commutator_frobenius_norm"], "||F D S - S D F||F",
            "AO_matrix_units", threshold["commutator_frobenius"], True, FINAL_OPERATOR, profile),
        "idempotency": _metric("ORD_IDEMP", metrics["closed_shell_idempotency_relative_residual"],
            "||D S D - 2 D||F / max(||D||F,1)", "AO_density_relative", threshold["idempotency_relative"],
            True, "PHYSICAL_OVERLAP", profile),
        "energy_closure": _metric("ORD_CLOSE", metrics["energy_component_closure_residual_hartree"],
            "sum(five components) - PySCF returned energy", "hartree", threshold["energy_closure_hartree"],
            True, "ORDINARY_FUNCTIONAL", profile)}
    metrics["qualification_tests"] = {
        "electron_count": abs(metrics["physical_metric_electron_count"] - electrons) <= threshold["electron_count_abs"],
        "commutator": metrics["final_commutator_frobenius_norm"] <= threshold["commutator_frobenius"],
        "idempotency": metrics["closed_shell_idempotency_relative_residual"] <= threshold["idempotency_relative"],
        "energy_closure": abs(metrics["energy_component_closure_residual_hartree"]) <= threshold["energy_closure_hartree"]}
    return metrics


def run_ordinary(request, atoms, profile, progress=lambda phase: None):
    """Run ordinary SCF and independently recompute all final quantities.

    ``atoms`` is the existing input parser's ``[[element,[x,y,z]],...]`` list.
    The context is in-memory only; export ``record`` as JSON and ``arrays`` to a
    separate NPZ. None of the profile's service-enabling flags are mutated.
    """
    context = build(request, atoms, profile)
    molecule, mean_field = context.mol, context.mean_field
    progress("GRID_BUILD")
    mean_field.grids.build(with_non0tab=True)
    grid_before = {name: array_identity(getattr(mean_field.grids, name)) for name in ("coords", "weights")}
    history = []
    def callback(environment):
        row = {"cycle": int(environment["cycle"]) + 1}
        for key in ("e_tot", "norm_gorb", "norm_ddm"):
            value = environment.get(key)
            row[key] = float(value) if value is not None and math.isfinite(float(value)) else None
        history.append(row)
    mean_field.callback = callback
    progress("ORDINARY_SCF")
    returned_energy = float(mean_field.kernel())
    if not math.isfinite(returned_energy):
        raise ValueError("Nonfinite ordinary SCF energy")
    grid_after = {name: array_identity(getattr(mean_field.grids, name)) for name in ("coords", "weights")}
    if grid_before != grid_after:
        raise ValueError("Original frozen grid changed during ordinary SCF")
    density = np.asarray(mean_field.make_rdm1(), dtype=float)
    progress("RAW_INTEGRALS")
    overlap = np.asarray(molecule.intor("int1e_ovlp_sph"), dtype=float)
    hcore = np.asarray(molecule.intor("int1e_kin_sph") + molecule.intor("int1e_nuc_sph"), dtype=float)
    eri = np.asarray(molecule.intor("int2e_sph", aosym="s1"), dtype=float)
    xc, hybrid = conditional.original_grid_xc(mean_field)
    progress("ORDINARY_RECOMPUTE")
    evaluated = ordinary_evaluate(density, hcore, overlap, eri, hybrid, float(molecule.energy_nuc()), xc)
    arrays = {key: value for key, value in evaluated.items() if isinstance(value, np.ndarray)}
    arrays.update({"overlap": overlap, "hcore": hcore, "eri": eri,
        "mo_coefficients": np.asarray(mean_field.mo_coeff, dtype=float),
        "mo_energies_hartree": np.asarray(mean_field.mo_energy, dtype=float),
        "mo_occupations": np.asarray(mean_field.mo_occ, dtype=float),
        "grid_coords": np.asarray(mean_field.grids.coords, dtype=float),
        "grid_weights": np.asarray(mean_field.grids.weights, dtype=float)})
    record = {key: value for key, value in evaluated.items() if not isinstance(value, np.ndarray)}
    record["independent_functional_energy_hartree"] = record["total_energy_hartree"]
    record["total_energy_hartree"] = returned_energy
    record.update(_final_metrics(density, overlap, arrays["Fraw"], molecule.nelectron, returned_energy,
                                  record["components_hartree"], profile))
    occupations = arrays["mo_occupations"]
    record["qualification_tests"].update({"converged": bool(mean_field.converged),
        "energy_finite": True, "occupation_electron_count": bool(abs(float(occupations.sum()) - molecule.nelectron) <= 1e-12),
        "closed_shell_occupation": bool(np.isin(occupations, [0., 2.]).all())})
    final_energies = eigvalsh(arrays["Fraw"], overlap, check_finite=True)
    arrays["final_non_diis_eigenvalues_hartree"] = final_energies
    count = molecule.nelectron // 2
    record.update({"converged": bool(mean_field.converged), "cycles": int(getattr(mean_field, "cycles", len(history))),
        "history": history, "final_operator_source": FINAL_OPERATOR,
        "occupied_virtual_gap_hartree": float(arrays["mo_energies_hartree"][count] - arrays["mo_energies_hartree"][count-1])
            if count < len(occupations) else None,
        "gap_operator_source": "PYSCF_RETURNED_ORDINARY_ORBITALS",
        "final_non_diis_gap_hartree": float(final_energies[count] - final_energies[count-1]) if count < len(occupations) else None,
        "final_non_diis_gap_operator_source": FINAL_OPERATOR,
        "undefined_diagnostics": [] if count < len(occupations) else [{"field": "occupied_virtual_gap_hartree", "reason": "NO_VIRTUAL_ORBITALS"}],
        "variational_status": "NOT_ESTABLISHED", "stability_analysis": "NOT_EXECUTED",
        "molecular_execution": "EXECUTED_DIAGNOSTIC_NOT_ACCEPTED", "research_status": "NOT_QUALIFIED",
        "grid_identity": grid_after, "grid_points": int(len(mean_field.grids.weights)),
        "metadata": context.metadata,
        "array_identities": {key: array_identity(value) for key, value in arrays.items()}})
    json.dumps(record, allow_nan=False)
    return ReferenceResult(record, arrays, context)


def run_conditional(ordinary, rule_path, expected_sha256, settings=None, progress=lambda phase: None):
    """Independent complete molecular fixed point from frozen ordinary D.

    This does not reuse the tested implementation's AO mask, operators, energy,
    occupation or iteration helpers. Shared raw integral/XC errors remain out
    of scope. Stopping criteria do not establish research qualification.
    """
    context, arrays = ordinary.context, ordinary.arrays
    profile = context.profile
    entries = conditional.load_rules(rule_path, expected_sha256)
    for key in ("density", "hcore", "overlap", "eri", "grid_coords", "grid_weights"):
        if array_identity(arrays[key]) != ordinary.record["array_identities"][key]:
            raise ValueError("Frozen ordinary array changed: " + key)
    if (array_identity(context.mean_field.grids.coords) != ordinary.record["array_identities"]["grid_coords"]
            or array_identity(context.mean_field.grids.weights) != ordinary.record["array_identities"]["grid_weights"]):
        raise ValueError("Original frozen grid changed before conditional reference")
    xc, hybrid = conditional.original_grid_xc(context.mean_field)
    progress("CONDITIONAL_REFERENCE")
    evaluated = conditional.fixed_point(density=arrays["density"], h=arrays["hcore"], overlap=arrays["overlap"],
        eri=arrays["eri"], aos=context.aos, entries=entries, electrons=int(context.mol.nelectron), hybrid=hybrid,
        nuclear=float(context.mol.energy_nuc()), xc=xc, settings=profile["conditional"] if settings is None else settings)
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
        "stability_analysis": "NOT_EXECUTED",
        "array_identities": {key: array_identity(value) for key, value in exported_arrays.items()}})
    forbidden = np.array([[left.kind == right.kind == "pi" and left.group != right.group
                           for right in context.aos] for left in context.aos], dtype=bool)
    record["masked_overlap_cross_pi_max_abs"] = float(np.max(np.abs(exported_arrays["masked_overlap"][forbidden]), initial=0))
    record["conditional_fock_cross_pi_max_abs"] = float(np.max(np.abs(exported_arrays["Fcond"][forbidden]), initial=0))
    threshold = profile["thresholds"]
    record["qualification_tests"] = {
        "converged": bool(record["converged"]), "energy_finite": math.isfinite(record["total_energy_hartree"]),
        "electron_count": abs(record["masked_metric_electron_count"] - context.mol.nelectron) <= threshold["electron_count_abs"],
        "commutator": record["final_commutator_frobenius_norm"] <= threshold["commutator_frobenius"],
        "idempotency": record["closed_shell_idempotency_relative_residual"] <= threshold["idempotency_relative"],
        "energy_closure": abs(record["energy_component_closure_residual_hartree"]) <= threshold["energy_closure_hartree"],
        "masked_overlap_positive": record["masked_overlap_minimum_eigenvalue"] > 0,
        "overlap_mask": record["masked_overlap_cross_pi_max_abs"] <= threshold["mask_max_abs"],
        "fock_mask": record["conditional_fock_cross_pi_max_abs"] <= threshold["mask_max_abs"],
        "occupation_electron_count": bool(abs(float(exported_arrays["mo_occupations"].sum()) - context.mol.nelectron) <= 1e-12),
        "closed_shell_occupation": bool(np.isin(exported_arrays["mo_occupations"], [0., 2.]).all())}
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
        "occupied_virtual_gap_hartree": ("COND_GAP_LAST", "epsilon[LUMO] - epsilon[HOMO] from last diagonalization", "hartree", None, False, record["gap_operator_source"]),
        "final_non_diis_gap_hartree": ("COND_GAP_FINAL", "eig(F_cond,S_tilde)[N/2] - eig(F_cond,S_tilde)[N/2-1]", "hartree", None, False, FINAL_OPERATOR)}
    record["metric_metadata"] = {name: _metric(metric_id, record[name], formula, units, bound, required, operator, profile)
        for name, (metric_id, formula, units, bound, required, operator) in descriptions.items()}
    record["undefined_diagnostics"] = [] if count < len(final_energies) else [
        {"field": "occupied_virtual_gap_hartree", "reason": "NO_VIRTUAL_ORBITALS"},
        {"field": "final_non_diis_gap_hartree", "reason": "NO_VIRTUAL_ORBITALS"}]
    json.dumps(record, allow_nan=False)
    return ReferenceResult(record, exported_arrays, context)
