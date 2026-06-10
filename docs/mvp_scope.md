# MVP Scope

This document defines the MVP boundary for the inference service framework.

The broader project goal is an inference service framework for embodied AI model evaluation MLOps. The MVP goal is narrower: build a runnable single-service inference loop that can execute a model runtime through configurable adapters, mappers, processors, and logging.

## 1. MVP Objective

The MVP must prove that the framework can run an embodied model evaluation service without hard-coding one model or one robot into the runtime core.

The MVP is successful when:

- a full inference loop can run with fake components on a development machine
- the same loop can be configured toward a real ROS2 input and DDS output path
- model runtime, robot mapping, processors, and adapters are resolved through config and registry
- lifecycle and logging are handled by framework core
- tests can validate the loop without robot hardware

## 2. In Scope

MVP includes the following capabilities.

### 2.1 Single Runtime Process

The service runs as one local process.

Included:

- one CLI entrypoint
- one loaded pipeline config
- one lifecycle state machine
- one service loop
- one logging output directory per run

Excluded:

- distributed workers
- remote orchestration
- multi-process scheduling
- autoscaling

### 2.2 Single-Stage Inference Loop

MVP supports one model stage.

Runtime flow:

```text
InputAdapter
  -> ObservationMapper
  -> Preprocess Chain
  -> ModelRuntime
  -> Postprocess Chain
  -> ActionMapper
  -> OutputAdapter
```

Excluded:

- VLA -> RL multi-stage graph
- stage edge contracts
- branching pipelines
- parallel model execution

### 2.3 Config-Based Composition

The run must be assembled from YAML config.

Config chooses:

- request server type and service endpoints
- robot command conventions and topics
- model runtime keys, runtime config names, and artifact paths
- input and output interface bindings
- preprocessors
- postprocessors
- runtime settings

MVP does not require a full config override system, but config validation must happen before execution.

### 2.4 Pluggable Model Runtime

The model runtime must be replaceable without editing framework core.

MVP includes:

- `ModelRuntime` interface
- dummy model runtime
- runtime registry
- runtime config
- load/warmup/infer/unload lifecycle calls
- inference latency logging

MVP may include a real VLA runtime stub or thin adapter, but the first complete loop should use a dummy runtime to avoid blocking on model dependencies.

### 2.5 Pluggable Robot Mapping

Robot-specific mapping must be outside framework core.

MVP includes:

- `ObservationMapper` interface
- `ActionMapper` interface
- fake robot mapper
- robot profile schema draft
- robot mapper registry

The first mapper can be fake or minimal. The important MVP requirement is that mapper logic is not embedded in the service loop.

### 2.6 Processor Chain

MVP includes ordered preprocess and postprocess chains.

Required behavior:

- processors are resolved by type
- processors receive config params
- processors run in declared order
- processor errors fail the current run or transition to `ERROR`
- processor chain execution is testable without robot/model dependencies

MVP processors:

- identity processor
- simple validation processor
- dummy model input builder
- dummy model output parser
- optional clamp processor

### 2.7 Input and Output Adapters

MVP includes both fake adapters and real-system adapter stubs.

Required first:

- fake input adapter
- fake output adapter

Expected next:

- ROS2 input adapter stub
- DDS output adapter stub

Fake adapters are required so local development, CI, and smoke tests can run without ROS2, DDS, robot hardware, or GPU runtime.

### 2.8 Lifecycle

MVP includes explicit lifecycle management.

States:

```text
CREATED
CONFIGURED
MODEL_LOADED
WARMED_UP
RUNNING
PAUSED
STOPPED
ERROR
```

Required behavior:

- invalid transitions fail clearly
- `configure` resolves config and plugins
- `load_model` loads runtime resources
- `warmup` runs inference and discards output
- `run` starts the service loop
- `pause` keeps resources loaded and stops publishing output
- `stop` releases adapters, model runtime, and logs
- `ERROR` records failure context

