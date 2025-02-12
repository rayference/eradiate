import attrs
import mitsuba as mi
import numpy as np
import xarray as xr

from ._core import BSDF
from ..core import KernelDict
from ... import converters
from ...attrs import documented, parse_docs
from ...contexts import KernelDictContext
from ...units import to_quantity
from ...units import unit_registry as ureg


@parse_docs
@attrs.define
class MQDiffuseBSDF(BSDF):
    """
    Measured quasi-diffuse BSDF [``mqdiffuse``].

    This BSDF models the reflection of light by opaque materials with a
    behaviour close to diffuse, *i.e* with no strong scattering lobe.
    Assumptions are as follows:

    * The material is isotropic. Consequently, only the azimuth difference
      matters.
    * The material is gray. Consequently, no spectral dimension is used.

    Notes
    -----
    The input is specified using an xarray dataset. It must contain a ``brdf``
    data variable with the following dimensions (the corresponding coordinate
    range is specified within brackets):

    * ``cos_theta_o`` [0, 1]: cosine of the outgoing zenith angle;
    * ``phi_d`` [0, 2π[: difference between the incoming and outgoing azimuth
      angles;
    * ``cos_theta_i`` [0, 1]: cosine of the incoming zenith angle.

    Coordinates must be evenly spaced and have a `"units"` metadata field.

    Warnings
    --------
    * Table values are not checked internally: ensuring that the data is
      consistent (*e.g* that the corresponding reflectance is not greater than
      1) is the user's responsibility.
    * While this BSDF may technically represent any isotropic material, its
      sampling routine's performance degrades as the material departs from a
      diffuse behaviour.
    """

    data: xr.Dataset = documented(
        attrs.field(
            converter=converters.to_dataset(),
            kw_only=True,
        ),
        type="Dataset",
        init_type="Dataset",
        doc="Measured quasi-diffuse BRDF data formatted as an xarray dataset.",
    )

    @data.validator
    def _data_validator(self, attribute, value):
        # Check type
        attrs.validators.instance_of(xr.Dataset)(self, attribute, value)

        # Check data variable
        if "brdf" not in value.data_vars:
            raise ValueError(
                f"while validating '{attribute.name}': missing required data "
                "variable 'brdf'"
            )

        # Check dimensions
        if set(value.data_vars["brdf"].dims) != {"cos_theta_o", "phi_d", "cos_theta_i"}:
            raise ValueError(
                f"while validating '{attribute.name}': incorrect dimension "
                f"list (got '{set(value.dims)}', "
                f"expected '{ {'cos_theta_o', 'phi_d', 'cos_theta_i'} }')"
            )

        # Check coordinates
        for coord_name in ["cos_theta_o", "cos_theta_i", "phi_d"]:
            try:
                coord = to_quantity(value.coords[coord_name])
            except ValueError as e:
                if e.args[0] == "this DataArray has no 'units' metadata field":
                    raise ValueError(
                        f"while validating '{attribute.name}': input dataset "
                        f"coordinate variable '{coord_name}' is missing "
                        "'units' metadata field"
                    ) from e
                else:
                    raise e

            expected = (
                np.linspace(0.0, 1.0, len(coord))
                if coord_name.startswith("cos")
                else (
                    np.linspace(0.0, 2.0 * np.pi, len(coord), endpoint=False) * ureg.rad
                )
            )
            if not np.allclose(coord, expected):
                raise ValueError(
                    f"while validating '{attribute.name}': incorrect "
                    f"coordinate values for field '{coord_name}'; got {coord}, "
                    f"expected {expected}"
                )

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        # Inherit docstring

        values = (
            self.data.data_vars["brdf"]
            .transpose("cos_theta_o", "phi_d", "cos_theta_i")
            .values
        )

        result = {
            self.id: {
                "type": "mqdiffuse",
                "grid": mi.VolumeGrid(values.astype(np.float32)),
            }
        }

        return KernelDict(result)
