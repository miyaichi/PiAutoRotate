#!/usr/bin/env python3

"""
Quick diagnostic script to confirm that the MPU6050 is reachable over I2C.
Run this before installing PiAutoRotate to verify wiring and sensor readings.
"""

import argparse
import csv
import os
import sys
import time

import smbus

DEV_ADDR = 0x68
WHO_AM_I = 0x75
ACCEL_XOUT = 0x3b
ACCEL_YOUT = 0x3d
ACCEL_ZOUT = 0x3f
GYRO_XOUT = 0x43
GYRO_YOUT = 0x45
GYRO_ZOUT = 0x47
GYRO_SCALE = 131.0  # LSB/deg/s for default ±250 dps range


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


def sample_gyro(bus):
    gx = read_word(bus, GYRO_XOUT) / GYRO_SCALE
    gy = read_word(bus, GYRO_YOUT) / GYRO_SCALE
    gz = read_word(bus, GYRO_ZOUT) / GYRO_SCALE
    return gx, gy, gz


def main():
    parser = argparse.ArgumentParser(
        description="Check MPU6050 connectivity, accel data, and gyro bias.")
    parser.add_argument(
        "--bus",
        type=int,
        default=int(os.environ.get("AUTOROTATE_BUS_ID", 1)),
        help="I2C bus number (default: %(default)s or AUTOROTATE_BUS_ID)",
    )
    parser.add_argument(
        "--gyro-samples",
        type=int,
        default=200,
        help="Number of samples for gyro bias estimation (default: %(default)s)",
    )
    parser.add_argument(
        "--gyro-delay",
        type=float,
        default=0.01,
        help="Delay in seconds between gyro samples (default: %(default)s)",
    )
    parser.add_argument(
        "--gyro-log",
        type=str,
        default=None,
        help="Optional CSV path to store raw gyro samples for offline calibration.",
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

    log_file = None
    csv_writer = None
    if args.gyro_log:
        try:
            log_file = open(args.gyro_log, "w", newline="")
            csv_writer = csv.writer(log_file)
            csv_writer.writerow(["index", "gx_dps", "gy_dps", "gz_dps"])
            print(f"Logging gyro samples to {args.gyro_log}")
        except OSError as exc:
            print(f"Failed to open gyro log file: {exc}")
            if log_file:
                log_file.close()
            log_file = None
            csv_writer = None

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

        print("\nGyro bias capture:")
        print(
            "Place the device on a stable surface and keep it still. "
            "Sampling will begin in 2 seconds..."
        )
        time.sleep(2.0)

        sums = [0.0, 0.0, 0.0]
        valid = 0
        for i in range(1, args.gyro_samples + 1):
            try:
                gx, gy, gz = sample_gyro(bus)
                sums[0] += gx
                sums[1] += gy
                sums[2] += gz
                valid += 1
                if csv_writer:
                    csv_writer.writerow([i, f"{gx:.6f}", f"{gy:.6f}", f"{gz:.6f}"])
            except OSError as exc:
                print(f"  Gyro sample {i}: read failed ({exc})")
            time.sleep(args.gyro_delay)

        if valid:
            avg = [s / valid for s in sums]
            print(
                f"Computed gyro bias from {valid} samples "
                f"(deg/s): X={avg[0]:.4f}, Y={avg[1]:.4f}, Z={avg[2]:.4f}"
            )
            print("Save these values for future bias compensation.")
        else:
            print("Unable to compute gyro bias (no valid samples).")
    finally:
        bus.close()
        print("Closed I2C bus.")
        if log_file:
            log_file.close()


if __name__ == "__main__":
    main()
