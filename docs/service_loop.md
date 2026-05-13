# Service Loop

This document defines the MVP service loop for the inference service framework.

The service loop is the executable path that connects input, mapping, preprocessing, model inference, postprocessing, action mapping, output publishing, and logging.

## 1. Service Loop Goals

The service loop should:

- run one single-stage inference pipeline
- call only interfaces, not concrete plugin internals
- support fake end-to-end execution
- measure inference latency
- respect lifecycle state
- support pause and stop behavior
- produce useful logs for model evaluation

The service loop should not:

- contain robot-specific mapping logic
- contain model-specific tensor construction logic
- directly import concrete model or robot plugins
- assume ROS2, DDS, GPU, or robot hardware is available

## 2. MVP Loop Shape

Runtime flow:

```text
read raw observation
  -> map observation
  -> preprocess
  -> infer
  -> postprocess
  -> map action
  -> publish command
  -> log iteration
```

Expanded:

```text
InputAdapter.read()
  -> ObservationMapper.map(raw)
  -> preprocess_chain.run(canonical_observation)
  -> ModelRuntime.infer(model_input)
  -> postprocess_chain.run(model_output)
  -> ActionMapper.map(canonical_action)
  -> OutputAdapter.publish(robot_command)
```

## 3. Loop Pseudocode

Conceptual MVP loop:

```python
def run_loop(self) -> None:
    self.input_adapter.start()
    self.output_adapter.start()
    self.transition_to(RUNNING)

    iteration_id = 0

    while self.should_continue():
        if self.state == PAUSED:
            self.handle_paused_iteration(iteration_id)
            iteration_id += 1
            continue

        raw = self.input_adapter.read()
        if raw is None:
            self.logger.log_event("input_timeout", {"iteration_id": iteration_id})
            continue

        canonical_obs = self.observation_mapper.map(raw)
        model_input = self.preprocess_chain.run(canonical_obs)

        started = monotonic()
        model_output = self.model_runtime.infer(model_input)
        latency_ms = (monotonic() - started) * 1000

        canonical_action = self.postprocess_chain.run(model_output)
        robot_command = self.action_mapper.map(canonical_action)

        if self.state == RUNNING:
            self.output_adapter.publish(robot_command)
        else:
            self.logger.log_event("publish_skipped", {"iteration_id": iteration_id})

        self.logger.log_event(
            "iteration_completed",
            {
                "iteration_id": iteration_id,
                "latency_ms": latency_ms,
            },
        )

        iteration_id += 1
        self.sleep_for_loop_rate_if_configured()
```

Implementation can split this into smaller methods, but the component order should remain explicit.

## 4. Startup Sequence

Before entering the loop:

```text
configure
  -> load_model
  -> warmup
  -> run
```

`run` should:

- verify state is `WARMED_UP`
- start input adapter
- start output adapter
- transition to `RUNNING`
- enter loop

Adapter start failures should transition to `ERROR`.

## 5. Iteration Steps

### 5.1 Read Input

Call:

```python
raw = input_adapter.read()
```

Expected result:

- `RawObservation` if data is available
- `None` on timeout or no data
- `AdapterError` on unrecoverable failure

MVP behavior:

- `None` logs `input_timeout`
- timeout does not transition to `ERROR`
- unrecoverable adapter error transitions to `ERROR`

### 5.2 Map Observation

Call:

```python
canonical_obs = observation_mapper.map(raw)
```

Expected result:

- valid `CanonicalObservation`

Failure:

- invalid raw observation
- missing required robot fields
- mapping exception

MVP behavior:

- mapper failure transitions to `ERROR` when `stop_on_error` is true

### 5.3 Run Preprocess Chain

Call:

```python
model_input = preprocess_chain.run(canonical_obs)
```

Expected result:

- valid `ModelInput`

MVP behavior:

- processors run in config order
- disabled processors are not included in resolved chain
- processor failure transitions to `ERROR` when `stop_on_error` is true

### 5.4 Run Model Inference

Call:

```python
model_output = model_runtime.infer(model_input)
```

Expected result:

- valid `ModelOutput`

MVP behavior:

- measure latency around `infer`
- log latency per successful iteration
- model runtime error transitions to `ERROR`

### 5.5 Run Postprocess Chain

Call:

```python
canonical_action = postprocess_chain.run(model_output)
```

Expected result:

- valid `CanonicalAction`

MVP behavior:

