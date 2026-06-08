"""Built-in fallbacks not declared via entry points (MVP)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inferfw.interfaces.model_runtime import ModelRuntime

# Populated lazily to avoid import cycles; dummy is also registered via entry point.
BUILTIN_MODEL_RUNTIMES: dict[str, type[ModelRuntime]] = {}
