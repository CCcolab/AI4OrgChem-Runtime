# SPDX-License-Identifier: Apache-2.0
"""Source-bound, charged independent evaluations for a separately granted run.

This module does not create authorization, a budget, an ordinary calculation,
or a prepared engine. Install the NR boundary before constructing the retained
reference. The default/inactive contract is refused before any native dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
from pathlib import Path

import numpy as np


class NativeBindingError(ValueError):
    pass


def _did(value):
    from reference.residual_candidate import density_id
    return density_id(value)


def _active_contract(contract, *, explicit_grant, local_cli_execute_requested):
    from .occupied_space_root_native_contract import validate_execution_contract
    validate_execution_contract(contract, explicit_grant=explicit_grant,
        local_cli_execute_requested=local_cli_execute_requested)
    if contract['scientific_execution_authorized'] is not True:
        raise NativeBindingError('Inactive engineering contract cannot bind a native evaluator')


def _source_bytes(root, contract):
    root=Path(root).resolve(strict=True)
    for relative, digest in contract['source_file_sha256'].items():
        path=root/relative
        cursor=path
        while cursor!=root:
            if cursor.is_symlink() or (hasattr(cursor,'is_junction') and cursor.is_junction()):
                raise NativeBindingError('Source link refused: '+relative)
            cursor=cursor.parent
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise NativeBindingError('Source bytes differ: '+relative)
    return root


class NativeReferenceNRBinding:
    """One original mol/grid/XC/D NR dispatch per explicit charged callback."""

    def __init__(self, *, context, accounting, contract, runtime_root,
            explicit_grant=None, local_cli_execute_requested=False, original_nr=None, contract_sha256=None,
            before_dispatch_check=None):
        _active_contract(contract,explicit_grant=explicit_grant,
            local_cli_execute_requested=local_cli_execute_requested)
        from pyscf.dft.numint import NumInt
        if type(context.mean_field._numint) is not NumInt:
            raise NativeBindingError('Exact pinned NumInt instance required')
        self.root=_source_bytes(runtime_root,contract)
        self.context,self.accounting=context,accounting
        self.contract=copy.deepcopy(contract)
        self.explicit_grant=copy.deepcopy(explicit_grant)
        self.local_cli_execute_requested=local_cli_execute_requested
        from .occupied_space_root_native_contract import execution_identity
        self.expected_journal_identity=execution_identity(contract,contract_sha256,
            explicit_grant=explicit_grant,local_cli_execute_requested=local_cli_execute_requested)
        self.mol,self.grid,self.ni=context.mol,context.mean_field.grids,context.mean_field._numint
        self.xc=context.mean_field.xc
        if self.mol is not context.mean_field.mol or self.xc!='B3LYPG' or self.mol.nelectron!=16:
            raise NativeBindingError('Frozen molecule/grid/XC identity differs')
        self.original_nr=self.ni.nr_rks if original_nr is None else original_nr
        self._preinstall_nr=self.ni.nr_rks
        if getattr(self.original_nr,'__self__',None) is not self.ni:
            raise NativeBindingError('Owned original NR bound method required')
        function=getattr(self.original_nr,'__func__',None)
        if (getattr(function,'__module__',None)!='pyscf.dft.numint'
                or getattr(function,'__name__',None)!='nr_rks'):
            raise NativeBindingError('Only the captured original pinned PySCF NR function is supported')
        self.active_token=None
        self.active_context=None
        self.installed=False
        if before_dispatch_check is not None and not callable(before_dispatch_check):
            raise NativeBindingError('Optional safe pre-dispatch check must be callable')
        self._before_dispatch_check=before_dispatch_check
        self._held_dispatch_check=before_dispatch_check
        # A stable function identity is frozen by PreparedResidualReference.
        def wrapper(*values,**settings):return self._dispatch(*values,**settings)
        self.wrapper=wrapper
        self._assert_accounting()

    def _assert_accounting(self):
        snap=self.accounting.snapshot()
        from .occupied_space_root_native_contract import validate_native_journal_identity
        validate_native_journal_identity(self.accounting.journal.identity,execution_kind='SOURCE_NATIVE_DIAGNOSTIC',
            initial_density_id=self.contract['initial_density']['density_id'],contract=self.contract,
            explicit_grant=self.explicit_grant,local_cli_execute_requested=self.local_cli_execute_requested)
        if self.accounting.journal.identity!=self.expected_journal_identity:
            raise NativeBindingError('Actual journal batch/family/source/contract identity differs')
        if (snap.get('execution_kind')!='SOURCE_NATIVE_DIAGNOSTIC'
                or snap.get('scientific_execution_authorized') is not True
                or snap.get('callback_slots',{}).get('limit')!=201
                or snap.get('persistence_intact') is not True):
            raise NativeBindingError('Separate authorized source-native accounting required')

    def install(self):
        if self.installed or self.ni.nr_rks!=self._preinstall_nr:
            raise NativeBindingError('Original NR binding changed or reused')
        self.ni.nr_rks=self.wrapper
        self.installed=True

    def assert_held(self):
        self._assert_accounting()
        if self._before_dispatch_check is not self._held_dispatch_check:
            raise NativeBindingError('Safe pre-dispatch checkpoint identity changed')
        if (not self.installed or self.ni.nr_rks is not self.wrapper
                or self.context.mean_field._numint is not self.ni
                or self.context.mol is not self.mol or self.context.mean_field.mol is not self.mol
                or self.context.mean_field.grids is not self.grid or self.context.mean_field.xc!=self.xc):
            raise NativeBindingError('Native source binding changed')
        _source_bytes(self.root,self.contract)

    def _dispatch(self,*values,**settings):
        self.assert_held()
        token, binding=self.active_token,self.active_context
        if token is None or binding is None:
            raise NativeBindingError('NR is unavailable outside a precharged callback')
        mol=settings.get('mol',values[0] if len(values)>0 else None)
        grid=settings.get('grids',values[1] if len(values)>1 else None)
        xc=settings.get('xc_code',values[2] if len(values)>2 else None)
        dm=settings.get('dms',values[3] if len(values)>3 else None)
        if mol is not self.mol or grid is not self.grid or xc!=self.xc or dm is None:
            raise NativeBindingError('Actual NR molecule/grid/XC differs from the frozen source')
        if _did(dm)!=binding['density_id']:
            raise NativeBindingError('Actual native D differs from the charged callback')
        options={'context_binding':binding}
        # Preserve existing callers without a hook; the worker supplies the
        # cooperative controller so requests during the intent write are caught.
        if self._before_dispatch_check is not None:options['pre_dispatch_check']=self._before_dispatch_check
        return self.accounting.native_nr(token,lambda:self.original_nr(*values,**settings),**options)


class SourceBoundRootEvaluator:
    """Exact prepared-reference adapter; cannot be supplied as an engineering fake."""

    execution_kind='SOURCE_NATIVE_DIAGNOSTIC'

    def __init__(self, *, engine, nr_binding, accounting, contract, runtime_root,
            explicit_grant=None, local_cli_execute_requested=False,
            save_snapshot=None, observe_resources=None):
        _active_contract(contract,explicit_grant=explicit_grant,
            local_cli_execute_requested=local_cli_execute_requested)
        from reference.residual_molecule import PreparedResidualReference
        if type(engine) is not PreparedResidualReference or type(nr_binding) is not NativeReferenceNRBinding:
            raise NativeBindingError('Exact source-bound prepared reference types required')
        self.root=_source_bytes(runtime_root,contract)
        if Path(inspect.getfile(PreparedResidualReference)).resolve()!=self.root/'reference/residual_molecule.py':
            raise NativeBindingError('Prepared reference loaded from another source root')
        if (nr_binding.context is not engine.context or nr_binding.accounting is not accounting
                or nr_binding.contract!=contract or engine.execution_kind!='PREPARED_MOLECULAR_DIAGNOSTIC'
                or engine.policy!='REQUIRE_EXISTING_MASKED_PROJECTOR' or engine.limit!=201
                or engine._settled or engine._used or engine.ledger or engine.electrons!=16
                or engine.overlap.shape!=(14,14)):
            raise NativeBindingError('Prepared context/path/limit or first-use binding differs')
        engine._assert_frozen();nr_binding.assert_held()
        self.engine,self.nr_binding,self.accounting=engine,nr_binding,accounting
        self.contract=copy.deepcopy(contract)
        self.initial_density_id=contract['initial_density']['density_id']
        self.scientific_execution_authorized=True
        if not callable(save_snapshot) or not callable(observe_resources):
            raise NativeBindingError('Durable capture and actual resource/deadline observers required')
        self._save_snapshot,self._observe=save_snapshot,observe_resources
        self._pending=None
        self._source_counts={'entered':0,'returned':0,'failed':0}
        self._complete_operator_ids={}

    def _held(self):
        self.nr_binding.assert_held();self.engine._assert_frozen()
        if self.engine._settled:
            raise NativeBindingError('Prepared source path is closed; no retry')

    def record_admission(self,row):
        self._held()
        return self.accounting.record_admission(row)

    def bind_candidate_callback(self,context):
        self._held()
        if self._pending is not None or not isinstance(context,dict):
            raise NativeBindingError('One explicit candidate context must be consumed once')
        ctx=dict(context)
        if (type(ctx.get('evaluation_count')) is not int or ctx['evaluation_count']<1
                or not isinstance(ctx.get('phase'),str) or not isinstance(ctx.get('density_id'),str)):
            raise NativeBindingError('Explicit evaluation/D/phase context required')
        self._pending=ctx

    def __call__(self,density,phase):
        self._held()
        ctx,self._pending=self._pending,None
        argument=np.asarray(density,dtype=np.float64).copy()
        did=_did(argument)
        if (ctx is None or ctx['density_id']!=did or ctx['phase']!=phase
                or argument.shape!=(14,14) or not np.isfinite(argument).all()
                or not np.allclose(argument,argument.T,rtol=0,atol=1e-12)):
            raise NativeBindingError('Requested D/phase does not match the consumed candidate context')
        if ctx['evaluation_count']==1 and (phase!='CURRENT_INITIAL' or did!=self.initial_density_id):
            raise NativeBindingError('First CURRENT_INITIAL must be the exact selected source D')
        # Admission failures remain distinct from charged slots and native entry.
        # Recheck before charging/dispatch so optimizer work cannot cross the
        # host stop deadline and silently begin another molecular evaluation.
        self._observe('BEFORE_CALLBACK_'+str(ctx['evaluation_count']))
        token=self.accounting.begin_callback(did,phase,candidate_context=ctx)
        binding={'slot_id':token.slot_id,'density_id':did,'path_id':'independent_reference','phase':phase}
        self.nr_binding.active_token,self.nr_binding.active_context=token,binding
        before=len(self.engine.ledger)
        try:
            self._source_counts['entered']+=1
            value=self.engine.evaluate(argument)
            self._source_counts['returned']+=1
            raw=copy.deepcopy(self.engine.last_evaluation)
            if (len(self.engine.ledger)!=before+1 or self.engine.ledger[-1]['status']!='VALIDATED'
                    or self.engine.ledger[-1]['density_id']!=did or _did(argument)!=did
                    or _did(raw['density'])!=did or value['density_id']!=did):
                raise NativeBindingError('Current raw source result belongs to another D or evaluation')
            wire=dict(value,raw_fock=raw['Fraw'],coulomb_matrix=raw['J'],exchange_matrix=raw['K'],
                xc_potential=raw['Vxc'],grid_electron_count=raw['grid_electron_count'],
                masked_metric_electron_count=raw['masked_metric_electron_count'],
                physical_metric_electron_count=raw['physical_metric_electron_count'],
                electronic_energy=raw['total_energy_hartree']-raw['components_hartree']['nuclear_repulsion'])
            from reference.occupied_space_root_native_candidate import operator_id,COMPONENTS,COUNTS
            oid=operator_id(did,wire['fock'],wire['raw_fock'],wire['total_energy'],
                {key:wire[key] for key in COMPONENTS},wire['electronic_energy'],
                {key:wire[key] for key in COUNTS})
            if did in self._complete_operator_ids and self._complete_operator_ids[did]!=oid:
                raise NativeBindingError('Same D changed the complete F/G/energy/count ledger')
            self._complete_operator_ids[did]=oid
            self._held()
            capture={'snapshot_id':'evaluation-'+str(ctx['evaluation_count']),
                'candidate_context':ctx,'slot_id':token.slot_id,'requested_density':argument.copy(),
                'requested_density_id':did,'operator_id':oid,'wire':copy.deepcopy(wire),
                'raw_reference_result':raw,'prepared_ledger_row':copy.deepcopy(self.engine.ledger[-1]),
                'scope':'SOURCE_EVALUATION_WIRE_NOT_FINAL_ENDPOINT_OR_RESEARCH_ACCEPTANCE'}
            if self._save_snapshot is not None:self._save_snapshot(capture)
            if self._observe is not None:self._observe('AFTER_CALLBACK_'+str(token.slot_id))
            self.accounting.finish_callback(token,oid,context_binding=binding)
            return wire
        except BaseException as error:
            if self._source_counts['returned']<self._source_counts['entered']:
                self._source_counts['failed']+=1
            self.accounting.fail_callback(token,error)
            raise
        finally:
            self.nr_binding.active_token=self.nr_binding.active_context=None

    def snapshot(self):
        self._held()
        return {'execution_kind':self.execution_kind,'scientific_execution_authorized':True,
            'initial_density_id':self.initial_density_id,'binding_validated':True,
            'accounting_snapshot':self.accounting.snapshot(),
            'source_evaluation_counts':dict(self._source_counts),
            'native_counter_scope':'OWNED_NUMINT_WRAPPER_ENTRY_COMPLETION_FAILURE_NOT_OS_SANDBOX',
            'same_density_repeatability_scope':'COMPLETE_OPERATOR_ID_F_G_LEDGER_AND_THREE_COUNTS',
            'Compute':False,'method_approval':False}
