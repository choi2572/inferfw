# Canonical Data Model

This document defines the MVP data model used inside the inference service framework.

The framework does not try to force every robot, simulator, and model into one identical tensor shape. Instead, it uses semantic containers at the runtime boundaries and allows robot/model-specific data to live in explicit extension fields.

## 1. Data Model Goals

The canonical data model should:

- keep the service loop independent from robot-specific message formats
- keep model runtime independent from robot transport protocols
- preserve enough metadata for model evaluation and debugging
- support fake components, simulators, and real robots
- allow gradual promotion of common fields from `extras` into canonical fields

The canonical data model should not:

- hide all robot differences
- force all robots into the same action dimension
- force all models into the same input tensor format
- replace model-specific preprocessors
- replace robot-specific mappers

## 2. Data Flow Types

MVP data flow:

```text
RawObservation
  -> CanonicalObservation
  -> ModelInput
  -> ModelOutput
  -> CanonicalAction
  -> RobotCommand
```

Ownership:

| Type | Produced By | Consumed By | Owned By |
| --- | --- | --- | --- |
| `RawObservation` | `InputAdapter` | `ObservationMapper` | adapter/plugin |
| `CanonicalObservation` | `ObservationMapper` | preprocess chain | framework data model |
| `ModelInput` | preprocess chain | `ModelRuntime` | model plugin contract |
| `ModelOutput` | `ModelRuntime` | postprocess chain | model plugin contract |
| `CanonicalAction` | postprocess chain | `ActionMapper` | framework data model |
| `RobotCommand` | `ActionMapper` | `OutputAdapter` | robot plugin/adapter contract |

## 3. Common Metadata

Most data containers should carry metadata when available.

Recommended metadata fields:

```python
@dataclass
class DataMetadata:
    timestamp: float | None = None
    source: str | None = None
    frame_id: str | None = None
    sequence_id: int | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

Field meaning:

- `timestamp`: observation, action, or command timestamp in seconds
- `source`: source name such as topic, adapter, simulator, or replay file
- `frame_id`: primary coordinate frame when applicable
- `sequence_id`: monotonic source sequence if available
- `extras`: metadata not yet standardized

MVP can keep metadata inline on each container instead of introducing a separate base class if that is simpler.

## 4. RawObservation

`RawObservation` is the output of `InputAdapter`.

It represents source-specific data before semantic mapping.

Example conceptual shape:

```python
@dataclass
class RawObservation:
    payload: object
    timestamp: float | None = None
    source: str | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

Examples:

- ROS2 message object
- decoded ROS2 message dictionary
- simulator observation dictionary
- replay frame dictionary
- fake observation dictionary

Rules:

- `RawObservation` may contain transport-specific or robot-specific structure.
- Framework core should not inspect source-specific payload fields.
- Only `InputAdapter` and `ObservationMapper` should need to understand the payload.

## 5. CanonicalObservation

`CanonicalObservation` is the semantic observation container used after robot mapping.

Conceptual shape:

```python
@dataclass
class CanonicalObservation:
    timestamp: float | None = None
    images: dict[str, ImageData] = field(default_factory=dict)
    joints: dict[str, JointGroup] = field(default_factory=dict)
    end_effectors: dict[str, PoseData] = field(default_factory=dict)
    grippers: dict[str, GripperData] = field(default_factory=dict)
    hands: dict[str, HandData] = field(default_factory=dict)
    frames: dict[str, FrameData] = field(default_factory=dict)
    extras: dict[str, object] = field(default_factory=dict)
```

The field names are semantic groups, not fixed tensor shapes.

### 5.1 Images

Images are keyed by semantic camera name.

Example:

```python
obs.images["front"]
obs.images["left_wrist"]
obs.images["right_wrist"]
```

Conceptual shape:

```python
@dataclass
class ImageData:
    data: object
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    encoding: str | None = None
    frame_id: str | None = None
    timestamp: float | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

`data` may initially be numpy arrays, bytes, or framework-neutral objects. Model-specific conversion to tensors belongs in processors.

### 5.2 Joints

Joints are keyed by semantic group name.

Example:

```python
obs.joints["left_arm"]
obs.joints["right_arm"]
obs.joints["waist"]
```

Conceptual shape:

```python
@dataclass
class JointGroup:
    names: list[str]
    positions: list[float] | None = None
    velocities: list[float] | None = None
    efforts: list[float] | None = None
    units: str = "rad"
    extras: dict[str, object] = field(default_factory=dict)
