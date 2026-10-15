# Additional read-only canonical MO review

The new tool leaves the frozen worker, old endpoint gates, source locks and historical results unchanged. It is not automatically wired into a production launcher.

Use an existing host Python and NumPy environment. Missing dependencies are a preparation gap; this tool does not install software or dispatch a container calculation.

```console
python -B scripts/review-canonical-orbitals.py --npz evidence/numerical-witnesses/ordinary-water/orbitals-density.npz --electron-count 10 --output /path/to/new-orbital-review
```

Use a new output directory. The required numeric NPZ arrays are `overlap`, `canonical_coefficients`, `orbital_energies_hartree`, `occupations`, `fock`; `density` is optional for density correspondence. Object arrays, missing required arrays, invalid dimensions/nonfinite values and threshold failures cannot obtain full orbital PASS.

The [versioned policy](../../review_tools/canonical_mo_policy_v1.json) records complete `||C†SC-I||F` (absolute dimensionless), `||FC-SCε||F` (Eh) and a whitened relative residual, with explicit normalization and engineering thresholds. Electron count, closed-shell 2/0 occupations, sorted energies and column alignment are checked. No implicit relative tolerance is used. This is an additional array policy, not a new scientific state definition.

Output separates the endpoint numerical status (not reevaluated by this tool), complete-orbital array qualification and wavefunction stability (NOT_EXECUTED). A positive result applies to the supplied arrays only. It does not certify a stable wavefunction, a new installation or all exported historical results.

The public regression preserves the synthetic counterexample with valid occupied density and a corrupted virtual column [7,7]: the old v1 endpoint flag remains True while the new review rejects it. Exit 0 means saved arrays meet the extra policy; rejection/non-execution returns 2. Existing output directories are refused without modification.
