"""In-process ModelRuntime that wraps openpi Policy (no WebSocket)."""

from __future__ import annotations

import logging

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput

logger = logging.getLogger(__name__)

_WARMUP_ITERATIONS = 3


def _cuda_synchronize() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.synchronize()


class OpenPiModelRuntime:
    """Loads a trained openpi policy and calls Policy.infer in-process."""

    def __init__(self) -> None:
        self._config_name: str | None = None
        self._model_path: str | None = None
        self._model = None

    def configure(self, params: dict) -> None:
        config_name = params.get("config_name")
        model_path = params.get("model_path")
        if not config_name or not model_path:
            msg = "openpi model_runtime requires 'config_name' and 'model_path' in params."
            raise ValueError(msg)
        self._config_name = str(config_name)
        self._model_path = str(model_path)

    def load_model(self) -> None:
        if self._config_name is None or self._model_path is None:
            msg = "Model runtime is not configured; call configure() first."
            raise RuntimeError(msg)

        import openpi.training.config as config_
        from openpi.policies import policy_config

        config = config_.get_config(self._config_name)
        logger.info("Loading openpi policy (config=%s, path=%s)", self._config_name, self._model_path)
        self._model = policy_config.create_trained_policy(config, self._model_path)

    def warmup(self, sample: ModelInput | None = None) -> None:
        if self._model is None:
            msg = "Policy is not loaded; call load_model() first."
            raise RuntimeError(msg)
        if sample is None:
            msg = "openpi warmup requires a ModelInput sample (e.g. from openpi_input_builder)."
            raise ValueError(msg)

        for _ in range(_WARMUP_ITERATIONS):
            _ = self._model.infer(sample.data)
            _cuda_synchronize()

    def infer(self, model_input: ModelInput) -> ModelOutput:
        if self._model is None:
            msg = "Policy is not loaded; call load_model() first."
            raise RuntimeError(msg)

        policy_output = self._model.infer(model_input.data)
        _cuda_synchronize()
        return self._to_model_output(policy_output)

    @staticmethod
    def _to_model_output(policy_output: dict) -> ModelOutput:
        return ModelOutput.from_dict({"actions": policy_output["actions"]})

    def unload(self) -> None:
        self._model = None
