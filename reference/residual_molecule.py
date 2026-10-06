"""Independent prepared-integral/original-grid residual reference adapter.

Only an existing frozen ordinary ReferenceResult is accepted.  Molecule,
ordinary SCF, integrals and grids are never constructed here.  Raw integrals,
XC and NumPy/SciPy remain shared dependencies, explicitly not independent.
"""
from __future__ import annotations

import copy
import hashlib
import math
from numbers import Integral, Real
from pathlib import Path
import time

import numpy as np

from reference import residual_candidate as solver
from reference import user_molecule as equations
from reference.ordinary_molecule import ReferenceResult


KEYS = ('density','overlap','hcore','eri','grid_coords','grid_weights')
ENGINE_FIELDS = ('charge','basis','symmetry','ecp','unit','_atom','_basis')


def array_identity(value):
    array = np.ascontiguousarray(solver.real_array(value),dtype='<f8')
    return {'shape':list(array.shape),'dtype':'<f8','order':'C',
            'sha256':hashlib.sha256(array.tobytes(order='C')).hexdigest()}


def _cached_value(value):
    """Immutable recursive snapshot; arrays never use ambiguous equality."""
    if isinstance(value,np.ndarray):
        return ('array',array_identity(value))
    if value is None or isinstance(value,(str,bool)):
        return (type(value).__name__,value)
    if isinstance(value,Integral):
        return ('integer',str(int(value)))
    if isinstance(value,Real):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Cached molecular fields must be finite')
        return ('real',number.hex())
    if isinstance(value,dict):
        return ('mapping',tuple(sorted((type(key).__name__+':'+repr(key),_cached_value(item))
                                      for key,item in value.items())))
    if isinstance(value,(list,tuple)):
        return (type(value).__name__,tuple(_cached_value(item) for item in value))
    raise ValueError('Unsupported cached molecular field type: '+type(value).__name__)


