"""Held Python dispatch audit for the fixed third-batch state contracts.

This is an enumerated Python-entry audit, not interception of every native/C
operation. Image identity, immutable source bytes and the container own that
boundary. No computation, retries or restoration from checkpoints are added.
"""
from __future__ import annotations

import copy
import functools
import importlib
import inspect
import json
import math
from pathlib import Path
import re
import sys
import threading

_ACTIVE = None
_SOURCE_MARKER = "/reference/high_cost_cases/source_tree/"
_OPERATORS = {"ordinary_rks", "source2007", "source2011", "furan_p09"}
_COUNTERS = {"scf", "gradient", "numint", "grids", "conditional"}


class GuardError(RuntimeError):
    pass


def _source_filename(module):
    return str(getattr(module, "__file__", "") or "").replace("\\", "/")


class HighCostGuard:
    def __init__(self, unit, mode, checkpoint=None, journal=None):
        if not isinstance(unit, dict) or mode not in ("ledger", "preflight", "live"):
            raise GuardError("One registered unit and fixed mode are required")
        self.unit = copy.deepcopy(unit)
        self.unit_id = unit.get("unit_id", unit.get("id"))
        if not isinstance(self.unit_id, str) or not self.unit_id:
            raise GuardError("Registered unit ID is required")
        self.operator = unit.get("operator_id", unit.get("method_id"))
        if self.operator not in _OPERATORS:
            raise GuardError("Explicit ordinary/source2007/source2011/furan operator ID required")
        self.optimizer = unit.get("optimizer", "none")
        if self.optimizer not in ("geometric", "scipy_minimize", "none"):
            raise GuardError("Unknown fixed optimizer")
        caps = unit.get("caps")
        if not isinstance(caps, dict) or set(caps) != _COUNTERS or any(type(value) is not int or value < 0 for value in caps.values()):
            raise GuardError("Five nonnegative integer dispatch caps are required")
        self.mode, self.checkpoint = mode, checkpoint
        self.journal = Path(journal) if journal is not None else None
        self.caps = {key: value if mode == "live" else 0 for key, value in caps.items()}
        self.caps["optimizer"] = 1 if mode == "live" and self.optimizer != "none" else 0
        self.counts, self.outcomes, self.operator_counts = {}, {}, {}
        self.engineering_counts, self.engineering_outcomes = {}, {}
        metadata = self.unit.get("case") == "P11" and self.unit_id == "P11-metadata" and mode != "live"
        cyanobenzene = (self.unit.get("case") == "P11"
                       and re.fullmatch(r"P11B-cyanobenzene-(?:G|GL_I|GL_II|GE[1-7])", self.unit_id)
                       and self.unit.get("system", "cyanobenzene") == "cyanobenzene"
                       and self.unit.get("subcase", "P11-B") == "P11-B")
        self.engineering_caps = {"coordinate_reconstruction": 64 if metadata else 4 if cyanobenzene else 0}
        self._coordinate_source = None
        self.denied, self.changed, self.bindings, self.restoration_errors = [], [], [], []
        self.active = self.closed = False
        self.restored = None
        self.thread = None
        self.stack = []
        self._rks = self._rks_gradient = None

    def _event(self, event, entry, operator=None):
        if self.journal is not None:
            row = {"event": event, "entry": entry, "unit_id": self.unit_id,
                   "counts": self.counts, "engineering_counts": self.engineering_counts,
                   "operator": operator}
            with self.journal.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()

    def _held(self):
        if not self.active or threading.get_ident() != self.thread:
            self.denied.append("INACTIVE_OR_FOREIGN_THREAD")
            self._event("DENIED_BEFORE_DELEGATE", "GUARD_CONTEXT")
            raise GuardError("Inactive or foreign-thread guard")
        changed = [label for owner, name, label, owned, direct, original, wrapper in self.bindings
                   if getattr(owner, name, None) is not wrapper]
        if changed:
            self.changed.extend(changed)
            raise GuardError("Held entry bindings changed: " + str(changed))

    def _deny(self, label):
        self.denied.append(label)
        self._event("DENIED_BEFORE_DELEGATE", label)
        raise GuardError("Outside the registered third-batch state: " + label)

    def _source_kind(self, cls, gradient=False):
        suffixes = {"source2007": ("p11_source2007_rks", "Source2007ConditionalRKS"),
                    "source2011": ("p12_source2011_rks", "Source2011DirectConditionalRKS")}
        terminal = "_Gradients" if gradient else "_RKS"
        for base in cls.__mro__:
            for kind, (suffix, factory) in suffixes.items():
                module_name = getattr(base, "__module__", "")
                qualname = getattr(base, "__qualname__", "")
                if module_name.rsplit(".", 1)[-1] != suffix or qualname != factory + ".build.<locals>." + terminal:
                    continue
                module = sys.modules.get(module_name)
                filename = _source_filename(module)
                if _SOURCE_MARKER not in filename or not filename.endswith("/" + suffix + ".py"):
                    return "UNREGISTERED_SOURCE_CLASS"
                method = vars(base).get("get_ovlp" if gradient else "get_fock")
                code = getattr(method, "__code__", None)
                if code is None or str(code.co_filename).replace("\\", "/") != filename:
                    return "UNREGISTERED_SOURCE_CLASS"
                return kind
        return None

    def _mean_field_kind(self, instance):
        if not isinstance(instance, self._rks):
            return "UNSUPPORTED_HF_OR_DFT"
        kind = self._source_kind(type(instance))
        if kind:
            return kind
        # PySCF creates scanner mixins dynamically. Ordinary RKS and its own
        # scanner are accepted; arbitrary user/source subclasses are not.
        for cls in type(instance).__mro__:
            if cls is self._rks:
                return "ordinary_rks"
            namespace = getattr(cls, "__module__", "")
            if not namespace.startswith("pyscf."):
                return "UNREGISTERED_RKS_SUBCLASS"
        return "UNSUPPORTED_RKS"

    def _check_operator(self, kind, label):
        allowed = {"ordinary_rks"}
        if self.operator in ("source2007", "source2011"):
            allowed.add(self.operator)
        if kind not in allowed:
            self._deny(label + ":" + kind)
        return kind

    def _gradient_kind(self, instance):
        base = getattr(instance, "base", None)
        kind = self._mean_field_kind(base)
        source = self._source_kind(type(instance), gradient=True)
        if source is not None:
            return source if source == kind else "GRADIENT_MEAN_FIELD_OPERATOR_MISMATCH"
        if kind != "ordinary_rks" or not isinstance(instance, self._rks_gradient):
            return "GRADIENT_OPERATOR_MISMATCH"
        for cls in type(instance).__mro__:
            if cls is self._rks_gradient:
                return kind
            if not getattr(cls, "__module__", "").startswith("pyscf."):
                return "UNREGISTERED_GRADIENT_SUBCLASS"
        return "UNSUPPORTED_GRADIENT"

    def _driver_allowed(self, filename):
        if self.mode != "live":
            return False
        case = self.unit.get("case")
        subcase = self.unit.get("subcase")
        if subcase is None and self.unit_id.startswith("P11A-"):
            subcase = "P11-A"
        if subcase is None and self.unit_id.startswith("P11B-"):
            subcase = "P11-B"
        if case == "P11" and subcase == "P11-A":
            return filename.endswith("/scripts/run_p11_furan_lde.py")
        if case == "P11" and subcase == "P11-B":
            return filename.endswith("/scripts/run_p11_source2007_planar_optimization.py")
        if case == "P12":
            suffix = ("run_p12_planar_g_optimization.py" if self.operator == "ordinary_rks"
                      else "run_p12_planar_source_state_optimization.py")
            return filename.endswith("/scripts/" + suffix)
        return False

    def _coordinate_call(self, original, args, kwargs, caller, label):
        """Admit only the frozen Figure-7 ring fitting call, never a QM fit."""
        if not self.engineering_caps["coordinate_reconstruction"] or self._coordinate_source is None:
            return self._deny(label + ":COORDINATE_SOURCE_NOT_PREPARED_OR_SCOPE_DIFFERS")
        module, function, filename = self._coordinate_source
        if (getattr(module, "reconstruct_ring", None) is not function
                or caller is None or caller.f_code is not function.__code__
                or caller.f_globals is not vars(module)):
            return self._deny(label + ":FROZEN_COORDINATE_CALLER_DIFFERS")
        if len(args) != 2 or set(kwargs) != {"method", "ftol", "xtol", "gtol", "max_nfev"}:
            return self._deny(label + ":COORDINATE_CALL_ARGUMENTS_DIFFER")
        residual, initial = args
        code = getattr(residual, "__code__", None)
        if (code is None or code not in function.__code__.co_consts
                or getattr(residual, "__qualname__", "") != "reconstruct_ring.<locals>.residuals"
                or str(code.co_filename).replace("\\", "/") != filename
                or getattr(residual, "__globals__", None) is not vars(module)):
            return self._deny(label + ":FROZEN_COORDINATE_RESIDUAL_DIFFERS")
        if (kwargs["method"] != "trf" or type(kwargs["max_nfev"]) is not int
                or kwargs["max_nfev"] != 5000
                or any(type(kwargs[key]) is not float or kwargs[key] != 1.0e-14 for key in ("ftol", "xtol", "gtol"))):
            return self._deny(label + ":FROZEN_COORDINATE_SOLVER_LIMITS_DIFFER")
        try:
            values = tuple(float(value) for value in initial)
            expected = tuple(float(value) for row in caller.f_locals["initial"][2:] for value in row)
            target = tuple(float(value) for value in caller.f_locals["target"])
            if (len(values) != 8 or len(expected) != 8 or values != expected
                    or len(target) != 6 or not all(math.isfinite(value) and value > 0 for value in target)
                    or not all(math.isfinite(value) for value in values)):
                return self._deny(label + ":FROZEN_COORDINATE_INITIAL_VALUES_DIFFER")
        except (KeyError, TypeError, ValueError, OverflowError):
            return self._deny(label + ":FROZEN_COORDINATE_INITIAL_SHAPE_DIFFERS")
        return self._invoke(label, original, args, kwargs,
                            operator="SOURCE_FIGURE7_COORDINATE_RECONSTRUCTION",
                            phase="coordinate_reconstruction", engineering="coordinate_reconstruction")

    def _invoke(self, label, original, args, kwargs, counter=None, operator=None, phase=None, engineering=None):
        self._held()
        if self.checkpoint:
            self.checkpoint("HIGH_COST_BEFORE_" + label[:100])
        self._held()
        counts = self.engineering_counts if engineering else self.counts
        outcomes = self.engineering_outcomes if engineering else self.outcomes
        caps = self.engineering_caps if engineering else self.caps
        counter = engineering or counter
        if counter is not None:
            if counts.get(counter, 0) >= caps.get(counter, 0):
                self._deny(label + ":CAP_EXHAUSTED")
            counts[counter] = counts.get(counter, 0) + 1
            outcomes.setdefault(counter, {"returned": 0, "failed": 0})
            if operator is not None and not engineering:
                key = counter + ":" + operator
                self.operator_counts[key] = self.operator_counts.get(key, 0) + 1
        self._event("OWNED_WRAPPER_ENTERED", label, operator)
        if phase:
            self.stack.append(phase)
        try:
            result = original(*args, **kwargs)
            if counter:
                outcomes[counter]["returned"] += 1
            self._event("DELEGATE_RETURNED", label, operator)
        except BaseException:
            if counter:
                outcomes[counter]["failed"] += 1
            self._event("DELEGATE_FAILED", label, operator)
            raise
        finally:
            if phase:
                self.stack.pop()
        if self.checkpoint:
            self.checkpoint("HIGH_COST_AFTER_" + label[:100])
        self._held()
        return result

    def _wrapper(self, label, original, kind):
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            self._held()
            if kind == "coordinate":
                frame = inspect.currentframe()
                try:
                    return self._coordinate_call(original, args, kwargs, frame.f_back, label)
                finally:
                    del frame
            if (kind == "deny" or self.mode != "live" and kind != "mole_build"
                    or kind == "mole_build" and self.mode == "ledger"):
                return self._deny(label)
            operator = None
            if kind in ("scf", "scf_gateway"):
                operator = self._check_operator(self._mean_field_kind(args[0]), label)
            elif kind == "gradient":
                operator = self._check_operator(self._gradient_kind(args[0]), label)
            elif kind.startswith("factory:"):
                operator = kind.split(":", 1)[1]
                if self.operator != operator:
                    return self._deny(label + ":WRONG_SOURCE_FACTORY")
            elif kind == "conditional":
                if self.operator == "furan_p09":
                    arguments = inspect.signature(original).bind_partial(*args, **kwargs)
                    arguments.apply_defaults()
                    if arguments.arguments.get("mask_one_electron_matrix") is not True:
                        return self._deny(label + ":FURAN_SOURCE_MATRIX_RULE_DIFFERS")
                    operator = "furan_p09"
                elif (self.operator == "source2007"
                      and re.fullmatch(r"P11B-cyanobenzene-GE[1-7]", self.unit_id)
                      and self.counts.get("optimizer", 0) == 0
                      and self.operator_counts.get("scf:source2007", 0) == 0):
                    arguments = inspect.signature(original).bind_partial(*args, **kwargs).arguments
                    if (arguments.get("mask_one_electron_matrix") is not False
                            or type(arguments.get("eri_classes")) is not list
                            or arguments["eri_classes"] != []
                            or self.counts.get("conditional", 0) >= 1):
                        return self._deny(label + ":SOURCE2007_FIXED_GL_INITIALIZER_DIFFERS")
                    operator = "SOURCE2007_FIXED_GL_INITIALIZER"
                else:
                    return self._deny(label + ":WRONG_CONDITIONAL_OPERATOR")
            elif kind == "geometric":
                if self.optimizer != "geometric":
                    return self._deny(label + ":WRONG_OPTIMIZER")
                candidate = args[0] if args else kwargs.get("method")
                operator = self._check_operator(self._mean_field_kind(getattr(candidate, "base", candidate)), label)
            elif kind == "scipy_minimize":
                if self.optimizer != "scipy_minimize":
                    return self._deny(label + ":WRONG_OPTIMIZER")
                objective = args[0] if args else kwargs.get("fun")
                filename = str(getattr(getattr(objective, "__code__", None), "co_filename", "")).replace("\\", "/")
                if _SOURCE_MARKER not in filename or not filename.endswith("/scripts/run_p11_furan_lde.py"):
                    return self._deny(label + ":UNREGISTERED_OBJECTIVE")
            counter = {"scf": "scf", "gradient": "gradient", "numint": "numint",
                       "grids": "grids", "conditional": "conditional",
                       "geometric": "optimizer", "scipy_minimize": "optimizer"}.get(kind)
            phase = "optimizer" if kind in ("geometric", "scipy_minimize") else kind if counter else None
            return self._invoke(label, original, args, kwargs, counter, operator, phase)
        return wrapped

    def __enter__(self):
        global _ACTIVE
        if _ACTIVE is not None or self.closed:
            raise GuardError("Nested or reused high-cost guard")
        from pyscf.scf import hf, uhf
        from pyscf.dft import rks, uks, roks, numint, gen_grid
        from pyscf.grad import rks as rks_grad, rhf as rhf_grad
        from pyscf import gto
        import scipy.optimize as optimize
        self._rks, self._rks_gradient = rks.RKS, rks_grad.Gradients
        targets = []
        def add(owner, name, label, kind, required=True):
            if callable(getattr(owner, name, None)):
                targets.append((owner, name, label, kind))
            elif required:
                raise GuardError("Required audit API missing: " + label)
        add(hf, "kernel", "hf.kernel", "scf")
        for name in ("kernel", "scf"):
            add(hf.SCF, name, "SCF." + name, "scf_gateway", required=False)
        for owner, label in ((hf.SCF, "SCF"), (rks.RKS, "RKS")):
            for name in ("density_fit", "newton", "MP2", "CCSD", "CISD", "CASCI", "CASSCF", "TDHF", "TDDFT"):
                add(owner, name, label + "." + name, "deny", required=False)
        for owner, name, label in ((uhf, "_hf1e_scf", "uhf._hf1e_scf"),
                                   (getattr(uhf, "HF1e", None), "scf", "HF1e.scf"),
                                   (uks.UKS, "kernel", "UKS.kernel"),
                                   (roks.ROKS, "kernel", "ROKS.kernel")):
            add(owner, name, label, "deny", required=False)
        module_nr = numint.nr_rks
        add(numint, "nr_rks", "numint.nr_rks", "numint")
        if getattr(numint.NumInt, "nr_rks", None) is module_nr:
            add(numint.NumInt, "nr_rks", "NumInt.nr_rks", "numint")
        else:
            add(numint.NumInt, "nr_rks", "NumInt.nr_rks", "numint", required=False)
        for owner, label in ((numint, "numint.nr_uks"), (numint.NumInt, "NumInt.nr_uks")):
            add(owner, "nr_uks", label, "deny", required=False)
        add(gen_grid.Grids, "build", "Grids.build", "grids")
        for owner, label in ((rks_grad.Gradients, "RKS.Gradients.kernel"),
                             (getattr(rhf_grad, "Gradients", None), "RHF.Gradients.kernel"),
                             (getattr(rhf_grad, "GradientsBase", None), "GradientsBase.kernel")):
            add(owner, "kernel", label, "gradient", required=False)
        add(gto.Mole, "build", "Mole.build", "mole_build")
        for name in ("intor", "intor_by_shell", "energy_nuc"):
            add(gto.Mole, name, "Mole." + name, "live_integral")
        add(optimize, "minimize", "scipy.optimize.minimize", "scipy_minimize")
        add(optimize, "least_squares", "scipy.optimize.least_squares", "coordinate")
        for name in ("differential_evolution", "basinhopping", "dual_annealing",
                     "shgo", "fmin", "fmin_bfgs", "fmin_l_bfgs_b"):
            add(optimize, name, "scipy.optimize." + name, "deny", required=False)
        # Frozen adapters prepare imports before entry. A missing geometric
        # dependency is a refusal, never silently changed to another optimizer.
        solver = sys.modules.get("pyscf.geomopt.geometric_solver")
        if solver is None:
            try:
                solver = importlib.import_module("pyscf.geomopt.geometric_solver")
            except ImportError as error:
                raise GuardError("Required geometric solver MODULE_NOT_PREPARED; no dependency fallback") from error
        add(solver, "kernel", "geometric_solver.kernel", "geometric")
        add(solver, "optimize", "geometric_solver.optimize", "deny", required=False)
        # Refuse loaded HF alternatives, density fitting, post-HF, localization,
        # Newton and other optimizer terminals. No module is executed here.
        blocked = ("pyscf.mp", "pyscf.cc", "pyscf.ci", "pyscf.mcscf", "pyscf.df",
                   "pyscf.lo", "pyscf.soscf", "pyscf.geomopt.berny")
        # Load standard installed PySCF namespaces before taking aliases so a
        # later direct MP2/DF/Newton import cannot create an unheld terminal.
        # The optional Berny optimizer is held if already prepared; the fixed
        # registry only admits geomeTRIC or the original furan SciPy optimizer.
        for module_name in blocked[:-1]:
            if module_name not in sys.modules:
                importlib.import_module(module_name)
        for module_name, module in list(sys.modules.items()):
            if module is None:
                continue
            namespace = getattr(module, "__dict__", {})
            if any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in blocked):
                add(module, "kernel", module_name + ".kernel", "deny", required=False)
                for name, value in list(namespace.items()):
                    class_module = getattr(value, "__module__", "")
                    if isinstance(value, type) and any(class_module == prefix or class_module.startswith(prefix + ".") for prefix in blocked):
                        add(value, "kernel", module_name + "." + name + ".kernel", "deny", required=False)
                        if class_module == "pyscf.df" or class_module.startswith("pyscf.df."):
                            for terminal in ("build", "get_jk"):
                                add(value, terminal, module_name + "." + name + "." + terminal, "deny", required=False)
            if _SOURCE_MARKER not in _source_filename(module):
                continue
            filename = _source_filename(module)
            if filename.endswith("/scripts/run_p11_cyanobenzene_effect.py"):
                function = namespace.get("reconstruct_ring")
                code = getattr(function, "__code__", None)
                if code is not None and str(code.co_filename).replace("\\", "/") == filename:
                    if self._coordinate_source is not None and self._coordinate_source[1] is not function:
                        raise GuardError("Mixed coordinate reconstruction source modules")
                    self._coordinate_source = (module, function, filename)
            for name, value in list(namespace.items()):
                if name in ("Source2007ConditionalRKS", "Source2011DirectConditionalRKS") and isinstance(value, type):
                    operator = "source2007" if name.startswith("Source2007") else "source2011"
                    add(value, "build", name + ".build", "factory:" + operator)
                if callable(value) and getattr(value, "__name__", "") == "run_p09_conditional_rks":
                    add(module, name, module_name + "." + name, "conditional")
                elif callable(value) and (getattr(value, "__name__", "").startswith("run_")
                                          or getattr(value, "__name__", "") in ("run", "optimize_state")):
                    filename = str(getattr(getattr(value, "__code__", None), "co_filename", "")).replace("\\", "/")
                    allowed = self._driver_allowed(filename)
                    add(module, name, module_name + "." + name, "source_driver" if allowed else "deny")
        # Capture first, then hold all preloaded aliases of enumerated terminals.
        captured, seen, aliases = [], set(), {}
        for owner, name, label, kind in targets:
            key = (id(owner), name)
            if key in seen:
                continue
            seen.add(key)
            original = getattr(owner, name)
            aliases.setdefault(id(original), (original, kind))
            captured.append((owner, name, label, kind, original, name in vars(owner), vars(owner).get(name)))
        for module_name, module in list(sys.modules.items()):
            for name, value in list(getattr(module, "__dict__", {}).items()):
                if id(value) in aliases and (id(module), name) not in seen:
                    original, kind = aliases[id(value)]
                    seen.add((id(module), name))
                    captured.append((module, name, module_name + "." + name, kind, original, True, value))
        self.thread = threading.get_ident(); self.active = True; _ACTIVE = self
        try:
            for owner, name, label, kind, original, owned, direct in captured:
                wrapper = self._wrapper(label, original, kind)
                replacement = staticmethod(wrapper) if isinstance(direct, staticmethod) else wrapper
                setattr(owner, name, replacement)
                self.bindings.append((owner, name, label, owned, direct, original, wrapper))
        except BaseException:
            self.__exit__(None, None, None)
            raise
        self._event("GUARD_INSTALLED", "all")
        return self

    def __exit__(self, *error):
        global _ACTIVE
        try:
            self._held()
        finally:
            try:
                for owner, name, label, owned, direct, original, wrapper in reversed(self.bindings):
                    try:
                        if owned:
                            setattr(owner, name, direct)
                        else:
                            delattr(owner, name)
                    except BaseException as failure:
                        self.restoration_errors.append(label + ": " + str(failure))
            finally:
                self.active = False; self.closed = True; _ACTIVE = None
            self.restored = all(getattr(row[0], row[1], None) is row[5] and (row[1] in vars(row[0])) == row[3] for row in self.bindings)
            self._event("GUARD_CLOSED", "all")
        if self.restoration_errors:
            raise GuardError("Entry restoration failed: " + str(self.restoration_errors))
        return False

    def snapshot(self):
        if self.active:
            self._held()
        passed = bool(self.bindings) and not self.denied and not self.changed and not self.restoration_errors and self.restored is not False
        return {"schema": "high-cost-native-audit-v1", "unit_id": self.unit_id, "mode": self.mode,
                "operator_id": self.operator, "status": "PASS" if passed else "FAIL",
                "counts": copy.deepcopy(self.counts), "caps": dict(self.caps),
                "engineering_counts": dict(self.engineering_counts), "engineering_caps": dict(self.engineering_caps),
                "engineering_outcomes": copy.deepcopy(self.engineering_outcomes),
                "coordinate_source_status": "FROZEN_CALLER_PREPARED" if self._coordinate_source else "MODULE_NOT_PREPARED",
                "operator_counts": dict(self.operator_counts), "outcomes": copy.deepcopy(self.outcomes),
                "denied": list(self.denied), "changed": list(self.changed), "closed": self.closed,
                "restored_attributes_intact": self.restored, "restoration_errors": list(self.restoration_errors),
                "held_entries": [row[2] for row in self.bindings], "automatic_retry": False, "resume": False,
                "scope": "OBSERVED_PYTHON_DISPATCH_NOT_ALL_C_NATIVE_OPERATIONS_OR_CONVERGENCE",
                "missing_count_is_observed_zero_only_when_guard_closed": self.closed}
