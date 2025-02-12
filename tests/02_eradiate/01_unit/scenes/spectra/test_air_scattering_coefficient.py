import mitsuba as mi
import numpy as np

import eradiate
from eradiate import unit_registry as ureg
from eradiate.contexts import KernelDictContext
from eradiate.scenes.spectra import AirScatteringCoefficientSpectrum


def test_air_scattering_coefficient(modes_all_mono_ckd):
    ctx = KernelDictContext()

    # We can instantiate the class
    s = AirScatteringCoefficientSpectrum()

    # The spectrum evaluates correctly (reference values computed manually)
    if eradiate.mode().is_mono:
        expected = ureg.Quantity(0.0114934, "km^-1")

    elif eradiate.mode().is_ckd:
        expected = ureg.Quantity(0.0114968, "km^-1")

    else:
        assert False

    value = s.eval(ctx.spectral_ctx)
    assert np.allclose(value, expected)

    # The associated kernel dict is correctly formed and can be loaded
    assert isinstance(s.kernel_dict(ctx=ctx).load(), mi.Texture)
