# Architecture

This document describes the MVP architecture of the inference service framework.

The architecture is optimized for a runnable single-service inference loop while preserving the longer-term goal: model evaluation across different model runtimes, robots, simulators, and IO backends.

## 1. Architectural Goal

The framework should make the following changes possible without editing runtime core:

- replace one model runtime with another
- replace one robot integration with another
- replace fake IO with ROS2/DDS IO
- replace or reorder preprocess/postprocess chains
- run the same service loop with different configs

The framework core owns execution. Plugins own semantics. Configs compose the run.

## 2. MVP System View

```text
                 Run Config
                    |
                    v
           +-----------------+
           | Config Loader   |
           | Validator       |
           +-----------------+
                    |
                    v
           +-----------------+
           | Plugin Registry |
           +-----------------+
                    |
                    v
+--------------------------------------------------+
| Inference Service Runtime                         |
|                                                  |
|  +-------------+     +-------------------------+ |
|  | Lifecycle   |     | Structured Logger       | |
|  +-------------+     +-------------------------+ |
|                                                  |
|  InputAdapter                                  |
|      -> ObservationMapper                       |
|      -> Preprocess Chain                        |
|      -> ModelRuntime                            |
|      -> Postprocess Chain                       |
|      -> ActionMapper                            |
|      -> OutputAdapter                           |
|                                                  |
+--------------------------------------------------+
```

## 3. Runtime Data Flow

The MVP runtime executes one linear pipeline.

```text
External Observation Source
  -> InputAdapter
  -> RawObservation
  -> ObservationMapper
  -> CanonicalObservation
  -> Preprocess Chain
  -> ModelInput
  -> ModelRuntime
  -> ModelOutput
  -> Postprocess Chain
  -> CanonicalAction
  -> ActionMapper
  -> RobotCommand
  -> OutputAdapter
  -> External Command Sink
```

The framework does not require every robot or model to share identical tensor shapes. Instead, it standardizes the service loop and uses canonical semantic containers at the robot/model boundary.

## 4. Core vs Plugin Boundary

### 4.1 Framework Core

Framework core owns:

- service lifecycle
- service loop
- config loading
- validation
- plugin resolution
- processor chain execution
- adapter interface contracts
- mapper interface contracts
- model runtime interface contracts
- canonical data containers
- structured logging hooks
- common error types

Framework core must not own:

- robot-specific joint layout
- robot-specific command packet construction
- model-specific preprocessing semantics
- model checkpoint loading details for a specific model
- IK/FK implementation
- hard-coded ROS2/DDS topics for a specific robot

### 4.2 Plugins

Plugins own concrete behavior.

Plugin examples:

- model runtime plugin
- model processor plugin
- robot mapper plugin
- robot processor plugin
- IO adapter plugin
- IK/FK plugin

Plugins can depend on core interfaces. Core must not depend on concrete plugins.

### 4.3 Configs

Configs select and compose components.

Configs define:

- which robot profile to use
- which model profile to use
- which adapters to instantiate
- which processors to run
- component params
- runtime params
- logging params

Configs should not contain executable behavior.

### 4.4 Profiles

Profiles describe metadata and conventions.

Robot profiles describe:

- joints
- joint groups
- joint limits
- sensors
- frames
- command conventions
- IO presets

Model profiles describe:

- input schema
- output schema
- artifact metadata
- runtime requirements
- warmup input requirements
- expected frequency or latency hints

Profiles should not perform runtime logic.

## 5. MVP Component Responsibilities

### 5.1 InferenceService

`InferenceService` is the top-level orchestrator.

Responsibilities:

- receive resolved config
- own lifecycle state
- start and stop adapters
- call model runtime lifecycle methods
- run warmup
- run inference loop
- pause/resume publishing behavior
- record lifecycle and runtime logs
- handle unrecoverable errors

It should not contain model-specific or robot-specific logic.

### 5.2 InputAdapter

Reads raw observation data from an external source.

MVP implementations:

- `FakeInputAdapter`
- `Ros2InputAdapter` stub

Output:

```text
RawObservation
```

The raw observation type may initially be a structured dict-like container, but it must remain distinct from `CanonicalObservation`.

### 5.3 ObservationMapper

Converts raw robot observation into a canonical semantic observation.

Input:

```text
RawObservation
```

Output:

```text
CanonicalObservation
```

The mapper is robot-specific and should use the robot profile.

### 5.4 Preprocess Chain

Transforms `CanonicalObservation` into `ModelInput`.

Input:

```text
CanonicalObservation
```

Output:

