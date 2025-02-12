import typing as t
from abc import ABC

import attrs

from ..core import SceneElement
from ..._factory import Factory
from ...attrs import documented, get_doc, parse_docs

phase_function_factory = Factory()
phase_function_factory.register_lazy_batch(
    [
        (
            "_blend.BlendPhaseFunction",
            "blend_phase",
            {},
        ),
        (
            "_hg.HenyeyGreensteinPhaseFunction",
            "hg",
            {},
        ),
        (
            "_isotropic.IsotropicPhaseFunction",
            "isotropic",
            {},
        ),
        (
            "_rayleigh.RayleighPhaseFunction",
            "rayleigh",
            {},
        ),
        (
            "_tabulated.TabulatedPhaseFunction",
            "tab_phase",
            {},
        ),
    ],
    cls_prefix="eradiate.scenes.phase",
)


@parse_docs
@attrs.define
class PhaseFunction(SceneElement, ABC):
    """
    An abstract base class defining common facilities for all phase functions.
    """

    id: t.Optional[str] = documented(
        attrs.field(
            default="phase",
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc=get_doc(SceneElement, "id", "doc"),
        type=get_doc(SceneElement, "id", "type"),
        init_type=get_doc(SceneElement, "id", "init_type"),
        default='"phase"',
    )
