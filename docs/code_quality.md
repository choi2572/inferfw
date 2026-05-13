# Code Quality

This document defines MVP code quality expectations for the inference service framework.

The goal is to keep the implementation small, executable, and testable while preserving the core/plugin boundaries needed for model runtime and robot integration swappability.

## 1. Quality Goals

MVP code should:

- keep framework core independent from concrete model and robot plugins
- make the fake end-to-end loop easy to run and test
- expose clear interfaces and error boundaries
- validate config before runtime resource allocation
- use type hints on public interfaces
- produce actionable logs on failure

MVP code should not:

- introduce large abstractions before the fake loop works
- require ROS2, DDS, GPU, or model checkpoints for core tests
- hide side effects in processors or config loading
- hard-code one robot or one model into core

## 2. Package Boundary Rules

Required dependency direction:

```text
core -> interfaces/data/config/registry/pipeline/lifecycle/logging
plugins -> interfaces/data
core -X-> concrete plugins
```

Rules:

- framework core must not import concrete robot or model plugins inside service logic
- plugins must depend on public interfaces, not private core internals
- adapters may depend on external transport libraries
- model runtimes may depend on model/runtime libraries
- optional dependencies must not be required for fake tests

## 3. Public API Policy

Public API includes:

- interface classes
- canonical data classes
- config schema classes
- registry methods
- lifecycle states
- framework error types
- CLI commands

Expectations:

- public APIs should have type hints
- public method names should be stable after MVP implementation begins
- breaking changes should update docs and tests together
- internal helpers may change freely

## 4. Typing Policy

MVP should use Python type hints for public surfaces.

Recommended:

- `Protocol` for plugin interfaces
- `dataclass` or pydantic models for structured data
- explicit return types on public methods
- `dict[str, object]` for plugin-specific params and metadata

Avoid:

- untyped public methods
- large unstructured dictionaries in core runtime state
- plugin-specific concrete types in core signatures

Type checking can start permissive and become stricter after the fake loop works.

## 5. Formatting and Linting

Preferred toolchain:

```bash
ruff format .
ruff check .
```

MVP should use one formatter and one linter. `ruff` is sufficient initially.

Lint rules should prioritize:

- unused imports
- syntax errors
- obvious undefined names
- import sorting
- simple style consistency

Do not block early MVP work on overly strict style rules.

## 6. Config Validation

Config validation must happen before:

- model artifact loading
- adapter start
- service loop entry
- output publishing

Validation should catch:

- missing required top-level config sections
- unknown plugin keys
- missing robot/model profiles
- malformed processor configs
- unsupported config version
- selected runtime not supported by model profile

Validation errors should identify:

- config path
- config section
- field name
- expected value or registered keys when useful

## 7. Error Handling Policy

Use framework error categories for component boundaries.

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

Rules:

- errors should preserve original exception context
- lifecycle errors should include current state and requested transition
- plugin resolution errors should include plugin kind and key
- loop errors should include iteration id when available
- cleanup errors should be logged but should not prevent further cleanup attempts

## 8. Logging Policy

MVP logging should be structured and file-based.

Required logs:

- run started
- resolved config written
- plugin resolution results
- lifecycle transitions
- warmup start/finish/skipped
- iteration completed
- inference latency
- publish skipped due to pause
- errors
- run stopped

Avoid logging:

- full image arrays
- full tensors
- large binary payloads
- secrets or API tokens

Prefer logging summaries:

- keys
- shapes
- dtypes
- command type
- plugin key
- latency

## 9. Processor Quality Rules

Processors should:

- do one transformation or validation step
- document expected input and output
- use params from config
- be deterministic where possible
- avoid hidden IO
- raise `ProcessorError` or documented exceptions on invalid input

Processors should not:

- publish commands
- read external observations
- load model checkpoints
- mutate global runtime state

## 10. Adapter Quality Rules

Adapters are allowed to have IO side effects.

Input adapters should:

- start and stop cleanly
- return `RawObservation` or `None`
- preserve source metadata
- raise clear adapter errors for unrecoverable failures

Output adapters should:

- start and stop cleanly
- publish `RobotCommand`
- avoid interpreting canonical action semantics
- expose fake capture behavior for tests

## 11. Model Runtime Quality Rules

Model runtimes should:

- validate runtime params during `configure`
- allocate resources during `load`
- run warmup before normal inference when enabled
- release resources during `unload`
- expose clear errors for missing artifacts or dependencies

Model runtimes should not:

- publish robot commands
- depend on a concrete robot plugin
- mutate framework lifecycle state directly

## 12. Review Checklist

Before merging MVP core code, check:

- fake loop runs end to end
- tests pass without optional dependencies
- core does not import concrete model/robot plugins in service logic
- config validation catches unknown plugin keys
- lifecycle invalid transitions are tested
- logs include run id and lifecycle events
- cleanup happens after error

## 13. MVP Code Quality Acceptance Criteria

Code quality is acceptable when:

- `ruff format` can run cleanly
- `ruff check` can run cleanly or with documented temporary exceptions
- public interfaces have type hints
- fake smoke test runs without ROS2/DDS/GPU/model artifacts
- framework core remains independent of concrete robot/model plugins
- errors and logs are actionable enough to debug failed config or failed loop execution
