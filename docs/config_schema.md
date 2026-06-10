# Config Schema

This document defines the current pipeline configuration shape for the inference service framework.

The canonical example is:

```text
config/pipeline_example.yaml
```

This schema is focused on a service-oriented runtime that receives requests, binds model inputs to transport topics, runs model pipelines, postprocesses model outputs, and publishes robot commands.

## 1. Config Goals

The config system should:

- assemble a runnable inference service from YAML
- define request server endpoints
- define robot command conventions and loop frequency
- define one or more model pipelines
- bind model inputs and outputs to external interfaces
- preserve processor order exactly
- fail early on malformed or unresolved config

The config system should not:

- contain executable code
- require framework core edits for a new model or robot
- silently ignore unknown required fields
- hide transport bindings inside model runtime code

## 2. Config File

The primary example lives under `config/`:

```text
config/
  pipeline_example.yaml
```

The config has three required top-level sections:

```yaml
request_server: {}
robot: {}
pipeline: {}
```

## 3. Full Example

```yaml
request_server:
  type: ros2
  node_name: inferfw
  services:
    load_model: /inferfw/load_model
    unload_model: /inferfw/unload_model
    infer: /inferfw/infer
    set_task: /inferfw/set_task
    set_operation_mode: /inferfw/set_operation_mode

robot:
  name: g129dof
  action_class: G1Action
  loop_hz: 30.0
  joint_config:
    torso: 6
    right_arm: 7
    left_arm: 7
    right_hand: 12
    left_hand: 12
  topics:
    joint_command:
      topic: /joint/command/joint_state
      message_type: sensor_msgs/JointState
    gripper_command:
      topic: /gripper/command/joint_state
      message_type: sensor_msgs/JointState

pipeline:
  name: g129dof_vla_test1
  preprocess:
    groups:
      - keys:
          - left_img
          - left_wrist_img
          - right_img
          - right_wrist_img
        steps:
          - name: resize
            params:
              width: 224
              height: 224
              mode: bilinear
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
          left_wrist_img:
            topic: /left_hand/color/image_rect_raw
            message_type: sensor_msgs/Image
          right_img:
            topic: /cam/right/image_raw_color/compressed
            message_type: sensor_msgs/CompressedImage
          right_wrist_img:
            topic: /right_hand/color/image_rect_raw
            message_type: sensor_msgs/Image
          joint_state:
            topic: /joint/state/joint_state
            message_type: sensor_msgs/JointState
      output_interface:
        bindings:
          actions:
            type: joint_trajectory
            groups:
              - torso
              - right_arm
              - left_arm
              - right_hand
              - left_hand
  postprocess:
    groups:
      - keys:
          - actions
        steps:
          - name: resample_action
            params:
              target_hz: 30
              tool_dim: 44
          - name: skip_closest_action
            params:
              tool_dim: 44
              min_remaining: 15
              use_joint_distance: true
          - name: smooth_action
            params:
              dt: 0.033333333333333
              spline_length: 5
              tool_dim: 44
```

## 4. `request_server`

`request_server` defines how external clients control the service.

```yaml
request_server:
  type: ros2
  node_name: inferfw
  services:
    load_model: /inferfw/load_model
    unload_model: /inferfw/unload_model
    infer: /inferfw/infer
    set_task: /inferfw/set_task
    set_operation_mode: /inferfw/set_operation_mode
```

Fields:

- `type`: request server implementation, such as `ros2`
- `node_name`: runtime node name
- `services`: service names exposed by the request server

Required services for the current service shape:

- `load_model`
- `unload_model`
- `infer`
- `set_task`
- `set_operation_mode`

Validation:

- request server type must be supported
- service names must be non-empty strings
- service keys required by the selected server type must exist

## 5. `robot`

`robot` defines robot-level execution conventions used by the pipeline output path.

```yaml
robot:
  name: g129dof
  action_class: G1Action
  loop_hz: 30.0
  joint_config:
    torso: 6
    right_arm: 7
    left_arm: 7
    right_hand: 12
    left_hand: 12
  topics:
    joint_command:
      topic: /joint/command/joint_state
      message_type: sensor_msgs/JointState
```

Fields:

- `name`: robot id used in logs and runtime metadata
- `action_class`: robot action representation or action mapper target
- `loop_hz`: target command loop rate
- `joint_config`: semantic joint groups and dimensions
- `topics`: robot command publication targets

Validation:

- `loop_hz` must be positive
- joint group dimensions must be positive integers
- command topics must include `topic` and `message_type`
- processor output groups should be compatible with `joint_config`

## 6. `pipeline`

`pipeline` defines preprocessing, model runtime bindings, and postprocessing.

```yaml
pipeline:
  name: g129dof_vla_test1
  preprocess: {}
  models: {}
  postprocess: {}
```

Fields:

- `name`: pipeline id used in logs and runtime metadata
- `preprocess`: grouped processors that run before model inference
- `models`: named model runtime configurations
- `postprocess`: grouped processors that run after model inference

## 7. Processor Groups

Preprocess and postprocess use grouped processors. A group applies ordered `steps` to one or more data `keys`.

