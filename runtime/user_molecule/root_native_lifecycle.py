"""Cooperative stop requests; signal handlers never interrupt durable writes.

Only an explicit checkpoint raises. A native routine may finish before the next
checkpoint; this controller is not an OS kill deadline or a native-call counter.
"""
from __future__ import annotations
from contextlib import contextmanager
import math
import signal
import time


class CooperativeStopRequested(RuntimeError):
    def __init__(self, receipt):
        self.receipt = dict(receipt)
        super().__init__('Cooperative stop requested: '+receipt['stop_reason'])


class StopController:
    def __init__(self, *, deadline_epoch=None, clock=None):
        self._clock = time.time if clock is None else clock
        if not callable(self._clock): raise ValueError('An explicit clock must be callable')
        self._deadline = None
        self._deadline_armed = False
        self._requested = False
        self._reason = None
        self._signal_number = None
        self._phase = None
        self._installed = False
        if deadline_epoch is not None: self.arm_deadline(deadline_epoch)

    def arm_deadline(self, deadline_epoch):
        if type(deadline_epoch) not in (int,float) or not math.isfinite(deadline_epoch) or deadline_epoch<=0:
            raise ValueError('A finite positive absolute host stop deadline is required')
        if self._deadline_armed: raise ValueError('Stop deadline cannot be extended/replaced')
        self._deadline = float(deadline_epoch)
        self._deadline_armed = True

    def request_stop(self, reason='EXPLICIT_COOPERATIVE_STOP', *, signal_number=None):
        if not isinstance(reason,str) or not 1<=len(reason)<=128: raise ValueError('Bounded stop reason required')
        if signal_number is not None and (type(signal_number) is not int or signal_number not in (int(signal.SIGTERM),int(signal.SIGINT))):
            raise ValueError('Only SIGTERM/SIGINT stop signals are supported')
        if not self._requested:
            self._reason=reason;self._signal_number=signal_number;self._requested=True

    def _signal_handler(self, signum, _frame):
        # No I/O, clock, lock acquisition or asynchronous exception here.
        if not self._requested:
            self._reason='SIGTERM' if signum==signal.SIGTERM else 'SIGINT'
            self._signal_number=int(signum);self._requested=True

    def checkpoint(self, phase):
        if not isinstance(phase,str) or not 1<=len(phase)<=128: raise ValueError('Explicit bounded checkpoint phase required')
        self._phase=phase
        if not self._requested and self._deadline is not None:
            now=self._clock()
            if type(now) not in (int,float) or not math.isfinite(now): raise ValueError('Clock must return a finite timestamp')
            if now>=self._deadline:self.request_stop('HOST_STOP_DEADLINE_REACHED')
        if self._requested:raise CooperativeStopRequested(self.snapshot())

    def snapshot(self):
        return {'schema':'root-native-cooperative-stop-v1','stop_requested':self._requested,
            'stop_reason':self._reason,'signal_number':self._signal_number,'checkpoint_phase':self._phase,
            'deadline_epoch':self._deadline,'deadline_is_absolute_and_not_extended':True,
            'handlers_installed':self._installed,'handler_semantics':'RECORD_ONLY_NO_IO_OR_ASYNCHRONOUS_EXCEPTION',
            'native_execution_counts':'NOT_OBSERVED_BY_STOP_CONTROLLER','automatic_retry':False,'resume':False}

    @contextmanager
    def installed(self):
        if self._installed:raise ValueError('Signal controller is already installed')
        previous={}
        try:
            for signum in (signal.SIGTERM,signal.SIGINT):
                previous[signum]=signal.getsignal(signum)
                signal.signal(signum,self._signal_handler)
            self._installed=True
            yield self
        finally:
            self._installed=False
            errors=[]
            for signum,handler in reversed(list(previous.items())):
                try:signal.signal(signum,handler)
                except BaseException as error:errors.append(error)
            if errors:raise RuntimeError('Original signal handler restoration failed') from errors[0]
