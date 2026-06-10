# Inference Service Framework Specification

## 1. Purpose

이 프로젝트의 목적은 embodied AI 모델 평가 MLOps를 위한 inference service framework를 개발하는 것이다.

프레임워크는 다양한 모델 런타임, 로봇, 시뮬레이터, 통신 방식을 하나의 실행 구조 위에서 조합할 수 있게 하며, 모델을 일관되게 실행, 기록, 비교, 재현할 수 있는 기반을 제공한다.

MVP의 초점은 완전한 MLOps 플랫폼이 아니라, 실제 모델을 로봇 또는 시뮬레이터 실행 흐름에 연결해 돌릴 수 있는 실행 중심 inference service이다.

## 2. Primary Goals

MVP의 주요 목표는 다음과 같다.

- 모델 런타임을 쉽게 교체할 수 있어야 한다.
- 로봇별 observation/action 차이를 plugin과 mapper로 격리해야 한다.
- config만 바꿔 실행 조합을 바꿀 수 있어야 한다.
- preprocess, inference, postprocess, output publish 흐름을 공통 runtime으로 실행해야 한다.
- lifecycle, logging, validation 같은 공통 기능은 framework core가 관리해야 한다.
- 향후 replay, metrics, experiment tracking으로 확장할 수 있는 실행 기록을 남겨야 한다.

## 3. Non-Goals for MVP

아래 항목은 중요한 확장 방향이지만 MVP 구현 범위에서는 제외한다.

- full MLOps dashboard
- distributed runtime
- cloud model registry
- advanced model artifact management
- multi-stage graph pipeline
- scheduler/orchestrator
- full replay evaluation system
- experiment tracking backend
- safety policy engine
- hardware-in-the-loop automation

MVP에서는 이 기능들을 바로 구현하지 않는다. 다만 config, logging, interface 설계가 추후 확장을 막지 않도록 한다.

## 4. Design Principles

### 4.1 Evaluation First

프레임워크의 중심 목적은 모델 평가이다. 단순히 모델 output을 로봇에 publish하는 것이 아니라, 어떤 모델, 어떤 robot profile, 어떤 processor chain, 어떤 runtime config로 실행했는지 추적할 수 있어야 한다.

MVP logging은 최소한 다음 정보를 남긴다.

- run id
- config path and resolved config
- model profile
- robot profile
- processor chain
- lifecycle events
- inference latency
- runtime errors

### 4.2 Model Runtime Swappability

모델 평가는 여러 모델과 checkpoint를 반복적으로 갈아끼우는 workflow를 전제로 한다.

따라서 `ModelRuntime`은 핵심 교체 지점이다. 모델 개발자는 framework core나 robot integration을 수정하지 않고 모델 runtime과 model-specific processor만 제공할 수 있어야 한다.

### 4.3 Robot Integration Swappability

로봇별 sensor layout, joint layout, command protocol은 서로 다르다. 프레임워크는 모든 로봇을 같은 tensor shape로 강제하지 않는다.

대신 robot-specific logic은 `ObservationMapper`, `ActionMapper`, robot profile, robot-specific processor에 둔다. Framework core는 robot semantics를 직접 소유하지 않는다.

### 4.4 Common Runtime Skeleton

Framework core는 아래의 실행 구조를 공통으로 제공한다.

```text
RawInput
  -> InputAdapter
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
```

Core는 흐름, 계약, lifecycle, logging, validation을 관리한다. Plugin은 robot/model-specific semantics를 처리한다.

## 5. MVP Scope

MVP는 single service, single stage inference loop로 제한한다.

포함 범위:

- one runtime process
- one input stream
- one model runtime
- one output stream
- one robot profile
- one model profile
- input adapter
- observation mapper
- preprocess chain
- model runtime
- postprocess chain
- action mapper
- output adapter
- basic lifecycle
- basic config validation
- basic structured logging
- fake adapter/model 기반 end-to-end smoke test

MVP reference flow:

```text
ROS2 observation
  -> ObservationMapper
  -> preprocess chain
  -> VLA ModelRuntime
  -> postprocess chain
  -> ActionMapper
  -> DDS publish
```

초기 구현에서는 ROS2/DDS가 준비되지 않은 환경에서도 개발과 테스트가 가능해야 한다. 이를 위해 fake input adapter, fake output adapter, dummy model runtime을 먼저 제공한다.

## 6. Core Components

### 6.1 InputAdapter

`InputAdapter`는 외부 시스템에서 raw input을 읽는다.

예상 구현:

- ROS2 input
- replay file input
- fake input
- shared memory input, future
- HTTP/gRPC input, future

책임:

- external source 연결
- input read
- start/stop lifecycle

금지:

