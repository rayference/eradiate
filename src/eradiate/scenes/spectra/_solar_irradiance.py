from __future__ import annotations

import datetime
import typing as t
import warnings

import attrs
import numpy as np
import pint
import xarray as xr

from ._core import Spectrum
from ..core import KernelDict
from ... import converters, data, validators
from ...attrs import documented, parse_docs
from ...ckd import Bindex
from ...contexts import KernelDictContext
from ...units import PhysicalQuantity, to_quantity
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg


def _datetime_converter(x: t.Any):
    if x is not None:
        try:
            import dateutil
        except ModuleNotFoundError:
            warnings.warn(
                "To use the date-based Solar irradiance scaling feature, you "
                "must install dateutil.\n"
                "See instructions on https://dateutil.readthedocs.io/#installation."
            )
            raise

        try:
            import astropy
        except ModuleNotFoundError:
            warnings.warn(
                "To use the date-based Solar irradiance scaling feature, you "
                "must install astropy.\n"
                "See instructions on https://www.astropy.org/."
            )
            raise

        return dateutil.parser.parse(x)


@parse_docs
@attrs.frozen
class SolarIrradianceSpectrum(Spectrum):
    """
    Solar irradiance spectrum [``solar_irradiance``].

    This scene element produces the scene dictionary required to
    instantiate a kernel plugin using the Sun irradiance spectrum. The data set
    used by this element is controlled by the ``dataset`` field.

    See Also
    --------

    :ref:`Solar irradiance spectrum data guide <sec-user_guide-data-solar_irradiance>`

    Notes
    ------

    * The spectral range of the data sets shipped can vary and an attempt for
      use outside the supported spectral range will raise a
      :class:`ValueError` upon calling :meth:`kernel_dict`.

    * When the ``datetime`` field is set, the spectrum is automatically scaled
      to account for the seasonal variations of the Earth-Sun distance using the
      ephemeris of :func:`astropy.coordinates.get_sun`.
      The dataset is assumed to be normalised to an Earth-Sun distance of 1 AU.
      This will trigger the import of :mod:`astropy.coordinates` and consume a
      significant amount of memory (150 MiB with astropy v5.1).

    * The ``scale`` field can be used to apply additional arbitrary scaling.
      It is mostly used for debugging purposes. It can also be used to rescale
      user-defined spectra normalised at an Earth-Sun distance different from
      1 AU.

    * The evaluation method depends on the active mode:

      * in ``mono_*`` modes, the spectrum is evaluated at the spectral context
        wavelength;
      * in ``ckd_*`` modes, the spectrum is evaluated as the average value over
        the spectral context bin (the integral is computed using a trapezoid
        rule).

    * The produced kernel dictionary automatically adjusts its irradiance units
      depending on the selected kernel default units.
    """

    # --------------------------------------------------------------------------
    #                           Fields and properties
    # --------------------------------------------------------------------------

    quantity: PhysicalQuantity = attrs.field(
        default=PhysicalQuantity.IRRADIANCE, init=False, repr=False
    )

    dataset: xr.Dataset = documented(
        attrs.field(
            default="coddington_2021-1_nm",
            converter=converters.to_dataset(
                load_from_id=lambda x: data.load_dataset(
                    f"spectra/solar_irradiance/{x}.nc",
                )
            ),
            validator=attrs.validators.instance_of(xr.Dataset),
        ),
        doc="Solar irradiance spectrum dataset. "
        "If a xarray.Dataset is passed, the dataset is used as is "
        "(refer to the data guide for the format requirements of this dataset)."
        "If a path is passed, the converter tries to open the corresponding "
        "file on the hard drive; should that fail, it queries the Eradiate data"
        "store with that path."
        "If a string is passed, it is interpreted as a Solar irradiance "
        "spectrum identifier "
        "(see :ref:`sec-user_guide-data-solar_irradiance` for the list); ",
        type="Dataset",
        init_type="Dataset or str or path-like, optional",
        default='"coddington_2021-1_nm"',
    )

    scale: float = documented(
        attrs.field(default=1.0, converter=float, validator=validators.is_positive),
        doc="Arbitrary scaling factor. This scaling factor is applied in "
        "addition to the datetime-based scaling controlled by the *datetime* "
        "parameter.",
        type="float or datetime",
        init_type="float or datetime or str",
        default="1.0",
    )

    datetime: t.Optional[datetime.datetime] = documented(
        attrs.field(
            default=None,
            converter=_datetime_converter,
        ),
        type="datetime or None",
        init_type="datetime or str, optional",
        doc="Date for which the spectrum is to be evaluated. An ISO "
        "string can be passed and will be interpreted by "
        ":meth:`dateutil.parser.parse`. This parameter scales the irradiance "
        "spectrum to account for the seasonal variation of the Earth-Sun "
        "distance. This scaling is applied in addition to the arbitrary "
        "scaling controlled by the *scale* parameter.",
    )

    def _scale_earth_sun_distance(self) -> float:
        """
        Compute scaling factor applied to the irradiance spectrum based on the
        Earth-Sun distance.
        """
        # Note: We assume that the loaded dataset is for a reference
        # Earth-Sun distance of 1 AU
        if self.datetime is None:
            return 1.0

        else:
            # Note: astropy.coordinates consumes a significant amount of memory
            # (150 MiB with astropy v5.1). The import is therefore optional for
            # performance.
            import astropy.coordinates
            import astropy.time
            import astropy.units

            # The irradiance scales as the inverse of d**2, where d is the
            # Earth-Sun distance divided by the AU (reference distance for all
            # Solar irradiance spectra in Eradiate).
            return (
                float(
                    astropy.units.au
                    / astropy.coordinates.get_sun(
                        astropy.time.Time(self.datetime)
                    ).distance
                )
                ** 2
            )

    def eval_mono(self, w: pint.Quantity) -> pint.Quantity:
        # Inherit docstring

        w_units = ureg(self.dataset.ssi.w.attrs["units"])
        irradiance = to_quantity(
            self.dataset.ssi.interp(w=w.m_as(w_units), method="linear")
        )

        # Raise if out of bounds or ill-formed dataset
        if np.any(np.isnan(irradiance.magnitude)):
            raise ValueError("interpolation of solar irradiance dataset returned nan")

        return irradiance * self.scale * self._scale_earth_sun_distance()

    def eval_ckd(self, *bindexes: Bindex) -> pint.Quantity:
        # Inherit docstring
        # Note: Spectrum is averaged over the spectral bin

        result = np.zeros((len(bindexes),))
        wavelength_units = ucc.get("wavelength")
        quantity_units = ucc.get(self.quantity)

        for i_bindex, bindex in enumerate(bindexes):
            bin = bindex.bin

            wmin_m = bin.wmin.m_as(wavelength_units)
            wmax_m = bin.wmax.m_as(wavelength_units)

            # -- Collect relevant spectral coordinate values
            w_m = ureg.convert(
                self.dataset.ssi.w.values,
                self.dataset.ssi.w.attrs["units"],
                wavelength_units,
            )
            w = (
                np.hstack(
                    (
                        [wmin_m],
                        w_m[np.where(np.logical_and(wmin_m < w_m, w_m < wmax_m))[0]],
                        [wmax_m],
                    )
                )
                * wavelength_units
            )

            # -- Evaluate spectrum at wavelengths
            interp = self.eval_mono(w)

            # -- Average spectrum on bin extent
            integral = np.trapz(interp, w)
            result[i_bindex] = (integral / bin.width).m_as(quantity_units)

        return result * quantity_units

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        # Apply scaling, build kernel dict
        value = float(self.eval(ctx.spectral_ctx).m_as(uck.get("irradiance")))
        return KernelDict({"spectrum": {"type": "uniform", "value": value}})

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        raise NotImplementedError
