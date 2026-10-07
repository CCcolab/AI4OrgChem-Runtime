"""Source binding rejection/dispatch witnesses; no molecular calls."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.user_molecule import root_native_binding as binding
from runtime.user_molecule.occupied_space_root_native_contract import ExecutionContractError
from test_root_native_contract import contract_fixture,future_fixture


class RootNativeBindingTests(unittest.TestCase):
    def test_inactive_valid_contract_rejects_before_source_or_accounting_access(self):
        contract=contract_fixture()
        with self.assertRaises(binding.NativeBindingError):
            binding.NativeReferenceNRBinding(context=None,accounting=None,contract=contract,runtime_root=None)
        with self.assertRaises(binding.NativeBindingError):
            binding.SourceBoundRootEvaluator(engine=None,nr_binding=None,accounting=None,contract=contract,runtime_root=None)

    def test_declared_true_contract_without_independent_grant_cannot_bind(self):
        contract,_=future_fixture()
        with self.assertRaises(ExecutionContractError):
            binding.NativeReferenceNRBinding(context=None,accounting=None,contract=contract,runtime_root=None)

    def test_source_contract_is_not_promoted_by_a_caller_execute_flag(self):
        with self.assertRaises(ExecutionContractError):
            binding.NativeReferenceNRBinding(context=None,accounting=None,contract=contract_fixture(),runtime_root=None,
                explicit_grant={},local_cli_execute_requested=True)

    def boundary_double(self):
        # Does not call __init__, register a real grant or access any PySCF API.
        obj=object.__new__(binding.NativeReferenceNRBinding)
        obj.assert_held=lambda:None
        obj.mol,obj.grid,obj.xc=object(),object(),'B3LYPG'
        obj.active_token=object()
        obj._before_dispatch_check=None
        obj.active_context={'slot_id':1,'density_id':'a'*64,'path_id':'independent_reference','phase':'CURRENT_INITIAL'}
        obj.calls=[]
        obj.original_nr=lambda *args,**kwargs:obj.calls.append((args,kwargs)) or ('test-only',)
        class Account:
            def native_nr(self,token,callback,*,context_binding):
                self.seen=(token,copy.deepcopy(context_binding));return callback()
        obj.accounting=Account()
        return obj

    def test_native_boundary_refuses_unowned_molecule_grid_xc_and_density_without_delegate(self):
        obj=self.boundary_double()
        with patch.object(binding,'_did',return_value='a'*64):
            for args in [(object(),obj.grid,obj.xc,object()),(obj.mol,object(),obj.xc,object()),
                         (obj.mol,obj.grid,'OTHER_XC',object()),(obj.mol,obj.grid,obj.xc,None)]:
                with self.subTest(args=args),self.assertRaises(binding.NativeBindingError):obj._dispatch(*args)
        with patch.object(binding,'_did',return_value='b'*64),self.assertRaises(binding.NativeBindingError):
            obj._dispatch(obj.mol,obj.grid,obj.xc,object())
        self.assertEqual(obj.calls,[])

    def test_native_boundary_without_active_token_refuses_before_delegate(self):
        obj=self.boundary_double();obj.active_token=None
        with self.assertRaises(binding.NativeBindingError):obj._dispatch(obj.mol,obj.grid,obj.xc,object())
        self.assertEqual(obj.calls,[])

    def test_changed_pre_dispatch_check_is_refused_before_source_or_native_call(self):
        obj=object.__new__(binding.NativeReferenceNRBinding)
        obj._assert_accounting=lambda:None
        obj._held_dispatch_check=lambda:None;obj._before_dispatch_check=lambda:None
        with patch.object(binding,'_source_bytes') as verify,self.assertRaisesRegex(binding.NativeBindingError,'checkpoint identity'):
            obj.assert_held()
        verify.assert_not_called()

    def test_captured_original_nr_can_be_installed_over_the_held_class_guard_once(self):
        obj=object.__new__(binding.NativeReferenceNRBinding)
        guard=lambda:None;original=lambda:None;wrapper=lambda:None
        obj.ni=SimpleNamespace(nr_rks=guard);obj._preinstall_nr=guard
        obj.original_nr=original;obj.wrapper=wrapper;obj.installed=False
        obj.install()
        self.assertIs(obj.ni.nr_rks,wrapper)
        with self.assertRaises(binding.NativeBindingError):obj.install()

    def test_changed_preinstall_nr_refused_even_if_original_function_is_retained(self):
        obj=object.__new__(binding.NativeReferenceNRBinding)
        obj.ni=SimpleNamespace(nr_rks=lambda:None);obj._preinstall_nr=lambda:None
        obj.original_nr=lambda:None;obj.wrapper=lambda:None;obj.installed=False
        with self.assertRaises(binding.NativeBindingError):obj.install()
        self.assertFalse(obj.installed)

    def test_native_boundary_passes_exact_owned_arguments_only_to_counted_test_delegate(self):
        obj=self.boundary_double();dm=object()
        with patch.object(binding,'_did',return_value='a'*64):
            self.assertEqual(obj._dispatch(obj.mol,obj.grid,obj.xc,dm,hermi=1),('test-only',))
        self.assertEqual(len(obj.calls),1)
        self.assertIs(obj.calls[0][0][3],dm)
        self.assertIs(obj.accounting.seen[0],obj.active_token)
        self.assertEqual(obj.accounting.seen[1],obj.active_context)

    def test_frozen_candidate_context_can_be_consumed_without_deepcopy_mutation(self):
        from reference.occupied_space_root_native_candidate import FrozenRecord
        obj=object.__new__(binding.SourceBoundRootEvaluator);obj._held=lambda:None;obj._pending=None
        ctx=FrozenRecord({'evaluation_count':1,'density_id':'a'*64,'phase':'CURRENT_INITIAL',
            'admission_group_id':None,'chart':None,'fd_sample':None,
            'base_snapshot_id':None,'base_density_id':None,'base_operator_id':None})
        obj.bind_candidate_callback(ctx)
        self.assertEqual(obj._pending,dict(ctx))
        with self.assertRaises(binding.NativeBindingError):obj.bind_candidate_callback(ctx)
        self.assertEqual(ctx['evaluation_count'],1)

    def test_worker_cli_needs_explicit_mode_and_cannot_mix_prepare_execute(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('root_native_worker_cli',root/'scripts/diagnose-user-molecule-root-native-worker.py')
        worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
        for argv in ([],['--prepare-only','--execute']):
            with self.subTest(argv=argv),self.assertRaises(SystemExit):worker.argument_parser().parse_args(argv)
        args=worker.argument_parser().parse_args(['--prepare-only'])
        self.assertTrue(args.prepare_only);self.assertFalse(args.execute);self.assertIsNone(args.grant_file)

    def test_pre_callback_resource_or_deadline_refusal_has_no_slot_or_native_entry(self):
        import numpy as np
        from unittest.mock import Mock
        density=np.zeros((14,14));did=binding._did(density)
        for reason in ('stop deadline','resource floor'):
            obj=object.__new__(binding.SourceBoundRootEvaluator)
            obj._held=lambda:None;obj.initial_density_id=did
            obj._pending={'evaluation_count':1,'density_id':did,'phase':'CURRENT_INITIAL'}
            obj._observe=Mock(side_effect=RuntimeError(reason))
            obj.accounting=SimpleNamespace(begin_callback=Mock())
            obj.engine=SimpleNamespace(evaluate=Mock())
            with self.subTest(reason=reason),self.assertRaisesRegex(RuntimeError,reason):
                obj(density,'CURRENT_INITIAL')
            obj._observe.assert_called_once_with('BEFORE_CALLBACK_1')
            obj.accounting.begin_callback.assert_not_called()
            obj.engine.evaluate.assert_not_called()
            self.assertIsNone(obj._pending)


class RootNativeWorkerCleanupTests(unittest.TestCase):
    """Close-only faults on toy journals, never importing/running molecular F."""
    def worker(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('native_worker_cleanup_only',root/'scripts/diagnose-user-molecule-root-native-worker.py')
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

    def journal(self, root, name):
        from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
        return ConditionalCallbackBudget(path=root/(name+'.json'),batch_id=name,
            identity={'mode':'ENGINEERING_SIMULATED_NATIVE','execution_kind':'ENGINEERING_SIMULATED_NATIVE',
                'scientific_execution_authorized':False,'geometry_sha256':'a'*64,'profile_sha256':'b'*64,'dependencies_sha256':'c'*64},
            path_limits={'independent_reference':201},total_limit=201)

    def test_accounting_constructor_failure_closes_created_journal_without_counter_fabrication(self):
        import json,tempfile
        worker=self.worker()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);book=self.journal(root,'constructor-fault')
            book.charge('independent_reference','d'*64,'CURRENT_INITIAL')
            result=worker.close_active_initialization(root,journal=book,accounting=None,reference=None,reason='ACCOUNTING_CONSTRUCTOR_REFUSED_NO_RETRY')
            self.assertIsNone(result)
            value=book.snapshot()
            self.assertEqual(value['charged_slots'],1);self.assertEqual(value['failed_slots'],1)
            self.assertEqual(value['paths']['independent_reference']['state'],'CLOSED')
            self.assertEqual(json.loads((root/'native-accounting-unavailable.json').read_bytes())['native_counts'],'UNKNOWN_NOT_REPLACED_BY_ZERO')
            with self.assertRaises(ValueError):book.charge('independent_reference','e'*64,'OPTIMIZER_BASE')

    def test_binding_reference_recipe_and_evaluator_initialization_faults_close_empty_owned_accounting(self):
        import tempfile
        from runtime.user_molecule.root_native_accounting import RootNativeAccounting
        worker=self.worker()
        for stage in ('NR_BINDING_CONSTRUCTION','PREPARED_REFERENCE_CONSTRUCTION','SEED_RECIPE_ADMISSION','SOURCE_EVALUATOR_CONSTRUCTION'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);book=self.journal(root,'initialization-fault')
                account=RootNativeAccounting(root/'accounting',book)
                reference=SimpleNamespace(_used=False,_settled=False) if stage in ('SEED_RECIPE_ADMISSION','SOURCE_EVALUATOR_CONSTRUCTION') else None
                result=worker.close_active_initialization(root,journal=book,accounting=account,reference=reference,reason=stage+'_REFUSED_NO_RETRY')
                self.assertTrue(result['closed']);self.assertEqual(result['nr_dispatch_counts']['entered'],0)
                self.assertEqual(book.snapshot()['charged_slots'],0)
                self.assertEqual(book.snapshot()['paths']['independent_reference']['state'],'CLOSED')
                if reference is not None:self.assertTrue(reference._used and reference._settled)

    def test_accounting_close_failure_still_settles_pending_journal_and_reference_then_fails(self):
        import json,tempfile
        worker=self.worker()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);book=self.journal(root,'close-fault')
            book.charge('independent_reference','d'*64,'CURRENT_INITIAL')
            account=SimpleNamespace(close=lambda reason:(_ for _ in ()).throw(OSError('toy receipt failure')))
            reference=SimpleNamespace(_used=False,_settled=False)
            with self.assertRaises(RuntimeError):
                worker.close_active_initialization(root,journal=book,accounting=account,reference=reference,reason='INITIALIZATION_FAILED_NO_RETRY')
            self.assertTrue(reference._used and reference._settled)
            self.assertEqual(book.snapshot()['pending_slots'],0);self.assertEqual(book.snapshot()['failed_slots'],1)
            self.assertEqual(book.snapshot()['paths']['independent_reference']['state'],'CLOSED')
            evidence=json.loads((root/'active-cleanup-errors.json').read_bytes())
            self.assertEqual(evidence['status'],'NOT_QUALIFIED');self.assertFalse(evidence['automatic_retry'])

    def test_worker_finally_spans_all_active_constructors_and_prepare_remains_outside_closure(self):
        import ast
        source=(Path(__file__).resolve().parents[1]/'scripts/diagnose-user-molecule-root-native-worker.py').read_text()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='run_worker')
        needed={'ConditionalCallbackBudget','RootNativeAccounting','NativeReferenceNRBinding','PreparedResidualReference',
            'preflight_occupied_space_response','SourceBoundRootEvaluator','solve_occupied_space_root_native_candidate'}
        def calls(nodes):
            return {node.func.id for statement in nodes for node in ast.walk(statement)
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)}
        boundary=next(node for node in function.body if isinstance(node,ast.Try) and needed<=calls(node.body))
        self.assertIn('close_active_initialization',calls(boundary.finalbody))
        gate=next(node for node in boundary.finalbody if isinstance(node,ast.If)
            and ast.unparse(node.test)=='args.execute')
        self.assertIn('close_active_initialization',calls(gate.body))
        inactive=next(node for node in boundary.body if isinstance(node,ast.If) and ast.unparse(node.test)=='not args.execute')
        self.assertNotIn('ConditionalCallbackBudget',calls(inactive.body))
        self.assertNotIn('RootNativeAccounting',calls(inactive.body))


if __name__=='__main__':unittest.main()
