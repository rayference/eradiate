import typing as t
from numbers import Number

import attr
import numpy as np

from .attrs import AUTO
from .units import PhysicalQuantity
from .units import unit_registry as ureg


def is_number(_, attribute, value):
    """
    A validator that raises if the initializer is called with a non-number
    value.

    Raises
    ------
    TypeError
        If the value is not a :class:`Number`.
    """
    if not isinstance(value, Number):
        raise TypeError(
            f"{attribute.name} must be a real number, "
            f"got {value} which is a {value.__class__}"
        )


def is_vector3(instance, attribute, value):
    """
    A validator that raises if the initializer is called with a value which
    cannot be converted to a (3,) Numpy array.

    Raises
    ------
    TypeError
        If value cannot be converted to a (3,) :class:`numpy.ndarray`.
    """
    return attr.validators.deep_iterable(
        member_validator=is_number, iterable_validator=has_len(3)
    )(instance, attribute, value)


def is_positive(_, attribute, value):
    """
    A validator that raises if the initializer is called with a negative value.

    Raises
    ------
    ValueError
        If the value is not positive or zero.
    """
    if value < 0.0:
        raise ValueError(f"{attribute} must be positive or zero, got {value}")


def all_positive(_, attribute, value):
    """
    A validator that raises if the initializer is called with a vector
    containing negative values.

    Raises
    ------
    ValueError
        If not all values are positive.
    """
    if isinstance(value, ureg.Quantity):
        value = value.magnitude
    if np.any(np.array(value) < 0):
        raise ValueError(f"{attribute} must be all positive or zero, got {value}")


def path_exists(_, attribute, value):
    """
    A validator that succeeds if the initializer is called with a value defining
    a path to an existing location.

    Raises
    ------
    FileNotFoundError
        If the value is not a :class:`pathlib.Path` which points to an existing
        location.
    """
    if not value.exists():
        raise FileNotFoundError(
            f"{attribute} points to '{str(value)}' (path does not exist)"
        )


def is_file(_, attribute, value):
    """
    A validator that succeeds if the initializer is called with a value defining
    a path to an existing file.

    Raises
    ------
    FileNotFoundError
        If the value is not a :class:`pathlib.Path` which points to an existing
        file.
    """
    if not value.is_file():
        raise FileNotFoundError(
            f"{attribute.name} points to '{str(value)}' (not a file)"
        )


def is_dir(_, attribute, value):
    """
    A validator that succeeds if the initializer is called with a value defining
    a path to an existing directory.

    Raises
    ------
    FileNotFoundError
        If the value is not a :class:`pathlib.Path` which points to an existing
        directory.
    """
    if not value.is_dir():
        raise FileNotFoundError(
            f"{attribute.name} points to '{str(value)}' (not a directory)"
        )


def has_len(size: int):
    """
    A validator which raises if the initializer is called with a value of a
    specified length.

    Parameters
    ----------
    size : int
        Expected size of the validated value.

    Raises
    ------
    ValueError
        If the value does not have the expected size.
    """

    def f(_, attribute, value):
        if len(value) != size:
            raise ValueError(
                f"{attribute} must be have length {size}, "
                f"got {value} of length {len(value)}"
            )

    return f


def has_quantity(quantity: t.Union[PhysicalQuantity, str]):
    """
    A validator that succeeds if the initializer is called with a value
    featuring a ``quantity`` field set to an expected value.

    Parameters
    ----------
    quantity : :class:`.PhysicalQuantity` or str
        Expected quantity field.

    Raises
    ------
    ValueError
        If the value's ``quantity`` field does not match the expected value.
    """

    quantity = PhysicalQuantity(quantity)

    def f(_, attribute, value):
        if value.quantity != quantity:
            raise ValueError(
                f"incompatible quantity '{value.quantity}' "
                f"used to set field '{attribute.name}' "
                f"(allowed: '{quantity}')"
            )

    return f


def on_quantity(wrapped_validator: t.Callable):
    """
    A validator that applies a validator to the magnitude of a value.

    Parameters
    ----------
    wrapped_validator : callable
        The validator applied to the value's magnitude.
    """

    def f(instance, attribute, value):
        if isinstance(value, ureg.Quantity):
            return wrapped_validator(instance, attribute, value.magnitude)
        else:
            return wrapped_validator(instance, attribute, value)

    return f


def auto_or(*wrapped_validators):
    """
    A validator that allows an attribute to be set to :class:`.AUTO`.

    Parameters
    ----------
    *wrapped_validators : callable
        Validators to be applied to values not equal to :class:`.AUTO`.
    """

    def f(instance, attribute, value):
        if value is AUTO:
            return

        for validator in wrapped_validators:
            validator(instance, attribute, value)

    return f
