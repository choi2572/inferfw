# Testing Strategy

This document defines the MVP testing strategy for the inference service framework.

The main testing goal is to verify the execution framework without requiring ROS2, DDS, GPU, model checkpoints, or robot hardware.

## 1. Testing Goals

MVP tests should prove that:

- the fake end-to-end loop works
- core lifecycle transitions are correct
- config validation catches bad runs before execution
- registry resolution is deterministic
- processor chains run in declared order
- model runtime can be swapped without robot code changes
- robot mapping can be swapped without model code changes
- logging captures enough run metadata for evaluation traceability

## 2. Test Levels

### 2.1 Unit Tests

Unit tests validate isolated components.

Targets:

- canonical data classes
- lifecycle state machine
- config loader and validator
- plugin registry
- processor chain runner
- fake adapters
- fake mappers
- dummy model runtime
- structured logger

Unit tests must not require optional external dependencies.

### 2.2 Contract Tests

Contract tests verify that plugin implementations satisfy framework interfaces.

Targets:

- `InputAdapter`
- `OutputAdapter`
- `ObservationMapper`
- `ActionMapper`
- `Processor`
- `ModelRuntime`

Examples:

- fake input adapter returns `RawObservation` or `None`
- fake observation mapper returns `CanonicalObservation`
- dummy runtime returns `ModelOutput`
- fake action mapper returns `RobotCommand`

### 2.3 Integration Tests

Integration tests connect multiple framework components.

MVP integration targets:

- config load -> registry resolve -> component construction
- observation mapper -> preprocess chain
- model runtime -> postprocess chain
- action mapper -> output adapter

These tests should use fake and dummy plugins.

### 2.4 Smoke Test

The smoke test runs the full fake service loop.

Expected path:

```text
FakeInputAdapter
  -> FakeObservationMapper
  -> IdentityProcessor
  -> DummyInputBuilder
  -> DummyModelRuntime
  -> DummyOutputParser
  -> ValidateAction
  -> FakeActionMapper
  -> FakeOutputAdapter
```

The smoke test should:

- load an example fake config
- validate config
- configure service
- load dummy model
- warm up
- run one iteration
- capture one output command
- stop cleanly
- write logs

## 3. Tests That Must Not Need Hardware

The default test suite must run without:

- ROS2
- DDS
- Unitree SDK
- GPU
- CUDA
- Torch
- TensorRT
- ONNX Runtime
- model checkpoints
- robot hardware

Optional dependency tests should be separated and skipped when dependencies are missing.

## 4. Required MVP Test Cases

### 4.1 Lifecycle

Test valid flow:

```text
CREATED -> CONFIGURED -> MODEL_LOADED -> WARMED_UP -> RUNNING -> STOPPED
```

Test invalid transitions:

- `CREATED -> RUNNING`
- `CONFIGURED -> RUNNING`
- `MODEL_LOADED -> RUNNING`
- `STOPPED -> RUNNING`

Test cleanup:

- `stop` after `ERROR`
- model unload called when loaded
- logger flush called on stop

### 4.2 Config Validation

Test failures:

- missing top-level section
- unsupported request server type
- malformed model input binding
- malformed model output binding
- unknown processor key
- unknown model runtime key
- invalid robot joint config
- postprocess output group not present in robot joint config

Test success:

- `config/pipeline_example.yaml` validates
- processor order is preserved
- preprocess keys align with model input bindings
- postprocess keys align with model output bindings

### 4.3 Registry

Test:

- built-in fake plugins register
- duplicate registration behavior is defined
- unknown key raises `PluginResolutionError`
- each plugin kind has independent namespace

### 4.4 Processor Chain

Test:

- processors run in declared order
- output of one processor is input to next
- processor error includes processor type and index
- disabled processors are skipped

### 4.5 Canonical Data

Test:

- joint names and positions length match
- action joint targets validate
- metadata is preserved across fake path where expected
- summaries do not serialize large arrays

### 4.6 Model Runtime

Test:

- dummy runtime configures
- dummy runtime loads
- dummy runtime warmup runs
- dummy runtime infer returns deterministic output
- dummy runtime unloads
- infer before load fails if implementation tracks loaded state

### 4.7 Service Loop

Test:

- fake loop completes one iteration
- warmup does not publish output
- `max_iterations` stops the loop
- input timeout is recoverable
- output adapter captures command
- inference latency is logged
- pause suppresses publish

### 4.8 Logging

Test:

- run id is present
- resolved config is written when enabled
- lifecycle events are logged
- iteration event is logged
- error event includes component context
- logger flushes on stop

## 5. Optional Integration Tests

These tests are not required for default MVP CI.

Optional targets:

- ROS2 input adapter
- DDS output adapter
- real model runtime
- simulator adapter
- replay adapter
- GPU runtime

Rules:

- mark optional tests clearly
- skip when dependency is missing
- do not make optional dependencies required for fake tests

## 6. Test Fixtures

Recommended fixtures:

- pipeline config
- invalid config variants
- built-in plugin registry
- temporary run output directory
- fake raw observation
- fake canonical observation
- dummy model input
- dummy model output
- fake canonical action

Fixtures should be small and deterministic.

## 7. Golden Data

MVP can use small golden data for fake tests.

Golden examples:

- expected fake `CanonicalObservation` summary
- expected dummy `ModelInput` keys
- expected dummy `ModelOutput` keys
- expected fake `RobotCommand` payload
- expected lifecycle event sequence

Avoid storing large binary golden files in MVP.

## 8. CI Strategy

Default CI should run:

```bash
ruff check .
ruff format --check .
pytest
```

If type checking is added:

```bash
mypy inferfw tests
```

CI should not require optional runtime dependencies.

## 9. Test Directory Direction

Suggested layout:

```text
tests/
  unit/
    test_lifecycle.py
    test_registry.py
    test_processor_chain.py
    test_config_validation.py
    test_canonical_data.py
  contract/
    test_fake_plugins.py
    test_dummy_runtime.py
  integration/
    test_fake_service_loop.py
  fixtures/
    config/
```

This can be adjusted during implementation.

## 10. MVP Testing Acceptance Criteria

Testing is acceptable when:

- default tests run without optional external dependencies
- fake service loop has at least one end-to-end smoke test
- lifecycle valid and invalid transitions are covered
- config validation failure cases are covered
- registry resolution is covered
- processor chain order is covered
- warmup output not publishing is covered
- logs are asserted enough to verify run traceability
