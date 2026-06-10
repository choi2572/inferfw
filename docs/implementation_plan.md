# Implementation Plan

This document defines the MVP implementation plan for the inference service framework.

The priority is to build an executable fake end-to-end inference service loop first. Real ROS2, DDS, robot, and model runtime integrations should come after the core loop, interfaces, lifecycle, config validation, logging, and tests are stable.

## 1. Implementation Goal

The MVP implementation is complete when:

- `inferfw validate --config config/pipeline_example.yaml` validates the canonical pipeline config
- `inferfw run --config config/pipeline_example.yaml` runs one inference iteration with configured runtime components
- model warmup runs and does not publish output
- fake output adapter captures one robot command
- run logs include resolved config, lifecycle events, and inference latency
- default tests run without ROS2, DDS, GPU, model checkpoints, or robot hardware

## 2. Development Principles

- Close the fake executable loop before adding real integrations.
- Keep framework core independent from concrete model/robot plugins.
- Keep optional dependencies out of default tests.
- Validate config before loading model resources.
- Make lifecycle transitions explicit and testable.
- Treat fake plugins as baseline test plugins, not throwaway demos.
- Prefer small, concrete modules over broad abstractions.

## 3. Milestone 0: Project Skeleton

Goal: create the minimum Python package structure.

Deliverables:

- `pyproject.toml`
- `inferfw/` package
- `tests/` directory
- basic CLI placeholder
- ruff configuration

Suggested layout:

```text
inferfw/
  __init__.py
  cli.py
  core/
  interfaces/
  data/
  config/
  registry/
  pipeline/
  lifecycle/
  logging/
  plugins/
tests/
config/
```

Acceptance:

- package imports successfully
- `python -m inferfw.cli --help` or equivalent placeholder works
- `ruff check .` can run

## 4. Milestone 1: Core Data and Interfaces

Goal: define the contracts used by the service loop.

Deliverables:

- canonical data classes
- raw/model/command data classes
- interface protocols
- framework error classes
- runtime context class

Files likely involved:

```text
inferfw/data/
inferfw/interfaces/
inferfw/core/context.py
inferfw/core/errors.py
```

Acceptance:

- fake data objects can be constructed
- public interfaces have type hints
- tests cover basic data validation such as joint name/value length

## 5. Milestone 2: Config Loader and Validation

Goal: load and validate the pipeline config.

Deliverables:

- YAML config loader
- pipeline config schema
- request server schema
- robot execution schema
- model binding schema
- validation errors

Acceptance:

- valid `config/pipeline_example.yaml` loads
- missing top-level section fails
- unsupported request server type fails
- malformed model binding fails
- unresolved processor or runtime config fails

## 6. Milestone 3: Local Plugin Registry

Goal: register and resolve plugin classes by key.

Deliverables:

- `PluginRegistry`
- register/get methods for all plugin types
- built-in registration entrypoint
- plugin resolution errors

Plugin types:

- input adapter
- output adapter
- observation mapper
- action mapper
- processor
- model runtime

Acceptance:

- built-in fake plugin keys register
- unknown keys fail during validation
- duplicate registration behavior is defined and tested

## 7. Milestone 4: Lifecycle State Machine

Goal: enforce valid runtime state transitions.

Deliverables:

- lifecycle state enum
- transition validator
- lifecycle error handling
- lifecycle logging hooks

Acceptance:

- valid transition sequence passes
- invalid transitions raise `LifecycleError`
- `ERROR -> STOPPED` is allowed
- `STOPPED -> RUNNING` is rejected

## 8. Milestone 5: Processor Chain Runner

Goal: execute ordered preprocess and postprocess chains.

Deliverables:

- processor chain class
- processor construction from config
- disabled processor handling
- processor error context

Acceptance:

- processors run in declared order
- disabled processors are skipped
- processor error includes processor key and index
- chain can convert fake observation to dummy model input through fake processors

## 9. Milestone 6: Fake and Dummy Plugins

Goal: provide dependency-free plugins for local execution and tests.

Deliverables:

- `FakeInputAdapter`
- `FakeOutputAdapter`
- `FakeObservationMapper`
- `FakeActionMapper`
- `IdentityProcessor`
- `DummyInputBuilder`
- `DummyOutputParser`
- `ValidateAction`
- `DummyModelRuntime`
- fake robot profile
- dummy model profile

Acceptance:

- fake input produces `RawObservation`
- fake mapper produces `CanonicalObservation`
- dummy input builder produces `ModelInput`
- dummy runtime produces deterministic `ModelOutput`
- dummy output parser produces `CanonicalAction`
- fake action mapper produces `RobotCommand`
- fake output adapter captures command

## 10. Milestone 7: Structured Logging

Goal: write enough run metadata for model evaluation traceability.

Deliverables:

- runtime logger
- event JSONL writer
- resolved config writer
- run summary writer
- data summary helper

