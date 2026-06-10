#!/usr/bin/env python3
"""Reference script: run openpi in-process via inferfw ModelRuntime.

Copy or adapt this when wiring inferfw-openpi into another service/repo.

Prerequisites (editable install example):
  pip install -e path/to/inferfw
  pip install -e path/to/inferfw-openpi
  pip install -e path/to/openpi

Usage:
  python run_model_runtime.py \\
    --config-name pi0_aloha_sim \\
    --model-path gs://openpi-assets/checkpoints/pi0_aloha_sim \\
    --prompt "pick up the block"

  # GPU / checkpoint not required (pipeline smoke test):
  python run_model_runtime.py --runtime dummy
"""

from __future__ import annotations

import dataclasses
import logging
import sys

import numpy as np
import tyro

from inferfw.core.model_runtime_session import ModelRuntimeSession
from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput
from inferfw.registry.registry import create_model_runtime


@dataclasses.dataclass
class Args:
    """CLI args for a single startup -> infer -> shutdown cycle."""

    # Registry type: "openpi" (default) or "dummy" for a lightweight smoke test.
    runtime: str = "openpi"

    # openpi TrainConfig name and checkpoint path (ignored for dummy runtime).
    config_name: str = "pi0_aloha_sim"
    model_path: str = "gs://openpi-assets/checkpoints/pi0_aloha_sim"

    # Task instruction passed in ModelInput.data["prompt"].
    prompt: str = "pick up the block"


def build_model_input(prompt: str) -> ModelInput:
    """Build one ModelInput for π/openpi runtimes.

    Replace this with openpi_input_builder output when integrating elsewhere.
    """
    return ModelInput.from_dict(
        {
            "state": np.zeros(44, dtype=np.float64),
            "images": {
                "cam_high_left": np.zeros((3, 500, 800), dtype=np.uint8),
                "cam_high_right": np.zeros((3, 500, 800), dtype=np.uint8),
                "cam_left_wrist": np.zeros((3, 480, 640), dtype=np.uint8),
                "cam_right_wrist": np.zeros((3, 480, 640), dtype=np.uint8),
            },
            "prompt": prompt,
        }
    )


def print_output(output: ModelOutput, latency_ms: float) -> None:
    actions = np.asarray(output.data["actions"], dtype=np.float64)
    logging.info("infer latency_ms=%.2f", latency_ms)
    logging.info("actions shape=%s", actions.shape)
    logging.info("actions[0][:8]=%s", actions[0, : min(8, actions.shape[1])])


def main(args: Args) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.runtime == "openpi":
        runtime_params = {
            "config_name": args.config_name,
            "model_path": args.model_path,
        }
    elif args.runtime == "dummy":
        runtime_params = {"action_horizon": 4, "action_dim": 8}
    else:
        logging.error("Unknown runtime %r. Use 'openpi' or 'dummy'.", args.runtime)
        return 1

    logging.info("Creating model runtime: type=%s", args.runtime)
    runtime = create_model_runtime(args.runtime, params=runtime_params)
    session = ModelRuntimeSession(runtime)

    model_input = build_model_input(args.prompt)
    if args.runtime == "dummy":
        # dummy runtime only needs state; keep the call shape similar.
        state = np.zeros(8, dtype=np.float64)
        model_input = ModelInput.from_dict({"state": state, "prompt": args.prompt})

    try:
        logging.info("startup: load_model + warmup")
        session.startup(model_input)

        logging.info("infer")
        output, latency_ms = session.infer(model_input)
        print_output(output, latency_ms)
    finally:
        logging.info("shutdown")
        session.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main(tyro.cli(Args)))
