"""Generic containers at the model boundary (backend-agnostic)."""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class ModelInput:
    """Payload passed into ModelRuntime.infer after preprocess.

    Backends may use different dict schemas. π/VLA uses PIInput as a typed helper.
    """

    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelInput:
        return cls(data=dict(data))


@dataclasses.dataclass
class ModelOutput:
    """Payload returned from ModelRuntime.infer before postprocess."""

    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelOutput:
        return cls(data=dict(data))
