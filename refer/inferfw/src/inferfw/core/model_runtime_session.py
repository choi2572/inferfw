"""Minimal lifecycle wrapper around a ModelRuntime (MVP; not full InferenceService)."""

from __future__ import annotations

import time

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput
from inferfw.errors import ModelRuntimeError
from inferfw.interfaces.model_runtime import ModelRuntime


class ModelRuntimeSession:
    """Drives configure -> load_model -> warmup -> infer -> unload for one runtime."""

    def __init__(self, runtime: ModelRuntime) -> None:
        self._runtime = runtime
        self._loaded = False
        self._warmed_up = False

    @property
    def runtime(self) -> ModelRuntime:
        return self._runtime

    def startup(self, warmup_sample: ModelInput | None = None) -> None:
        try:
            self._runtime.load_model()
            self._loaded = True
            self._runtime.warmup(warmup_sample)
            self._warmed_up = True
        except Exception as e:
            raise ModelRuntimeError(f"Model runtime startup failed: {e}") from e

    def infer(self, model_input: ModelInput) -> tuple[ModelOutput, float]:
        if not self._warmed_up:
            msg = "Model runtime session is not warmed up; call startup() first."
            raise ModelRuntimeError(msg)
        start = time.perf_counter()
        try:
            output = self._runtime.infer(model_input)
        except Exception as e:
            raise ModelRuntimeError(f"Model runtime infer failed: {e}") from e
        latency_ms = (time.perf_counter() - start) * 1000.0
        return output, latency_ms

    def shutdown(self) -> None:
        if self._loaded:
            self._runtime.unload()
        self._loaded = False
        self._warmed_up = False
