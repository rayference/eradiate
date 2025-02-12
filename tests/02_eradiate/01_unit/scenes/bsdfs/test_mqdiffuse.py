import numpy as np
import pytest
import xarray as xr

from eradiate.contexts import KernelDictContext
from eradiate.scenes.bsdfs import MQDiffuseBSDF

ds = xr.Dataset(
    {
        "brdf": xr.DataArray(
            data=np.full((3, 3, 3), 1.0 * np.pi),
            coords=[
                ("cos_theta_o", np.linspace(0, 1, 3), {"units": ""}),
                (
                    "phi_d",
                    np.linspace(0, 2.0 * np.pi, 3, endpoint=False),
                    {"units": "rad"},
                ),
                ("cos_theta_i", np.linspace(0, 1, 3), {"units": ""}),
            ],
        )
    }
)


def test_construct():
    # Constructing with a well-formed dataset succeeds
    assert MQDiffuseBSDF(data=ds)

    # Missing 'brdf' variable fails
    with pytest.raises(ValueError, match="missing required data variable"):
        MQDiffuseBSDF(data=ds.rename({"brdf": "bsdf"}))

    # Incorrect dimension fails
    with pytest.raises(ValueError, match="incorrect dimension list"):
        MQDiffuseBSDF(data=ds.rename({"phi_d": "phi_r"}))

    # Incorrect coordinate fails
    with pytest.raises(
        ValueError, match="incorrect coordinate values for field 'phi_d'"
    ):
        MQDiffuseBSDF(
            data=ds.assign_coords(
                {
                    "phi_d": (
                        "phi_d",
                        np.linspace(0.0, 2.0 * np.pi, len(ds.phi_d)),
                        {"units": "rad"},
                    )
                }
            )
        )

    # Missing units fails
    with pytest.raises(
        ValueError,
        match="input dataset coordinate variable 'phi_d' is missing 'units' "
        "metadata field",
    ):
        MQDiffuseBSDF(
            data=ds.assign_coords(
                {
                    "phi_d": (
                        "phi_d",
                        np.linspace(0.0, 2.0 * np.pi, len(ds.phi_d), endpoint=True),
                    )
                }
            )
        )


def test_kernel_dict(mode_mono):
    bsdf = MQDiffuseBSDF(data=ds)
    ctx = KernelDictContext()

    # Kernel dictionary generation succeeds
    kernel_dict = bsdf.kernel_dict(ctx)

    # Generated kernel dictionary can be loaded by Mitsuba
    assert kernel_dict.load()
