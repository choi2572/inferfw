# Runtime Lifecycle

This document defines the MVP runtime lifecycle for the inference service framework.

The lifecycle exists to make model loading, warmup, inference, pause, stop, and error behavior explicit and testable.

## 1. Lifecycle Goals

The lifecycle should:

- prevent invalid call ordering
- keep runtime resource allocation explicit
- fail before `RUNNING` when config or plugin setup is invalid
- make warmup behavior clear
- support pause without unloading the model
- attempt cleanup after errors
- produce structured lifecycle logs

## 2. States

MVP lifecycle states:

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

### CREATED

Initial state after service object construction.

Allowed next states:

- `CONFIGURED`
- `ERROR`

No plugins should be started and no model resources should be loaded in this state.

### CONFIGURED

Config has been loaded, validated, and resolved. Component instances have been created and configured.

Allowed next states:

- `MODEL_LOADED`
- `STOPPED`
- `ERROR`

Expected completed work:

- config validation
- profile resolution
- plugin resolution
- component construction
- processor chain construction
- logger initialization

### MODEL_LOADED

Model runtime resources have been loaded.

Allowed next states:

- `WARMED_UP`
- `STOPPED`
- `ERROR`

Expected completed work:

- `ModelRuntime.load`
- model artifacts loaded or dummy runtime initialized
- device resources allocated when needed

Adapters may be configured but should not need to publish output yet.

### WARMED_UP

Warmup has completed successfully.

Allowed next states:

- `RUNNING`
- `STOPPED`
- `ERROR`

Expected completed work:

- warmup input created or loaded
- `ModelRuntime.warmup` executed
- warmup output discarded
- warmup event logged

If warmup is disabled, the service may transition from `MODEL_LOADED` to `WARMED_UP` as a no-op with a log event.

### RUNNING

The service loop is active.

Allowed next states:

- `PAUSED`
- `STOPPED`
- `ERROR`

Expected behavior:

- input adapter reads observations
- mapper converts observations
- preprocess chain builds model input
- model runtime runs inference
- postprocess chain builds canonical action
- action mapper builds robot command
- output adapter publishes command
- iteration summaries and latency are logged

### PAUSED

Runtime resources remain loaded, but output publish is suspended.

Allowed next states:

- `RUNNING`
- `STOPPED`
- `ERROR`

MVP default pause behavior:

- service remains alive
- model remains loaded
- input may still be read
- inference is skipped by default
- output publish is skipped
- skipped publish or skipped inference is logged

Pause policy may become configurable through `lifecycle.pause_policy`.

### STOPPED

The service has stopped and resources have been released.

Allowed next states:

- none for MVP

Expected completed work:

- service loop exited
- input adapter stopped
- output adapter stopped
- model runtime unloaded
- logger flushed

MVP does not require restart from `STOPPED`. A new service instance should be created for a new run.

### ERROR

An unrecoverable error occurred or an invalid transition was attempted.

Allowed next states:

- `STOPPED`

Expected behavior:

- error context logged
- service should attempt cleanup on `stop`
- original exception context should be preserved

## 3. Valid Transitions

Valid transitions:

```text
CREATED -> CONFIGURED
CONFIGURED -> MODEL_LOADED
MODEL_LOADED -> WARMED_UP
WARMED_UP -> RUNNING
RUNNING -> PAUSED
PAUSED -> RUNNING
RUNNING -> STOPPED
PAUSED -> STOPPED
CONFIGURED -> STOPPED
MODEL_LOADED -> STOPPED
WARMED_UP -> STOPPED
ERROR -> STOPPED
any non-STOPPED state -> ERROR
```

Invalid examples:

- `CREATED -> RUNNING`
- `CONFIGURED -> RUNNING`
- `MODEL_LOADED -> RUNNING`
- `STOPPED -> RUNNING`
- `STOPPED -> ERROR`

Invalid transitions should raise `LifecycleError` and log the attempted transition.

## 4. Lifecycle Method Contracts

### configure

Input:

```text
RunConfig
```

Allowed state:

