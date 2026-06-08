"""Unit tests for OpenPiModelRuntime without loading real checkpoints."""

from __future__ import annotations

import numpy as np

from inferfw.data.model import ModelInput
from inferfw.data.pi import PIInput
from inferfw.data.pi import PIOutput
from inferfw_openpi.runtime import OpenPiModelRuntime


def test_pi_output_round_trip_via_model_output():
    actions = np.arange(6, dtype=np.float64).reshape(2, 3)
    model_output = PIOutput.from_actions(actions).to_model_output()
    restored = PIOutput.from_model_output(model_output)
    assert np.allclose(restored.actions, actions)


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

    model_input = PIInput().to_model_input()
    runtime.warmup(model_input)
    output = runtime.infer(model_input)
    runtime.unload()

    assert output.data["actions"].shape == (2, 4)
    assert len(output.data["data"]) == 8