```

Rules:

- group names come from robot profile
- joint order must match `names`
- units must be explicit when not radians
- model-specific concatenation belongs in preprocessors

### 5.3 End Effectors

End effectors are keyed by semantic name.

Example:

```python
obs.end_effectors["left_ee"]
obs.end_effectors["right_ee"]
```

Conceptual shape:

```python
@dataclass
class PoseData:
    position: list[float] | None = None
    orientation: list[float] | None = None
    orientation_type: str = "quat_xyzw"
    frame_id: str | None = None
    units: str = "m"
    extras: dict[str, object] = field(default_factory=dict)
```

Coordinate frame and orientation convention must be explicit.

### 5.4 Grippers and Hands

Simple grippers:

```python
@dataclass
class GripperData:
    position: float | None = None
    velocity: float | None = None
    effort: float | None = None
    normalized: bool = False
    extras: dict[str, object] = field(default_factory=dict)
```

Dexterous hands:

```python
@dataclass
class HandData:
    joints: JointGroup | None = None
    tactile: object | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

### 5.5 Frames

Frames describe coordinate transforms or named frame metadata.

Conceptual shape:

```python
@dataclass
class FrameData:
    parent: str | None = None
    child: str | None = None
    pose: PoseData | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

MVP can keep frame support minimal, but frame names and conventions should not be implicit when pose data is used.

## 6. ModelInput

`ModelInput` is the input contract for a specific model runtime.

The framework does not define one universal `ModelInput` shape.

MVP conceptual shape:

```python
@dataclass
class ModelInput:
    data: dict[str, object]
    metadata: dict[str, object] = field(default_factory=dict)
```

Examples:

```python
ModelInput(
    data={
        "image": image_tensor,
        "proprio": proprio_tensor,
        "instruction": "pick up the block",
    }
)
```

Rules:

- preprocess chain produces `ModelInput`
- model profile defines expected keys, shapes, dtypes, and conventions
- `ModelRuntime` validates or assumes the contract declared by the model profile
- robot-specific raw fields should not leak into `ModelInput` unless intentionally passed through

## 7. ModelOutput

`ModelOutput` is the output contract of a specific model runtime.

MVP conceptual shape:

```python
@dataclass
class ModelOutput:
    data: dict[str, object]
    metadata: dict[str, object] = field(default_factory=dict)
```

Examples:

```python
ModelOutput(
    data={
        "action": action_tensor,
        "confidence": 0.82,
    }
)
```

Rules:

- `ModelRuntime` produces `ModelOutput`
- model profile defines output keys, shapes, dtypes, and conventions
- postprocess chain converts `ModelOutput` into `CanonicalAction`

## 8. CanonicalAction

`CanonicalAction` is the semantic action container before robot command mapping.

Conceptual shape:

```python
@dataclass
class CanonicalAction:
    timestamp: float | None = None
    joint_targets: dict[str, JointTarget] = field(default_factory=dict)
    end_effector_targets: dict[str, PoseTarget] = field(default_factory=dict)
    grippers: dict[str, GripperTarget] = field(default_factory=dict)
    hands: dict[str, HandTarget] = field(default_factory=dict)
    extras: dict[str, object] = field(default_factory=dict)
```

`CanonicalAction` is not a robot command. It does not include transport-specific packet structure.

### 8.1 JointTarget

```python
@dataclass
class JointTarget:
    names: list[str]
    positions: list[float] | None = None
    velocities: list[float] | None = None
    efforts: list[float] | None = None
    gains: dict[str, object] = field(default_factory=dict)
    units: str = "rad"
    extras: dict[str, object] = field(default_factory=dict)
```

Rules:

- `names` order must match target arrays
- units must be explicit when not radians
- robot-specific packet fields belong in `RobotCommand`

### 8.2 PoseTarget

```python
@dataclass
class PoseTarget:
    position: list[float] | None = None
    orientation: list[float] | None = None
    orientation_type: str = "quat_xyzw"
    frame_id: str | None = None
    units: str = "m"
    extras: dict[str, object] = field(default_factory=dict)
