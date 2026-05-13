# Interfaces

This document defines the MVP interface contracts for the inference service framework.

Interfaces are the main boundary between framework core and plugins. Framework core calls interfaces. Plugins implement interfaces. Configs select concrete implementations.

The signatures in this document are target contracts, not necessarily final code. Implementation can refine details, but changes should preserve the ownership boundaries described here.

## 1. Interface Principles

- Interfaces should be small and explicit.
- Core must depend on interfaces, not concrete plugins.
- Plugins may depend on core data structures and interface definitions.
- Interface methods should raise framework-defined errors or documented exceptions.
- `configure` should validate static setup before runtime resources are allocated.
- Runtime resource allocation should happen in `start`, `load`, or equivalent lifecycle methods.
- Side effects should be limited to adapters, model runtimes, and loggers.

## 2. Shared Types

These names are used across interfaces.

```python
RawObservation
CanonicalObservation
ModelInput
ModelOutput
CanonicalAction
RobotCommand
RuntimeContext
ProcessorConfig
AdapterConfig
ModelRuntimeConfig
RobotProfile
ModelProfile
```

Detailed data model definitions are covered in `docs/canonical_data.md`.

## 3. RuntimeContext

`RuntimeContext` provides shared runtime metadata and services to components.

Conceptual shape:

```python
@dataclass
class RuntimeContext:
    run_id: str
    run_name: str | None
    config_path: str
    output_dir: str
    robot_profile: RobotProfile
    model_profile: ModelProfile
    logger: RuntimeLogger
    registry: PluginRegistry
```

Allowed use:

- access run metadata
- access profiles
- emit logs
- inspect registry metadata if necessary

Disallowed use:

- mutate global runtime state unexpectedly
- bypass configured pipeline
- publish robot commands directly
- load unrelated plugins dynamically without config

## 4. InputAdapter

`InputAdapter` reads raw observations from an external source.

Interface:

```python
class InputAdapter(Protocol):
    def configure(self, config: AdapterConfig, context: RuntimeContext) -> None: ...
    def start(self) -> None: ...
    def read(self) -> RawObservation | None: ...
    def stop(self) -> None: ...
```

### Responsibilities

- connect to external observation source
- read raw observation messages
- handle adapter-specific start/stop lifecycle
- preserve source metadata when available

### Must Not

- perform robot semantic mapping
- perform model preprocessing
- create `ModelInput`
- publish commands

### `read` Semantics

For MVP, `read` may be blocking or timeout-based depending on config.

Recommended behavior:

- return `RawObservation` when data is available
- return `None` when no data is available before timeout
- raise adapter error for unrecoverable failures

The config should make timeout behavior explicit.

## 5. OutputAdapter

`OutputAdapter` publishes robot commands to an external sink.

Interface:

```python
class OutputAdapter(Protocol):
    def configure(self, config: AdapterConfig, context: RuntimeContext) -> None: ...
    def start(self) -> None: ...
    def publish(self, command: RobotCommand) -> None: ...
    def stop(self) -> None: ...
```

### Responsibilities

- connect to external command sink
- publish robot-specific command objects
- handle adapter-specific start/stop lifecycle

### Must Not

- infer command semantics
- convert `CanonicalAction` to robot command
- run model-specific postprocessing

## 6. ObservationMapper

`ObservationMapper` converts robot-specific raw observations to canonical semantic observations.

Interface:

```python
class ObservationMapper(Protocol):
    def configure(self, robot_profile: RobotProfile, context: RuntimeContext) -> None: ...
    def map(self, raw: RawObservation) -> CanonicalObservation: ...
```

### Responsibilities

- apply robot profile metadata
- map raw joint/sensor names into semantic groups
- preserve timestamps and frame metadata where possible
- populate canonical fields and `extras`

### Must Not

- build model-specific tensors
- normalize images for a specific model
- call `ModelRuntime`
- publish commands

## 7. ActionMapper

`ActionMapper` converts canonical semantic actions to robot-specific commands.

Interface:

```python
class ActionMapper(Protocol):
    def configure(self, robot_profile: RobotProfile, context: RuntimeContext) -> None: ...
    def map(self, action: CanonicalAction) -> RobotCommand: ...
```

### Responsibilities

- apply robot command conventions
- map semantic joint or end-effector targets to command fields
- validate or clamp robot limits according to config
- attach command metadata needed by output adapter

### Must Not

- parse model-specific output directly
- call `ModelRuntime`
- publish through transport

## 8. Processor

`Processor` transforms data between pipeline stages.

Interface:

```python
class Processor(Protocol):
    def configure(self, config: ProcessorConfig, context: RuntimeContext) -> None: ...
    def process(self, data: object) -> object: ...
```

### Responsibilities

- perform one explicit transformation or validation step
- use config params passed at construction/configure time
- return transformed data
- raise a processor error if input is invalid

### Recommended Properties

- deterministic for the same input and config
- minimal hidden state
- no direct IO unless explicitly documented
- clear expected input and output types

### Processor Chain Contract

The processor chain runs processors in declared order.

Example:

```yaml
preprocess:
  - type: resize_image
    params:
      width: 224
      height: 224
  - type: openpi_input_builder
```

Conceptual runner:

