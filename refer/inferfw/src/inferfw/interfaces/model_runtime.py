"""Model runtime plugin contract."""

from __future__ import annotations

from typing import Protocol
from typing import runtime_checkable

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput


@runtime_checkable
class ModelRuntime(Protocol):
    """Owns model lifecycle and inference. Implementations live in plugin packages."""

    def configure(self, params: dict) -> None:
        """Apply runtime params from run config (called before load_model)."""

    def load_model(self) -> None:
        """Load model weights and build inference handles."""

    def warmup(self, sample: ModelInput | None = None) -> None:
        """Run inference warmup before the service loop."""

    def infer(self, model_input: ModelInput) -> ModelOutput:
        """Run a single inference step."""

    def unload(self) -> None:
        """Release model resources."""
