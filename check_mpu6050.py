#!/usr/bin/env python3

"""
Quick diagnostic script to confirm that the MPU6050 is reachable over I2C.
Run this before installing PiAutoRotate to verify wiring and sensor readings.
"""

import argparse
import os
import sys
import time

import smbus

DEV_ADDR = 0x68
WHO_AM_I = 0x75
ACCEL_XOUT = 0x3b
ACCEL_YOUT = 0x3d
ACCEL_ZOUT = 0x3f


def read_word(bus, register):
    high = bus.read_byte_data(DEV_ADDR, register)
    low = bus.read_byte_data(DEV_ADDR, register + 1)
    value = (high << 8) + low
    return value - 65536 if value >= 0x8000 else value


def sample_accel(bus):
    x = read_word(bus, ACCEL_XOUT) / 8192
    y = read_word(bus, ACCEL_YOUT) / 8192
    z = read_word(bus, ACCEL_ZOUT) / 8192
    return x, y, z


def main():
    parser = argparse.ArgumentParser(
        description="Check MPU6050 connectivity and read a few accel samples.")
    parser.add_argument(
        "--bus",
        type=int,
        default=int(os.environ.get("AUTOROTATE_BUS_ID", 1)),
        help="I2C bus number (default: %(default)s or AUTOROTATE_BUS_ID)",
    )
    args = parser.parse_args()

    print(f"Opening I2C bus {args.bus} ...")
    try:
        bus = smbus.SMBus(args.bus)
    except FileNotFoundError as exc:
        print(f"Failed to open /dev/i2c-{args.bus}: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error opening bus: {exc}")
        sys.exit(1)

    try:
        whoami = bus.read_byte_data(DEV_ADDR, WHO_AM_I)
        print(f"WHO_AM_I register: 0x{whoami:02X}")
        if whoami != DEV_ADDR:
            print(
                "Warning: expected WHO_AM_I == 0x68. "
                "Check wiring or the sensor address."
            )

        print("Reading acceleration values (g units):")
        for i in range(5):
            try:
                ax, ay, az = sample_accel(bus)
                print(f"  Sample {i + 1}: X={ax:.3f}, Y={ay:.3f}, Z={az:.3f}")
            except OSError as exc:
                print(f"  Sample {i + 1}: read failed ({exc})")
            time.sleep(0.3)
    finally:
        bus.close()
        print("Closed I2C bus.")


if __name__ == "__main__":
    main()
