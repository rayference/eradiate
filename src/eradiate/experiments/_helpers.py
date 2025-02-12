from __future__ import annotations

import typing as t

from ..contexts import KernelDictContext
from ..scenes.atmosphere import Atmosphere
from ..scenes.bsdfs import BSDF, bsdf_factory
from ..scenes.measure import Measure, MultiRadiancemeterMeasure
from ..scenes.measure._distant import DistantMeasure
from ..scenes.shapes import RectangleShape
from ..scenes.surface import BasicSurface, Surface, surface_factory

# ------------------------------------------------------------------------------
#                             Experiment helpers
# ------------------------------------------------------------------------------


def measure_inside_atmosphere(
    atmosphere: Atmosphere, measure: Measure, ctx: KernelDictContext
) -> bool:
    """
    Evaluate whether a sensor is placed within an atmosphere.

    Raises a ValueError if called with a :class:`.MultiRadiancemeterMeasure`
    with origins both inside and outside the atmosphere.
    """
    if atmosphere is None:
        return False

    shape = atmosphere.eval_shape(ctx)

    if isinstance(measure, MultiRadiancemeterMeasure):
        inside = shape.contains(measure.origins)

        if all(inside):
            return True
        elif not any(inside):
            return False
        else:
            raise ValueError(
                "Inconsistent placement of MultiRadiancemeterMeasure origins. "
                "Origins must lie either all inside or all outside of the "
                "atmosphere."
            )

    elif isinstance(measure, DistantMeasure):
        # Note: This will break if the user makes something weird such as using
        # a large offset value which would put some origins outside and others
        # inside the atmosphere shape
        return not measure.is_distant()

    else:
        # Note: This will likely break if a new measure type is added
        return shape.contains(measure.origin)


def _surface_converter(value: t.Union[dict, Surface, BSDF]) -> Surface:
    """
    Attempt to convert the surface specification into a surface type.

    Surfaces can be defined purely by their BSDF, in which case Eradiate will
    define a rectangular surface and attach that BSDF to it.
    """
    if isinstance(value, dict):
        try:
            # First, attempt conversion to BSDF
            value = bsdf_factory.convert(value)
        except TypeError:
            # If this doesn't work, attempt conversion to Surface
            return surface_factory.convert(value)

    # If we make it to this point, it means that dict conversion has been
    # performed with success
    if isinstance(value, BSDF):
        return BasicSurface(
            shape=RectangleShape(),
            bsdf=value,
        )

    return value