```text
ModelInput
```

In practice, intermediate processors may produce intermediate structures. The chain contract should still make the expected final output explicit.

### 5.5 ModelRuntime

Owns model lifecycle and inference.

Input:

```text
ModelInput
```

Output:

```text
ModelOutput
```

The service measures latency around `infer`.

### 5.6 Postprocess Chain

Transforms `ModelOutput` into `CanonicalAction`.

Input:

```text
ModelOutput
```

Output:

```text
CanonicalAction
```

Postprocessors can parse model output, clamp values, validate action schema, or convert model-specific intermediate outputs.

### 5.7 ActionMapper

Converts canonical semantic action into robot-specific command.

Input:

```text
CanonicalAction
```

Output:

```text
RobotCommand
```

The mapper is robot-specific and should use the robot profile.

### 5.8 OutputAdapter

Publishes robot-specific command to an external sink.

MVP implementations:

- `FakeOutputAdapter`
- `DdsOutputAdapter` stub

Input:

```text
RobotCommand
```

## 6. Registry Architecture

MVP uses a local registry.

Registry resolves:

- input adapter types
- output adapter types
- observation mapper types
- action mapper types
- processor types
- model runtime types

Example conceptual API:

```python
registry.get_input_adapter("fake")
registry.get_output_adapter("fake")
registry.get_model_runtime("dummy")
registry.get_processor("identity")
```

The registry can be manually populated in MVP. Package discovery and entry-point based plugin loading are future extensions.

## 7. Lifecycle Architecture

The lifecycle is explicit and enforced by the runtime core.

```text
CREATED
  -> CONFIGURED
  -> MODEL_LOADED
  -> WARMED_UP
  -> RUNNING
  -> STOPPED
```

Additional states:

```text
RUNNING -> PAUSED -> RUNNING
any state -> ERROR
```

Key architectural rule:

Configuration and plugin resolution happen before model resources are loaded. Runtime resource allocation happens after config validation succeeds.

## 8. Logging Architecture

MVP logging is file-based structured logging.

The service should record:

- run metadata
- resolved config
- lifecycle transitions
- component resolution results
- inference latency
- processor errors
- adapter errors
- model runtime errors
- shutdown event

Future systems can consume the same records for metrics, replay, or experiment tracking.

## 9. Error Handling Architecture

Errors should identify the failing component boundary.

Examples:

- config validation error
- plugin resolution error
- lifecycle transition error
- input adapter error
- observation mapper error
- processor error
- model runtime error
- action mapper error
- output adapter error

MVP behavior:

- config and registry errors fail during `configure`
- model loading errors fail during `load_model`
- warmup errors fail before `RUNNING`
- loop errors transition to `ERROR` unless explicitly recoverable
- `stop` should attempt cleanup even after `ERROR`

## 10. Package Layout Direction

Initial package layout:

```text
inferfw/
  __init__.py
  cli.py
  core/
    service.py
    context.py
    errors.py
  interfaces/
    adapters.py
    mappers.py
    model_runtime.py
    processors.py
  data/
    canonical.py
    raw.py
    model.py
    command.py
  config/
    loader.py
    schema.py
  registry/
    registry.py
    builtin.py
  pipeline/
    processor_chain.py
  lifecycle/
    state.py
  logging/
    logger.py
  plugins/
    fake/
    dummy_model/
```

This layout can be adjusted during implementation, but the dependency direction should remain:

```text
core -> interfaces/data/config/registry/pipeline/lifecycle/logging
plugins -> interfaces/data
core -X-> concrete plugins
```

`core -X-> concrete plugins` means core must not import concrete plugin modules directly.

## 11. Fake-First Architecture

The first executable system should use fake components:

```text
FakeInputAdapter
FakeObservationMapper
IdentityProcessor
DummyInputBuilder
DummyModelRuntime
DummyOutputParser
FakeActionMapper
FakeOutputAdapter
```

This fake path is the architecture's integration test baseline.

Reasons:

- no robot required
- no ROS2/DDS required
- no GPU required
- no model checkpoint required
- deterministic test data
- fast feedback during core development

Real ROS2, DDS, robot, and VLA integrations should be added only after the fake path validates the core architecture.

## 12. Future Architecture Extensions

Future extensions should build on the MVP architecture without changing the core contracts unnecessarily.

Likely extensions:

- multi-stage pipeline graph
- edge contracts between stages
- replay input adapter
- replay evaluator
- metrics exporter
- experiment tracking integration
- plugin package discovery
- model artifact manager
- distributed execution
- dashboard
- safety policy layer
