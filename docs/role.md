# Roles and Ownership

This document defines ownership boundaries for the inference service framework.

The framework is designed so that model developers, robot integrators, framework developers, experiment users, and deploy/ops owners can work independently and connect components through interfaces, configs, and plugins.

The primary product goal is an inference service framework for embodied AI model evaluation MLOps. The MVP goal is narrower: a runnable single-service inference loop with clear ownership boundaries.

## 1. Ownership Summary

| Role | Owns | Does Not Own |
| --- | --- | --- |
| Framework Developer | runtime core, lifecycle, pipeline execution, config loading, validation, logging hooks | robot semantics, model semantics, IK/FK, concrete robot mappings |
| Model Developer | model runtime, model profile, model-specific processors, model IO schema | robot command protocol, robot joint layout, service orchestration |
| Robot Integrator | robot profile, observation mapper, action mapper, robot-specific processors, IO presets | model internals, model checkpoint loading, core lifecycle |
| Integration / Experiment User | run config, selected robot/model/plugins, evaluation run parameters | core implementation, robot/model plugin implementation |
| Deploy / Ops Owner | runtime environment, packaging, process launch, logs/artifacts location, health checks | model semantics, robot semantic mapping, framework API design |

## 2. Framework Developer

Framework developers own the reusable runtime core.

### Responsibilities

- lifecycle management
- service loop and pipeline execution
- plugin registry and component resolution
- processor chain runner
- adapter interfaces
- model runtime interface
- canonical data structures
- config loading
- validation framework
- structured logging and metrics hooks
- runtime orchestration

### Owns

Example package area:

```text
inferfw/
  core/
  lifecycle/
  registry/
  pipeline/
  logging/
  validation/
```

### Does Not Own

Framework core must not directly contain:

- robot-specific logic
- model-specific logic
- IK/FK implementation
- concrete robot mappings
- model preprocess/postprocess semantics
- hard-coded ROS2/DDS topic conventions for a specific robot
- hard-coded checkpoint or model artifact assumptions

Those belong to plugins, profiles, adapters, or run configs.

### Must Provide

- stable interfaces for plugins
- runtime context passed to components
- config validation errors that are actionable
- lifecycle transition validation
- deterministic processor chain execution
- fake components for local smoke tests

## 3. Model Developer

Model developers own model runtime behavior and model-specific transformations.

### Responsibilities

- implement `ModelRuntime`
- define model input/output schema
- implement model-specific preprocess/postprocess processors
- provide model metadata, runtime presets, or schemas needed by validation
- provide model artifact metadata
- optionally provide warmup sample input
- document runtime dependencies such as Torch, TensorRT, ONNX Runtime, tokenizers, or remote API clients

### Owns

Example plugin area:

```text
inferfw_openpi/
  runtime.py
  processors.py
  io_schema.py
  warmup.py
  pyproject.toml
```

The package can be distributed separately from framework core. For example, `inferfw-openpi` may depend on `openpi`, register an `openpi` `ModelRuntime`, and provide `openpi_input_builder` / `openpi_output_parser` processors.

### Must Implement

Minimum runtime interface:

```python
class ModelRuntime:
    def configure(self, config, context): ...
    def load(self): ...
    def warmup(self, sample_input): ...
    def infer(self, model_input): ...
    def unload(self): ...
```

Primary contract:

```text
infer(model_input) -> model_output
```

### Must Define

Input requirements:

- required image keys
- proprioception dimensions
- instruction format
- tensor dtype and shape
- normalization expectations
- device requirements, if any

Output format:

- action dimensions
- trajectory format
- pose convention
- coordinate frame
- units
- confidence or auxiliary outputs, if any

### Does Not Own

Model plugins must not own:

- robot-specific command packet construction
- robot joint group definitions
- robot transport publish logic
- framework lifecycle transitions
- global logging policy

Model-specific postprocessing can produce `CanonicalAction` or an intermediate output consumed by another processor, but final robot command generation belongs to `ActionMapper`.

## 4. Robot Integrator

Robot integrators own robot-specific semantic mapping and robot execution conventions.

### Responsibilities

- implement `ObservationMapper`
- implement `ActionMapper`
- provide robot profile
- provide robot-specific processors
- provide IK/FK plugins when needed
- provide IO presets for common deployments
- document robot command conventions and safety-relevant limits

### Owns

Example plugin area:

```text
plugins/
  unitree_g1/
    robot_profile.yaml
    observation_mapper.py
    action_mapper.py
    processors.py
    ik.py
    io_presets.yaml
```

