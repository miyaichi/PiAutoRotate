# PiAutoRotate
PiAutoRotate is a tiny service that watches an MPU6050 accelerometer over I2C and rotates a Wayland display automatically (via `wlr-randr`) on a Raspberry Pi. It was written for Labwc/Sway-like compositors, but any compositor that ships `wlr-randr` should work.
