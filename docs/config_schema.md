# Config Schema

This document defines the MVP configuration structure for the inference service framework.

MVP execution should be config-driven. A user should be able to change model runtime, robot mapping, adapters, processors, and logging behavior without editing framework core.

The examples below are target schemas. Exact Python validation models can be refined during implementation.

## 1. Config Goals

The config system should:

- assemble a runnable inference service
- select model, robot, adapters, processors, and logging
- validate missing or unknown components before execution
- support fake end-to-end execution without ROS2/DDS/model dependencies
- preserve run metadata for evaluation and reproducibility

The config system should not:

- contain executable code
- hide plugin implementation details in arbitrary scripts
- require framework core edits for a new model or robot
- silently ignore unknown required fields

## 2. Config Files

MVP uses three primary config/profile file types.

```text
configs/
  mvp_fake.yaml
  mvp_g1_vla.yaml

profiles/
  robots/
    fake_robot.yaml
    unitree_g1.yaml
  models/
    dummy_model.yaml
    openpi_vla.yaml
```

For docs examples, these can live under:

```text
docs/examples/
  mvp_run.yaml
  robot_profile.yaml
  model_profile.yaml
```

## 3. Main Run Config

The main run config defines what components are connected for one service execution.

Example:

```yaml
version: 1

run:
  name: mvp_fake
  description: fake end-to-end inference service smoke run
  seed: 0

robot:
  profile: fake_robot
  observation_mapper: fake_observation_mapper
  action_mapper: fake_action_mapper

model:
  profile: dummy_model
  runtime: dummy_runtime
  params:
    latency_ms: 1

input:
  type: fake
  params:
    num_messages: 1
    timeout_ms: 100

output:
  type: fake
  params:
    capture: true

preprocess:
  - type: identity
  - type: dummy_input_builder

postprocess:
  - type: dummy_output_parser
  - type: validate_action

lifecycle:
  warmup: true
  max_iterations: 1
  stop_on_error: true

logging:
  level: info
  output_dir: runs/
  write_resolved_config: true
  write_iteration_summary: true
```

## 4. Main Run Config Schema

### 4.1 Top-Level Fields

```yaml
version: 1
run: {}
robot: {}
model: {}
input: {}
output: {}
preprocess: []
postprocess: []
lifecycle: {}
logging: {}
```

Required:

- `version`
- `run`
- `robot`
- `model`
- `input`
- `output`
- `preprocess`
- `postprocess`
- `lifecycle`
- `logging`

### 4.2 `run`

```yaml
run:
  name: mvp_fake
  description: optional text
  seed: 0
  tags:
    - smoke
    - fake
```

Fields:

- `name`: human-readable run name
- `description`: optional run description
- `seed`: optional deterministic seed
- `tags`: optional labels for filtering

The framework should generate a unique `run_id` at runtime.

### 4.3 `robot`

```yaml
robot:
  profile: unitree_g1
  observation_mapper: unitree_g1_observation_mapper
  action_mapper: unitree_g1_action_mapper
  params:
    control_mode: joint_position
```

Fields:

- `profile`: robot profile id or path
- `observation_mapper`: registry key
- `action_mapper`: registry key
- `params`: optional robot integration params

Validation:

- profile must resolve
- mapper types must be registered
- profile must satisfy mapper requirements when declared

### 4.4 `model`

```yaml
model:
  profile: openpi_vla
  runtime: openpi_torch
  params:
    device: cuda:0
    checkpoint: /models/openpi/checkpoint.pt
```

Fields:

- `profile`: model profile id or path
- `runtime`: model runtime registry key
- `params`: runtime-specific params

Validation:

- profile must resolve
- runtime type must be registered
- required runtime params must exist when declared by the plugin or profile

### 4.5 `input`

```yaml
input:
  type: ros2
  params:
    observation_topic: /robot/observation
    timeout_ms: 100
```

Fields:

- `type`: input adapter registry key
- `params`: adapter-specific params

Validation:

- adapter type must be registered
- timeout behavior should be explicit for adapters that block

### 4.6 `output`

```yaml
output:
  type: unitree_dds
  params:
    domain_id: 0
```

Fields:

- `type`: output adapter registry key
- `params`: adapter-specific params

Validation:

- adapter type must be registered
- required output params must exist

### 4.7 `preprocess` and `postprocess`

Processor lists are ordered.

```yaml
preprocess:
  - type: resize_image
    params:
      camera: front
      width: 224
      height: 224
  - type: openpi_input_builder

postprocess:
  - type: openpi_output_parser
  - type: clamp_joint_limits
    params:
      source: robot_profile
```

Processor fields:

- `type`: processor registry key
- `params`: optional processor-specific params
- `enabled`: optional boolean, defaults to true

Validation:

- processor type must be registered
- disabled processors may be skipped
- each processor config must match the processor's declared requirements when available

### 4.8 `lifecycle`

```yaml
lifecycle:
  warmup: true
  max_iterations: 1
  loop_hz: 10
  stop_on_error: true
  pause_policy:
    read_input: true
    run_inference: false
    publish_output: false
```

Fields:

- `warmup`: whether to run warmup before normal inference
- `max_iterations`: optional finite iteration limit for smoke tests
- `loop_hz`: optional target loop frequency
- `stop_on_error`: whether first loop error stops service
- `pause_policy`: optional pause behavior

MVP default pause policy:

```yaml
pause_policy:
  read_input: true
  run_inference: false
  publish_output: false
```

### 4.9 `logging`

```yaml
logging:
  level: info
  output_dir: runs/
  write_resolved_config: true
  write_iteration_summary: true
  include_data_summaries: true
```

Fields:

- `level`: debug, info, warning, error
- `output_dir`: base directory for run logs
- `write_resolved_config`: save final resolved config
- `write_iteration_summary`: save per-iteration summaries
- `include_data_summaries`: log keys/shapes/dtypes where possible