class PreparedResidualReference:
    def __init__(self, *, ordinary, rule_path, expected_sha256,
                 initialization_policy,
                 maximum_evaluations=201, execution_kind='ENGINEERING_FAKE'):
        if not isinstance(ordinary,ReferenceResult):
            raise ValueError('A frozen ordinary ReferenceResult is required')
        if initialization_policy not in solver.POLICIES:
            raise ValueError('Explicit supported initialization policy required')
        if type(maximum_evaluations) is not int or not 2 <= maximum_evaluations <= 201:
            raise ValueError('Actual callback budget must be an integer in [2,201]')
        if execution_kind not in ('ENGINEERING_FAKE','PREPARED_MOLECULAR_DIAGNOSTIC'):
            raise ValueError('Explicit fake or prepared molecular diagnostic kind required')
        self.ordinary,self.context = ordinary,ordinary.context
        self.policy,self.limit,self.execution_kind = initialization_policy,maximum_evaluations,execution_kind
        self.ledger,self._used,self._settled,self.last_evaluation,self.last_snapshot = [],False,False,None,None
        self._operators = {}
        self.rule_path,self.rule_sha = rule_path,expected_sha256
        self.entries = equations.load_rules(rule_path,expected_sha256)
        self.profile = copy.deepcopy(self.context.profile)
        if self.profile.get('compute_enabled') is not False or self.profile.get('xc') != 'B3LYPG':
            raise ValueError('The retained B3LYPG production profile must remain disabled')
        self.metadata = copy.deepcopy(self.context.metadata)
        self.record = copy.deepcopy(ordinary.record)
        self.identities = copy.deepcopy(ordinary.record['array_identities'])
        self.arrays = {}
        for key in KEYS:
            array = solver.real_array(ordinary.arrays[key],key)
            if array_identity(array) != self.identities[key]:
                raise ValueError('Frozen ordinary array identity differs: '+key)
            self.arrays[key] = array.copy()
        self.aos = tuple(self.context.aos)
        if any(not isinstance(ao,equations.AO) or (ao.kind == 'pi' and ao.group not in ('A','B')) for ao in self.aos):
            raise ValueError('Independent source AO descriptors require sigma or pi-A/pi-B')
        self.ao_identity = [(ao.kind,ao.group) for ao in self.aos]
        n = len(self.aos)
        for key in ('density','overlap','hcore'):
            array = self.arrays[key]
            if array.shape != (n,n) or not np.allclose(array,array.T,rtol=0,atol=1e-12):
                raise ValueError('Invalid frozen ordinary symmetric matrix: '+key)
        eri = self.arrays['eri']
        if eri.shape != (n,)*4 or any(not np.allclose(eri,eri.transpose(axes),rtol=0,atol=1e-12)
                for axes in ((1,0,2,3),(0,1,3,2),(2,3,0,1))):
            raise ValueError('Prepared ERI must retain real chemist permutation symmetry')
        self.electrons = self.context.mol.nelectron
        if (type(self.electrons) is not int or self.electrons < 2 or self.electrons%2 or
                self.electrons >= 2*n or (self.electrons//2)*(n-self.electrons//2) > 64):
            raise ValueError('Reference occupation/rotation dimension unsupported')
        self.nuclear = solver.real_scalar(self.record['components_hartree']['nuclear_repulsion'],'Cached nuclear repulsion')
        self.overlap,self.hcore = equations.project(self.arrays['overlap'],self.aos),equations.project(self.arrays['hcore'],self.aos)
        if np.linalg.eigvalsh(self.overlap).min() <= 0:
            raise ValueError('Masked overlap is not positive definite; no repair allowed')
        self.masked_eri,self.deleted = equations.mask_integrals(eri,self.aos,self.entries)
        self.mask = np.array([[a.kind == b.kind == 'pi' and a.group != b.group
                               for b in self.aos] for a in self.aos],dtype=bool)
        self._xc,self.hybrid = equations.original_grid_xc(self.context.mean_field)
        if self.hybrid != .2 or self.context.mean_field.xc != 'B3LYPG':
            raise ValueError('The retained B3LYPG global hybrid definition is required')
        if (self.context.mean_field.max_memory != self.profile['ordinary']['max_memory_mb'] or
                self.context.mean_field.grids.level != self.profile['grid']['level']):
            raise ValueError('Prepared original-grid level or memory setting differs from the frozen profile')
        self.settings = self._settings()
        self.engine_cache_scope = {name:hasattr(self.context.mean_field.mol,name) for name in ENGINE_FIELDS}
        self._owned = {key:array_identity(value) for key,value in self.arrays.items()}
        self._owned.update(masked_overlap=array_identity(self.overlap),masked_hcore=array_identity(self.hcore),
                           masked_eri=array_identity(self.masked_eri))
        for array in (*self.arrays.values(),self.overlap,self.hcore,self.masked_eri,self.mask):
            array.setflags(write=False)
        self._assert_frozen()

    def _settings(self):
        mf = self.context.mean_field
        result = {'xc':mf.xc,'max_memory':mf.max_memory,'nr_rks':mf._numint.nr_rks,
                  'hybrid_coeff':mf._numint.rsh_and_hybrid_coeff,'spin':mf.mol.spin,
                  'cart':mf.mol.cart,'nelectron':mf.mol.nelectron}
        for name in ENGINE_FIELDS:
            result['mol_'+name] = _cached_value(getattr(mf.mol,name)) if hasattr(mf.mol,name) else ('UNAVAILABLE',)
        for key in ('level','prune','radi_method','radii_adjust','atomic_radii','becke_scheme','alignment','atom_grid'):
            if hasattr(mf.grids,key):
                value = getattr(mf.grids,key)
                result['grid_'+key] = array_identity(value) if isinstance(value,np.ndarray) else copy.deepcopy(value)
        return result

    def _assert_frozen(self):
        if hashlib.sha256(Path(self.rule_path).read_bytes()).hexdigest() != self.rule_sha:
            raise solver.ReferenceRefusal('FROZEN_RULES_CHANGED','The exact fifteen-rule bytes changed')
        if self.context.profile != self.profile or self.context.metadata != self.metadata or self.ordinary.record != self.record:
            raise solver.ReferenceRefusal('FROZEN_METADATA_CHANGED','Ordinary profile, record or source metadata changed')
        if self._settings() != self.settings:
            raise solver.ReferenceRefusal('FROZEN_SETTINGS_CHANGED','Original XC/grid settings or callbacks changed')
        if [(ao.kind,ao.group) for ao in self.context.aos] != self.ao_identity:
            raise solver.ReferenceRefusal('FROZEN_AO_MAPPING_CHANGED','Original independent AO descriptors changed')
        for key in KEYS:
            if array_identity(self.ordinary.arrays[key]) != self.identities[key]:
                raise solver.ReferenceRefusal('FROZEN_ORDINARY_ARRAY_CHANGED',key)
        grids = self.context.mean_field.grids
        for key,actual in (('grid_coords',grids.coords),('grid_weights',grids.weights)):
            if array_identity(actual) != self.identities[key]:
                raise solver.ReferenceRefusal('FROZEN_GRID_CHANGED',key)
        for key,array in self.arrays.items():
            if array_identity(array) != self._owned[key]:
                raise solver.ReferenceRefusal('OWNED_ARRAY_CHANGED',key)
        for key,array in (('masked_overlap',self.overlap),('masked_hcore',self.hcore),('masked_eri',self.masked_eri)):
            if array_identity(array) != self._owned[key]:
                raise solver.ReferenceRefusal('OWNED_ARRAY_CHANGED',key)

    def evaluate(self,density):
        if self._settled:
            raise solver.ReferenceRefusal('REFERENCE_BUDGET_SETTLED','No prepared callback is allowed after run settlement')
        if len(self.ledger) >= self.limit:
            raise solver.ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED','Prepared independent callback ceiling reached')
        self._assert_frozen()
        argument = solver.real_array(density,'Requested density').copy()
        if argument.shape != self.overlap.shape or not np.allclose(argument,argument.T,rtol=0,atol=1e-12):
            raise ValueError('Requested density must be same-size symmetric real matrix')
        identity = solver.density_id(argument)
        row = {'evaluation_count':len(self.ledger)+1,'density_id':identity,'status':'STARTED',
               'execution_kind':self.execution_kind,'phase':'DRIVER_DIRECT_CALLBACK'}
        self.ledger.append(row); started = time.monotonic()
        def checked_xc(dm):
            before = solver.density_id(dm)
            try:
                count,energy,potential = self._xc(dm)
            finally:
                self._assert_frozen()
            if solver.density_id(dm) != before:
                raise solver.ReferenceRefusal('REQUESTED_DENSITY_MODIFIED','Raw XC modified its density')
            potential = solver.real_array(potential,'Original-grid XC potential')
            if potential.shape != argument.shape or not np.allclose(potential,potential.T,rtol=0,atol=1e-12):
                raise ValueError('Original-grid XC potential must be same-size symmetric')
            return solver.real_scalar(count,'Grid electrons'),solver.real_scalar(energy,'XC energy'),potential.copy()
        try:
            with np.errstate(over='raise',invalid='raise',divide='raise'):
                value = equations.evaluate(argument,self.hcore,self.overlap,self.arrays['overlap'],
                    self.masked_eri,self.aos,self.hybrid,self.nuclear,checked_xc)
            self._assert_frozen()
            if solver.density_id(argument) != identity:
                raise solver.ReferenceRefusal('REQUESTED_DENSITY_MODIFIED','Independent functional changed requested density')
            fock = solver.real_array(value['Fcond'],'True conditional F').copy()
            fock_id = solver.density_id(fock); previous = self._operators.get(identity)
            row.update(fock_id=fock_id,previous_same_density_fock_id=previous,
                       same_density_operator_reproducible=None if previous is None else previous == fock_id)
            if previous is not None and previous != fock_id:
                raise solver.ReferenceRefusal('NONREPRODUCIBLE_SAME_DENSITY_OPERATOR','Same prepared density returned different true-F bytes')
            self._operators[identity] = fock_id
            self.last_evaluation = value
            components = value['components_hartree']
            checked = {'density_id':identity,'operator_source':solver.TRUE_OPERATOR,'fock':fock,
                'total_energy':value['total_energy_hartree'],
                'one_electron_energy':components['one_electron'],'coulomb_energy':components['coulomb'],
                'exact_exchange_energy':components['exact_exchange'],'semilocal_xc_energy':components['semilocal_xc'],
                'nuclear_repulsion':components['nuclear_repulsion']}
            self.last_snapshot = copy.deepcopy(dict(value,requested_density_id=identity,
                operator_source=solver.TRUE_OPERATOR,wire_result=checked))
            row.update(status='VALIDATED',operator_source=solver.TRUE_OPERATOR,total_energy_hartree=checked['total_energy'])
            return checked
        except Exception as error:
            row.update(status='REFUSED',reason=getattr(error,'reason','INDEPENDENT_FUNCTIONAL_REFUSED'),detail=str(error))
            raise
        finally:
            row['elapsed_seconds'] = time.monotonic()-started

    def run(self,**settings):
        if self._used:
            raise solver.ReferenceRefusal('REFERENCE_ALREADY_USED','No automatic reference retry/budget reset')
        self._used = True
        offset = len(self.ledger)
        try:
            remaining = self.limit-offset
            if remaining < 1:
                raise solver.ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED','No prepared callback budget remains')
            result = solver.solve(density=self.arrays['density'],overlap=self.overlap,electrons=self.electrons,
                evaluate=self.evaluate,initialization_policy=self.policy,maximum_evaluations=remaining,
                matrix_delete_mask=self.mask,**settings)
            phase_mapping_complete = len(result['evaluation_ledger']) == len(self.ledger)-offset
            for own,row in zip(self.ledger[offset:],result['evaluation_ledger']):
                if own['density_id'] == row['density_id']:
                    own['phase'] = row['phase']
                    if 'local_rotation_coordinates' in row:
                        own['local_rotation_coordinates'] = row['local_rotation_coordinates']
                else:
                    phase_mapping_complete = False
        finally:
            self._settled = True
        result.update(prepared_evaluation_ledger=copy.deepcopy(self.ledger),global_evaluation_count=len(self.ledger),
            global_evaluation_limit=self.limit,execution_kind=self.execution_kind,
            nuclear_source='FROZEN_ORDINARY_RECORD_COMPONENT_NOT_EXTRA_ENERGY_NUC_CALL',
            rules_sha256=self.rule_sha,ordinary_density_identity=self.identities['density'],
            metadata=copy.deepcopy(self.metadata),last_evaluation=self.last_evaluation,
            last_snapshot=copy.deepcopy(self.last_snapshot),prepared_budget_settled=self._settled,
            phase_mapping_status='COMPLETE' if phase_mapping_complete else
                'PARTIAL_REFUSED_CALLBACK_WITHOUT_TRUE_FUNCTIONAL_ATTEMPT',
            real_functional_attempt_count=0 if self.execution_kind == 'ENGINEERING_FAKE' else len(self.ledger),
            engine_cache_scope=dict(self.engine_cache_scope),
            identity_evidence_kind='FROZEN_ORDINARY_RECORD_IDENTITIES_NOT_EXTERNAL_AUTHENTICATION',
            shared_dependencies=['RAW_INTEGRALS','ORIGINAL_GRID_XC','NUMPY','SCIPY'],
            molecular_execution='NOT_EXECUTED_ENGINEERING_FAKE' if self.execution_kind == 'ENGINEERING_FAKE' else
                ('EXECUTED_DIAGNOSTIC_UNQUALIFIED' if self.ledger else 'NOT_EXECUTED'))
        return result