```yaml
preprocess:
  groups:
    - keys:
        - left_img
        - right_img
      steps:
        - name: resize
          params:
            width: 224
            height: 224
            mode: bilinear
```

Processor group fields:

- `keys`: data keys the group applies to
- `steps`: ordered processor steps

Processor step fields:

- `name`: processor registry key
- `params`: optional processor-specific params

Validation:

- processor names must resolve
- `keys` must be non-empty
- `steps` must preserve YAML order
- preprocess keys should exist in at least one model input binding unless the processor creates them
- postprocess keys should exist in model output bindings or be produced by an earlier postprocess step

## 8. `pipeline.models`

`pipeline.models` is a mapping from model id to model runtime configuration.

```yaml
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
          groups:
            - torso
            - right_arm
```

Model fields:

- `runtime`: model runtime plugin key
- `config_name`: model-specific runtime config name or preset name
- `model_path`: model artifact path
- `input_interface.bindings`: named input bindings consumed by the model
- `output_interface.bindings`: named output bindings produced by the model

`runtime` resolves to a model runtime key provided by core or an external model plugin package. For example, an `inferfw-openpi` package can provide the `openpi` runtime and OpenPI-specific processors through package entry points.

`config_name` is passed to the selected runtime as model-specific configuration. For OpenPI, this can be the OpenPI train config name such as `act_g1`.

Input binding fields:

- `topic`: external source topic
- `message_type`: transport message type

Output binding fields are output-specific. For joint trajectory outputs, expected fields are:

- `type`: output semantic type, such as `joint_trajectory`
- `groups`: robot joint groups the action targets

Validation:

- model ids must be unique
- `runtime` must resolve to a model runtime plugin
- `config_name` must be present when required by the selected runtime
- `model_path` must be present for runtimes that load artifacts
- input binding keys must be unique within a model
- output binding keys must be unique within a model
- output groups should exist in `robot.joint_config`

## 9. Resolved Config

The runtime should produce a resolved config snapshot after validation.

Resolved config should include:

- config file path
- selected request server type
- robot name and joint configuration
- pipeline name
- resolved processor names
- resolved model runtime keys and config names
- model artifact paths
- input and output bindings

The resolved config snapshot should be written to the run output directory when logging support is enabled.

## 10. Validation Rules

Validation should fail before service execution when:

- required top-level section is missing
- request server type is unsupported
- required request service is missing
- robot loop rate is invalid
- joint group dimension is invalid
- command topic config is malformed
- pipeline name is missing
- model config is missing required fields
- model runtime cannot be resolved
- processor name cannot be resolved
- processor group is malformed
- preprocess/postprocess keys cannot be connected to model bindings
- output action groups do not match robot joint groups

Validation warnings may be used for:

- unknown optional fields
- `model_path` existence checks skipped in a remote runtime
- processor keys intentionally created by earlier processors
- output bindings with runtime-specific fields that core does not inspect

## 11. Concept Reference Implementation

`refer/inferfw` is a concept reference for the model runtime boundary, not the full service implementation.

It currently demonstrates:

- `ModelRuntime` as a plugin contract
- `ModelInput` and `ModelOutput` as backend-agnostic model boundary containers
- entry point based model runtime resolution
- a minimal `ModelRuntimeSession` for `load_model -> warmup -> infer -> unload`
- latency measurement around model inference

It does not yet implement the full `request_server -> pipeline -> robot output` service loop described by this config schema.

`refer/inferfw-openpi` is a concept reference for an external model plugin package. It demonstrates how OpenPI can be installed separately, register an `openpi` model runtime entry point, load a trained policy in-process, and convert between OpenPI-specific data and `ModelInput` / `ModelOutput`.

In the full service, OpenPI-specific preprocess and postprocess steps should also be plugin-owned:

- `openpi_input_builder`: robot/pipeline data to OpenPI-compatible `ModelInput`
- `openpi_output_parser`: OpenPI `ModelOutput` to action data consumed by later postprocess or robot mapping

The core package should not define OpenPI-specific public input/output container types. OpenPI payload shape should be expressed as the `ModelInput.data` / `ModelOutput.data` schema owned by the OpenPI plugin. The service contract remains:

```text
openpi_input_builder -> ModelInput -> OpenPiModelRuntime -> ModelOutput -> openpi_output_parser
```

Expected OpenPI payload example:

```python
ModelInput.data == {
    "state": state_vector,
    "images": {
        "cam_high_left": image_tensor,
        "cam_high_right": image_tensor,
        "cam_left_wrist": image_tensor,
        "cam_right_wrist": image_tensor,
    },
    "prompt": instruction_text,
}

ModelOutput.data == {
    "actions": action_chunk,
}
```

## 12. Acceptance Criteria

The config schema is acceptable when:

- `config/pipeline_example.yaml` parses as YAML
- required top-level sections are present
- processor order is preserved exactly
- preprocess keys align with model input bindings
- postprocess keys align with model output bindings
- output action groups align with robot joint groups
- malformed service, model, processor, or binding config fails before runtime starts
