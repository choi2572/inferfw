"""Typed helpers for the π / openpi model I/O schema (one backend among many)."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput


def default_pi_input_data() -> dict[str, Any]:
    return {
        "state": np.zeros(44, dtype=np.float64),
        "images": {
            "cam_high_left": np.zeros((3, 500, 800), dtype=np.uint8),
            "cam_high_right": np.zeros((3, 500, 800), dtype=np.uint8),
            "cam_left_wrist": np.zeros((3, 480, 640), dtype=np.uint8),
            "cam_right_wrist": np.zeros((3, 480, 640), dtype=np.uint8),
        },
        "prompt": "prompt string",
    }


@dataclasses.dataclass
class PIInput:
    """π-model input schema. Convert to ModelInput at the runtime boundary."""

    data: dict[str, Any] = dataclasses.field(default_factory=default_pi_input_data)

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def to_model_input(self) -> ModelInput:
        return ModelInput(data=dict(self.data))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PIInput:
        return cls(data=dict(data))

    @classmethod
    def from_model_input(cls, model_input: ModelInput) -> PIInput:
        return cls(data=dict(model_input.data))


@dataclasses.dataclass(frozen=True)
class MultiArrayDimension:
    label: str
    size: int
    stride: int


@dataclasses.dataclass(frozen=True)
class MultiArrayLayout:
    dim: tuple[MultiArrayDimension, ...]
    data_offset: int = 0


@dataclasses.dataclass
class PIOutput:
    """π-model output schema (Float64MultiArray-equivalent, no ROS2)."""

    layout: MultiArrayLayout
    data: list[float]

    @classmethod
    def from_actions(cls, actions: np.ndarray) -> PIOutput:
        actions = np.asarray(actions, dtype=np.float64)
        layout = MultiArrayLayout(
            dim=(
                MultiArrayDimension(label="chunk_size", size=actions.shape[0], stride=actions.size),
                MultiArrayDimension(label="action_dim", size=actions.shape[1], stride=actions.shape[1]),
            ),
            data_offset=0,
        )
        return cls(layout=layout, data=actions.flatten().tolist())

    @property
    def actions(self) -> np.ndarray:
        chunk_size = self.layout.dim[0].size
        action_dim = self.layout.dim[1].size
        return np.asarray(self.data, dtype=np.float64).reshape(chunk_size, action_dim)

    def to_model_output(self) -> ModelOutput:
        return ModelOutput(
            data={
                "layout": {
                    "dim": [
                        {"label": d.label, "size": d.size, "stride": d.stride}
                        for d in self.layout.dim
                    ],
                    "data_offset": self.layout.data_offset,
                },
                "data": list(self.data),
                "actions": self.actions,
            }
        )

    @classmethod
    def from_model_output(cls, model_output: ModelOutput) -> PIOutput:
        if "actions" in model_output.data:
            return cls.from_actions(model_output.data["actions"])
        layout = model_output.data["layout"]
        dims = tuple(
            MultiArrayDimension(label=d["label"], size=d["size"], stride=d["stride"])
            for d in layout["dim"]
        )
        return cls(
            layout=MultiArrayLayout(dim=dims, data_offset=layout["data_offset"]),
            data=list(model_output.data["data"]),
        )
