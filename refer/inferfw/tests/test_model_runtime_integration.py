"""End-to-end ModelRuntime path: registry -> session -> infer (no full InferenceService)."""

from __future__ import annotations

import importlib.metadata

import numpy as np
import pytest

from inferfw.core.model_runtime_session import ModelRuntimeSession
from inferfw.data.model import ModelInput
from inferfw.registry.registry import create_model_runtime
from inferfw.registry.registry import get_model_runtime_class


def test_dummy_runtime_via_entry_point():
    runtime = create_model_runtime(
        "dummy",
        params={"action_horizon": 2, "action_dim": 3},
    )
    session = ModelRuntimeSession(runtime)

    warmup = ModelInput.from_dict({"state": np.ones(3, dtype=np.float64)})
    session.startup(warmup)

    out, latency_ms = session.infer(ModelInput.from_dict({"state": np.array([1.0, 2.0, 3.0])}))
    session.shutdown()

    assert out.data["actions"].shape == (2, 3)
    assert latency_ms >= 0.0


def test_model_input_carries_backend_specific_payload():
    model_input = ModelInput.from_dict({"state": np.ones(44), "prompt": "pick"})
    assert model_input.data["prompt"] == "pick"
    assert model_input.data["state"].shape == (44,)


def test_openpi_runtime_class_is_registered_when_plugin_installed():
    eps = {ep.name for ep in importlib.metadata.entry_points(group="inferfw.model_runtime")}
    assert "dummy" in eps
    if "openpi" not in eps:
        pytest.skip("inferfw-openpi is not installed in this environment")

    cls = get_model_runtime_class("openpi")
    assert cls.__name__ == "OpenPiModelRuntime"
