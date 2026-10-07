# LFMO source-method mapping v0.1

- Status: source-equivalence decision record
- Date: 2026-08-14
- Production labels allowed: no
- Public source: Z.-H. Yu, *Questioning Fundamental Principles of Organic Chemistry*, DOI `10.6084/m9.figshare.27261243`
- Independent implementation: no original program code used

## 1. Decision

The frozen-density B--C pi transition-coupling pilot is **not source-equivalent**
to any of the following source definitions:

1. the 1998/2006 LFMO DSI/FUD state-difference method;
2. the Chapter 5 sigma--pi component decomposition;
3. the 2011 electron-localization method that additionally deletes selected
   two-electron exchange integrals.

It remains a project-defined, non-production
`transition_density_coupling_diagnostic`. Its positive sign at two endpoint
densities may be retained as an internal directional observation, but it is not
evidence that the source LFMO pi--pi energy has been reproduced.

## 2. Source-defined quantities

### 2.1 1998/2006 LFMO state differences

The source constructs conditional electronic states by deleting selected Fock
and overlap blocks during SCF over an LFMO basis. In this method the relevant
two-electron exchange integrals remain present. The primary vertical pi
delocalization quantity is

`Delta E^V(theta) = E_FUD(theta) - E_DSI(theta)`.

DSI-3, DSI-2, FUD, PDSI, and FUL are distinct conditional states, not frozen
evaluations of one common density under two Hamiltonians.

### 2.2 Chapter 5 sigma--pi quantity and component equations

The total sigma--pi interaction energy is defined by the ground/FUD state
difference

`Delta E^(pi-sigma)(theta) = E_G(theta) - E_FUD(theta)`.

Equations 5-12 to 5-16 then decompose this state difference into intra- and
interfragment terms using state-specific density matrices and the corresponding
one-electron and Fock matrix elements. This is not a B--C pi--pi Hamiltonian
deletion and is not a frozen-density direct term.

The nonbonded sigma--sigma quantity is separately obtained from a PDSI/FUL
state difference. It must not be inferred from the present pilot.

### 2.3 2011 electron-localization method

For localized pi groups, the source's 2011 method deletes cross-group pi
one-electron and overlap elements and additionally deletes a specified set of
15 classes of two-electron exchange integrals. The source distinguishes
multiple program versions because retaining or deleting different integral
classes changes both magnitude and sign.

The 15-class topology is not equivalent to deleting every electron-repulsion
integral for which either compound pair index is a B--C pi transition pair.
The source also applies the deletion during conditional SCF or restricted
geometry optimization, whereas the pilot evaluates two fixed endpoint
densities without coupling-off reoptimization.

## 3. State-basis correction

The source's LFMO-n reorganization is not merely a metadata regrouping. When
primitive fragments are merged, the composition of the sub-LFMO basis and the
number of cut-bond singly occupied LFMOs can change. The printed page 89
example explicitly changes two singly occupied LFMOs to one after merging two
sub-bases.

Therefore a source-equivalent DSI-2/DSI-3 comparison must permit
state-specific bases

`C_L^(DSI-2) != C_L^(DSI-3)`

and state-specific overlap matrices, occupations, and root rules. The current
same-basis construction, in which only the pi block membership changes, is a
deliberate project variant. Its DSI-2 domain contains its DSI-3 domain and its
negative energy difference is correctly classified only as
`nested_variational_lowering` for that variant.

## 4. Item-by-item equivalence matrix

| Definition item | Public source | Current pilot | Verdict |
|---|---|---|---|
| Orbital basis | Source-constructed LFMO-n; state reorganization may change basis contents and cut SOMOs | One square DSI-3 candidate reused for both endpoint densities | mismatch |
| Pi--pi source energy | `E_FUD-E_DSI` or a declared conditional-state difference | Frozen `E_full[P]-E_off[P]` | mismatch |
| Sigma--pi source energy | `E_G-E_FUD`, then Eqs. 5-12--5-16 | Not evaluated | absent |
| Fock/overlap constraint | Deleted cross blocks during every SCF iteration | No coupling-off SCF; overlap unchanged in frozen evaluation | mismatch |
| Two-electron treatment, 2006 | Exchange integrals retained | Broad transition-pair ERI deletion | mismatch |
| Two-electron treatment, 2011 | Specific 15 exchange-integral classes | Any ERI containing the selected B--C transition pair on either coordinate | mismatch |
| Density | State-specific self-consistent densities | DSI-3 and DSI-2 endpoint controls | mismatch |
| Energy-component formula | State-difference matrix contractions | Full-minus-coupling-off frozen Hamiltonian contraction | mismatch |
| Reference-density invariance | Source quantity is defined by named states | Direct magnitude changes by factor `14.451754` | fails as transferable magnitude |
| Sign convention | Positive named state difference is destabilizing | Positive project direct term | same sign vocabulary only; not same observable |

## 5. Minimal numerical cross-check

The source's Scheme 4-3 example gives

`E_DSI-2 - E_DSI-3 = (-556.88775)-(-556.89302) = +0.00527 Eh`

at its stated molecule, geometry, method, and basis. The current same-basis
project variant gives `-0.015103912012 Eh` for its different pilot contract.
The opposite signs are not an apples-to-apples validation test because the
molecule and computational contract differ. They do, however, reinforce that
the current nested-space result must not be substituted for the source state
difference.

## 6. Consequences

- Withdraw any source-equivalence implication for the frozen coupling pilot.
- Retain the pilot only as an identifiability result: its sign is common across
  two endpoint densities, while its magnitude and offset allocation are not.
- Do not generate LFMO, pi--pi, sigma--pi, conjugation, stabilization, or
  production labels from the pilot.
- Do not extend the pilot to additional molecules, bases, or scans on the core
  LFMO replication track.
- The next implementation target is a state-specific LFMO-n reconstruction
  contract, followed by named source state differences. Chapter 5 component
  equations are implemented only after those states close independently.

## 7. Page-level evidence

- Printed pp. 84-85: method generations and DSI/PDSI/FUD/FUL definitions.
- Printed pp. 89-91: LFMO-n reorganization and conditional Fock/overlap states.
- Printed pp. 96-99: retained exchange in the 2006 method and state-energy behavior.
- Printed pp. 138-141: `E_G-E_FUD` and Eqs. 5-12--5-16 for sigma--pi decomposition.
- Printed pp. 144-147: FUL/PDSI construction and nonbonded sigma--sigma difference.
- Printed pp. 254-265: AO/LFMO decomposition, retained exchange problem, and
  2011 15-class exchange-integral deletion variants.

