"""Framework error types."""


class InferfwError(Exception):
    """Base error for inferfw."""


class PluginResolutionError(InferfwError):
    """Failed to resolve a plugin by type name."""


class ModelRuntimeError(InferfwError):
    """Error raised from a model runtime boundary."""
