"""Plugin resolution via entry points (core does not import concrete plugins)."""

from __future__ import annotations

import importlib.metadata

from inferfw.errors import PluginResolutionError
from inferfw.interfaces.model_runtime import ModelRuntime
from inferfw.registry import builtin as _builtin


_ENTRY_POINT_GROUP = "inferfw.model_runtime"


def _load_entry_point_classes() -> dict[str, type[ModelRuntime]]:
    classes: dict[str, type[ModelRuntime]] = {}
    for entry in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        cls = entry.load()
        if not isinstance(cls, type):
            msg = f"Entry point {entry.name!r} must load a class, got {type(cls)}"
            raise PluginResolutionError(msg)
        classes[entry.name] = cls
    return classes


def get_model_runtime_class(type_name: str) -> type[ModelRuntime]:
    """Resolve a ModelRuntime implementation class by config type name."""
    entry_classes = _load_entry_point_classes()
    merged = {**_builtin.BUILTIN_MODEL_RUNTIMES, **entry_classes}
    if type_name not in merged:
        available = ", ".join(sorted(merged))
        msg = f"Unknown model_runtime type {type_name!r}. Available: {available}"
        raise PluginResolutionError(msg)
    return merged[type_name]


def create_model_runtime(type_name: str, params: dict | None = None) -> ModelRuntime:
    """Instantiate and configure a model runtime."""
    cls = get_model_runtime_class(type_name)
    runtime = cls()
    runtime.configure(params or {})
    return runtime
