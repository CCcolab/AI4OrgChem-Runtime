"""Independent restricted-hybrid energy assembly for the P09 protocol."""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping, Sequence

import numpy as np

from .p09_ao_classification import apply_interfragment_pi_matrix_mask
from .p09_eri_mask import AODescriptor, matches_index_predicate, should_delete_eri


ERI_SYMMETRY_AXES = (
    (0, 1, 2, 3),
    (1, 0, 2, 3),
    (0, 1, 3, 2),
    (1, 0, 3, 2),
    (2, 3, 0, 1),
    (3, 2, 0, 1),
    (2, 3, 1, 0),
    (3, 2, 1, 0),
)


def _tokens(predicate: Mapping[str, Any]) -> tuple[str, str, str, str]:
    result = tuple(predicate["bra"]) + tuple(predicate["ket"])
    if len(result) != 4:
        raise ValueError("a source predicate must have four AO tokens")
    return result  # type: ignore[return-value]


def build_eri_delete_mask(
    descriptors: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
) -> np.ndarray:
    """Build the permutation-closed Figure 8-4 mask without four-AO Python loops."""

    size = len(descriptors)
    sigma_indices = np.asarray(
        [index for index, item in enumerate(descriptors) if item.kind == "sigma"], dtype=int
    )
    pi_by_fragment = {
        fragment: np.asarray(
            [
                index
                for index, item in enumerate(descriptors)
                if item.kind == "pi" and item.fragment == fragment
            ],
            dtype=int,
        )
        for fragment in dict.fromkeys(
            item.fragment for item in descriptors if item.kind == "pi"
        )
    }
    fragments = tuple(pi_by_fragment)
    mask = np.zeros((size, size, size, size), dtype=bool)

    for entry in source_entries:
        predicate = entry["index_predicate"]
        tokens = _tokens(predicate)
        variables = tuple(dict.fromkeys(token.removeprefix("pi_") for token in tokens if token.startswith("pi_")))
        for values in product(fragments, repeat=len(variables)):
            assignment = dict(zip(variables, values, strict=True))
            witness = tuple(
                AODescriptor("sigma")
                if token == "sigma"
                else AODescriptor("pi", assignment[token.removeprefix("pi_")])
                for token in tokens
            )
            if not matches_index_predicate(witness, predicate):
                continue
            index_sets = tuple(
                sigma_indices
                if token == "sigma"
                else pi_by_fragment[assignment[token.removeprefix("pi_")]]
                for token in tokens
            )
            if all(indices.size for indices in index_sets):
                mask[np.ix_(*index_sets)] = True

    source_ordered = mask.copy()
    for axes in ERI_SYMMETRY_AXES[1:]:
        mask |= source_ordered.transpose(axes)
    return mask


def apply_eri_tensor_mask(
    eri: np.ndarray,
    descriptors: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
) -> tuple[np.ndarray, np.ndarray]:
    """Return a masked four-index ERI tensor and the applied delete mask."""

    values = np.asarray(eri)
    expected = (len(descriptors),) * 4
    if values.shape != expected:
        raise ValueError(f"ERI tensor must have shape {expected}")
    delete_mask = build_eri_delete_mask(descriptors, source_entries)
    result = values.copy()
    result[delete_mask] = 0.0
    return result, delete_mask


def apply_eri_tensor_mask_inplace_by_category(
    eri: np.ndarray,
    descriptors: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
) -> int:
    """Zero source-deleted ERIs in place without a four-index boolean mask.

    AO descriptors partition the tensor into disjoint sigma/pi-fragment
    category blocks.  Testing the at most ``Ncategory**4`` symbolic quartets
    and assigning a scalar zero to the corresponding blocks avoids both the
    full ERI copy and the full boolean delete tensor used by the reference
    implementation.  The returned count is the exact number of deleted
    ordered tensor elements.
    """

    values = np.asarray(eri)
    expected = (len(descriptors),) * 4
    if values.shape != expected:
        raise ValueError(f"ERI tensor must have shape {expected}")
    if not values.flags.writeable:
        raise ValueError("in-place ERI masking requires a writeable tensor")

    categories: dict[AODescriptor, np.ndarray] = {}
    for descriptor in dict.fromkeys(descriptors):
        categories[descriptor] = np.asarray(
            [index for index, item in enumerate(descriptors) if item == descriptor],
            dtype=int,
        )
    deleted_count = 0
    category_items = tuple(categories.items())
    for quartet in product(category_items, repeat=4):
        descriptor_quartet = tuple(item[0] for item in quartet)
        if not should_delete_eri(descriptor_quartet, source_entries):
            continue
        index_sets = tuple(item[1] for item in quartet)
        if not all(indices.size for indices in index_sets):
            continue
        values[np.ix_(*index_sets)] = 0.0
        deleted_count += int(np.prod([indices.size for indices in index_sets]))
    return deleted_count


