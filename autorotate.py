# -*- coding: utf-8 -*-

import os
import subprocess
import time

import smbus

# --- MPU6050 constants ---
DEV_ADDR = 0x68
ACCEL_XOUT = 0x3b
ACCEL_YOUT = 0x3d
ACCEL_ZOUT = 0x3f


# --- configuration ---
def _float_from_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        print(f"Invalid float for {name}: {value}. Using default {default}.")
        return default


def _int_from_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"Invalid integer for {name}: {value}. Using default {default}.")
        return default


OUTPUT_NAME = os.environ.get('AUTOROTATE_OUTPUT', 'HDMI-A-1')
CHECK_INTERVAL = _float_from_env('AUTOROTATE_INTERVAL', 0.5)
ROTATION_THRESHOLD = _float_from_env('AUTOROTATE_THRESHOLD', 0.5)
DEFAULT_ROTATION = os.environ.get('AUTOROTATE_DEFAULT_ROTATION', 'normal')
BUS_ID = _int_from_env('AUTOROTATE_BUS_ID', 1)


class SensorReadError(Exception):
    """Raised when the sensor cannot provide data"""


class MPU6050:

    def __init__(self, bus_id=BUS_ID, address=DEV_ADDR):
        self.address = address
        self.bus_id = bus_id
        self.bus = None
        self._connect_bus()

    def _connect_bus(self):
        self.bus = smbus.SMBus(self.bus_id)
        self._initialize()

    def _initialize(self):
        time.sleep(0.2)
        sequence = [
            (0x6B, 0x80, 0.25),
            (0x6B, 0x00, 0.25),
            (0x6A, 0x07, 0.25),
            (0x6A, 0x00, 0.25),
            (0x1A, 0x00, 0.0),
            (0x1B, 0x18, 0.0),
            (0x1C, 0x08, 0.1),
        ]
        for register, value, delay in sequence:
            self.bus.write_byte_data(self.address, register, value)
            if delay:
                time.sleep(delay)

    def read_word(self, register, retries=3, retry_delay=0.01):
        if self.bus is None:
            raise SensorReadError("I2C bus has not been initialized")
        for attempt in range(retries):
            try:
                high = self.bus.read_byte_data(self.address, register)
                low = self.bus.read_byte_data(self.address, register + 1)
                return (high << 8) + low
            except OSError:
                if attempt == retries - 1:
                    raise
                time.sleep(retry_delay)

    def read_word_sensor(self, register):
        value = self.read_word(register)
        return value - 65536 if value >= 0x8000 else value

    def get_accel(self):
        try:
            x = self.read_word_sensor(ACCEL_XOUT) / 8192
            y = self.read_word_sensor(ACCEL_YOUT) / 8192
            z = self.read_word_sensor(ACCEL_ZOUT) / 8192
            return x, y, z
        except OSError as exc:
            raise SensorReadError(f"read failed: {exc}") from exc

    def close(self):
        try:
            self.bus.close()
        except Exception:
            pass
        finally:
            self.bus = None

    def reset(self):
        self.close()
        self._connect_bus()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class RotationController:

    def __init__(self, output_name, threshold=ROTATION_THRESHOLD):
        self.output_name = output_name
        self.threshold = threshold
        self.current_rotation = DEFAULT_ROTATION

    def determine_rotation(self, accel_x, accel_y):
        if abs(accel_x) > abs(accel_y) and abs(accel_x) > self.threshold:
            return '270' if accel_x > 0 else '90'
        if abs(accel_y) > self.threshold:
            return '180' if accel_y > 0 else DEFAULT_ROTATION
        return self.current_rotation

    def apply(self, direction):
        if direction == self.current_rotation:
            return

        command = [
            'wlr-randr', '--output', self.output_name, '--transform', direction
        ]

        try:
            subprocess.run(command, check=True, capture_output=True)
            self.current_rotation = direction
            print(f"Display rotated to {direction} degrees.")
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.decode().strip()
            print(f"Command error ({direction}): {message}")
        except FileNotFoundError:
            print("Error: wlr-randr not found.")


class AutoRotateService:

    def __init__(self, sensor, controller, interval=CHECK_INTERVAL):
        self.sensor = sensor
        self.controller = controller
        self.interval = interval

    def run(self):
        print("Starting MPU6050 auto rotation service.")
        while True:
            try:
                accel_x, accel_y, _ = self.sensor.get_accel()
                direction = self.controller.determine_rotation(
                    accel_x, accel_y)
                self.controller.apply(direction)
                time.sleep(self.interval)
            except SensorReadError as exc:
                self._recover_from_sensor_error(exc)
            except OSError as exc:
                print(f"I2C read error: {exc}")
                time.sleep(1.0)
            except KeyboardInterrupt:
                print("\nAuto rotation service interrupted.")
                raise
            except Exception as exc:
                print(f"Unexpected error: {exc}")
                time.sleep(1.0)

    def _recover_from_sensor_error(self, error):
        print(f"Sensor read error: {error}")
        try:
            self.sensor.reset()
            print("Sensor reinitialized.")
        except Exception as exc:
            print(f"Sensor reinitialization failed: {exc}")
            time.sleep(2.0)


def main():
    sensor = None
    try:
        sensor = MPU6050()
    except Exception as exc:
        print(f"Initialization error: {exc}")
        return

    controller = RotationController(OUTPUT_NAME)
    service = AutoRotateService(sensor, controller, CHECK_INTERVAL)

    try:
        service.run()
    except KeyboardInterrupt:
        pass
    finally:
        if sensor:
            sensor.close()
            print("Closed I2C bus.")


if __name__ == "__main__":
    main()
