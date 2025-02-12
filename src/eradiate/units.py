__all__ = [
    "symbol",
    "to_quantity",
    "unit_context_config",
    "unit_context_kernel",
    "unit_registry",
    "PhysicalQuantity",
]


import enum
import typing as t
from functools import lru_cache

import pint
import pinttr
import xarray
from pinttr.exceptions import UnitsError
from pinttr.util import units_compatible

# -- Global data members -------------------------------------------------------

#: Unit registry common to all Eradiate components. All units used in Eradiate
#: must be created using this registry. Aliased in :mod:`eradiate`.
unit_registry = pint.UnitRegistry()

unit_registry.define(
    "dobson_unit = 2.687e20 * meter^-2 "
    "= du = dobson = dobson_units"  # aliases
)
"""IUPAC. Compendium of Chemical Terminology, 2nd ed. (the "Gold Book").
Compiled by A. D. McNaught and A. Wilkinson. Blackwell Scientific Publications,
Oxford (1997). Online version (2019-) created by S. J. Chalk. ISBN 0-9678550-9-8.
https://doi.org/10.1351/goldbook."""

unit_registry.define(
    "atmo_centimeter = 1000 * dobson_unit "
    "= atm_cm = centimeter_atmosphere = centimeter_amagat"  # aliases
)
"""Chapter 1 Vertical Structure of an Atmosphere. In International Geophysics,
22:1–45. Elsevier, 1978. https://doi.org/10.1016/S0074-6142(09)60038-3.
"""


class PhysicalQuantity(enum.Enum):
    """An enumeration defining physical quantities known to Eradiate."""

    ALBEDO = "albedo"
    ANGLE = "angle"
    COLLISION_COEFFICIENT = "collision_coefficient"
    DIMENSIONLESS = "dimensionless"
    IRRADIANCE = "irradiance"
    LENGTH = "length"
    MASS = "mass"
    RADIANCE = "radiance"
    REFLECTANCE = "reflectance"
    SPEED = "speed"
    TIME = "time"
    TRANSMITTANCE = "transmittance"
    WAVELENGTH = "wavelength"

    @classmethod
    @lru_cache(maxsize=32)
    def spectrum(cls):
        """
        Return a tuple containing a subset of :class:`PhysicalQuantity`
        members suitable for :class:`.Spectrum` initialisation. This function
        caches its results for improved efficiency.
        """
        return (
            cls.ALBEDO,
            cls.COLLISION_COEFFICIENT,
            cls.DIMENSIONLESS,
            cls.IRRADIANCE,
            cls.RADIANCE,
            cls.REFLECTANCE,
            cls.TRANSMITTANCE,
        )


def _make_unit_context():
    uctx = pinttr.UnitContext(
        interpret_str=True, ureg=unit_registry, key_converter=PhysicalQuantity
    )

    # fmt: off
    for key, value in {
        # We allow for dimensionless quantities
        PhysicalQuantity.DIMENSIONLESS: pinttr.UnitGenerator(unit_registry.dimensionless),
        # Basic quantities must be named after their SI name
        # https://en.wikipedia.org/wiki/International_System_of_Units
        PhysicalQuantity.LENGTH: pinttr.UnitGenerator(unit_registry.m),
        PhysicalQuantity.TIME: pinttr.UnitGenerator(unit_registry.s),
        PhysicalQuantity.MASS: pinttr.UnitGenerator(unit_registry.kg),
        # Derived quantity names are more flexible
        PhysicalQuantity.ALBEDO: pinttr.UnitGenerator(unit_registry.dimensionless),
        PhysicalQuantity.ANGLE: pinttr.UnitGenerator(unit_registry.deg),
        PhysicalQuantity.REFLECTANCE: pinttr.UnitGenerator(unit_registry.dimensionless),
        PhysicalQuantity.TRANSMITTANCE: pinttr.UnitGenerator(unit_registry.dimensionless),
        PhysicalQuantity.WAVELENGTH: pinttr.UnitGenerator(unit_registry.nm),
    }.items():
        uctx.register(key, value)
    # fmt: on

    # The following quantities will update automatically based on their parent units
    uctx.register(
        PhysicalQuantity.COLLISION_COEFFICIENT,
        pinttr.UnitGenerator(lambda: uctx.get(PhysicalQuantity.LENGTH) ** -1),
    )
    uctx.register(
        PhysicalQuantity.IRRADIANCE,
        pinttr.UnitGenerator(
            lambda: unit_registry.watt
            / uctx.get(PhysicalQuantity.LENGTH) ** 2
            / uctx.get(PhysicalQuantity.WAVELENGTH)
        ),
    )
    uctx.register(
        PhysicalQuantity.RADIANCE,
        pinttr.UnitGenerator(
            lambda: unit_registry.watt
            / uctx.get(PhysicalQuantity.LENGTH) ** 2
            / unit_registry.steradian
            / uctx.get(PhysicalQuantity.WAVELENGTH)
        ),
    )

    return uctx