### 2.9 Basic Logging

MVP logging must support model evaluation traceability.

Required fields:

- run id
- timestamp
- lifecycle events
- config path
- resolved config snapshot
- robot profile id
- model profile id
- adapter types
- processor chain
- inference latency
- errors

MVP does not require a metrics database or experiment tracking backend.

### 2.10 Local CLI

MVP should expose a minimal CLI.

Target commands:

```bash
inferfw validate --config config/pipeline_example.yaml
inferfw run --config config/pipeline_example.yaml
inferfw list-plugins
```

The CLI can be implemented after the core loop works, but the docs and package layout should assume this entrypoint.

## 3. Out of Scope

The following are explicitly out of scope for MVP.

- multi-stage graph pipeline
- cloud model registry
- remote artifact download
- experiment tracking backend
- dashboard
- distributed runtime
- scheduler/orchestrator
- automated benchmark service
- hardware-in-the-loop automation
- safety policy engine
- advanced replay evaluation
- production robot safety certification
- full ROS2/DDS feature coverage
- plugin package discovery through installed Python packages

These can be added after the MVP loop, interface contracts, and fake-component tests are stable.

## 4. MVP Reference Flow

The target real-system flow is:

```text
ROS2 observation
  -> robot ObservationMapper
  -> preprocess chain
  -> VLA ModelRuntime
  -> postprocess chain
  -> robot ActionMapper
  -> DDS publish
```

The required first implementation flow is:

```text
FakeInputAdapter
  -> FakeObservationMapper
  -> preprocess chain
  -> DummyModelRuntime
  -> postprocess chain
  -> FakeActionMapper
  -> FakeOutputAdapter
```

The fake flow is not a throwaway demo. It is the baseline smoke test for the framework.

## 5. MVP Success Criteria

The MVP is complete when all of the following are true.

### 5.1 Execution

- `inferfw validate --config ...` validates an example config.
- `inferfw run --config ...` runs the fake end-to-end loop.
- The loop executes at least one inference iteration.
- The loop can stop cleanly.
- Warmup runs before normal inference and does not publish output.

### 5.2 Swappability

- dummy model runtime can be replaced through config.
- fake robot mapper can be replaced through config.
- processor chain can be changed through config.
- fake input/output adapters can be replaced through config.
- framework core does not import a concrete model or robot plugin directly.

### 5.3 Observability

- run metadata is logged.
- lifecycle transitions are logged.
- inference latency is logged.
- errors include enough context to identify failed component type and config path.

### 5.4 Testability

- unit tests cover lifecycle transitions.
- unit tests cover processor chain ordering.
- unit tests cover config validation failure cases.
- unit tests cover registry resolution.
- smoke test covers fake input to fake output.
- tests run without ROS2, DDS, GPU, model checkpoints, or robot hardware.

## 6. MVP Deliverables

Expected code deliverables:

- package skeleton
- core interfaces
- canonical data classes
- config loader and validator
- local plugin registry
- processor chain runner
- lifecycle state machine
- service loop
- fake input adapter
- fake output adapter
- fake observation mapper
- fake action mapper
- dummy model runtime
- basic structured logger
- CLI entrypoint
- example configs
- smoke tests

Expected documentation deliverables:

- specification
- roles and ownership
- MVP scope
- architecture
- interfaces
- canonical data
- config schema
- plugin architecture
- runtime lifecycle
- service loop
- code quality
- testing strategy
- deployment
- implementation plan

## 7. Implementation Priority

MVP implementation should prioritize closing the executable loop before adding real robot/model integrations.

Recommended order:

1. core interfaces
2. canonical data classes
3. config schema
4. local registry
5. lifecycle state machine
6. processor chain runner
7. fake components
8. dummy model runtime
9. service loop
10. structured logging
11. CLI
12. smoke tests
13. ROS2 input adapter stub
14. DDS output adapter stub

This order keeps the first milestone focused on execution and testability.
