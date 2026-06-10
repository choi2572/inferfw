"""Unit tests for OpenPiModelRuntime without loading real checkpoints."""

from __future__ import annotations

import numpy as np

from inferfw.data.model import ModelInput
from inferfw_openpi.runtime import OpenPiModelRuntime


def test_model_output_carries_openpi_actions():
    actions = np.arange(6, dtype=np.float64).reshape(2, 3)
    output = OpenPiModelRuntime._to_model_output({"actions": actions})
    assert np.allclose(output.data["actions"], actions)


def test_openpi_runtime_infer_with_mock_policy(monkeypatch):
    class _FakePolicy:
        def infer(self, obs: dict) -> dict:
            state = np.asarray(obs["state"])
            return {"actions": np.stack([state[:4], state[:4]])}

    monkeypatch.setattr(
        "openpi.policies.policy_config.create_trained_policy",
        lambda *_a, **_k: _FakePolicy(),
    )

    runtime = OpenPiModelRuntime()
    runtime.configure({"config_name": "pi0_aloha_sim", "model_path": "/tmp/fake"})
    runtime.load_model()

    model_input = ModelInput.from_dict({"state": np.zeros(44, dtype=np.float64), "prompt": "test"})
    runtime.warmup(model_input)
    output = runtime.infer(model_input)
    runtime.unload()

    assert output.data["actions"].shape == (2, 4)
