from __future__ import annotations

import typing as t

import attrs
import numpy as np
import pint
import xarray as xr

from ._core import RadProfile, make_dataset, rad_profile_factory
from ._util_mono import get_us76_u86_4_spectrum_filename
from .absorption import compute_sigma_a
from .rayleigh import compute_sigma_s_air
from .. import data
from .._mode import UnsupportedModeError
from ..attrs import documented, parse_docs
from ..ckd import Bindex
from ..thermoprops import us76
from ..units import to_quantity
from ..units import unit_registry as ureg


def _convert_thermoprops_us76_approx(
    value: t.Union[t.MutableMapping, xr.Dataset]
) -> xr.Dataset:
    if isinstance(value, dict):
        return us76.make_profile(**value)
    else:
        return value


@parse_docs
@attrs.define
class US76ApproxRadProfile(RadProfile):
    """
    Radiative properties profile approximately corresponding to an
    atmospheric profile based on the original U.S. Standard Atmosphere 1976
    atmosphere model.

    Warnings
    --------
    This class does not support ``ckd`` modes.

    Notes
    -----
    * The :mod:`~eradiate.thermoprops.us76` module implements the original *U.S.
      Standard Atmosphere 1976* atmosphere model, as defined by the
      :cite:`NASA1976USStandardAtmosphere` technical report.
      In the original atmosphere model, the gases are assumed well-mixed below
      the altitude of 86 kilometers.
      In the present radiative properties profile, the absorption coefficient is
      computed using the ``spectra-us76_u86_4`` absorption dataset.
      This dataset provides the absorption cross section of a specific mixture
      of N2, O2, CO2 and CH4, the mixing ratio of which are those defined by the
      *U.S. Standard Atmosphere 1976* model for the region of altitudes under
      86 kilometers, where these four gas species are well-mixed.
      As a result, the dataset is representative of the *U.S. Standard Atmosphere
      1976* model only below 86 kilometers.
      Since the atmosphere is typically a hundred kilometers high or more in
      radiative transfer applications, and in order to make the radiative
      properties profile reach these altitudes, the absorption coefficient
      is nevertheless computed using the ``spectra-us76_u86_4`` dataset.
      This approximation assumes that the absorption coefficient does not vary
      much whether the mixing ratios of the absorbing gas mixture are those
      below or above 86 km.

    * Furthermore, the *U.S. Standard Atmosphere 1976* model includes other gas
      species than N2, O2, CO2 and CH4.
      They are: Ar, He, Ne, Kr, H, O, Xe, He and H2.
      All these species except H2 are absent from the
      `HITRAN <https://hitran.org/>`_ spectroscopic database.
      Since the absorption datasets are computed using HITRAN, the atomic species
      could not be included in ``spectra-us76_u86_4``.
      H2 was mistakenly forgotten and should be added to the dataset in a future
      revision.

    * We refer to the *U.S. Standard Atmosphere 1976* atmosphere model as the
      model defined by the set of assumptions and equations in part 1 of the
      report, and "numerically" illustrated by the extensive tables in part
      4 of the report.
      In particular, the part 3, entitled *Trace constituents*, which
      provides rough estimates and discussions on the amounts of trace
      constituents such as ozone, water vapor, nitrous oxide, methane, and so
      on, is not considered as part of the *U.S. Standard Atmosphere 1976*
      atmosphere model because it does not clearly defines the concentration
      values of all trace constituents at all altitudes, neither does it
      provide a way to compute them.

    * It seems that the identifier "US76" is commonly used to refer to a
      standard atmospheric profile used in radiative transfer applications.
      However, there appears to be some confusion around the definition of
      that standard atmospheric profile.
      In our understanding, what is called the "US76 standard atmospheric
      profile", or "US76" in short, **is not the U.S. Standard Atmosphere
      1976 atmosphere model** but instead the so-called "U.S. Standard (1976)
      atmospheric constituent profile model" in a AFGL technical report
      entitled *AFGL Atmospheric Constituent Profiles (0-120km)* and
      published in 1986 by Anderson et al
      :cite:`Anderson1986AtmosphericConstituentProfiles`.
      Although the "U.S. Standard (1976) atmospheric profile model" of the
      AFGL's report is based on the *U.S. Standard Atmosphere* 1976 atmosphere
      model (hence the name), it is significantly different when it comes
      about the gas species concentration profiles.
      Notably, the "U.S. Standard (1976) atmospheric profile model" of the
      AFGL's report include radiatively active gases such as H2O, O3, N2O,
      and CO, that the *U.S. Standard Atmosphere 1976* atmosphere model does
      not include.
    """

    _thermoprops: xr.Dataset = documented(
        attrs.field(
            factory=lambda: us76.make_profile(),
            converter=_convert_thermoprops_us76_approx,
            validator=attrs.validators.instance_of(xr.Dataset),
        ),
        doc="Thermophysical properties.",
        type=":class:`~xarray.Dataset`",
        default="us76.make_profile",
    )

    has_absorption: bool = documented(
        attrs.field(
            default=True,
            converter=bool,
            validator=attrs.validators.instance_of(bool),
        ),
        doc="Absorption switch. If ``True``, the absorption coefficient is "
        "computed. Else, the absorption coefficient is not computed and "
        "instead set to zero.",
        type="bool",
        default="True",
    )

    has_scattering: bool = documented(
        attrs.field(
            default=True,
            converter=bool,
            validator=attrs.validators.instance_of(bool),
        ),
        doc="Scattering switch. If ``True``, the scattering coefficient is "
        "computed. Else, the scattering coefficient is not computed and "
        "instead set to zero.",
        type="bool",
        default="True",
    )

    absorption_data_set: t.Optional[str] = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(str),
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc="Absorption data set file path. If ``None``, the default "
        "absorption data sets will be used to compute the absorption "
        "coefficient. Otherwise, the absorption data set whose path is "
        "provided will be used to compute the absorption coefficient.",
        type="str",
    )

    @property
    def thermoprops(self) -> xr.Dataset:
        """
        Return thermophysical properties.
        """
        return self._thermoprops

    @property
    def levels(self) -> pint.Quantity:
        """
        Return level altitudes.
        """
        return to_quantity(self.thermoprops.z_level)

    def eval_sigma_a_mono(self, w: pint.Quantity) -> pint.Quantity:
        profile = self.thermoprops
        if self.has_absorption:
            if self.absorption_data_set is None:  # ! this is never tested
                ds = data.open_dataset(get_us76_u86_4_spectrum_filename(w))
            else:
                ds = xr.open_dataset(self.absorption_data_set)

            # Compute scattering coefficient
            result = compute_sigma_a(
                ds=ds,
                wl=w,
                p=to_quantity(profile.p),
                n=to_quantity(profile.n),
                fill_values=dict(
                    pt=0.0
                ),  # us76_u86_4 dataset is limited to pressures above
                # 0.101325 Pa, but us76 thermophysical profile goes below that
                # value for altitudes larger than 93 km. At these altitudes, the
                # number density is so small compared to that at the sea level that
                # we assume it is negligible.
            )
            ds.close()

            return result

        else:
            return ureg.Quantity(np.zeros(profile.z_layer.size), "km^-1")

    def eval_sigma_a_ckd(self, *bindexes: Bindex, bin_set_id: str) -> pint.Quantity:
        raise UnsupportedModeError(supported="monochromatic")

    def eval_sigma_s_mono(self, w: pint.Quantity) -> pint.Quantity:
        profile = self.thermoprops
        if self.has_scattering:
            return compute_sigma_s_air(
                wavelength=w,
                number_density=to_quantity(profile.n),
            )
        else:
            return ureg.Quantity(np.zeros(profile.z_layer.size), "km^-1")

    def eval_sigma_s_ckd(self, *bindexes: Bindex) -> pint.Quantity:
        raise UnsupportedModeError(supported="monochromatic")

    def eval_albedo_mono(self, w: pint.Quantity) -> pint.Quantity:
        sigma_s = self.eval_sigma_s_mono(w)
        sigma_t = self.eval_sigma_t_mono(w)
        return np.divide(
            sigma_s, sigma_t, where=sigma_t != 0.0, out=np.zeros_like(sigma_s)
        ).to("dimensionless")

    def eval_albedo_ckd(self, *bindexes: Bindex, bin_set_id: str) -> pint.Quantity:
        raise UnsupportedModeError(supported="monochromatic")

    def eval_sigma_t_mono(self, w: pint.Quantity) -> pint.Quantity:
        return self.eval_sigma_a_mono(w) + self.eval_sigma_s_mono(w)

    def eval_sigma_t_ckd(self, *bindexes: Bindex, bin_set_id: str) -> pint.Quantity:
        raise UnsupportedModeError(supported="monochromatic")

    def eval_dataset_mono(self, w: pint.Quantity) -> xr.Dataset:
        profile = self.thermoprops
        return make_dataset(
            wavelength=w,
            z_level=to_quantity(profile.z_level),
            z_layer=to_quantity(profile.z_layer),
            sigma_a=self.eval_sigma_a_mono(w),
            sigma_s=self.eval_sigma_s_mono(w),
        ).squeeze()

    def eval_dataset_ckd(self, *bindexes: Bindex, bin_set_id: str) -> xr.Dataset:
        raise UnsupportedModeError(supported="monochromatic")
