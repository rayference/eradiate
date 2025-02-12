"""Basic CKD correctness check."""

import numpy as np

import eradiate
from eradiate import unit_registry as ureg
from eradiate.experiments import AtmosphereExperiment
from eradiate.scenes.bsdfs import LambertianBSDF
from eradiate.scenes.measure import MultiDistantMeasure


def test_ckd_basic(modes_all_ckd):
    """
    CKD correctness check
    =====================

    We check for correctness when using CKD modes with atmosphere-free scenes.
    This test is designed to check that the CKD infrastructure
    (preprocessing, spectral loop, postprocessing) works.

    Rationale
    ---------

    Create an ``AtmosphereExperiment`` instance with no atmosphere, a Lambertian
    surface with reflectance equal to 1 and a ``MultiDistantMeasure``:

    * Sensor: Distant measure covering a plane (25 angular points,
      10^6 sample per pixel) and targeting (0, 0, 0).
    * Illumination: Directional illumination with a zenith angle
      :math:`\\theta = 0.0°` with black body irradiance spectrum.
    * Surface: a square surface with a Lambertian BRDF with 100 % reflectance.
    * Integrator: path tracer.

    Expected behaviour
    ------------------

    Recorded BRF must be exactly equal to one for all defined spectral bins.
    """

    # Configure experiment, run and postprocess results
    exp = AtmosphereExperiment(
        atmosphere=None,
        surface=LambertianBSDF(reflectance=1.0),
        measures=[
            MultiDistantMeasure.from_viewing_angles(
                zeniths=np.arange(-60, 61, 5) * ureg.deg,
                azimuths=0.0 * ureg.deg,
                spectral_cfg={
                    "bin_set": "10nm",
                    "bins": [
                        "550",
                        "560",
                        "570",
                        "510",
                    ],  # We specify bins in arbitrary order on purpose
                },
            )
        ],
    )
    results = eradiate.run(exp)
    results = np.squeeze(results.data_vars["brf"].values)

    # Reflectance is uniform, equal to 1
    assert np.allclose(results, 1.0), f"diff = {results - 1.0}"