### ObservationMapper Contract

Converts:

```text
raw robot observation -> CanonicalObservation
```

Example:

```text
29DOF joint array -> left_arm / right_arm / waist groups
```

### ActionMapper Contract

Converts:

```text
CanonicalAction -> robot-specific command
```

Example:

```text
joint_targets -> Unitree DDS LowCmd
```

### Robot Profile Must Define

- joint groups
- joint limits
- sensor metadata
- camera names and frame metadata
- frame mapping
- gripper or hand metadata
- command conventions
- control frequency expectations
- default IO presets, if available

### Does Not Own

Robot plugins must not own:

- model checkpoint loading
- model input tensor construction, except robot-specific transform processors
- framework lifecycle orchestration
- experiment run selection
- global deployment packaging

## 5. Integration / Experiment User

Integration users assemble the final runtime configuration for a model evaluation run.

### Responsibilities

- select model profile and runtime
- select robot profile
- choose input and output adapters
- compose preprocess and postprocess chains
- configure runtime parameters
- configure logging output
- run validation before execution
- capture run metadata for evaluation

### Owns

Example config area:

```text
config/
  pipeline_example.yaml
```

Example pipeline config:

```yaml
request_server:
  type: ros2
  node_name: inferfw

robot:
  name: g129dof
  action_class: G1Action
  loop_hz: 30.0

pipeline:
  name: g129dof_vla_test1
  preprocess:
    groups:
      - keys: [left_img, right_img]
        steps:
          - name: resize
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
      output_interface:
        bindings:
          actions:
            type: joint_trajectory
  postprocess:
    groups:
      - keys: [actions]
        steps:
          - name: smooth_action
```

### Does Not Own

Integration users should not need to modify:

- framework core
- robot mapper code
- model runtime code
- plugin registry internals

If a run requires code changes in these areas, the change should be treated as framework, model plugin, or robot plugin work.

## 6. Deploy / Ops Owner

Deploy/ops owners make the service runnable in the target environment.

For MVP, this can be the same person as the framework developer or integration user. The role is still documented because ROS2, DDS, GPU runtimes, and model dependencies can make deployment behavior part of the system contract.

### Responsibilities

- define local process execution
- define Docker image strategy, if used
- manage Python and system dependencies
- manage ROS2/DDS runtime environment
- manage GPU runtime requirements
- configure environment variables
- define log and artifact output locations
- define health check and process supervision strategy
- define graceful shutdown behavior

### Owns

Example deployment area:

```text
deploy/
  docker/
  systemd/
scripts/
  run_local.sh
```

MVP does not require these directories to exist immediately, but deployment decisions should be documented before the first real robot integration.

### Does Not Own

Deploy/ops owners should not need to understand:

- model tensor semantics
- robot joint mapping internals
- processor implementation details

They do need clear config, dependency, and runtime entrypoint contracts.

## 7. Boundary Rules

These rules are intended to keep the MVP implementation from becoming tightly coupled.

- Framework core must not import robot-specific or model-specific plugins.
- Plugins depend on core interfaces, not on core internals.
- Configs compose components; they do not define new behavior.
- Profiles describe metadata and conventions; they do not execute runtime logic.
- Adapters move bytes or messages across process/system boundaries; they do not perform semantic mapping.
- Mappers perform robot semantic mapping; they do not perform model-specific preprocessing.
- Processors transform data between explicit stages; they should be deterministic unless documented otherwise.
- ModelRuntime performs model lifecycle and inference; it does not publish robot commands.
- OutputAdapter publishes commands; it does not decide what the command means.

## 8. MVP Ownership Acceptance Criteria

The MVP ownership model is considered healthy if:

- a dummy model runtime can be swapped with a real model runtime without editing framework core
- a fake robot plugin can be swapped with a real robot plugin without editing model runtime code
- a fake input/output setup can run end-to-end without ROS2 or DDS installed
- config validation fails before execution when a required plugin, profile, or processor is missing
- run logs identify the selected model, robot, adapters, processors, and config
- tests can verify lifecycle, processor chain, registry, and fake end-to-end execution without hardware

## 9. Design Goal

The main goal of ownership separation is:

- robot developers should not need to modify framework core
- model developers should not need to understand robot internals
- framework developers should not need to implement robot/model semantics
- integration users should be able to assemble runs through configs
- deploy/ops owners should be able to run the service from documented entrypoints and environment requirements

All components should connect through:

- interfaces
- canonical data structures
- configs
- profiles
- plugins
