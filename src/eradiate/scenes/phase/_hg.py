from __future__ import annotations

import attrs

import eradiate

from ._core import PhaseFunction
from ..core import KernelDict
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import documented, parse_docs
from ...contexts import KernelDictContext
from ...exceptions import UnsupportedModeError
from ...util.misc import onedict_value


@parse_docs
@attrs.define
class HenyeyGreensteinPhaseFunction(PhaseFunction):
    """
    Henyey-Greenstein phase function [``hg``].

    The Henyey-Greenstein phase function :cite:`Henyey1941Diffuse` models
    scattering in an isotropic medium. The scattering pattern is controlled by
    its :math:`g` parameter, which is equal to the phase function's asymmetry
    parameter (the mean cosine of the scattering angle): a positive (resp.
    negative) value corresponds to predominant forward (resp. backward)
    scattering.
    """

    g: Spectrum = documented(
        attrs.field(
            default=0.0,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Asymmetry parameter. Must be dimensionless. "
        "Must be in :math:`]-1, 1[`.",
        type=":class:`.Spectrum`",
        init_type=":class:`.Spectrum` or dict or float, optional",
        default="0.0",
    )

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        if eradiate.mode().is_mono:
            # TODO: This is a workaround until the hg plugin accepts spectra for
            #  its g parameter
            g = float(onedict_value(self.g.kernel_dict(ctx=ctx))["value"])
            return KernelDict(
                {
                    self.id: {
                        "type": "hg",
                        "g": g,
                    }
                }
            )
        else:
            raise UnsupportedModeError(supported="monochromatic")
