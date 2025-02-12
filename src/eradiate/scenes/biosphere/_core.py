from __future__ import annotations

import os
import typing as t
from abc import ABC, abstractmethod

import attrs
import mitsuba as mi
import numpy as np
import pint
import pinttr

from ..core import KernelDict, SceneElement
from ... import validators
from ..._factory import Factory
from ...attrs import documented, get_doc, parse_docs
from ...contexts import KernelDictContext
from ...typing import PathLike
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg

biosphere_factory = Factory()
biosphere_factory.register_lazy_batch(
    [
        (
            "_core.InstancedCanopyElement",
            "instanced",
            {},
        ),
        (
            "_discrete.DiscreteCanopy",
            "discrete_canopy",
            {"dict_constructor": "padded"},
        ),
        (
            "_leaf_cloud.LeafCloud",
            "leaf_cloud",
            {},
        ),
        (
            "_tree.AbstractTree",
            "abstract_tree",
            {},
        ),
        (
            "_tree.MeshTree",
            "mesh_tree",
            {},
        ),
    ],
    cls_prefix="eradiate.scenes.biosphere",
)


@parse_docs
@attrs.define
class Canopy(SceneElement, ABC):
    """
    An abstract base class defining a base type for all canopies.
    """

    id: t.Optional[str] = documented(
        attrs.field(
            default="canopy",
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc=get_doc(SceneElement, "id", "doc"),
        type=get_doc(SceneElement, "id", "type"),
        init_type=get_doc(SceneElement, "id", "init_type"),
        default='"canopy"',
    )

    size: t.Optional[pint.Quantity] = documented(
        pinttr.field(
            default=None,
            validator=attrs.validators.optional(
                [
                    pinttr.validators.has_compatible_units,
                    validators.on_quantity(validators.is_vector3),
                ]
            ),
            units=ucc.deferred("length"),
        ),
        doc="Canopy size as a 3-vector.\n\nUnit-enabled field (default: ucc['length']).",
        type="quantity",
        init_type="array-like",
    )

    @abstractmethod
    def kernel_bsdfs(self, ctx: KernelDictContext) -> t.MutableMapping:
        """
        Return BSDF plugin specifications only.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the BSDFs
            attached to the shapes in the canopy.
        """
        pass

    @abstractmethod
    def kernel_shapes(self, ctx: KernelDictContext) -> t.MutableMapping:
        """
        Return shape plugin specifications only.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the shapes
            in the canopy.
        """
        pass


@parse_docs
@attrs.define
class CanopyElement(SceneElement, ABC):
    """
    An abstract class representing a component of a :class:`.Canopy` object.
    Concrete canopy classes can manage their components as they prefer.
    """

    @abstractmethod
    def kernel_bsdfs(self, ctx: KernelDictContext) -> t.MutableMapping:
        """
        Return BSDF plugin specifications only.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            Return a dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the BSDFs
            attached to the shapes in the canopy.
        """
        pass

    @abstractmethod
    def kernel_shapes(self, ctx: KernelDictContext) -> t.MutableMapping:
        """
        Return shape plugin specifications only.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the shapes
            in the canopy.
        """
        pass

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        return KernelDict({**self.kernel_bsdfs(ctx=ctx), **self.kernel_shapes(ctx=ctx)})


@parse_docs
@attrs.define
class InstancedCanopyElement(SceneElement):
    """
    Instanced canopy element [``instanced``].

    This class wraps a canopy element and defines locations where to position
    instances (*i.e.* clones) of it.

    .. admonition:: Class method constructors

       .. autosummary::

          from_file
    """

    canopy_element: t.Optional[CanopyElement] = documented(
        attrs.field(
            default=None,
            validator=attrs.validators.optional(
                attrs.validators.instance_of(CanopyElement)
            ),
            converter=biosphere_factory.convert,
        ),
        doc="Instanced canopy element. Can be specified as a dictionary, which "
        "will be converted by :data:`.biosphere_factory`.",
        type=":class:`.CanopyElement`, optional",
    )

    instance_positions: pint.Quantity = documented(
        pinttr.field(
            factory=list,
            units=ucc.deferred("length"),
        ),
        doc="Instance positions as an (n, 3)-array.\n"
        "\n"
        "Unit-enabled field (default: ucc['length'])",
        type="quantity",
        init_type="array-like",
        default="[]",
    )

    @instance_positions.validator
    def _instance_positions_validator(self, attribute, value):
        if value.shape and value.shape[0] > 0 and value.shape[1] != 3:
            raise ValueError(
                f"while validating {attribute.name}, must be an array of shape "
                f"(n, 3), got {value.shape}"
            )

    # --------------------------------------------------------------------------
    #                               Constructors
    # --------------------------------------------------------------------------

    @classmethod
    def from_file(
        cls,
        filename: PathLike,
        canopy_element: t.Optional[CanopyElement] = None,
    ):
        """
        Construct a :class:`.InstancedCanopyElement` from a text file specifying
        instance positions.

        .. admonition:: File format

           Each line defines an instance position as a whitespace-separated
           3-vector of Cartesian coordinates.

        .. important::

           Location coordinates are assumed to be given in meters.

        Parameters
        ----------
        filename : path-like
            Path to the text file specifying the leaves in the canopy.
            Can be absolute or relative.

        canopy_element : .CanopyElement or dict, optional
            :class:`.CanopyElement` to be instanced. If a dictionary is passed,
            if is interpreted by :data:`.biosphere_factory`. If set to
            ``None``, an empty leaf cloud will be created.

        Returns
        -------
        :class:`.InstancedCanopyElement`
            Created :class:`.InstancedCanopyElement`.

        Raises
        ------
        ValueError
            If ``filename`` is set to ``None``.

        FileNotFoundError
            If ``filename`` does not point to an existing file.
        """
        if not os.path.isfile(filename):
            raise FileNotFoundError(f"no file at {filename} found.")

        if canopy_element is None:
            canopy_element = {"type": "leaf_cloud"}

        canopy_element = biosphere_factory.convert(canopy_element)

        instance_positions = []

        with open(filename, "r") as f:
            for i_line, line in enumerate(f):
                try:
                    coords = np.array(line.split(), dtype=float)
                except ValueError as e:
                    raise ValueError(
                        f"while reading {filename}, on line {i_line + 1}: "
                        f"cannot convert {line} to a 3-vector!"
                    ) from e

                if len(coords) != 3:
                    raise ValueError(
                        f"while reading {filename}, on line {i_line + 1}: "
                        f"cannot convert {line} to a 3-vector!"
                    )

                instance_positions.append(coords)

        instance_positions = np.array(instance_positions) * ureg.m
        return cls(canopy_element=canopy_element, instance_positions=instance_positions)

    # --------------------------------------------------------------------------
    #                        Kernel dictionary generation
    # --------------------------------------------------------------------------

    def kernel_bsdfs(self, ctx: KernelDictContext) -> t.MutableMapping:
        """
        Return BSDF plugin specifications.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            Return a dictionary suitable for merge with a :class:`.KernelDict`
            containing all the BSDFs attached to the shapes in the leaf cloud.
        """
        return self.canopy_element.kernel_bsdfs(ctx=ctx)

    def kernel_shapes(self, ctx: KernelDictContext) -> t.Dict:
        """
        Return shape plugin specifications.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the shapes
            in the canopy.
        """
        return {
            self.canopy_element.id: {
                "type": "shapegroup",
                **self.canopy_element.kernel_shapes(ctx=ctx),
            }
        }

    def kernel_instances(self, ctx: KernelDictContext) -> t.Dict:
        """
        Return instance plugin specifications.

        Parameters
        ----------
        ctx : :class:`.KernelDictContext`
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing instances.
        """
        kernel_length = uck.get("length")

        return {
            f"{self.canopy_element.id}_instance_{i}": {
                "type": "instance",
                "group": {"type": "ref", "id": self.canopy_element.id},
                "to_world": mi.ScalarTransform4f.translate(position),
            }
            for i, position in enumerate(self.instance_positions.m_as(kernel_length))
        }

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        return KernelDict(
            {
                **self.kernel_bsdfs(ctx=ctx),
                **self.kernel_shapes(ctx=ctx),
                **self.kernel_instances(ctx=ctx),
            }
        )
