"""Specialised container datatypes providing alternatives to Python’s general
purpose built-in containers, dict, list, set, and tuple."""

import collections

from dpath import util as dpu
from dpath.exceptions import PathNotFound

from .units import ureg


def onedict_value(d):
    """Get the value of a single-entry dictionary."""

    if len(d) != 1:
        raise ValueError(f"dictionary has wrong length (expected 1, got {len(d)}")

    return next(iter(d.values()))


class frozendict(collections.abc.Mapping):
    """A frozen dictionary implementation. See
    https://stackoverflow.com/questions/2703599/what-would-a-frozen-dict-be.

    It behaves like a dictionary, except that it cannot be modified after
    initialisation.
    """

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __repr__(self):
        return f"frozendict({self._d.__repr__()})"

    def __hash__(self):
        # It would have been simpler and maybe more obvious to
        # use hash(tuple(sorted(self._d.iteritems()))) from this discussion
        # so far, but this solution is O(n). I don't know what kind of
        # n we are going to run into, but sometimes it's hard to resist the
        # urge to optimize when it will gain improved algorithmic performance.
        if self._hash is None:
            hash_ = 0
            for pair in self.items():
                hash_ ^= hash(pair)
            self._hash = hash_
        return self._hash

    def copy(self):
        """Return shallow copy of encapsulated dict"""
        return self._d.copy()


def update(d, u):
    """This function updates nested dictionaries.
    See https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth.

    Parameter ``d`` (dict)
        Dictionary which will be updated (**modified in-place**).

    Parameter ``u`` (dict)
        Dictionary holding the values to update ``d`` with.

    Returns → dict
        Updated ``d``.
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class configdict(dict):
    """A nested dict structure suitable to hold configuration contents. Keys
    are expected to be strings (untested with different key types).
    """

    # Requires dpath [https://github.com/akesterson/dpath-python]

    def __init__(self, d={}, separator="."):
        """Initialise from another dictionary.

        Parameter ``d`` (dict)
            Dictionary to initialise from.

        Parameter ``separator`` (str)
            Key separator.

        """
        super().__init__(d)
        self.separator = separator

    def update(self, other):
        """Recursively update with content of another nested dict structure.
        Existing leaves are overwritten.

        Parameter ``other`` (dict):
            Dictionary to update ``self`` with.
        """
        dpu.merge(self, other, separator=self.separator, flags=dpu.MERGE_REPLACE)

    def rget(self, key):
        """Recursively access an element in the nested dictionary.

        Parameter ``key`` (str)
            Path to the queried element. The path separator is defined by
            ``self.separator``.

        Returns → object
            Requested object.

        Raises → ``KeyError``
            The requested key could not be found.
        """
        return dpu.get(self, key, separator=self.separator)

    def rset(self, key, value):
        """Set an element in the nested dictionary.

        Parameter ``key`` (str)
            Path to the element to set. The path separator is defined by
            ``self.separator``.

        Raises → ``KeyError``
            The requested key could not be found.
        """
        try:
            dpu.new(self, key, value, separator=self.separator)
        except PathNotFound:
            raise KeyError(key)

    def get_quantity(self, key):
        """Get a quantity from the dictionary. The ``key`` item is first looked
        up as with a regular dictionary. If it is found, this method looks
        for the corresponding ``_unit``-suffixed entry. If a corresponding unit
        field is found, the retrieved value is turned into a
        :class:`pint.Quantity` object using the unit found bby the method.

        Parameter ``key``
            Key to lookup from the dictionary.

        Returns
            The ``key`` item. In addition, if a unit
            field is found, the ``key`` item is returned as a
            :class:`pint.Quantity`.

        Raises → ``KeyError``
            The requested key could not be found.
        """
        magnitude = self[key]
        units = self.get(f"{key}_units", None)
        if units is None:
            return magnitude
        else:
            return ureg.Quantity(magnitude, units)
