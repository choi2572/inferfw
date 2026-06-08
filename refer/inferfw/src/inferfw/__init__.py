"""Inference service framework core."""

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput
from inferfw.interfaces.model_runtime import ModelRuntime

__all__ = ["ModelInput", "ModelOutput", "ModelRuntime"]
