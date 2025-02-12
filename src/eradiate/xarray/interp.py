__all__ = ["dataarray_to_rgb", "film_to_angular"]

import typing as t

import numpy as np
import xarray as xr

from .. import frame
from .._config import config
from ..warp import uniform_hemisphere_to_square


def film_to_angular(
    da: xr.DataArray,
    theta: np.typing.ArrayLike,
    phi: np.typing.ArrayLike,
    x_label: str = "x",
    y_label: str = "y",
    theta_label: str = "theta",
    phi_label: str = "phi",
    azimuth_convention: t.Union[frame.AzimuthConvention, str, None] = None,
) -> xr.DataArray:
    """
    Interpolate a hemispherical film data array on an angular grid.

    Parameters
    ----------
    da : DataArray
        Data array with film coordinate pixels to interpolate on an angular grid.

    theta : array-like
        List of zenith angle values.

    phi : array-like
        List of azimuth angle values.

    x_label : str, default: "x"
        Label for the width pixel coordinate.

    y_label : str, default: "y"
        Label for the height pixel coordinate.

    theta_label : str, default: "theta"
        Label for the zenith angle coordinate.

    phi_label : str, default: "phi"
        Label for the azimuth angle coordinate.

    azimuth_convention : .AzimuthConvention or str, optional
        Azimuth convention used in the produced data array. If unset the default
        active convention is used.

    Returns
    -------
    DataArray
        Data array interpolated on the specified angular grid.
    """
    # TODO: Double check where this function is used and if the azimuth
    #       transformation is correctly applied.

    # Define azimuth convention
    if azimuth_convention is None:
        azimuth_convention = config.azimuth_convention
    elif isinstance(azimuth_convention, str):
        azimuth_convention = frame.AzimuthConvention[azimuth_convention.upper()]
    else:
        pass

    # Interpolate values on angular grid
    data = np.empty((len(phi), len(theta)))

    # Map angular grid points to (x, y) space
    for i, ph in enumerate(phi):
        xs = np.empty_like(theta)
        ys = np.empty_like(theta)

        angles = np.array([[th, ph] for th in theta.ravel()])
        directions = frame.angles_to_direction(angles)
        film_coords = uniform_hemisphere_to_square(directions)
        xs.ravel()[:] = film_coords[:, 0]
        ys.ravel()[:] = film_coords[:, 1]

        x = xr.DataArray(xs, dims=theta_label)
        y = xr.DataArray(ys, dims=theta_label)
        data[i, :] = da.interp(**{x_label: x, y_label: y}).values

    return xr.DataArray(
        data,
        coords=(
            (
                phi_label,
                frame.transform_azimuth(phi, to_convention=azimuth_convention),
            ),
            (theta_label, theta),
        ),
        dims=(phi_label, theta_label),
    )


def dataarray_to_rgb(
    da: xr.DataArray,
    channels: t.Sequence[t.Tuple[str, t.Any]],
    normalize: bool = True,
    gamma_correction: bool = True,
) -> np.ndarray:
    """
    Compose an RGB image from radiance data.

    Parameters
    ----------
    da : DataArray
        The data array from which radiance data will be taken. It has to be such
        that data, when selected on a spectral axis, is 2-dimensional.

    channels : sequence of tuples
        Three (coordinate label, coordinate value) pairs used to select the data
        used to compose the image. Channels are ordered as follows: (R, G, B).
        For instance, to select wavelengths (dimension ``"w'``) at 440 (blue),
        550 (green) and 660 (red) nm, use
        ``channels=[("w", 660), ("w", 550), ("w", 440)]``.

    normalize : bool, optional
        If ``True``, the data will be normalized by its maximum value.

    gamma_correction : bool, optional
        If ``True``, apply a gamma operator to the data.

    Returns
    -------
    ndarray
        An RGB image which can be displayed using
        :func:`matplotlib.pyplot.imshow`.

    Warnings
    --------
    The image processing pipeline implemented by this function is rudimentary.
    It only applies, if instructed, a gamma operator. For more advanced tone
    mapping operations, use this function with ``normalize=False`` and
    ``gamma_correction=False``, then apply your own post-processing to the
    resulting (N, M, 3)-shaped array.
    """
    if len(channels) != 3:
        raise ValueError("channel list must have 3 elements (R, G, B)")

    # Collect data
    result = []

    for coord, value in channels:
        x = da.sel(**{coord: value}).squeeze().values
        if x.ndim != 2:
            raise ValueError("only 2D arrays can be assembled into an RGB image")
        result.append(np.expand_dims(x, axis=-1))

    result = np.concatenate(result, axis=2)

    # Normalize to [0, 1] interval
    if normalize:
        result /= np.max(result)

    # Apply gamma correction
    if gamma_correction:
        result **= 1.0 / 2.2

    return result
