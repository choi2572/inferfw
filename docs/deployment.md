# Deployment

This document defines the MVP deployment direction for the inference service framework.

MVP deployment is focused on local process execution first. Docker, ROS2, DDS, GPU runtimes, and process supervision can be added after the fake loop and CLI are stable.

## 1. Deployment Goals

MVP deployment should:

- run the fake end-to-end loop on a development machine
- provide a stable CLI entrypoint
- use config paths for run selection
- write logs and resolved config to a run output directory
- support graceful shutdown
- keep optional ROS2/DDS/GPU dependencies isolated

MVP deployment should not require:

- robot hardware
- ROS2
- DDS
- GPU
- model checkpoints
- Docker
- distributed orchestration

## 2. Primary Execution Mode

Primary MVP execution mode:

```text
local Python process
  -> CLI entrypoint
  -> YAML config
  -> local plugin registry
  -> fake or selected runtime components
```

Target commands:

```bash
inferfw validate --config config/pipeline_example.yaml
inferfw run --config config/pipeline_example.yaml
inferfw list-plugins
```

The first deployable target is the canonical pipeline config with fake or selected runtime components depending on the installed plugins.

## 3. CLI Contract

### validate

```bash
inferfw validate --config config/pipeline_example.yaml
```

Expected behavior:

- load config
- register built-in plugins
- resolve request server, processor, and model runtime keys
- validate robot and model bindings
- print validation result
- exit non-zero on validation failure

### run

```bash
inferfw run --config config/pipeline_example.yaml
```

Expected behavior:

- validate config
- configure service
- load model
- warm up
- run service loop
- stop cleanly
- write logs

### list-plugins

```bash
inferfw list-plugins
```

Expected behavior:

- register built-in plugins
- print plugin keys grouped by type

## 4. Package Installation Direction

MVP can start with editable install:

```bash
pip install -e .
```

Recommended packaging:

```text
pyproject.toml
inferfw/
  cli.py
  ...
```

CLI entrypoint target:

```toml
[project.scripts]
inferfw = "inferfw.cli:main"
```

Exact packaging can be finalized during implementation.

## 5. Config Paths

Recommended project layout:

```text
config/
  pipeline_example.yaml
```

Path resolution policy:

- config path is passed explicitly
- model artifact paths are read from `pipeline.models.<model_id>.model_path`
- transport topics are read from model bindings and robot topics
- resolved config should record final resolved config path and model artifact paths

MVP can start with simple relative path resolution from project root or config file directory.

## 6. Run Output Directory

Default:

```text
runs/
  <run_id>/
    resolved_config.yaml
    events.jsonl
    summary.json
```

Required outputs:

- structured event log
- resolved config snapshot
- run summary

Optional future outputs:

- metrics file
- replay metadata
- sampled input/output summaries
- model artifact reference

Logs should avoid writing full images or large tensors by default.

## 7. Environment Variables

MVP should minimize required environment variables.

Potential variables:

```bash
INFERFW_PROFILE_PATH=profiles
INFERFW_PLUGIN_PATH=plugins
INFERFW_RUNS_DIR=runs
INFERFW_LOG_LEVEL=info
```

Optional future variables:

```bash
ROS_DOMAIN_ID=0
CYCLONEDDS_URI=...
CUDA_VISIBLE_DEVICES=0
```

Config values should take precedence over environment defaults where practical.

## 8. Optional Dependencies

Optional dependencies should be isolated by plugin.

Examples:

- ROS2 adapter may require `rclpy`
- DDS adapter may require robot vendor SDK or DDS bindings
- Torch runtime may require `torch`
- TensorRT runtime may require TensorRT libraries

MVP rule:

- importing framework core must not require optional dependencies
- fake run must work without optional dependencies
- selecting an optional plugin with missing dependencies should fail clearly during configure or plugin initialization

## 9. Docker Direction

Docker is optional for MVP.

Initial Docker targets, future:

- fake runtime image
- ROS2-enabled image
- GPU model runtime image
- robot-specific deployment image

Potential split:

```text
docker/
  Dockerfile.fake
  Dockerfile.ros2
  Dockerfile.gpu
```

MVP does not need to block on Docker. Local CLI execution comes first.

## 10. ROS2 and DDS Deployment

ROS2/DDS support should be plugin-scoped.

Real robot deployment will need:

- ROS2 environment sourced
- DDS domain configured
- robot network configured
- message types available
- adapter params configured
- command publish path verified

MVP real-oriented stubs can document required params without implementing full transport behavior.

Example:

```yaml
request_server:
  type: ros2

pipeline:
  models:
    g1_vla:
      runtime: openpi
      config_name: act_g1
      model_path: /workspace/sim_models/act_sim_model/
      input_interface:
        bindings:
          left_img:
            topic: /cam/left/image_raw_color/compressed
            message_type: sensor_msgs/CompressedImage

robot:
  topics:
    joint_command:
      topic: /joint/command/joint_state
      message_type: sensor_msgs/JointState
```

## 11. GPU and Model Runtime Deployment

GPU is not required for fake MVP.

Real model runtime deployment should document:

- runtime backend
- device selection
- checkpoint path
- CUDA/Torch/TensorRT requirements
- warmup behavior
- memory assumptions

Example:

```yaml
pipeline:
  models:
    g1_vla:
      runtime: openpi
      config_name: act_g1
      model_path: /models/openpi/checkpoint
```

Missing model artifacts or GPU dependencies should fail before `RUNNING`.

## 12. Graceful Shutdown

The runtime should handle stop requests by:

- exiting service loop
- stopping input adapter
- stopping output adapter
- unloading model runtime
- flushing logs
- returning non-zero exit code on unrecoverable failure

CLI should handle:

- normal completion
- `KeyboardInterrupt`
- config validation failure
- runtime error

## 13. Health and Status

MVP does not require a health server.

Minimal status should be available through logs:

- current lifecycle state
- last lifecycle transition
- last iteration id
- last error

Future health options:

- HTTP health endpoint
- metrics exporter
- process supervisor integration
- heartbeat file

## 14. Process Supervision

MVP does not require systemd, Kubernetes, or a scheduler.

Future deployment can add:

- systemd service
- Docker Compose
- Kubernetes Job or Deployment
- robot-specific launch scripts

Do not add orchestration before the local CLI path is stable.

## 15. Deployment Acceptance Criteria

MVP deployment is acceptable when:

- `inferfw validate --config ...` works for fake config
- `inferfw run --config ...` runs fake loop locally
- run output directory contains resolved config and event logs
- command exits cleanly after `max_iterations`
- framework import does not require ROS2/DDS/GPU/model dependencies
- missing optional plugin dependency produces clear error when selected
- SIGINT or stop request attempts cleanup and log flush