- processors run in config order
- output parser should convert model-specific output to canonical action
- validation/clamp processors can run after parsing

### 5.6 Map Action

Call:

```python
robot_command = action_mapper.map(canonical_action)
```

Expected result:

- valid `RobotCommand`

Failure:

- invalid action
- missing joint target
- command conversion error
- joint limit violation, depending on policy

### 5.7 Publish Output

Call:

```python
output_adapter.publish(robot_command)
```

Expected behavior:

- publish or capture command

MVP behavior:

- publish only when state is `RUNNING`
- skip publish when state is `PAUSED`
- output adapter error transitions to `ERROR`

### 5.8 Log Iteration

At minimum, log:

- run id
- iteration id
- timestamp
- lifecycle state
- input availability
- model runtime type
- inference latency
- publish status
- error status

When data summaries are enabled, log:

- observation keys
- model input keys
- model output keys
- action keys
- command type

Do not log full image arrays or large tensors by default.

## 6. Warmup Path

Warmup is not a normal loop iteration.

Warmup flow:

```text
build or load sample ModelInput
  -> ModelRuntime.warmup(sample_input)
  -> discard output
  -> log warmup latency
```

Rules:

- no `OutputAdapter.publish`
- no `ActionMapper.map`
- no command generation
- failure prevents entering `RUNNING`

Warmup sample sources:

- model plugin generated sample
- model profile sample reference
- preprocess fake observation through normal path, future option

MVP can start with model plugin generated sample input.

## 7. Pause Behavior

MVP default pause policy:

```yaml
pause_policy:
  read_input: true
  run_inference: false
  publish_output: false
```

Default paused iteration:

```python
def handle_paused_iteration(iteration_id: int) -> None:
    if pause_policy.read_input:
        input_adapter.read()

    logger.log_event(
        "paused_iteration",
        {
            "iteration_id": iteration_id,
            "run_inference": False,
            "publish_output": False,
        },
    )
```

Future policy may allow inference during pause while still suppressing publish, useful for debugging latency without commanding a robot.

## 8. Stop Behavior

Stop request should cause the loop condition to become false.

Cleanup order:

```text
exit loop
  -> stop input adapter
  -> stop output adapter
  -> unload model runtime
  -> flush logger
  -> transition to STOPPED
```

Cleanup should be best-effort:

- continue cleanup after individual stop failure
- log cleanup errors
- preserve original error if stop followed `ERROR`

## 9. Loop Rate

MVP may support `lifecycle.loop_hz`.

Behavior:

- if `loop_hz` is omitted, run as fast as input and model allow
- if `loop_hz` is set, sleep after iteration to target that rate
- if iteration exceeds budget, log an overrun warning

Loop timing should not be used as a hard real-time guarantee in MVP.

## 10. Max Iterations

`max_iterations` is useful for smoke tests.

Behavior:

- if set, loop stops after that many successful or attempted iterations
- if omitted, loop runs until stop signal or error

For fake smoke tests, set:

```yaml
lifecycle:
  max_iterations: 1
```

## 11. Signal Handling

MVP should handle process termination gracefully where practical.

Expected behavior:

- SIGINT/SIGTERM requests stop
- service exits loop
- adapters stop
- model unloads
- logger flushes

Exact implementation can be handled in CLI/runtime wrapper.

## 12. Recoverable vs Unrecoverable Errors

MVP default is conservative:

- input timeout is recoverable
- invalid config is unrecoverable
- plugin resolution failure is unrecoverable
- model load failure is unrecoverable
- warmup failure is unrecoverable
- mapper failure is unrecoverable by default
- processor failure is unrecoverable by default
- model inference failure is unrecoverable by default
- output publish failure is unrecoverable by default

Future configs may support limited retry policies.

## 13. Fake Loop Requirements

The fake end-to-end loop must:

- run without ROS2
- run without DDS
- run without GPU
- run without model checkpoint
- produce one fake raw observation
- produce one canonical observation
- produce one model input
- produce one model output
- produce one canonical action
- produce one robot command
- capture one published command
- log one completed iteration

This fake path is the baseline smoke test.

## 14. MVP Service Loop Acceptance Criteria

The service loop is acceptable when:

- it calls only interface methods
- fake run executes at least one full iteration
- warmup does not publish output
- inference latency is logged
- input timeout does not crash the service
- unknown plugin/config errors fail before the loop starts
- loop stops after `max_iterations`
- pause suppresses publishing
- stop cleans up adapters, model runtime, and logger
