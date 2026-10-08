"""Analytic-gradient-compatible source-2011 conditional RKS for P12.

The implementation keeps the source h/S/F inter-fragment-pi masks and the
validated direct-J/K X14 exchange subtraction in one variational PySCF object.
It is an engine component only: no P12 geometry, CESE value, or classification
is created here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .p09_ao_classification import (
    apply_interfragment_pi_matrix_mask,
    interfragment_pi_delete_mask,
)
from .p09_eri_mask import AODescriptor
from .p12_direct_source2011 import (
    _pi_fragment_indices,
    density_block_residual,
    direct_source2011_restricted_jk,
    project_planar_localized_density,
)


def direct_source2011_restricted_jk_derivative(
    molecule: Any,
    density: np.ndarray,
    descriptors: Sequence[AODescriptor],
    *,
    block_tolerance: float = 1.0e-10,
) -> tuple[np.ndarray, np.ndarray]:
    """Return source-2011 J/K first derivatives on the AO bra centre.

    PySCF's molecular gradient driver completes the ket-centre contribution by
    symmetry.  The X14 correction is assembled in the same ordered fragment
    blocks as the independently validated zero-order direct-J/K kernel.
    """

    from pyscf.grad import rhf

    dm = np.asarray(density, dtype=float)
    residual = density_block_residual(dm, descriptors)
    if residual > float(block_tolerance):
        raise ValueError(
            "source-2011 J/K derivative requires a planar block-diagonal density; "
            f"observed residual {residual:.3e}"
        )

    physical_j, physical_k = rhf.get_jk(molecule, dm)
    physical_j = np.asarray(physical_j, dtype=float)
    physical_k = np.asarray(physical_k, dtype=float)
    fragments = _pi_fragment_indices(descriptors)
    deleted_k = np.zeros_like(physical_k)

    for q_fragment, q_indices in fragments.items():
        fragment_density = np.zeros_like(dm)
        fragment_density[np.ix_(q_indices, q_indices)] = dm[
            np.ix_(q_indices, q_indices)
        ]
        contribution = np.asarray(rhf.get_k(molecule, fragment_density), dtype=float)
        for p_fragment, p_indices in fragments.items():
            if p_fragment == q_fragment:
                continue
            deleted_k[:, p_indices[:, None], p_indices] += contribution[
                :, p_indices[:, None], p_indices
            ]

    source_j = physical_j.copy()
    source_k = physical_k - deleted_k
    cross_pi = interfragment_pi_delete_mask(descriptors)
    source_j[:, cross_pi] = 0.0
    source_k[:, cross_pi] = 0.0
    return source_j, source_k


class Source2011DirectConditionalRKS:
    """Factory for the source-2011 conditional RKS and its gradient."""

    @staticmethod
    def build(molecule: Any, descriptors: Sequence[AODescriptor]) -> Any:
        from pyscf.dft import rks as rks_scf
        from pyscf.grad import rks as rks_grad
        from pyscf.scf import hf

        frozen_descriptors = tuple(descriptors)

        def mask_components(values: np.ndarray) -> np.ndarray:
            array = np.asarray(values, dtype=float)
            return np.asarray(
                [
                    apply_interfragment_pi_matrix_mask(component, frozen_descriptors)
                    for component in array
                ],
                dtype=float,
            )

        class _Gradients(rks_grad.Gradients):
            def get_ovlp(self, mol: Any | None = None) -> np.ndarray:
                return mask_components(super().get_ovlp(mol))

            def hcore_generator(self, mol: Any | None = None) -> Any:
                generator = super().hcore_generator(mol)

                def masked_generator(atom_index: int) -> np.ndarray:
                    return mask_components(generator(atom_index))

                return masked_generator

            def get_jk(
                self,
                mol: Any | None = None,
                dm: np.ndarray | None = None,
                hermi: int = 0,
                omega: float | None = None,
            ) -> tuple[np.ndarray, np.ndarray]:
                if omega not in (None, 0, 0.0):
                    raise ValueError("source-2011 gradient supports only a global hybrid")
                if mol is None:
                    mol = self.mol
                if dm is None:
                    dm = self.base.make_rdm1()
                projected = project_planar_localized_density(dm, frozen_descriptors)
                return direct_source2011_restricted_jk_derivative(
                    mol, projected, frozen_descriptors
                )

        class _RKS(rks_scf.RKS):
            def get_ovlp(self, mol: Any | None = None) -> np.ndarray:
                physical = np.asarray(super().get_ovlp(mol), dtype=float)
                return apply_interfragment_pi_matrix_mask(physical, frozen_descriptors)

            def get_hcore(self, mol: Any | None = None) -> np.ndarray:
                physical = np.asarray(super().get_hcore(mol), dtype=float)
                return apply_interfragment_pi_matrix_mask(physical, frozen_descriptors)

            def get_jk(
                self,
                mol: Any | None = None,
                dm: np.ndarray | None = None,
                hermi: int = 1,
                with_j: bool = True,
                with_k: bool = True,
                omega: float | None = None,
            ) -> tuple[np.ndarray | None, np.ndarray | None]:
                if omega not in (None, 0, 0.0):
                    raise ValueError("source-2011 RKS supports only a global hybrid")
                if mol is None:
                    mol = self.mol
                if dm is None:
                    dm = self.make_rdm1()
                projected = project_planar_localized_density(dm, frozen_descriptors)
                source_j, source_k, _metadata = direct_source2011_restricted_jk(
                    self, projected, frozen_descriptors, block_tolerance=1.0e-10
                )
                return (source_j if with_j else None, source_k if with_k else None)

            def get_fock(
                self,
                h1e: np.ndarray | None = None,
                s1e: np.ndarray | None = None,
                vhf: np.ndarray | None = None,
                dm: np.ndarray | None = None,
                cycle: int = -1,
                diis: Any | None = None,
                diis_start_cycle: int | None = None,
                level_shift_factor: float | None = None,
                damp_factor: float | None = None,
                fock_last: np.ndarray | None = None,
            ) -> np.ndarray:
                if h1e is None:
                    h1e = self.get_hcore()
                if vhf is None:
                    vhf = self.get_veff(self.mol, dm)
                constrained = apply_interfragment_pi_matrix_mask(
                    np.asarray(h1e) + np.asarray(vhf), frozen_descriptors
                )
                processed = hf.get_fock(
                    self,
                    h1e=constrained,
                    s1e=s1e,
                    vhf=np.zeros_like(constrained),
                    dm=dm,
                    cycle=cycle,
                    diis=diis,
                    diis_start_cycle=diis_start_cycle,
                    level_shift_factor=level_shift_factor,
                    damp_factor=damp_factor,
                    fock_last=fock_last,
                )
                return apply_interfragment_pi_matrix_mask(
                    np.asarray(processed), frozen_descriptors
                )

            def nuc_grad_method(self) -> Any:
                return _Gradients(self)

        mean_field = _RKS(molecule)
        mean_field.direct_scf = False
        mean_field.source2011_descriptors = frozen_descriptors
        return mean_field