```

### 8.3 GripperTarget and HandTarget

```python
@dataclass
class GripperTarget:
    position: float | None = None
    effort: float | None = None
    normalized: bool = False
    extras: dict[str, object] = field(default_factory=dict)

@dataclass
class HandTarget:
    joints: JointTarget | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

## 9. RobotCommand

`RobotCommand` is robot-specific output generated by `ActionMapper`.

Conceptual shape:

```python
@dataclass
class RobotCommand:
    payload: object
    command_type: str
    timestamp: float | None = None
    target: str | None = None
    extras: dict[str, object] = field(default_factory=dict)
```

Examples:

- Unitree DDS `LowCmd`
- ROS2 command message
- simulator command dictionary
- fake command dictionary

Rules:

- output adapter understands `RobotCommand.payload`
- framework core should not inspect robot-specific payload fields
- command metadata should be sufficient for logging and debugging

## 10. Extras Policy

`extras` is an explicit extension mechanism, not a dumping ground.

Allowed uses:

- robot-specific values that are not common enough to standardize
- model-specific auxiliary values
- debug metadata
- source-specific message metadata
- temporary fields during early integration

Rules:

- keys should be stable and documented by the owning plugin
- values should be serializable when possible
- avoid storing large binary blobs in `extras` unless necessary
- do not use `extras` to bypass canonical fields that already exist
- repeated cross-plugin usage should trigger promotion discussion

Promotion criteria:

- used by more than one robot or model plugin
- needed by framework-level validation or logging
- required for common evaluation workflows
- can be given a clear semantic name and convention

## 11. Units and Frames

Units and frames must be explicit where ambiguity would affect behavior.

Default assumptions:

- joint angles: radians
- linear position: meters
- orientation: quaternion `xyzw`
- timestamp: seconds

If a plugin uses different conventions, it must either convert to the default convention or mark the convention explicitly in the data object.

Frame-related data should include `frame_id` where possible.

## 12. Mutability and Copying

MVP can use mutable dataclasses for practical implementation speed.

Guidelines:

- processors may return new objects or mutate in place if documented
- hidden mutation across components should be avoided
- tests should catch processor order and output changes
- logging should avoid retaining references that later mutate

If mutation causes debugging issues, the framework can move toward frozen dataclasses or copy-on-write patterns later.

## 13. Serialization

MVP should support serializing metadata and small structured fields for logging.

Serialization requirements:

- run metadata must be serializable
- config snapshot must be serializable
- lifecycle events must be serializable
- latency metrics must be serializable
- error payloads must be serializable

Large arrays and images do not need to be fully serialized in MVP logs. Logs may record shape, dtype, encoding, keys, or summaries instead.

## 14. Validation

Validation happens at multiple levels.

Config validation:

- verifies profile references
- verifies plugin types
- verifies processor config shape

Data validation:

- verifies required fields exist
- verifies known units and frame conventions
- verifies array lengths match names
- verifies model profile input/output schema when feasible

MVP should prioritize validation at component boundaries:

- after `ObservationMapper`
- after preprocess chain
- after `ModelRuntime`
- after postprocess chain
- after `ActionMapper`

## 15. Fake Data Requirements

Fake components must produce valid framework data.

Fake observation should include:

- timestamp
- one image or image-like placeholder
- one joint group
- optional instruction or task metadata in `extras`

Dummy model input should include:

- deterministic data keys
- model metadata

Dummy model output should include:

- deterministic action-like data

Fake action/command should include:

- one joint target or simple command payload
- enough metadata to verify end-to-end execution

The fake path is the baseline smoke test and should remain stable.

## 16. MVP Data Model Acceptance Criteria

The data model is acceptable when:

- fake end-to-end loop can pass data through all stages
- model runtime can consume `ModelInput` without robot-specific imports
- output adapter can publish `RobotCommand` without model-specific imports
- robot-specific source payload remains isolated to adapter/mapper
- robot-specific command payload remains isolated to mapper/adapter
- logs can summarize each iteration without serializing large tensors or images
- tests can validate joint name/value length consistency
