# Example Configurations

This directory contains example MVP configurations.

The examples are intentionally varied to show that the framework is config-driven:

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

These files are documentation examples, not guaranteed executable configs until the corresponding plugins and loaders are implemented.
