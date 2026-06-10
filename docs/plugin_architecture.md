# Plugin Architecture

This document defines the MVP plugin architecture for the inference service framework.

The plugin system exists so model runtimes, robot integrations, processors, and IO adapters can be added or replaced without editing framework core.

## 1. Plugin Goals

The plugin architecture should make it possible to:

- swap model runtimes through config
- swap robot integrations through config
- add model-specific processors without core changes
- add robot-specific mappers without core changes
- test the full service loop with fake plugins
- keep core free of robot/model-specific semantics

The MVP plugin system should stay simple, but it must allow model and robot integrations to live outside the core package. A package such as `inferfw-openpi` should be able to provide a model runtime and model-specific processors without editing `inferfw`.

## 2. Plugin Boundary

Framework core owns:

- interfaces
- lifecycle
- service loop
- config loading
- validation
- registry
- processor chain runner
- canonical data containers
- logging hooks

Plugins own:

- concrete `ModelRuntime`
- concrete `InputAdapter`
- concrete `OutputAdapter`
- concrete `ObservationMapper`
- concrete `ActionMapper`
- concrete `Processor`
- robot metadata and command conventions
- model IO schemas or runtime presets
- robot/model-specific helper logic

Core must not import concrete robot or model plugins directly inside service logic.

## 3. MVP Plugin Types

### 3.1 Input Adapter Plugin

Implements:

```python
InputAdapter
```

Examples:

- `fake`
- `ros2`
- `replay`, future
- `shared_memory`, future

Responsibilities:

- read raw observations
- manage input connection lifecycle
- preserve source metadata

### 3.2 Output Adapter Plugin

Implements:

```python
OutputAdapter
```

Examples:

- `fake`
- `unitree_dds`
- `ros2`
- `shared_memory`, future

Responsibilities:

- publish `RobotCommand`
- manage output connection lifecycle
- handle adapter-specific serialization

### 3.3 Observation Mapper Plugin

Implements:

```python
ObservationMapper
```

Examples:

- `fake_observation_mapper`
- `unitree_g1_observation_mapper`

Responsibilities:

- convert `RawObservation` to `CanonicalObservation`
- use robot profile metadata
- isolate robot-specific observation semantics

### 3.4 Action Mapper Plugin

Implements:

```python
ActionMapper
```

Examples:

- `fake_action_mapper`
- `unitree_g1_action_mapper`

Responsibilities:

- convert `CanonicalAction` to `RobotCommand`
- use robot command conventions
- isolate robot-specific command semantics

### 3.5 Processor Plugin

Implements:

```python
Processor
```

Examples:

- `identity`
- `resize_image`
- `dummy_input_builder`
- `dummy_output_parser`
- `openpi_input_builder`
- `openpi_output_parser`
- `clamp_joint_limits`

Responsibilities:

- transform or validate data at one pipeline step
- declare expected input/output behavior where possible
- remain composable in ordered chains

### 3.6 Model Runtime Plugin

Implements:

```python
ModelRuntime
```

Examples:

- `dummy`
- `openpi`
- `onnx_runtime`, future
- `tensorrt_runtime`, future
- `remote_http_runtime`, future

Responsibilities:

- load model artifacts
- allocate runtime resources
- warm up model
- run inference
- unload resources

## 4. Registry and Discovery

MVP uses an in-process registry. Built-in plugins may be registered explicitly. External packages may use Python package entry points for discovery.

Conceptual structure:

```python
class PluginRegistry:
    input_adapters: dict[str, type[InputAdapter]]
    output_adapters: dict[str, type[OutputAdapter]]
    observation_mappers: dict[str, type[ObservationMapper]]
    action_mappers: dict[str, type[ActionMapper]]
    processors: dict[str, type[Processor]]
    model_runtimes: dict[str, type[ModelRuntime]]
```

Explicit registration example:

```python
registry.register_input_adapter("fake", FakeInputAdapter)
registry.register_output_adapter("fake", FakeOutputAdapter)
registry.register_observation_mapper("fake_observation_mapper", FakeObservationMapper)
registry.register_action_mapper("fake_action_mapper", FakeActionMapper)
registry.register_processor("identity", IdentityProcessor)
registry.register_processor("dummy_input_builder", DummyInputBuilder)
registry.register_processor("dummy_output_parser", DummyOutputParser)
registry.register_model_runtime("dummy", DummyModelRuntime)
registry.register_model_runtime("openpi", OpenPiModelRuntime)
```

Resolution example:

```python
runtime_cls = registry.get_model_runtime(model_config.runtime)
processor_cls = registry.get_processor(processor_step.name)
```

Entry point example for an external model runtime package:

```toml
[project.entry-points."inferfw.model_runtime"]
openpi = "inferfw_openpi.runtime:OpenPiModelRuntime"
```

Processor discovery may use a separate entry point group when processor packages move out of core:

```toml
[project.entry-points."inferfw.processor"]
openpi_input_builder = "inferfw_openpi.processors:OpenPiInputBuilder"
openpi_output_parser = "inferfw_openpi.processors:OpenPiOutputParser"
```

## 5. Built-In MVP Plugins

The MVP should include a minimal built-in plugin set.

Required built-ins:

- `fake` input adapter
- `fake` output adapter
- `fake_observation_mapper`
- `fake_action_mapper`
- `identity` processor
- `dummy_input_builder` processor
- `dummy_output_parser` processor
- `validate_action` processor
- `dummy` model runtime

Optional early stubs:

- `ros2` input adapter stub
- `unitree_dds` output adapter stub
- `resize_image` processor stub
- `clamp_joint_limits` processor

The fake plugins are not temporary sample code. They are the baseline test plugins for the framework.

## 6. Plugin Package Layout

Initial simple layout:

```text
inferfw/
  plugins/
    fake/
      adapters.py
      mappers.py
      processors.py
    dummy_model/
      runtime.py
      processors.py
    ros2/
      input_adapter.py
    unitree_dds/
      output_adapter.py
```

External plugin layout, future:

```text
inferfw_unitree_g1/
  observation_mapper.py
  action_mapper.py
  processors.py
  metadata.py
  register.py

inferfw_openpi/
  runtime.py
  processors.py
  io_schema.py
  pyproject.toml
```

MVP can keep fake plugins inside the repository until the core contracts stabilize. Model integrations such as OpenPI should be designed as separate installable packages.

## 7. Plugin Registration Policy

Core built-ins may be registered explicitly.

Example:

```python
def register_builtin_plugins(registry: PluginRegistry) -> None:
    register_fake_plugins(registry)
    register_dummy_model_plugins(registry)
```

Plugin modules may expose:

```python
def register(registry: PluginRegistry) -> None:
    ...
```

The service startup may call known registration functions before config validation.

External packages may also expose Python entry points. The `refer/inferfw-openpi` concept package demonstrates this for model runtimes with:

```toml
[project.entry-points."inferfw.model_runtime"]
openpi = "inferfw_openpi.runtime:OpenPiModelRuntime"
```

The registry should fail clearly when a selected plugin is not installed or cannot be imported.

## 8. Plugin Config

Plugins receive config through their `configure` method.

Pipeline config selects plugins by names in processor steps and model config names.

```yaml
pipeline:
  preprocess:
    groups:
      - keys: [left_img, right_img]
        steps:
          - name: resize
            params:
              width: 224
              height: 224
          - name: openpi_input_builder
  models:
    g1_vla:
      runtime: openpi
      config_name: act_g1
      model_path: /workspace/sim_models/openpi_checkpoint/
      input_interface:
        bindings:
          left_img:
            topic: /cam/left/image_raw_color/compressed
            message_type: sensor_msgs/CompressedImage
  postprocess:
    groups:
      - keys: [actions]
        steps:
          - name: openpi_output_parser
```

Rules:

- processor `name` selects a processor registry key
- model `runtime` selects a model runtime plugin key
- model `config_name` is passed to the selected runtime as model-specific configuration
- `model_path` is passed to runtimes that load artifacts
- processor `params` are plugin-specific
- plugin-specific params should be documented by the plugin owner
- validation should catch missing required params before `RUNNING`

For the OpenPI concept package, runtime params are derived from:

```yaml
runtime: openpi
config_name: act_g1
model_path: /workspace/sim_models/openpi_checkpoint/
```

The runtime then loads the OpenPI policy in-process and calls `Policy.infer`.

## 8.1 External OpenPI Package Concept

`refer/inferfw-openpi` is a concept reference for a separately distributed model plugin package.

It demonstrates:

- package name: `inferfw-openpi`
- import package: `inferfw_openpi`
- entry point key: `openpi`
- runtime class: `OpenPiModelRuntime`
- dependency isolation: `openpi` is a dependency of `inferfw-openpi`, not `inferfw`
- in-process policy execution, not a WebSocket bridge

The example script `refer/inferfw-openpi/examples/run_model_runtime.py` demonstrates the intended integration path:

```text
create_model_runtime("openpi", params)
  -> ModelRuntimeSession
  -> startup(load_model + warmup)
  -> infer(ModelInput)
  -> ModelOutput
```

In the full service, robot observations should be converted to OpenPI-compatible `ModelInput` by preprocessors such as `openpi_input_builder`. OpenPI-specific model outputs should be parsed by postprocessors such as `openpi_output_parser`. Those processors belong in the OpenPI plugin package, not in framework core.

Framework core should expose only the generic `ModelInput` / `ModelOutput` containers at the model runtime boundary. The OpenPI plugin should document the expected `ModelInput.data` and `ModelOutput.data` keys instead of introducing separate public input/output container types.

Example plugin-owned processor shape:

```python
import numpy as np

from inferfw.data.model import ModelInput
from inferfw.data.model import ModelOutput


class OpenPiInputBuilder:
    def process(self, observation: CanonicalObservation) -> ModelInput:
        return ModelInput.from_dict(
            {
                "state": np.asarray(build_openpi_state(observation), dtype=np.float64),
                "images": {
                    "cam_high_left": build_openpi_image(observation, "cam_high_left"),
                    "cam_high_right": build_openpi_image(observation, "cam_high_right"),
                    "cam_left_wrist": build_openpi_image(observation, "cam_left_wrist"),
                    "cam_right_wrist": build_openpi_image(observation, "cam_right_wrist"),
                },
                "prompt": observation.metadata["instruction"],
            }
        )


class OpenPiOutputParser:
    def process(self, output: ModelOutput) -> CanonicalAction:
        actions = np.asarray(output.data["actions"], dtype=np.float64)
        return build_canonical_action_from_openpi_actions(actions)
```

The runtime then stays thin:

```text
OpenPiInputBuilder
  -> ModelInput.data: {"state", "images", "prompt"}
  -> OpenPiModelRuntime.infer(ModelInput)
  -> ModelOutput.data: {"actions"}
  -> OpenPiOutputParser
```

The exact OpenPI key names, image layout, state dimension, action shape, and dtype rules should be documented in the OpenPI plugin docs and validated by `OpenPiInputBuilder` / `OpenPiOutputParser` where practical.

## 9. Plugin Metadata

MVP does not require a full metadata schema, but plugins should expose enough information for debugging and validation.

Recommended metadata:

```python
PLUGIN_NAME = "dummy"
PLUGIN_KIND = "model_runtime"
PLUGIN_VERSION = "0.1.0"
```

Optional future metadata:

- supported framework version
- required dependencies
- expected config schema
- expected input data type
- produced output data type
- hardware requirements

## 10. Compatibility Checks

MVP compatibility checks should happen during `configure`.

Checks:

- selected plugin key exists
- selected mapper exists
- selected processors exist
- selected model runtime or runtime preset exists
- selected model binding schema is valid
- processor chain final output expectations are documented or validated where possible

Future compatibility checks:

- model output schema compatible with postprocess chain
- postprocess output compatible with action mapper
- robot control frequency compatible with model latency
- adapter message schema compatible with mapper

## 11. Dependency Policy

Plugin dependencies should not leak into framework core.

Examples:

- ROS2 dependencies should be needed only for ROS2 adapter plugin.
- Unitree DDS dependencies should be needed only for Unitree DDS adapter/plugin.
- Torch dependencies should be needed only for Torch model runtime plugins.
- TensorRT dependencies should be needed only for TensorRT runtime plugins.

MVP implication:

- fake end-to-end test must run without ROS2, DDS, Torch, TensorRT, GPU, or robot SDKs.
- optional plugins should fail with clear dependency errors when selected but dependencies are missing.

## 12. Error Handling

Plugin errors should preserve component context.

Examples:

- `PluginResolutionError`: unknown registry key
- `AdapterError`: input/output connection failure
- `MapperError`: invalid raw observation or action mapping failure
- `ProcessorError`: invalid input or transformation failure
- `ModelRuntimeError`: model load, warmup, or inference failure

Error payload should include:

- plugin kind
- plugin key
- lifecycle state
- config section
- original exception message

## 13. Testing Plugins

Each plugin type should be testable independently.

Required MVP tests:

- registry registers built-in fake plugins
- registry rejects unknown keys
- fake input adapter produces `RawObservation`
- fake observation mapper produces `CanonicalObservation`
- dummy input builder produces `ModelInput`
- dummy runtime produces `ModelOutput`
- dummy output parser produces `CanonicalAction`
- fake action mapper produces `RobotCommand`
- fake output adapter captures published command

The end-to-end smoke test should use only fake and dummy plugins.

## 14. Plugin Discovery Scope

Typed package entry points are allowed for externally distributed plugins, especially model runtimes:

```toml
[project.entry-points."inferfw.model_runtime"]
openpi = "inferfw_openpi.runtime:OpenPiModelRuntime"
```

Bulk plugin registration through a generic plugin entry point can remain future work:

```toml
[project.entry-points."inferfw.plugins"]
unitree_g1 = "inferfw_unitree_g1:register"
openpi = "inferfw_openpi:register"
```

The registry should remain simple enough to debug. A missing optional package should fail during validation or plugin resolution with a clear error.

## 15. MVP Plugin Acceptance Criteria

The plugin architecture is acceptable when:

- framework core can run the fake loop using only registry-resolved components
- unknown plugin keys fail during config validation
- fake plugins can be registered without external dependencies
- adding a new dummy model runtime does not require editing robot mapper code
- adding a new fake robot mapper does not require editing model runtime code
- optional ROS2/DDS plugins can be absent without breaking fake tests
- plugin dependency errors are clear when a selected plugin cannot import its dependencies