def restricted_jk(
    density: np.ndarray,
    eri: np.ndarray,
    *,
    optimize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Assemble closed-shell Coulomb and exchange matrices in chemist notation."""

    dm = np.asarray(density, dtype=float)
    values = np.asarray(eri, dtype=float)
    if dm.ndim != 2 or dm.shape[0] != dm.shape[1] or values.shape != dm.shape * 2:
        raise ValueError("density and ERI dimensions are incompatible")
    coulomb = np.einsum("pqrs,rs->pq", values, dm, optimize=optimize)
    exchange = np.einsum("prqs,rs->pq", values, dm, optimize=optimize)
    return coulomb, exchange


def assemble_restricted_hybrid_energy(
    *,
    density: np.ndarray,
    hcore: np.ndarray,
    overlap: np.ndarray,
    eri: np.ndarray,
    xc_potential: np.ndarray,
    semilocal_xc_energy: float,
    exact_exchange_fraction: float,
    nuclear_repulsion: float,
    descriptors: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Assemble the masked RKS hybrid functional at one fixed density.

    ``semilocal_xc_energy`` and ``xc_potential`` exclude the explicit exact-
    exchange contribution, as in PySCF's hybrid RKS split.
    """

    dm = np.asarray(density, dtype=float)
    h = np.asarray(hcore, dtype=float)
    s = np.asarray(overlap, dtype=float)
    vxc = np.asarray(xc_potential, dtype=float)
    size = len(descriptors)
    expected_matrix = (size, size)
    if any(matrix.shape != expected_matrix for matrix in (dm, h, s, vxc)):
        raise ValueError("all AO matrices must match the descriptor count")
    if not 0.0 <= exact_exchange_fraction <= 1.0:
        raise ValueError("exact-exchange fraction must lie in [0, 1]")

    masked_h = apply_interfragment_pi_matrix_mask(h, descriptors)
    masked_s = apply_interfragment_pi_matrix_mask(s, descriptors)
    masked_eri, eri_delete_mask = apply_eri_tensor_mask(eri, descriptors, source_entries)
    coulomb, exchange = restricted_jk(dm, masked_eri)
    raw_fock = masked_h + coulomb - 0.5 * exact_exchange_fraction * exchange + vxc
    conditional_fock = apply_interfragment_pi_matrix_mask(raw_fock, descriptors)

    one_electron = float(np.einsum("pq,qp->", masked_h, dm, optimize=True))
    coulomb_energy = 0.5 * float(np.einsum("pq,qp->", coulomb, dm, optimize=True))
    exact_exchange_energy = -0.25 * exact_exchange_fraction * float(
        np.einsum("pq,qp->", exchange, dm, optimize=True)
    )
    electronic_energy = (
        one_electron
        + coulomb_energy
        + exact_exchange_energy
        + float(semilocal_xc_energy)
    )
    return {
        "masked_hcore": masked_h,
        "masked_overlap": masked_s,
        "masked_eri": masked_eri,
        "eri_delete_mask": eri_delete_mask,
        "coulomb_matrix": coulomb,
        "exchange_matrix": exchange,
        "raw_fock": raw_fock,
        "conditional_fock": conditional_fock,
        "one_electron_energy": one_electron,
        "coulomb_energy": coulomb_energy,
        "exact_exchange_energy": exact_exchange_energy,
        "semilocal_xc_energy": float(semilocal_xc_energy),
        "electronic_energy": electronic_energy,
        "nuclear_repulsion": float(nuclear_repulsion),
        "total_energy": electronic_energy + float(nuclear_repulsion),
        "masked_metric_electron_count": float(np.einsum("pq,qp->", masked_s, dm)),
        "physical_metric_electron_count": float(np.einsum("pq,qp->", s, dm)),
    }
