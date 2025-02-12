from __future__ import annotations

import typing as t

import attrs
import numpy as np
import pint
import pinttr
from pinttr.util import ensure_units

from ._core import Shape
from ..bsdfs import BSDF
from ..core import KernelDict
from ...attrs import documented, parse_docs
from ...contexts import KernelDictContext
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg
from ...util.misc import onedict_value


def _normalize(v: np.typing.ArrayLike) -> np.ndarray:
    return np.array(v) / np.linalg.norm(v)


@parse_docs
@attrs.define
class SphereShape(Shape):
    """
    Sphere shape [``sphere``].

    This shape represents a sphere parametrised by its centre and radius.
    """

    center: pint.Quantity = documented(
        pinttr.field(factory=lambda: [0, 0, 0], units=ucc.deferred("length")),
        doc="Location of the centre of the sphere. Unit-enabled field "
        '(default: ``ucc["length"]``).',
        type="quantity",
        init_type="quantity or array-like, optional",
        default="[0, 0, 0]",
    )

    radius: pint.Quantity = documented(
        pinttr.field(
            factory=lambda: 1.0 * ucc.get("length"), units=ucc.deferred("length")
        ),
        doc='Sphere radius. Unit-enabled field (default: ``ucc["length"]``).',
        type="quantity",
        init_type="quantity or float, optional",
        default="1.0",
    )

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        # Inherit docstring
        result = KernelDict(
            {
                self.id: {
                    "type": "sphere",
                    "center": self.center.m_as(uck.get("length")),
                    "radius": self.radius.m_as(uck.get("length")),
                }
            }
        )

        if self.bsdf is not None:
            result[self.id]["bsdf"] = onedict_value(self.bsdf.kernel_dict(ctx))

        return result

    def contains(self, p: np.typing.ArrayLike, strict: bool = False) -> bool:
        """
        Test whether a point lies within the sphere.

        Parameters
        ----------
        p : quantity or array-like
            An array of shape (3,) (resp. (N, 3)) representing one (resp. N)
            points. If a unitless value is passed, it is interpreted as
            ``ucc["length"]``.

        strict : bool
            If ``True``, comparison is done using strict inequalities (<, >).

        Returns
        -------
        result : array of bool or bool
            ``True`` iff ``p`` in within the sphere.
        """
        length_units = ucc.get("length")
        p = np.atleast_2d(ensure_units(p, ucc.get("length")).m_as(length_units))
        c = self.center.m_as(length_units)
        d = np.linalg.norm(p - c, axis=1)
        r = self.radius.m_as(length_units)
        return d < r if strict else d <= r

    @classmethod
    def surface(
        cls,
        altitude=0.0 * ureg.km,
        planet_radius: pint.Quantity = 6378.1 * ureg.km,
        bsdf: t.Optional[BSDF] = None,
    ) -> SphereShape:
        """
        This class method constructor provides a simplified parametrisation of
        the sphere shape better suited for the definition of the surface when
        configuring the one-dimensional model.

        The resulting sphere shape is centred at [0, 0, -`planet_radius`] and
        has a radius equal to `planet_radius` + `altitude`.

        Parameters
        ----------
        altitude : quantity or array-like, optional, default: 0 km
            Surface altitude. If a unitless value is passed, it is interpreted
            as ``ucc["length"]``.

        planet_radius : quantity or float, optional, default: 6378.1 km
            Planet radius. If a unitless value is passed, it is interpreted
            as ``ucc["length"]``. The default is Earth's radius.

        bsdf : BSDF or dict, optional, default: None
            A BSDF specification, forwarded to the main constructor.

        Returns
        -------
        SphereShape
            A sphere shape which can be used as the surface in a spherical shell
            geometry.
        """
        altitude = pinttr.util.ensure_units(altitude, default_units=ucc.get("length"))

        planet_radius = pinttr.util.ensure_units(
            planet_radius, default_units=ucc.get("length")
        )

        return cls(
            center=[0.0, 0.0, 0.0] * planet_radius.units,
            radius=planet_radius + altitude,
            bsdf=bsdf,
        )

    @classmethod
    def atmosphere(
        cls,
        top: pint.Quantity = 100.0 * ureg.km,
        planet_radius: pint.Quantity = 6378.1 * ureg.km,
        bsdf: t.Optional[BSDF] = None,
    ) -> SphereShape:
        """
        This class method constructor provides a simplified parametrisation of
        the sphere shape better suited for the definition of the surface when
        configuring the one-dimensional model.

        The resulting sphere shape is centred at [0, 0, -`planet_radius`] and
        has a radius equal to `planet_radius` + `top`.

        Parameters
        ----------
        top : quantity or array-like, optional, default: 100 km
            Top-of-atmosphere altitude. If a unitless value is passed, it is
            interpreted as ``ucc["length"]``.

        planet_radius : quantity or float, optional, default: 6378.1 km
            Planet radius. If a unitless value is passed, it is interpreted
            as ``ucc["length"]``. The default is Earth's radius.

        bsdf : BSDF or dict, optional, default: None
            A BSDF specification, forwarded to the main constructor.

        Returns
        -------
        SphereShape
            A sphere shape which can be used as the stencil of a participating
            medium in a spherical shell geometry.
        """
        top = pinttr.util.ensure_units(top, default_units=ucc.get("length"))

        planet_radius = pinttr.util.ensure_units(
            planet_radius, default_units=ucc.get("length")
        )

        return cls(
            center=[0.0, 0.0, 0.0] * planet_radius.units,
            radius=planet_radius + top,
            bsdf=bsdf,
        )
