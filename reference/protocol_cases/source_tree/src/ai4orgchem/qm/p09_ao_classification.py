"""Planar PySCF AO classification and matrix masking for P09.

The frozen primary implementation places each planar molecule in the ``xy``
plane.  Basis functions odd under ``z -> -z`` are pi-type; even functions are
sigma-type.  For 6-31G(d), this classifies ``pz``, ``dxz`` and ``dyz`` as pi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Hashable

import numpy as np

from .p09_eri_mask import AODescriptor, should_delete_eri


def z_reflection_parity(angular_label: str, component: str) -> int:
    """Return ``+1`` (sigma) or ``-1`` (pi) under reflection through ``xy``."""

    angular_momentum = angular_label[-1].lower()
    normalized = component.lower().replace(" ", "")
    if angular_momentum == "s":
        return 1
    if angular_momentum == "p":
        if normalized not in {"x", "y", "z"}:
            raise ValueError(f"unsupported p component: {component!r}")
        return -1 if normalized == "z" else 1
    if angular_momentum == "d":
        parities = {
            "xy": 1,
            "yz": -1,
            "z^2": 1,
            "xz": -1,
            "x2-y2": 1,
        }
        if normalized not in parities:
            raise ValueError(f"unsupported spherical d component: {component!r}")
        return parities[normalized]
    raise ValueError(
        f"P09 primary AO classifier supports only s, p and spherical d labels; got {angular_label!r}"
    )


def classify_planar_pyscf_aos(
    mol: Any,
    pi_atom_to_fragment: Mapping[int, Hashable],
    *,
    plane_tolerance_angstrom: float = 1.0e-8,
) -> tuple[AODescriptor, ...]:
    """Classify real PySCF AOs for an ``xy``-planar molecular orientation."""

    coordinates = np.asarray(mol.atom_coords(unit="Angstrom"), dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError("molecular coordinates must have shape (natom, 3)")
    maximum_out_of_plane = float(np.max(np.abs(coordinates[:, 2]), initial=0.0))
    if maximum_out_of_plane > plane_tolerance_angstrom:
        raise ValueError(
            f"molecule is not in the frozen xy plane: max |z|={maximum_out_of_plane:.3e} A"
        )

    descriptors: list[AODescriptor] = []
    for label in mol.ao_labels(fmt=False):
        atom_index, _element, angular_label, component = label
        if z_reflection_parity(angular_label, component) == 1:
            descriptors.append(AODescriptor("sigma"))
            continue
        if atom_index not in pi_atom_to_fragment:
            raise ValueError(
                f"pi-type AO on atom {atom_index} has no localized double-bond/group assignment"
            )
        descriptors.append(AODescriptor("pi", pi_atom_to_fragment[atom_index]))

    if len(descriptors) != mol.nao_nr():
        raise ValueError("AO label count does not match PySCF nao_nr()")
    return tuple(descriptors)


def interfragment_pi_delete_mask(
    descriptors: Sequence[AODescriptor],
) -> np.ndarray:
    """Return the source matrix mask for inter-group pi/pi AO elements."""

    size = len(descriptors)
    mask = np.zeros((size, size), dtype=bool)
    for i, left in enumerate(descriptors):
        if left.kind != "pi":
            continue
        for j, right in enumerate(descriptors):
            mask[i, j] = right.kind == "pi" and left.fragment != right.fragment
    return mask


def apply_interfragment_pi_matrix_mask(
    matrix: np.ndarray, descriptors: Sequence[AODescriptor]
) -> np.ndarray:
    """Zero source-declared inter-group pi blocks of F, h, or S."""

    values = np.asarray(matrix)
    if values.shape != (len(descriptors), len(descriptors)):
        raise ValueError("matrix dimensions must match the AO descriptor count")
    result = values.copy()
    result[interfragment_pi_delete_mask(descriptors)] = 0
    return result


def apply_eri_scalar_mask(
    value: float,
    quartet: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
) -> float:
    """Apply the symmetry-closed Figure 8-4 predicate to one real ERI value."""

    return 0.0 if should_delete_eri(quartet, source_entries) else float(value)


def pyscf_eri_value_by_ao_indices(mol: Any, indices: Sequence[int]) -> float:
    """Evaluate one AO ERI through its PySCF shell block, avoiding a full tensor."""

    if len(indices) != 4:
        raise ValueError("an ERI requires four AO indices")
    locations = np.asarray(mol.ao_loc_nr(), dtype=int)
    shells: list[int] = []
    local_indices: list[int] = []
    for index in indices:
        if index < 0 or index >= locations[-1]:
            raise IndexError(f"AO index out of range: {index}")
        shell = int(np.searchsorted(locations, index, side="right") - 1)
        shells.append(shell)
        local_indices.append(int(index - locations[shell]))
    block = np.asarray(mol.intor_by_shell("int2e_sph", tuple(shells)))
    return float(block[tuple(local_indices)])