```python
data = initial_data
for processor in processors:
    data = processor.process(data)
return data
```

For MVP, preprocess chain final output must be valid `ModelInput`, and postprocess chain final output must be valid `CanonicalAction`.

## 9. ModelRuntime

`ModelRuntime` owns model lifecycle and inference.

Interface:

```python
class ModelRuntime(Protocol):
    def configure(self, config: ModelRuntimeConfig, context: RuntimeContext) -> None: ...
    def load(self) -> None: ...
    def warmup(self, sample_input: ModelInput) -> None: ...
    def infer(self, model_input: ModelInput) -> ModelOutput: ...
    def unload(self) -> None: ...
```

### Responsibilities

- validate model runtime config
- load model artifacts and runtime resources
- allocate required device resources
- run optional warmup
- execute inference
- release resources

### Must Not

- read robot observations
- publish robot commands
- own framework lifecycle state
- directly depend on a specific robot plugin

### Warmup Semantics

Warmup runs before normal inference.

Rules:

- warmup receives a valid `ModelInput`
- warmup may call the underlying model
- warmup output is discarded
- warmup failure prevents entering `RUNNING`

## 10. RuntimeLogger

`RuntimeLogger` records structured runtime events.

Interface:

```python
class RuntimeLogger(Protocol):
    def log_event(self, event_type: str, payload: dict) -> None: ...
    def log_error(self, error_type: str, payload: dict) -> None: ...
    def flush(self) -> None: ...
```

### Required Event Types

MVP should log:

- run started
- resolved config
- plugin resolved
- lifecycle transition
- warmup started/finished
- inference completed
- publish skipped due to pause
- error occurred
- run stopped

### Required Inference Payload

Inference event should include:

- run id
- iteration id
- timestamp
- model runtime type
- latency ms
- success or failure

## 11. PluginRegistry

`PluginRegistry` resolves concrete classes from config types.

Interface:

```python
class PluginRegistry(Protocol):
    def register_input_adapter(self, name: str, cls: type[InputAdapter]) -> None: ...
    def register_output_adapter(self, name: str, cls: type[OutputAdapter]) -> None: ...
    def register_observation_mapper(self, name: str, cls: type[ObservationMapper]) -> None: ...
    def register_action_mapper(self, name: str, cls: type[ActionMapper]) -> None: ...
    def register_processor(self, name: str, cls: type[Processor]) -> None: ...
    def register_model_runtime(self, name: str, cls: type[ModelRuntime]) -> None: ...

    def get_input_adapter(self, name: str) -> type[InputAdapter]: ...
    def get_output_adapter(self, name: str) -> type[OutputAdapter]: ...
    def get_observation_mapper(self, name: str) -> type[ObservationMapper]: ...
    def get_action_mapper(self, name: str) -> type[ActionMapper]: ...
    def get_processor(self, name: str) -> type[Processor]: ...
    def get_model_runtime(self, name: str) -> type[ModelRuntime]: ...
```

MVP may implement the registry with dictionaries.

Resolution failures must happen during `configure`, not after the service enters `RUNNING`.

## 12. ConfigLoader and Validator

Config loading and validation should happen before runtime resources are allocated.

Conceptual interface:

```python
class ConfigLoader(Protocol):
    def load(self, path: str) -> RunConfig: ...

class ConfigValidator(Protocol):
    def validate(self, config: RunConfig, registry: PluginRegistry) -> None: ...
```

Validation should check:

- required sections exist
- selected plugin types are registered
- required profile references exist
- processor configs are well formed
- adapter params are well formed
- logging output path is valid or creatable

## 13. InferenceService

`InferenceService` orchestrates the MVP runtime.

Conceptual interface:

```python
class InferenceService:
    def configure(self, config: RunConfig) -> None: ...
    def load_model(self) -> None: ...
    def warmup(self) -> None: ...
    def run(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
```

The service owns lifecycle state and component instances.

It should call component interfaces in this order:

```text
configure
  -> load_model
  -> warmup
  -> run
  -> stop
```

## 14. Error Types

MVP should define framework error categories.

Suggested categories:

```python
InferFwError
ConfigError
ValidationError
PluginResolutionError
LifecycleError
AdapterError
MapperError
ProcessorError
ModelRuntimeError
LoggingError
```

Error payloads should include:

- component type
- component name, if available
- lifecycle state
- config path, if relevant
- original exception message

## 15. Pause and Stop Semantics

### Pause

Pause means:

- runtime resources remain loaded
- input may still be read, depending on service loop policy
- inference may be skipped or continue, depending on config
- output publish must be suspended

MVP default:

- keep service alive
- skip publishing output
- log skipped publish events

### Stop

Stop means:

- exit service loop
- stop input adapter
- stop output adapter
- unload model runtime
- flush logger
- transition to `STOPPED`

Stop should attempt cleanup even if the service is in `ERROR`.

## 16. MVP Interface Acceptance Criteria

The interface design is acceptable when:

- fake components can implement all required interfaces
- dummy model runtime can run without robot dependencies
- service loop can call only interfaces, not concrete plugin internals
- config validation can resolve every component before runtime starts
- unit tests can mock each interface independently
- adding a real model runtime does not require editing robot mapper code
- adding a real robot mapper does not require editing model runtime code
