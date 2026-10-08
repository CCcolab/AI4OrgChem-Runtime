"""Held Python-entry audit, with independent protocol-specific budgets.

Container limits, offline execution and read-only mounts provide the process
boundary. This audit does not claim to intercept every native/C operation.
"""
from __future__ import annotations
import copy
import functools
import json
import sys
import threading
from pathlib import Path
from . import SCF_CAPS, CUSTOM_CAPS

_ACTIVE=None
class GuardError(RuntimeError): pass

class ProtocolGuard:
    def __init__(self,case,mode,*,checkpoint=None,journal=None):
        self.case=case; self.mode=mode; self.checkpoint=checkpoint
        self.journal=Path(journal) if journal else None
        self.counts={}; self.outcomes={}; self.denied=[]; self.bindings=[]
        self.stack=[]; self.thread=None; self.active=False; self.closed=False; self.changed=[]
        self.restored=None
        self.restoration_errors=[]
        self.caps={('scf_'+k):v for k,v in SCF_CAPS[case].items()} if mode=='live' else {}
        if mode=='live':
            self.caps.update(CUSTOM_CAPS.get(case,{}))
            self.caps['newton_kernel']={'P04':14,'P05':7,'P06':4}.get(case,0)
            self.caps['stability']=1 if case=='P09' else 0
            self.caps['nr_conditional']=101 if case=='P09' else 0
            self.caps['nr_gl']=321 if case=='P08' else 0
            self.caps['nr_ordinary']={'P03':220,'P08':200,'P09':220,'P10':550}.get(case,0)
            self.caps['nr_stability']=300 if case=='P09' else 0
            self.caps['grids_build']=30 if case in ('P03','P08','P09','P10') else 0

    def _event(self,kind,label):
        if self.journal:
            with self.journal.open('a',encoding='utf-8',newline='\n') as stream:
                stream.write(json.dumps({'event':kind,'entry':label,'counts':self.counts},sort_keys=True)+'\n'); stream.flush()

    def _held(self):
        if not self.active or threading.get_ident()!=self.thread:
            self.denied.append('INACTIVE_OR_FOREIGN_THREAD'); self._event('DENIED_BEFORE_DELEGATE','GUARD_CONTEXT')
            raise GuardError('Inactive or foreign-thread guard')
        changed=[r[2] for r in self.bindings if getattr(r[0],r[1],None) is not r[6]]
        if changed:
            self.changed.extend(changed); raise GuardError('Changed entry guards: '+str(changed))

    def _deny(self,label):
        self.denied.append(label); self._event('DENIED_BEFORE_DELEGATE',label)
        raise GuardError('Outside fixed protocol scope: '+label)

    def _invoke(self,label,original,args,kwargs,counter=None,phase=None):
        self._held()
        if self.checkpoint: self.checkpoint('PROTOCOL_BEFORE_'+label)
        self._held()
        if counter is not None:
            if self.counts.get(counter,0)>=self.caps.get(counter,0): self._deny(label)
            self.counts[counter]=self.counts.get(counter,0)+1
            self.outcomes.setdefault(counter,{'returned':0,'failed':0})
        self._event('OWNED_WRAPPER_ENTERED',label)
        if phase: self.stack.append(phase)
        try:
            result=original(*args,**kwargs)
            if counter: self.outcomes[counter]['returned']+=1
            self._event('DELEGATE_RETURNED',label)
        except BaseException:
            if counter: self.outcomes[counter]['failed']+=1
            self._event('DELEGATE_FAILED',label); raise
        finally:
            if phase: self.stack.pop()
        if self.checkpoint: self.checkpoint('PROTOCOL_AFTER_'+label)
        self._held()
        return result

    def _wrapper(self,label,original,kind):
        @functools.wraps(original)
        def wrapped(*args,**kwargs):
            if kind=='deny':
                self._held(); self._deny(label)
            if kind=='hf':
                instance=args[0]
                from pyscf.dft.rks import KohnShamDFT
                from pyscf.scf.uhf import UHF
                from pyscf.scf.hf import RHF
                if isinstance(instance,KohnShamDFT): category='RKS' if isinstance(instance,RHF) else 'UNSUPPORTED_DFT'
                elif isinstance(instance,UHF): category='UHF'
                elif isinstance(instance,RHF): category='RHF'
                else: category='UNSUPPORTED_HF'
                return self._invoke(label,original,args,kwargs,'scf_'+category,'ordinary')
            if kind=='nr':
                phase=('conditional' if 'run_p09_conditional_rks' in self.stack else
                       'gl' if 'run_gl2014_scf' in self.stack else
                       'stability' if 'stability' in self.stack else 'ordinary')
                return self._invoke(label,original,args,kwargs,'nr_'+phase)
            return self._invoke(label,original,args,kwargs,kind,kind)
        return wrapped

    def __enter__(self):
        global _ACTIVE
        if _ACTIVE is not None or self.closed: raise GuardError('Nested or reused guard')
        from pyscf.scf import hf
        from pyscf.dft import numint,gen_grid,rks,uks,roks
        from pyscf.lo import boys,pipek
        from pyscf import gto
        targets=[(hf,'kernel','hf.kernel','hf'), (numint,'nr_rks','numint.nr_rks','nr'),
                 (numint,'nr_uks','numint.nr_uks','deny'),(numint.NumInt,'nr_uks','NumInt.nr_uks','deny'),
                 (gen_grid.Grids,'build','Grids.build','grids_build'),
                 (rks.RKS,'stability','RKS.stability','stability'),
                 (uks.UKS,'kernel','UKS.kernel','deny'),(roks.ROKS,'kernel','ROKS.kernel','deny'),
                 (boys.Boys,'kernel','Boys.kernel','deny'),(pipek.PipekMezey,'kernel','PM.kernel','deny')]
        from pyscf.soscf import newton_ah
        if hasattr(newton_ah,'kernel'): targets.append((newton_ah,'kernel','newton_ah.kernel','newton_kernel'))
        # NumInt methods may hold a direct alias of the module function. Capture
        # aliases before mutation and count only the deepest original dispatch.
        module_nr=numint.nr_rks
        if numint.NumInt.nr_rks is module_nr:
            targets.append((numint.NumInt,'nr_rks','NumInt.nr_rks','nr'))
        if self.mode!='live':
            for name in ('intor','intor_by_shell','energy_nuc'):
                targets.append((gto.Mole,name,'Mole.'+name,'deny'))
        # Source custom iterators are outside SCF.kernel. All already loaded
        # aliases of these function objects are held, including driver aliases.
        custom=set().union(*(set(v) for v in CUSTOM_CAPS.values()))
        source_functions={}
        for module in list(sys.modules.values()):
            namespace=getattr(module,'__dict__',{})
            filename=namespace.get('__file__','') or ''
            if 'reference/protocol_cases/source_tree' not in str(filename).replace('\\','/'): continue
            for name,value in list(namespace.items()):
                if callable(value) and getattr(value,'__name__','') in custom:
                    source_functions[id(value)]=getattr(value,'__name__')
        for module in list(sys.modules.values()):
            namespace=getattr(module,'__dict__',{})
            for name,value in list(namespace.items()):
                if id(value) in source_functions:
                    kind=source_functions[id(value)]
                    targets.append((module,name,getattr(module,'__name__','')+'.'+name,kind))
        captured=[]; seen=set()
        for owner,name,label,kind in targets:
            key=(id(owner),name)
            if key in seen: continue
            seen.add(key); original=getattr(owner,name,None)
            if not callable(original): raise GuardError('Required API missing: '+label)
            captured.append((owner,name,label,kind,original,name in vars(owner),vars(owner).get(name)))
        self.thread=threading.get_ident(); self.active=True; _ACTIVE=self
        try:
            for owner,name,label,kind,original,owned,direct in captured:
                wrapper=self._wrapper(label,original,kind)
                setattr(owner,name,wrapper)
                self.bindings.append((owner,name,label,owned,direct,original,wrapper))
        except BaseException:
            self.__exit__(None,None,None); raise
        self._event('GUARD_INSTALLED','all')
        return self

    def __exit__(self,*error):
        global _ACTIVE
        try: self._held()
        finally:
            try:
                for owner,name,label,owned,direct,original,wrapper in reversed(self.bindings):
                    try:
                        if owned: setattr(owner,name,direct)
                        else: delattr(owner,name)
                    except BaseException as failure:
                        self.restoration_errors.append(label+': '+str(failure))
            finally:
                self.active=False; self.closed=True; _ACTIVE=None
            self.restored=all(getattr(r[0],r[1],None) is r[5] and (r[1] in vars(r[0]))==r[3] for r in self.bindings)
            self._event('GUARD_CLOSED','all')
        if self.restoration_errors: raise GuardError('Restoration failed: '+str(self.restoration_errors))
        return False

    def snapshot(self):
        if self.active: self._held()
        return {'schema':'protocol-case-native-audit-v1','case':self.case,'mode':self.mode,
                'status':'PASS' if self.bindings and not self.denied and not self.changed and not self.restoration_errors and self.restored is not False else 'FAIL',
                'counts':copy.deepcopy(self.counts),'caps':self.caps,'outcomes':copy.deepcopy(self.outcomes),
                'denied':list(self.denied),'changed':list(self.changed),'closed':self.closed,
                'restored_attributes_intact':self.restored,'restoration_errors':list(self.restoration_errors),'held_entries':[r[2] for r in self.bindings],
                'scope':'OBSERVED_PYTHON_DISPATCH_NOT_ALL_C_NATIVE_OPERATIONS_OR_CONVERGENCE',
                'missing_count_is_observed_zero_only_when_guard_closed':self.closed}