MVP logs should not serialize full images or large tensors by default.

## 5. Robot Profile Schema

Robot profile describes robot metadata and conventions.

Example:

```yaml
version: 1

id: fake_robot
name: Fake Robot

joints:
  groups:
    arm:
      names:
        - joint_1
        - joint_2
      limits:
        position:
          min: [-1.0, -1.0]
          max: [1.0, 1.0]
        velocity:
          max: [2.0, 2.0]

sensors:
  cameras:
    front:
      width: 640
      height: 480
      channels: 3
      encoding: rgb8
      frame_id: camera_front

frames:
  base: base_link
  world: world

commands:
  default_mode: joint_position
  frequency_hz: 10

io_presets:
  fake:
    input:
      type: fake
    output:
      type: fake
```

### Required Robot Profile Fields

- `version`
- `id`
- `name`

MVP fake profile should define at least:

- one joint group
- one camera or image-like sensor
- one command convention

Real robot profiles should define:

- joint groups
- joint limits
- sensor metadata
- frame metadata
- command conventions
- IO presets, if useful

## 6. Model Profile Schema

Model profile describes model IO contracts and runtime requirements.

Example:

```yaml
version: 1

id: dummy_model
name: Dummy Model

runtime:
  default: dummy_runtime
  supported:
    - dummy_runtime

input_schema:
  required:
    image:
      dtype: float32
      shape: [1, 3, 224, 224]
    proprio:
      dtype: float32
      shape: [1, 2]

output_schema:
  required:
    action:
      dtype: float32
      shape: [1, 2]

frequency:
  target_hz: 10

latency:
  expected_ms: 1

artifact:
  type: none

warmup:
  sample: generated
```

### Required Model Profile Fields

- `version`
- `id`
- `name`
- `runtime`
- `input_schema`
- `output_schema`

Real model profiles should also define:

- artifact location or resolution rule
- device requirements
- preprocessing expectations
- output conventions
- warmup sample strategy

## 7. Plugin References

MVP uses registry keys for plugin references.

Examples:

```yaml
input:
  type: fake

model:
  runtime: dummy_runtime

preprocess:
  - type: dummy_input_builder
```

Rules:

- registry key names should be stable
- config validation fails if a key cannot be resolved
- package discovery is not required for MVP
- aliases may be added later, but canonical keys should be logged

## 8. Resolved Config

The runtime should produce a resolved config snapshot after validation.

Resolved config should include:

- generated `run_id`
- config file path
- robot profile content or resolved path
- model profile content or resolved path
- canonical plugin keys
- processor chain after disabled items are removed
- logging output path

The resolved config snapshot should be written to the run output directory when `write_resolved_config` is enabled.

## 9. Validation Rules

MVP validation should fail before service execution when:

- required top-level section is missing
- config version is unsupported
- robot profile cannot be found
- model profile cannot be found
- adapter type is not registered
- mapper type is not registered
- model runtime type is not registered
- processor type is not registered
- required adapter params are missing
- required model runtime params are missing
- processor config is malformed
- logging output directory cannot be created
- model profile runtime does not allow selected runtime

Validation warnings may be used for:

- unknown optional fields
- missing latency hints
- missing IO presets
- missing warmup sample
- profile fields unused by MVP

## 10. Example Fake Run Config

```yaml
version: 1

run:
  name: mvp_fake
  tags: [smoke, fake]

robot:
  profile: fake_robot
  observation_mapper: fake_observation_mapper
  action_mapper: fake_action_mapper

model:
  profile: dummy_model
  runtime: dummy_runtime
  params:
    latency_ms: 1

input:
  type: fake
  params:
    num_messages: 1
    timeout_ms: 100

output:
  type: fake
  params:
    capture: true

preprocess:
  - type: identity
  - type: dummy_input_builder

postprocess:
  - type: dummy_output_parser
  - type: validate_action

lifecycle:
  warmup: true
  max_iterations: 1
  stop_on_error: true

logging:
  level: info
  output_dir: runs/
  write_resolved_config: true
  write_iteration_summary: true
  include_data_summaries: true
```

## 11. Example Real-Oriented Run Config

This config is a target shape for real integration. It may not run until concrete plugins exist.

```yaml
version: 1

run:
  name: g1_openpi_vla
  tags: [unitree_g1, openpi, vla]

robot:
  profile: unitree_g1
  observation_mapper: unitree_g1_observation_mapper
  action_mapper: unitree_g1_action_mapper

model:
  profile: openpi_vla
  runtime: openpi_torch
  params:
    device: cuda:0
    checkpoint: /models/openpi/checkpoint.pt

input:
  type: ros2
  params:
    observation_topic: /g1/observation
    timeout_ms: 100

output:
  type: unitree_dds
  params:
    domain_id: 0
    command_topic: lowcmd

preprocess:
  - type: resize_image
    params:
      camera: front
      width: 224
      height: 224
  - type: openpi_input_builder

postprocess:
  - type: openpi_output_parser
  - type: clamp_joint_limits
    params:
      source: robot_profile

lifecycle:
  warmup: true
  loop_hz: 10
  stop_on_error: true

logging:
  level: info
  output_dir: runs/
  write_resolved_config: true
  write_iteration_summary: true
  include_data_summaries: true
```

## 12. MVP Config Acceptance Criteria

The config schema is acceptable when:

- fake run config can validate without ROS2, DDS, GPU, or model artifacts
- unresolved plugin keys fail during validation
- missing profiles fail during validation
- processor order is preserved exactly
- disabled processors are omitted from resolved chain
- resolved config can be written to a run output directory
- model runtime can be changed without editing robot config
- robot mapper can be changed without editing model config