#: Unit context used when interpreting config dictionaries.
#: Aliased in :mod:`eradiate`.
unit_context_config = _make_unit_context()

#: Unit context used when building kernel dictionaries.
#: Aliased in :mod:`eradiate`.
unit_context_kernel = _make_unit_context()


# -- Public functions ----------------------------------------------------------


def symbol(units: t.Union[pint.Unit, str]) -> str:
    """
    Normalise a string or Pint units to a symbol string.

    Parameters
    ----------
    units : :class:`pint.Unit` or str
        Value to convert to a symbol string.

    Returns
    -------
    str
        Symbol string (*e.g.* ``'m'`` for ``'metre'``, ``'W / m ** 2'`` for
        ``'W/m^2'``, etc.).
    """
    units = unit_registry.Unit(units)
    return format(units, "~")


def to_quantity(da: xarray.DataArray) -> pint.Quantity:
    """
    Converts a :class:`~xarray.DataArray` to a :class:`~pint.Quantity`.
    The array's ``attrs`` metadata mapping must contain a ``units`` field.

    Parameters
    ----------
    da : DataArray
        :class:`~xarray.DataArray` instance which will be converted.


    Returns
    -------
    quantity
        The corresponding Pint quantity.

    Raises
    ------
    ValueError
        If the array's metadata do not contain a ``units`` field.

    Notes
    -----
    This function can also be used on coordinate variables.
    """
    try:
        units = da.attrs["units"]
    except KeyError as e:
        raise ValueError("this DataArray has no 'units' metadata field") from e
    else:
        return unit_registry.Quantity(da.values, units)


def interpret_quantities(
    d: t.Dict[str, t.Any],
    quantity_map: t.Dict[str, str],
    uctx: pinttr.UnitContext,
    force: bool = False,
):
    """
    Advanced unit interpretation and wrapping for dictionaries. This function
    first calls :func:`pinttr.interpret_units` to interpret units attached to
    a given field. Then, it converts quantities and possibly applies default
    units to fields specified in ``quantity_map`` based on ``uctx``.

    Parameters
    ----------
    d : dict
        Dictionary to apply unit conversion, checking and defaults.

    quantity_map : dict[str, str]
        Dictionary mapping fields to quantity identifiers (see
        :class:`.PhysicalQuantity` for valid quantity IDs).

    uctx : :class:`pinttr.UnitContext`
        Unit context containing quantity and default units definitions.

    force : bool, default: False
        If ``True``, fields specified as quantities will be converted to target
        units; otherwise, only units compatibility will be checked.

    Returns
    -------
    dict
        Dictionary with units interpreted and checked, and default units
        applied to relevant fields.

    Raises
    ------
    :class:`pinttr.UnitsError`:
        If a field and its mapped quantity have incompatible units.

    See Also
    --------
    :class:`.PhysicalQuantity`
    """
    ureg = uctx.ureg

    # Interpret unit fields
    result = pinttr.interpret_units(d, ureg)

    # Convert to or apply default units based on the unit map
    if quantity_map is None:
        quantity_map = {}

    for key, quantity in quantity_map.items():
        value = result[key]
        if isinstance(value, pint.Quantity):
            units = uctx.get(quantity)
            if not units_compatible(value.units, units):
                raise UnitsError(value.units, units)

            if force:
                result[key] = value.to(units)
            else:
                result[key] = value
        else:
            result[key] = ureg.Quantity(result[key], uctx.get(quantity))

    return result