Acceptance:

- run output directory is created
- resolved config is written
- lifecycle events are written
- iteration event includes latency
- logs avoid full image/tensor payloads by default

## 11. Milestone 8: Inference Service Loop

Goal: connect config, registry, lifecycle, plugins, processors, model runtime, adapters, and logger.

Deliverables:

- `InferenceService`
- `configure`
- `load_model`
- `warmup`
- `run`
- `pause`
- `resume`
- `stop`
- max iteration support
- input timeout handling
- best-effort cleanup

Acceptance:

- fake run executes one full iteration
- warmup does not publish output
- `max_iterations` stops the loop
- inference latency is logged
- output command is captured
- stop unloads model and flushes logger

## 12. Milestone 9: CLI

Goal: expose MVP runtime through command line.

Deliverables:

- `inferfw validate --config ...`
- `inferfw run --config ...`
- `inferfw list-plugins`
- clear exit codes
- basic error printing

Acceptance:

- validate succeeds for fake config
- validate fails for invalid config
- run executes fake loop
- list-plugins shows built-in plugin keys

## 13. Milestone 10: Tests and CI Baseline

Goal: lock the fake MVP behavior with tests.

Deliverables:

- unit tests
- contract tests
- fake service loop integration test
- ruff check
- ruff format check

Required tests:

- lifecycle valid/invalid transitions
- config validation success/failure
- registry resolution
- processor chain order
- fake plugin contracts
- dummy model runtime
- fake service loop
- warmup output not publishing
- logging output creation

Acceptance:

- `pytest` passes without optional dependencies
- `ruff check .` passes
- `ruff format --check .` passes

## 14. Milestone 11: Real-Oriented Adapter Stubs

Goal: create extension points for ROS2 input and DDS output without blocking fake MVP.

Deliverables:

- `Ros2InputAdapter` stub
- `DdsOutputAdapter` or `UnitreeDdsOutputAdapter` stub
- dependency error behavior
- real-oriented example config

Acceptance:

- fake tests still pass without ROS2/DDS
- selecting ROS2/DDS plugin without dependencies fails clearly
- config schema supports real-oriented adapter params

## 15. Milestone 12: First Real Model or Robot Integration

Goal: integrate one real model runtime or one real robot path after fake loop stability.

Candidate paths:

- real VLA model runtime with fake robot
- fake model runtime with real robot IO stubs
- replay input with real model runtime

Recommended first real integration:

```text
real model runtime + fake input/output
```

Reason:

- tests model runtime contract without robot command risk
- validates model profile and processor chain
- keeps deployment simpler than real robot control

Acceptance:

- selected real runtime loads
- warmup runs
- one inference iteration runs
- output is converted to fake command or captured action
- failure modes are logged clearly

## 16. Work Breakdown by Priority

Priority 0:

- package skeleton
- data classes
- interfaces
- config loader
- registry
- lifecycle

Priority 1:

- fake plugins
- dummy runtime
- processor chain
- logger
- service loop
- CLI
- fake smoke test

Priority 2:

- ROS2 input stub
- DDS output stub
- real-oriented configs
- optional dependency handling

Priority 3:

- first real model runtime
- first real robot mapper
- replay input
- metrics improvements

## 17. Implementation Risks

### Over-abstracting before execution

Risk:

- large abstractions slow down MVP and hide actual runtime needs

Mitigation:

- fake loop first
- add abstractions only when repeated concrete needs appear

### Optional dependency leakage

Risk:

- ROS2/DDS/Torch imports break default tests

Mitigation:

- plugin-scoped imports
- dependency errors only when selected
- fake tests run dependency-free

### Core/plugin boundary drift

Risk:

- robot/model logic leaks into core service loop

Mitigation:

- tests and review checklist check imports and boundaries
- keep mappers/processors/runtime as plugins

### Logging too much data

Risk:

- logs become huge or leak sensitive/model data

Mitigation:

- log summaries by default
- no full tensors/images unless explicitly enabled later

### Real robot integration too early

Risk:

- hardware-specific issues delay core framework

Mitigation:

- fake loop and real model/fake IO path before real robot command path

## 18. MVP Done Definition

MVP is done when:

- fake config validates
- fake service loop runs through CLI
- one full inference iteration completes
- warmup output is not published
- output command is captured
- run logs contain resolved config, lifecycle events, and inference latency
- tests pass without optional dependencies
- docs include specification, roles, MVP scope, architecture, interfaces, data model, config schema, plugin architecture, lifecycle, service loop, code quality, testing, deployment, implementation plan, and examples

## 19. Post-MVP Next Steps

After MVP:

- implement or wire a real model runtime
- implement replay input adapter
- implement ROS2 input adapter
- implement DDS output adapter
- add one real robot profile and mapper
- add model/robot compatibility checks
- add richer metrics
- add replay-based regression tests
- evaluate whether package entry-point plugin discovery is needed
