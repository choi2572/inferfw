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

The MVP plugin system should stay simple. Local registry-based plugins are enough for the first implementation.

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
- robot profiles
- model profiles
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

- `dummy_runtime`
- `openpi_torch`
- `onnx_runtime`, future
- `tensorrt_runtime`, future
- `remote_http_runtime`, future

Responsibilities:

- load model artifacts
- allocate runtime resources
- warm up model
- run inference
- unload resources

## 4. Local Registry

MVP uses a local in-process registry.

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

Registration example:

```python
registry.register_input_adapter("fake", FakeInputAdapter)
registry.register_output_adapter("fake", FakeOutputAdapter)
registry.register_observation_mapper("fake_observation_mapper", FakeObservationMapper)
registry.register_action_mapper("fake_action_mapper", FakeActionMapper)
registry.register_processor("identity", IdentityProcessor)
registry.register_processor("dummy_input_builder", DummyInputBuilder)
registry.register_processor("dummy_output_parser", DummyOutputParser)
registry.register_model_runtime("dummy_runtime", DummyModelRuntime)
```

Resolution example:

```python
input_cls = registry.get_input_adapter(config.input.type)
runtime_cls = registry.get_model_runtime(config.model.runtime)
processor_cls = registry.get_processor(processor_config.type)
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
- `dummy_runtime` model runtime

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
      profile.yaml
    dummy_model/
      runtime.py
      processors.py
      model_profile.yaml
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
  robot_profile.yaml
  register.py

inferfw_openpi/
  runtime.py
  processors.py
  model_profile.yaml
  register.py
```

MVP can keep plugins inside the repository until the core contracts stabilize.

## 7. Plugin Registration Policy

MVP registration can be explicit.

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

Package entry points are not required in MVP.

## 8. Plugin Config

Plugins receive config through their `configure` method.

Example adapter config:

```yaml
input:
  type: fake
  params:
    num_messages: 1
    timeout_ms: 100
```

Example processor config:

```yaml
preprocess:
  - type: resize_image
    params:
      camera: front
      width: 224
      height: 224
```

Example model runtime config:

```yaml
model:
  profile: openpi_vla
  runtime: openpi_torch
  params:
    device: cuda:0
    checkpoint: /models/openpi/checkpoint.pt
```

Rules:

- `type` or `runtime` selects registry key
- `params` are plugin-specific
- plugin-specific params should be documented by the plugin owner
- validation should catch missing required params before `RUNNING`

## 9. Plugin Metadata

MVP does not require a full metadata schema, but plugins should expose enough information for debugging and validation.

Recommended metadata:

```python
PLUGIN_NAME = "dummy_runtime"
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
- selected model runtime is allowed by model profile
- selected mapper exists
- selected processors exist
- robot profile exists
- model profile exists
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

## 14. Future Plugin Discovery

After MVP, plugin discovery may use Python package entry points.

Potential shape:

```toml
[project.entry-points."inferfw.plugins"]
unitree_g1 = "inferfw_unitree_g1:register"
openpi = "inferfw_openpi:register"
```

This is intentionally out of MVP scope. The MVP registry should be simple enough to debug without package discovery behavior.

## 15. MVP Plugin Acceptance Criteria

The plugin architecture is acceptable when:

- framework core can run the fake loop using only registry-resolved components
- unknown plugin keys fail during config validation
- fake plugins can be registered without external dependencies
- adding a new dummy model runtime does not require editing robot mapper code
- adding a new fake robot mapper does not require editing model runtime code
- optional ROS2/DDS plugins can be absent without breaking fake tests
- plugin dependency errors are clear when a selected plugin cannot import its dependencies
