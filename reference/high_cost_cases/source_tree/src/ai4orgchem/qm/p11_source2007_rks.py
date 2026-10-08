"""Source-2007 conditional RKS with an analytic-gradient-compatible interface.

The occupied orbitals are orthonormal in the AO overlap after zeroing
inter-fragment pi/pi blocks.  The same blocks are zeroed in the Fock matrix at
every SCF iteration.  The physical one-electron and two-electron operators are
retained in the energy functional.  This is the branch needed for the 2007
P11-B restricted-geometry recalculation.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .p09_ao_classification import apply_interfragment_pi_matrix_mask
from .p09_eri_mask import AODescriptor


class Source2007ConditionalRKS:
    """Factory namespace for the PySCF-backed conditional RKS implementation."""

    @staticmethod
    def build(molecule: Any, descriptors: Sequence[AODescriptor]) -> Any:
        from pyscf.dft import rks as rks_scf
        from pyscf.grad import rks as rks_grad

        frozen_descriptors = tuple(descriptors)

        class _Gradients(rks_grad.Gradients):
            def get_ovlp(self, mol: Any | None = None) -> np.ndarray:
                derivatives = np.asarray(super().get_ovlp(mol), dtype=float)
                return np.asarray(
                    [
                        apply_interfragment_pi_matrix_mask(component, frozen_descriptors)
                        for component in derivatives
                    ],
                    dtype=float,
                )

        class _RKS(rks_scf.RKS):
            def get_ovlp(self, mol: Any | None = None) -> np.ndarray:
                physical = np.asarray(super().get_ovlp(mol), dtype=float)
                return apply_interfragment_pi_matrix_mask(physical, frozen_descriptors)

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
                from pyscf.scf import hf

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
        mean_field.source2007_descriptors = frozen_descriptors
        return mean_field