- robot semantic mapping
- model-specific preprocessing

### 6.2 ObservationMapper

`ObservationMapper`는 robot-specific raw observation을 `CanonicalObservation`으로 변환한다.

예:

```text
29DOF joint array
  -> left_arm / right_arm / waist semantic joint groups
```

책임:

- robot profile 기반 semantic normalization
- sensor name mapping
- joint group mapping
- frame metadata mapping

금지:

- model input tensor 생성
- model-specific image normalization

### 6.3 CanonicalObservation

`CanonicalObservation`은 프레임워크 내부에서 observation을 의미 단위로 담는 container이다.

목표는 모든 로봇을 동일 shape로 맞추는 것이 아니다. 자주 쓰이는 semantic field를 공통화하고, 특수 값은 `extras`에 둔다.

예상 필드:

```python
CanonicalObservation(
    timestamp=...,
    images={},
    joints={},
    end_effectors={},
    grippers={},
    hands={},
    frames={},
    extras={},
)
```

`extras`에서 여러 robot/model plugin이 반복적으로 사용하는 값은 추후 canonical field로 승격할 수 있다.

### 6.4 Processor Chain

Processor chain은 preprocess/postprocess 실행 구조를 공통화한다.

프레임워크는 processor를 순서대로 실행하고, 각 processor의 config와 runtime context를 전달한다. Processor 자체의 semantic logic은 plugin이 소유한다.

Generic processor 예:

- resize image
- normalize image
- stack history
- concatenate arrays
- clamp values
- validate schema

Model/robot-specific processor 예:

- OpenPI input builder
- VLA output parser
- Unitree joint remapper
- G1 IK solver

### 6.5 ModelRuntime

`ModelRuntime`은 모델 lifecycle과 inference를 담당한다.

기본 interface:

```python
class ModelRuntime:
    def configure(self, config, context): ...
    def load(self): ...
    def warmup(self, sample_input): ...
    def infer(self, model_input): ...
    def unload(self): ...
```

모델 개발자의 핵심 책임은 `infer(model_input) -> model_output`을 안정적으로 제공하는 것이다.

Framework core의 책임:

- config loading
- lifecycle call order
- preprocess/postprocess execution
- logging
- latency measurement
- output mapping
- adapter orchestration

### 6.6 CanonicalAction

`CanonicalAction`은 모델 output을 로봇 command로 보내기 전의 semantic action 표현이다.

예상 필드:

```python
CanonicalAction(
    timestamp=...,
    joint_targets={},
    end_effector_targets={},
    grippers={},
    hands={},
    extras={},
)
```

`CanonicalAction`은 `RobotCommand`가 아니다. Robot-specific command packet 생성은 `ActionMapper`가 담당한다.

### 6.7 ActionMapper

`ActionMapper`는 `CanonicalAction`을 robot-specific command로 변환한다.

예:

```text
CanonicalAction.joint_targets
  -> Unitree DDS LowCmd
```

책임:

- robot profile 기반 command mapping
- joint limit 적용 또는 검증
- frame convention 변환
- command metadata 생성

금지:

- model inference
- model-specific output parsing

### 6.8 OutputAdapter

`OutputAdapter`는 robot command를 외부 시스템에 publish한다.

예상 구현:

- DDS output
- fake output
- ROS2 output
- shared memory output, future

책임:

- external sink 연결
- command publish
- start/stop lifecycle

금지:

- semantic action mapping
- model-specific postprocessing

## 7. Lifecycle

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

Lifecycle phase:

- `configure`: config validation, plugin resolve, profile load, processor chain build
- `load_model`: model artifact and runtime resource load
- `warmup`: sample input inference, output discarded
- `run`: input read, inference loop, output publish
- `pause`: runtime remains loaded, output publish is suspended
- `stop`: adapters stop, model unload, logs flush
- `error`: unrecoverable runtime failure or invalid transition

MVP에서는 lifecycle transition을 명시적으로 검증한다. 예를 들어 `CREATED` 상태에서 바로 `run`을 호출할 수 없어야 한다.

## 8. Configuration

MVP는 YAML config 기반 실행을 기본으로 한다.

Pipeline config 예:

```yaml
request_server:
  type: ros2
  node_name: inferfw
  services:
    load_model: /inferfw/load_model
    unload_model: /inferfw/unload_model
    infer: /inferfw/infer
    set_task: /inferfw/set_task
    set_operation_mode: /inferfw/set_operation_mode

robot:
  name: g129dof
  action_class: G1Action
  loop_hz: 30.0
  joint_config:
    torso: 6
    right_arm: 7
    left_arm: 7
    right_hand: 12
    left_hand: 12

pipeline:
  name: g129dof_vla_test1
  preprocess:
    groups:
      - keys: [left_img, left_wrist_img, right_img, right_wrist_img]
        steps:
          - name: resize
            params:
              width: 224
              height: 224
              mode: bilinear
  models:
    g1_vla:
      runtime: openpi
      config_name: act_g1
      model_path: /workspace/sim_models/act_sim_model/
      input_interface:
        bindings:
          left_img:
            topic: /cam/left/image_raw_color/compressed
            message_type: sensor_msgs/CompressedImage
      output_interface:
        bindings:
          actions:
            type: joint_trajectory
            groups: [torso, right_arm, left_arm, right_hand, left_hand]
  postprocess:
    groups:
      - keys: [actions]
        steps:
          - name: resample_action
            params:
              target_hz: 30
```

Config validation은 MVP에서 필수이다. 실행 중 필요한 plugin, profile, processor가 resolve되지 않으면 `configure` 단계에서 실패해야 한다.

## 9. Plugin Architecture

Framework core가 소유하는 것:

- lifecycle management
- service loop
- processor chain runner
- adapter interfaces
- model runtime interface
- canonical data structures
- config loader
- validation framework
- logging and metrics hooks

Plugin이 소유하는 것:

- model runtime implementation
- model-specific preprocess/postprocess
- robot observation mapper
- robot action mapper
- robot profile
- model profile
- robot-specific processors
- IK/FK logic
- concrete ROS2/DDS/Zenoh adapters

MVP에서는 local plugin registry를 우선한다. Python package dynamic discovery는 추후 확장으로 둔다.

## 10. Code Quality Expectations

MVP라도 core와 plugin boundary는 엄격하게 유지한다.

기본 원칙:

- core package는 robot/model-specific package를 import하지 않는다.
- plugin은 core interface에만 의존한다.
- public interface에는 type hint를 작성한다.
- config는 실행 전에 validation한다.
- runtime error는 structured log로 남긴다.
- processor는 가능한 한 deterministic하게 작성한다.
- side effect는 adapter, model runtime, logger에 집중시킨다.

초기 toolchain 후보:

- formatter/linter: `ruff`
- type checking: `mypy` 또는 `pyright`
- test runner: `pytest`
- config validation: `pydantic` 또는 dataclass 기반 validator

구체적인 rule은 별도 `docs/code_quality.md`에서 확정한다.

## 11. Testing Strategy

MVP 개발은 실제 로봇 없이도 검증 가능해야 한다.

우선 테스트할 항목:

- canonical data model 생성과 validation
- config load and validation
- plugin registry resolve
- processor chain execution order
- lifecycle valid/invalid transition
- dummy model runtime load/warmup/infer/unload
- fake input -> mapper -> preprocess -> model -> postprocess -> mapper -> fake output end-to-end
- logging output 생성

추후 확장 테스트:

- ROS2 input integration test
- DDS output integration test
- replay-based regression test
- latency benchmark
- hardware-in-the-loop test

구체적인 테스트 레벨과 fixture 전략은 별도 `docs/testing_strategy.md`에서 확정한다.

## 12. Deployment Direction

MVP 배포는 local process 실행을 기본으로 한다.

초기 실행 방식:

```bash
inferfw validate --config config/pipeline_example.yaml
inferfw run --config config/pipeline_example.yaml
inferfw list-plugins
```

MVP에서 정리할 운영 항목:

- Python package layout
- CLI entrypoint
- config path convention
- plugin path convention
- run output directory
- log format
- graceful shutdown
- Docker optional
- ROS2/DDS dependency handling
- GPU runtime handling

구체적인 배포 방식은 별도 `docs/deployment.md`에서 확정한다.

## 13. Implementation Roadmap

MVP 구현 순서:

1. package skeleton
2. canonical data classes
3. core interfaces
4. config schema and loader
5. plugin registry
6. processor chain runner
7. lifecycle state machine
8. fake input adapter
9. dummy model runtime
10. fake output adapter
11. end-to-end service loop
12. structured logging
13. example config and profiles
14. smoke tests
15. ROS2 input adapter stub
16. DDS output adapter stub
17. CLI entrypoint

이 순서는 fake components로 전체 실행 경로를 먼저 닫고, 이후 실제 ROS2/DDS/model runtime을 붙이는 방향을 따른다.

## 14. Future Extensions

MVP 이후 확장 후보:

- multi-stage graph pipeline
- stage edge contract and validators
- replay evaluation
- metrics aggregation
- experiment tracking integration
- model artifact management
- model registry
- distributed runtime
- dashboard
- scheduler/orchestrator
- safety policy engine

이 확장들은 MVP core interface를 깨지 않는 방향으로 추가되어야 한다.
