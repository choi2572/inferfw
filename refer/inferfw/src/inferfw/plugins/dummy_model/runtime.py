"""Fake model runtime for pipeline tests without GPU or checkpoints."""

from __future__ import annotations

import numpy as np

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput


class DummyModelRuntime:
    """Returns deterministic actions from state dim hints in params."""

    def __init__(self) -> None:
        self._params: dict = {}
        self._action_horizon = 1
        self._action_dim = 4

    def configure(self, params: dict) -> None:
        self._params = dict(params)
        self._action_horizon = int(params.get("action_horizon", 1))
        self._action_dim = int(params.get("action_dim", 4))

    def load_model(self) -> None:
        pass

    def warmup(self, sample: ModelInput | None = None) -> None:
        _ = self.infer(sample or ModelInput.from_dict({"state": np.zeros(self._action_dim)}))

    def infer(self, model_input: ModelInput) -> ModelOutput:
        state = np.asarray(model_input.data.get("state", np.zeros(self._action_dim)))
        dim = min(state.shape[-1], self._action_dim)
        chunk = np.zeros((self._action_horizon, self._action_dim), dtype=np.float64)
        chunk[:, :dim] = state[..., :dim]
        return ModelOutput.from_dict({"actions": chunk, "runtime": "dummy"})

    def unload(self) -> None:
        pass
