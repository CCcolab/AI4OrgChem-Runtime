"""Validate conditional-RKS energy and gradient before P11-B planar optimization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p11_source2007_rks import Source2007ConditionalRKS
from scripts.run_p11_cyanobenzene_effect import (
    build_molecule,
    build_mean_field,
    conditional_state,
    cyanobenzene_atoms,
    ordinary_state,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/qm/p11_substituted_benzene_effect_v0.1.yaml"
OUTPUT = ROOT / "data/processed/p11_source2007_gradient_pilot_v0.2.json"
REPORT = ROOT / "docs/reports/p11_source2007_gradient_pilot_v0.2.md"


def main() -> int:
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    atoms, _ = cyanobenzene_atoms(
        protocol["geometry"]["states"]["GL_II"], protocol["geometry"]
    )
    fragment_map = {
        0: "A", 1: "A", 2: "B", 3: "B", 4: "C", 5: "C", 6: "X", 7: "X"
    }
    g_atoms, _ = cyanobenzene_atoms(
        protocol["geometry"]["states"]["G"], protocol["geometry"]
    )
    g = ordinary_state(g_atoms, protocol)
    reference = conditional_state(
        atoms,
        fragment_map,
        np.asarray(g["density"], dtype=float),
        protocol,
        mask_one_electron_matrix=False,
    )

    def configured_conditional(mol):
        descriptors = classify_planar_pyscf_aos(mol, fragment_map)
        candidate = Source2007ConditionalRKS.build(mol, descriptors)
        template = build_mean_field(mol, protocol)
        candidate.xc = template.xc
        candidate.grids.level = template.grids.level
        candidate.conv_tol = template.conv_tol
        candidate.max_cycle = template.max_cycle
        candidate.max_memory = template.max_memory
        candidate.verbose = 0
        return candidate

    molecule = build_molecule(atoms, protocol)
    mean_field = configured_conditional(molecule)
    energy = float(mean_field.kernel(dm0=np.asarray(g["density"], dtype=float)))
    gradient = np.asarray(mean_field.nuc_grad_method().kernel(), dtype=float)
    displacement_bohr = 1.0e-3
    finite_difference_energies = []
    for sign in (-1.0, 1.0):
        displaced = molecule.copy()
        coordinates = np.asarray(molecule.atom_coords(unit="Bohr"), dtype=float)
        coordinates[6, 0] += sign * displacement_bohr
        displaced.set_geom_(coordinates, unit="Bohr")
        displaced_mean_field = configured_conditional(displaced)
        finite_difference_energies.append(
            float(displaced_mean_field.kernel(dm0=np.asarray(mean_field.make_rdm1())))
        )
    finite_difference_gradient = (
        finite_difference_energies[1] - finite_difference_energies[0]
    ) / (2.0 * displacement_bohr)
    analytic_gradient = float(gradient[6, 0])
    gradient_difference = analytic_gradient - finite_difference_gradient
    record = {
        "schema_version": 1,
        "state": "cyanobenzene_GL_II",
        "reference_energy_hartree": float(reference["total_energy_hartree"]),
        "analytic_interface_energy_hartree": energy,
        "energy_difference_hartree": energy - float(reference["total_energy_hartree"]),
        "scf_converged": bool(mean_field.converged),
        "maximum_absolute_z_gradient_hartree_per_bohr": float(np.max(np.abs(gradient[:, 2]))),
        "gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(gradient * gradient))),
        "gradient_max_hartree_per_bohr": float(np.max(np.linalg.norm(gradient, axis=1))),
        "finite_difference_coordinate": "atom_7_x_one_based",
        "finite_difference_step_bohr": displacement_bohr,
        "analytic_gradient_hartree_per_bohr": analytic_gradient,
        "finite_difference_gradient_hartree_per_bohr": finite_difference_gradient,
        "gradient_difference_hartree_per_bohr": gradient_difference,
        "all_input_z_angstrom": [float(atom[3]) for atom in atoms],
        "pass": bool(
            mean_field.converged
            and abs(energy - float(reference["total_energy_hartree"])) <= 1.0e-8
            and float(np.max(np.abs(gradient[:, 2]))) <= 1.0e-8
            and abs(gradient_difference) <= 2.0e-4
        ),
    }
    write_json(OUTPUT, record)
    REPORT.write_text(
        "\n".join(
            [
                "# P11-B 2007条件RKS梯度接口先导验证",
                "",
                f"- 固定几何能量差：`{record['energy_difference_hartree']:+.3e} Eh`",
                f"- 最大面外梯度：`{record['maximum_absolute_z_gradient_hartree_per_bohr']:.3e} Eh/Bohr`",
                f"- 平面内解析/有限差分梯度差：`{record['gradient_difference_hartree_per_bohr']:+.3e} Eh/Bohr`",
                f"- 梯度RMS：`{record['gradient_rms_hartree_per_bohr']:.3e} Eh/Bohr`",
                f"- 结论：`{'PASS' if record['pass'] else 'FAIL'}`",
                "",
                "该先导只验证优化器入口；不生成P11-B科学分类。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0 if record["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
