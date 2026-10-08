"""Reuse the tested dispatch limiter, permitting one RHF and no localization."""
from runtime.registered_cases.native_guard import RegisteredNativeGuard

class MolecularNativeGuard(RegisteredNativeGuard):
    def __init__(self,*,engine_modules=None,stop_checkpoint=None):
        # This is the shared ordinary-operation budget, not a P01 geometry/protocol.
        super().__init__('p01-orbital-density',engine_modules=engine_modules,stop_checkpoint=stop_checkpoint)
    def _targets(self,modules):
        return [(owner,name,label,'deny' if kind in ('boys_kernel','pipek_mezey_kernel','lo') else kind)
                for owner,name,label,kind in super()._targets(modules)]
    def snapshot(self):
        value=super().snapshot()
        value.update(schema='molecular-service-native-guard-v1',task='single-point',
                     base_operation_limiter='RegisteredNativeGuard; geometry/condition protocol not reused',
                     scope='ONE_ORDINARY_RHF_NO_LOCALIZATION_OR_CONDITIONAL_DFT_GRID_NR',
                     p01_ordinary_integral_JK_energy_calls_allowed_not_individually_counted=False,
                     ordinary_integral_JK_energy_calls_allowed_not_individually_counted=True)
        return value
