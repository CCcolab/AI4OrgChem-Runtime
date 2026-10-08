"""Generate auditable planar annulene seeds for the P12 source-2011 lane.

The source configuration notation records the number of carbon atoms in each
fragment between consecutive *inner* hydrogens, counting both end carbons.
Consequently, a digit ``d`` advances ``d - 1`` ring positions.  This script
uses that topological definition only.  The resulting coordinates are
independent, idealized starting structures and are never treated as evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/qm/p12_source2011_planar_cese_recalculation_v0.1.yaml"
OUTPUT_DIR = ROOT / "data/inputs/p12_source2011_planar_seeds_v0.1"
MANIFEST = OUTPUT_DIR / "manifest.json"


def parse_configuration(configuration: str, n_carbon: int) -> tuple[list[int], list[int]]:
    prefix = f"[{n_carbon}]-"
    if not configuration.startswith(prefix):
        raise ValueError(f"configuration mismatch: {configuration!r} versus N={n_carbon}")
    digits = [int(char) for char in configuration[len(prefix) :]]
    if any(digit < 3 for digit in digits):
        raise ValueError(f"invalid source fragment length in {configuration!r}")
    if sum(digit - 1 for digit in digits) != n_carbon:
        raise ValueError(f"source configuration does not close: {configuration!r}")

    inner = [0]
    cursor = 0
    for digit in digits[:-1]:
        cursor = (cursor + digit - 1) % n_carbon
        inner.append(cursor)
    if len(set(inner)) != len(inner):
        raise ValueError(f"duplicate inner-H position in {configuration!r}")
    return digits, inner


def _carbon_points(turn_magnitudes: np.ndarray, signs: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    n_carbon = len(signs)
    directions = np.zeros(n_carbon)
    for edge in range(1, n_carbon):
        directions[edge] = directions[edge - 1] + signs[edge] * turn_magnitudes[edge]
    points = np.zeros((n_carbon + 1, 2))
    for edge in range(n_carbon):
        points[edge + 1] = points[edge] + lengths[edge] * np.array(
            [math.cos(directions[edge]), math.sin(directions[edge])]
        )
    return points


def solve_carbon_ring(n_carbon: int, inner_positions: list[int]) -> tuple[np.ndarray, dict[str, float]]:
    inner = set(inner_positions)
    signs = np.array([-1.0 if index in inner else 1.0 for index in range(n_carbon)])
    target = 2.0 * math.pi / float(n_carbon - 2 * len(inner))
    lengths = np.array([1.34 if index % 2 == 0 else 1.46 for index in range(n_carbon)])

    def steric_residuals(magnitudes: np.ndarray) -> np.ndarray:
        points = _carbon_points(magnitudes, signs, lengths)
        carbons = points[:-1]
        hydrogens = add_hydrogens(carbons)
        residuals = []
        for first in range(n_carbon):
            for second in range(first + 1, n_carbon):
                h_h = float(np.linalg.norm(hydrogens[first] - hydrogens[second]))
                residuals.append(max(0.0, 1.10 - h_h) / 0.05)
                if second not in {(first + 1) % n_carbon, (first - 1) % n_carbon}:
                    c_c = float(np.linalg.norm(carbons[first] - carbons[second]))
                    residuals.append(max(0.0, 1.70 - c_c) / 0.05)
            for second in range(n_carbon):
                if second != first:
                    c_h = float(np.linalg.norm(carbons[first] - hydrogens[second]))
                    residuals.append(max(0.0, 1.20 - c_h) / 0.05)
        return np.asarray(residuals)

    def objective(magnitudes: np.ndarray) -> float:
        angle_residuals = (magnitudes - target) / 0.20
        clashes = steric_residuals(magnitudes)
        return float(np.dot(angle_residuals, angle_residuals) + np.dot(clashes, clashes))

    def closure_constraint(magnitudes: np.ndarray) -> np.ndarray:
        points = _carbon_points(magnitudes, signs, lengths)
        return points[-1] - points[0]

    def winding_constraint(magnitudes: np.ndarray) -> float:
        return float(np.dot(signs, magnitudes) - 2.0 * math.pi)

    # Closure and winding are equality constraints.  The objective softly
    # retains source-like C-C-C angles and uses a seed-only steric barrier.
    result = minimize(
        objective,
        np.full(n_carbon, target),
        method="SLSQP",
        bounds=[(math.radians(20.0), math.radians(80.0))] * n_carbon,
        constraints=[
            {"type": "eq", "fun": closure_constraint},
            {"type": "eq", "fun": winding_constraint},
        ],
        options={"ftol": 1.0e-12, "maxiter": 3000, "disp": False},
    )
    if not result.success:
        raise RuntimeError(f"planar seed closure failed for N={n_carbon}: {result.message}")
    closed = _carbon_points(np.asarray(result.x), signs, lengths)
    closure_error = float(np.linalg.norm(closed[-1] - closed[0]))
    heading_error = abs(float(np.dot(signs, result.x) - 2.0 * math.pi))
    if closure_error > 1.0e-6 or heading_error > 1.0e-7:
        raise RuntimeError(
            f"planar seed failed closure checks for N={n_carbon}: "
            f"distance={closure_error:.3e}, heading={heading_error:.3e}"
        )
    carbons = closed[:-1]
    carbons -= carbons.mean(axis=0)
    diagnostics = {
        "closure_error_angstrom": closure_error,
        "winding_error_radian": heading_error,
        "minimum_CCC_angle_degree": 180.0 - math.degrees(float(np.max(result.x))),
        "maximum_CCC_angle_degree": 180.0 - math.degrees(float(np.min(result.x))),
    }
    return carbons, diagnostics


def add_hydrogens(carbons: np.ndarray) -> np.ndarray:
    hydrogens = []
    n_carbon = len(carbons)
    for index, carbon in enumerate(carbons):
        to_previous = carbons[(index - 1) % n_carbon] - carbon
        to_next = carbons[(index + 1) % n_carbon] - carbon
        to_previous /= np.linalg.norm(to_previous)
        to_next /= np.linalg.norm(to_next)
        direction = -(to_previous + to_next)
        direction /= np.linalg.norm(direction)
        hydrogens.append(carbon + 1.08 * direction)
    return np.asarray(hydrogens)


def _orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ab = b - a
    ac = c - a
    return float(ab[0] * ac[1] - ab[1] * ac[0])


def _segments_intersect(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> bool:
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    return o1 * o2 < -1.0e-12 and o3 * o4 < -1.0e-12


def count_nonadjacent_intersections(carbons: np.ndarray) -> int:
    n_carbon = len(carbons)
    intersections = 0
    for first in range(n_carbon):
        for second in range(first + 1, n_carbon):
            if second in {first, (first + 1) % n_carbon} or first == (second + 1) % n_carbon:
                continue
            if _segments_intersect(
                carbons[first],
                carbons[(first + 1) % n_carbon],
                carbons[second],
                carbons[(second + 1) % n_carbon],
            ):
                intersections += 1
    return intersections


def point_in_polygon(point: np.ndarray, polygon: np.ndarray) -> bool:
    """Return whether a point is inside a simple polygon by ray casting."""
    x_value, y_value = float(point[0]), float(point[1])
    inside = False
    previous = len(polygon) - 1
    for current in range(len(polygon)):
        x_current, y_current = polygon[current]
        x_previous, y_previous = polygon[previous]
        crosses = (y_current > y_value) != (y_previous > y_value)
        if crosses:
            x_crossing = (x_previous - x_current) * (y_value - y_current) / (
                y_previous - y_current
            ) + x_current
            if x_value < x_crossing:
                inside = not inside
        previous = current
    return inside


def write_xyz(path: Path, configuration: str, carbons: np.ndarray, hydrogens: np.ndarray) -> None:
    lines = [str(2 * len(carbons)), f"{configuration} idealized planar configuration seed; not evidence"]
    for element, coordinates in [("C", point) for point in carbons] + [
        ("H", point) for point in hydrogens
    ]:
        lines.append(f"{element:2s} {coordinates[0]: .12f} {coordinates[1]: .12f} {0.0: .12f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def minimum_nonbonded_distance(carbons: np.ndarray, hydrogens: np.ndarray) -> float:
    coordinates = np.vstack([carbons, hydrogens])
    n_carbon = len(carbons)
    distances = []
    for first in range(2 * n_carbon):
        for second in range(first + 1, 2 * n_carbon):
            ring_bond = (
                first < n_carbon
                and second < n_carbon
                and (second == first + 1 or (first == 0 and second == n_carbon - 1))
            )
            carbon_hydrogen_bond = first < n_carbon and second == n_carbon + first
            if not ring_bond and not carbon_hydrogen_bond:
                distances.append(float(np.linalg.norm(coordinates[first] - coordinates[second])))
    return min(distances)


def main() -> int:
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for panel in protocol["panel"]:
        n_carbon = int(panel["N"])
        configuration = str(panel["configuration"])
        digits, inner_positions = parse_configuration(configuration, n_carbon)
        carbons, diagnostics = solve_carbon_ring(n_carbon, inner_positions)
        hydrogens = add_hydrogens(carbons)
        intersections = count_nonadjacent_intersections(carbons)
        if intersections:
            raise RuntimeError(f"self-intersecting carbon ring for {configuration}: {intersections}")
        hydrogens_inside = [
            index for index, hydrogen in enumerate(hydrogens) if point_in_polygon(hydrogen, carbons)
        ]
        if hydrogens_inside != inner_positions:
            raise RuntimeError(
                f"inner-H topology mismatch for {configuration}: "
                f"expected {inner_positions}, observed {hydrogens_inside}"
            )
        output = OUTPUT_DIR / f"N{n_carbon}_{configuration.split('-', 1)[1]}_seed.xyz"
        write_xyz(output, configuration, carbons, hydrogens)
        content = output.read_bytes()
        constraints = OUTPUT_DIR / f"N{n_carbon}_all_atom_planar.constraints"
        constraints.write_text(f"$freeze\nz 1-{2 * n_carbon}\n", encoding="utf-8")
        records.append(
            {
                "N": n_carbon,
                "configuration": configuration,
                "source_fragment_lengths": digits,
                "inner_hydrogen_carbon_indices_zero_based": inner_positions,
                "inner_hydrogen_count": len(inner_positions),
                "hydrogens_inside_carbon_polygon_zero_based": hydrogens_inside,
                "inner_hydrogen_topology_verified": True,
                "nonadjacent_carbon_edge_intersections": intersections,
                "minimum_nonbonded_distance_angstrom": minimum_nonbonded_distance(
                    carbons, hydrogens
                ),
                "maximum_absolute_z_angstrom": 0.0,
                **diagnostics,
                "path": output.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "constraint_path": constraints.relative_to(ROOT).as_posix(),
                "constraint_sha256": hashlib.sha256(constraints.read_bytes()).hexdigest(),
                "role": "configuration_identity_seed_only_not_scientific_evidence",
            }
        )
    manifest = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "gate": "P12-R2 planar seed preparation",
        "source_program_code_used": False,
        "fit_to_published_energy_or_geometry_values": False,
        "topology_rule": "each source digit d advances d-1 carbon positions between inner hydrogens",
        "records": records,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
