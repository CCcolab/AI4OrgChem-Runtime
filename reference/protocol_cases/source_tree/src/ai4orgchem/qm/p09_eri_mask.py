"""Typed, source-declared ERI mask for the P09 Figure 8-4 protocol.

This module implements only the symbolic AO-type and fragment predicates.  It
does not decide which real PySCF basis functions are sigma or pi; that separate
molecular-plane classification must pass before P09 QM execution is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class AODescriptor:
    """Minimal AO classification used by the source Figure 8-4 mask."""

    kind: str
    fragment: Hashable | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"sigma", "pi"}:
            raise ValueError("AO kind must be 'sigma' or 'pi'")
        if self.kind == "pi" and self.fragment is None:
            raise ValueError("pi AOs require a localized double-bond/group fragment")


def chemist_eightfold_permutations(
    quartet: Sequence[AODescriptor],
) -> tuple[tuple[AODescriptor, AODescriptor, AODescriptor, AODescriptor], ...]:
    """Return unique ``(ij|kl)`` permutations under real-AO ERI symmetry."""

    if len(quartet) != 4:
        raise ValueError("an ERI quartet must contain four AO descriptors")
    i, j, k, l = quartet
    permutations = (
        (i, j, k, l),
        (j, i, k, l),
        (i, j, l, k),
        (j, i, l, k),
        (k, l, i, j),
        (l, k, i, j),
        (k, l, j, i),
        (l, k, j, i),
    )
    return tuple(dict.fromkeys(permutations))


def _bind_token(
    token: str, descriptor: AODescriptor, bindings: dict[str, Hashable]
) -> bool:
    if token == "sigma":
        return descriptor.kind == "sigma"
    if not token.startswith("pi_") or descriptor.kind != "pi":
        return False
    variable = token.removeprefix("pi_")
    bound = bindings.get(variable)
    if bound is None:
        bindings[variable] = descriptor.fragment  # type: ignore[assignment]
        return True
    return bound == descriptor.fragment


def _constraints_hold(bindings: Mapping[str, Hashable], constraints: Iterable[str]) -> bool:
    constraints = set(constraints)
    p = bindings.get("P")
    q = bindings.get("Q")
    s = bindings.get("S")
    t = bindings.get("T")

    if "P_not_equal_Q" in constraints and p is not None and q is not None and p == q:
        return False
    if "S_not_equal_T" in constraints and s is not None and t is not None and s == t:
        return False

    membership_requested = bool({"S_in_P_or_Q", "T_in_P_or_Q"} & constraints)
    if membership_requested:
        if s is None or t is None or s == t:
            return False
        source_pair = {s, t}
        if p is not None and p not in source_pair:
            return False
        if q is not None and q not in source_pair:
            return False
        if p is not None and q is not None and {p, q} != source_pair:
            return False

    return True


def matches_index_predicate(
    quartet: Sequence[AODescriptor], predicate: Mapping[str, Any]
) -> bool:
    """Match one ordered source class without applying ERI permutations."""

    if len(quartet) != 4:
        raise ValueError("an ERI quartet must contain four AO descriptors")
    tokens = tuple(predicate["bra"]) + tuple(predicate["ket"])
    if len(tokens) != 4:
        raise ValueError("a source predicate must define two bra and two ket tokens")
    bindings: dict[str, Hashable] = {}
    if not all(
        _bind_token(token, descriptor, bindings)
        for token, descriptor in zip(tokens, quartet, strict=True)
    ):
        return False
    return _constraints_hold(bindings, predicate.get("constraints", ()))


def matching_source_classes(
    quartet: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
    *,
    permutation_closed: bool = True,
) -> frozenset[str]:
    """Return source class IDs that delete an ERI quartet."""

    permutations = (
        chemist_eightfold_permutations(quartet)
        if permutation_closed
        else (tuple(quartet),)
    )
    return frozenset(
        entry["id"]
        for entry in source_entries
        if any(matches_index_predicate(candidate, entry["index_predicate"]) for candidate in permutations)
    )


def should_delete_eri(
    quartet: Sequence[AODescriptor], source_entries: Sequence[Mapping[str, Any]]
) -> bool:
    """Return whether the symmetry-closed Figure 8-4 mask deletes a quartet."""

    return bool(matching_source_classes(quartet, source_entries))