```text
CREATED
```

Responsibilities:

- validate config shape
- resolve robot profile
- resolve model profile
- resolve plugin classes
- instantiate and configure components
- build preprocess and postprocess chains
- initialize logger
- write resolved config if enabled

On success:

```text
CREATED -> CONFIGURED
```

On failure:

```text
CREATED -> ERROR
```

### load_model

Allowed state:

```text
CONFIGURED
```

Responsibilities:

- call `ModelRuntime.load`
- log model load start and finish

On success:

```text
CONFIGURED -> MODEL_LOADED
```

On failure:

```text
CONFIGURED -> ERROR
```

### warmup

Allowed state:

```text
MODEL_LOADED
```

Responsibilities:

- create or load sample `ModelInput`
- call `ModelRuntime.warmup`
- discard any warmup output
- log warmup latency

On success:

```text
MODEL_LOADED -> WARMED_UP
```

On failure:

```text
MODEL_LOADED -> ERROR
```

### run

Allowed state:

```text
WARMED_UP
```

Responsibilities:

- start input adapter
- start output adapter
- enter service loop
- log lifecycle transition

On start:

```text
WARMED_UP -> RUNNING
```

On normal completion:

```text
RUNNING -> STOPPED
```

On loop failure:

```text
RUNNING -> ERROR
```

### pause

Allowed state:

```text
RUNNING
```

Responsibilities:

- suspend output publishing
- keep resources loaded
- log transition

On success:

```text
RUNNING -> PAUSED
```

### resume

Allowed state:

```text
PAUSED
```

Responsibilities:

- allow loop to publish output again
- log transition

On success:

```text
PAUSED -> RUNNING
```

### stop

Allowed states:

```text
CONFIGURED
MODEL_LOADED
WARMED_UP
RUNNING
PAUSED
ERROR
```

Responsibilities:

- request loop exit
- stop input adapter if started
- stop output adapter if started
- unload model runtime if loaded
- flush logger
- log stop event

On success:

```text
<allowed state> -> STOPPED
```

Stop should be best-effort. Cleanup should continue even if one component fails during stop.

## 5. Resource Ownership by State

| Resource | CREATED | CONFIGURED | MODEL_LOADED | WARMED_UP | RUNNING | PAUSED | STOPPED |
| --- | --- | --- | --- | --- | --- | --- | --- |
| resolved config | no | yes | yes | yes | yes | yes | yes |
| component instances | no | yes | yes | yes | yes | yes | released or inactive |
| model resources | no | no | yes | yes | yes | yes | unloaded |
| input adapter connection | no | no | no | no | yes | policy-dependent | stopped |
| output adapter connection | no | no | no | no | yes | started but publish skipped | stopped |
| logger | no | yes | yes | yes | yes | yes | flushed |

## 6. Error Handling

Lifecycle errors should include:

- current state
- requested transition
- method name
- component name, if applicable
- original exception, if applicable

MVP error behavior:

- config errors occur during `configure`
- plugin resolution errors occur during `configure`
- model load errors occur during `load_model`
- warmup errors occur during `warmup`
- adapter start errors occur during `run`
- loop errors occur during `RUNNING`
- cleanup errors are logged but should not prevent other cleanup attempts

## 7. Logging Requirements

Every lifecycle transition should log:

- run id
- previous state
- next state
- method name
- timestamp
- success or failure
- error payload, if any

Required lifecycle events:

- service created
- configure started/finished
- model load started/finished
- warmup started/finished/skipped
- run started
- pause requested/completed
- resume requested/completed
- stop requested/completed
- error entered

## 8. MVP Lifecycle Acceptance Criteria

The lifecycle implementation is acceptable when:

- invalid transitions raise `LifecycleError`
- fake run follows `CREATED -> CONFIGURED -> MODEL_LOADED -> WARMED_UP -> RUNNING -> STOPPED`
- warmup output is never published
- `pause` prevents output publishing
- `stop` unloads model and flushes logs
- `stop` can be called after `ERROR`
- lifecycle transitions are logged with previous and next state
