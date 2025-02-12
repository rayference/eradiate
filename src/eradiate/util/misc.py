"""
A collection of tools which don't really fit anywhere else.
"""

import functools
import inspect
import re
import typing as t
from collections import OrderedDict
from numbers import Number

import numpy as np
import pint


class LoggingContext(object):
    """
    This context manager allows for a temporary override of logger settings.
    """

    # from https://docs.python.org/3/howto/logging-cookbook.html#using-a-context-manager-for-selective-logging
    def __init__(self, logger, level=None, handler=None, close=True):
        self.logger = logger
        self.level = level
        self.handler = handler
        self.close = close

    def __enter__(self):
        if self.level is not None:
            self.old_level = self.logger.level
            self.logger.setLevel(self.level)
        if self.handler:
            self.logger.addHandler(self.handler)

    def __exit__(self, et, ev, tb):
        if self.level is not None:
            self.logger.setLevel(self.old_level)
        if self.handler:
            self.logger.removeHandler(self.handler)
        if self.handler and self.close:
            self.handler.close()
        # implicit return of None => don't swallow exceptions


class Singleton(type):
    """
    A simple singleton implementation. See [1]_ for details.

    References
    -------
    .. [1] `Creating a singleton in Python on Stack Overflow <https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python>`_.

    Examples
    --------

    .. testsetup:: singleton

       from eradiate.util.misc import Singleton

    .. doctest:: singleton

       >>> class MySingleton(metaclass=Singleton): ...
       >>> my_singleton1 = MySingleton()
       >>> my_singleton2 = MySingleton()
       >>> my_singleton1 is my_singleton2
       True

    .. testcleanup:: singleton

       del Singleton
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def camel_to_snake(name):
    # from https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def deduplicate(value: t.Sequence, preserve_order: bool = True) -> t.List:
    """
    Remove duplicates from a sequence.

    Parameters
    ---------
    value : sequence
        Sequence to remove duplicates from.

    preserve_order : bool, optional, default: True
        If ``True``, preserve item ordering. The first occurrence of duplicated
        items is kept. Setting to ``False`` may slightly improve performance.

    Returns
    -------
    list
        List of values with duplicates removed.
    """

    if preserve_order:
        return list(OrderedDict.fromkeys(value))

    else:
        return list(set(value))


def fullname(obj: t.Any) -> str:
    """
    Get the fully qualified name of `obj`. Aliases will be dereferenced.
    """
    cls = get_class_that_defined_method(obj)

    if cls is None:
        return f"{obj.__module__}.{obj.__qualname__}"

    # else: # (it's a method)
    return f"{cls.__module__}.{obj.__qualname__}"


def get_class_that_defined_method(meth: t.Any) -> t.Type:
    """
    Get the class which defined a method, if relevant. Otherwise, return
    ``None``.
    """
    # See https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545
    if isinstance(meth, functools.partial):
        return get_class_that_defined_method(meth.func)

    if inspect.ismethod(meth) or (
        inspect.isbuiltin(meth)
        and getattr(meth, "__self__", None) is not None
        and getattr(meth.__self__, "__class__", None)
    ):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        meth = getattr(meth, "__func__", meth)  # fallback to __qualname__ parsing

    if inspect.isfunction(meth):
        cls = getattr(
            inspect.getmodule(meth),
            meth.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0],
            None,
        )
        if isinstance(cls, type):
            return cls

    return getattr(meth, "__objclass__", None)  # handle special descriptor objects


def is_vector3(value: t.Any):
    """
    Check if value can be interpreted as a 3-vector.

    Parameters
    ----------
    value
        Value to be checked.

    Returns
    -------
    bool
        ``True`` if a value can be interpreted as a 3-vector.
    """

    if isinstance(value, pint.Quantity):
        return is_vector3(value.magnitude)

    return (
        (
            isinstance(value, np.ndarray)
            or (isinstance(value, t.Sequence) and not isinstance(value, str))
        )
        and len(value) == 3
        and all(map(lambda x: isinstance(x, Number), value))
    )


def natsort_alphanum_key(x):
    """
    Simple sort key natural order for string sorting. See [2]_ for details.

    See Also
    --------
    `Sorting HOWTO <https://docs.python.org/3/howto/sorting.html>`_

    References
    ----------
    .. [2] `Natural sorting on Stack Overflow <https://stackoverflow.com/a/11150413/3645374>`_.
    """
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    return tuple(convert(c) for c in re.split("([0-9]+)", x))


def natsorted(l):
    """
    Sort a list of strings with natural ordering.

    Parameters
    ----------
    l : iterable
        List to sort.

    Returns
    -------
    list
        List sorted using :func:`natsort_alphanum_key`.
    """
    return sorted(l, key=natsort_alphanum_key)


def onedict_value(d: t.Mapping) -> t.Any:
    """
    Get the value of a single-entry dictionary.

    Parameters
    ----------
    d : mapping
        A single-entry mapping.

    Returns
    -------
    object
        Unwrapped value.

    Raises
    ------
    ValueError
        If ``d`` has more than a single element.

    Notes
    -----
    This function is basically ``next(iter(d.values()))`` with a safeguard.

    Examples
    --------

    .. testsetup:: onedict_value

       from eradiate.util.misc import onedict_value

    .. doctest:: onedict_value

       >>> onedict_value({"foo": "bar"})
       'bar'

    .. testcleanup:: onedict_value

       del onedict_value
    """

    if len(d) != 1:
        raise ValueError(f"dictionary has wrong length (expected 1, got {len(d)}")

    return next(iter(d.values()))


def str_summary_numpy(x):
    with np.printoptions(
        threshold=4, edgeitems=2, formatter={"float_kind": lambda x: f"{x:g}"}
    ):
        shape_str = ",".join(map(str, x.shape))
        prefix = f"array<{shape_str}>("
        array_str = f"{x}"

        # Indent repr if it is multiline
        split = array_str.split("\n")
        if len(split) > 1:
            array_str = ("\n" + " " * len(prefix)).join(split)

        return f"{prefix}{array_str})"
