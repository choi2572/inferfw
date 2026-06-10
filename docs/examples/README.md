# Example Configurations

The canonical pipeline example is `config/pipeline_example.yaml`.

The files in this directory are older target examples used while exploring profile-based MVP shapes. They are useful design references, but they are not the current canonical config schema.

Current canonical shape:

- `request_server`
- `robot`
- `pipeline`

Legacy examples kept here:

1. `mvp_fake_run.yaml`
   - dependency-free fake smoke run
   - fake robot profile
   - dummy model runtime/profile

2. `sim_replay_onnx_run.yaml`
   - simulator/replay-oriented run
   - tabletop arm profile
   - ONNX policy profile

3. `unitree_g1_openpi_run.yaml`
   - real-oriented robot run shape
   - Unitree G1 profile
   - OpenPI-style VLA profile
   - ROS2 input and DDS output target

These files are documentation examples, not guaranteed executable configs until the corresponding plugins and loaders are implemented. New docs should prefer `config/pipeline_example.yaml`.
