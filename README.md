# PiAutoRotate

PiAutoRotate is a tiny service that watches an MPU6050 accelerometer over I2C
and rotates a Wayland display automatically (via `wlr-randr`) on a Raspberry Pi.
It was written for Labwc/Sway-like compositors, but any compositor that ships
`wlr-randr` should work.

## Features

- Resilient I2C reader with automatic re-initialisation on transient failures.
- Simple rotation heuristic based on the dominant axis of gravity.
- Environment-variable driven configuration for output name, polling interval,
  threshold, default rotation, and I2C bus ID.
- Ready-to-use `systemd` unit files for unattended startup.

## Requirements

- Raspberry Pi running Raspberry Pi OS (Bookworm/Bullseye) or another system
  that provides Python 3.9+ with `smbus` support.
- Enabled I2C interface (`sudo raspi-config` → Interface Options → I2C → Enable).
- MPU6050 connected to the Pi’s I2C pins (3.3 V logic).
- A Wayland compositor that provides `wlr-randr` (Labwc, Sway, Wayfire, etc.).
- Display output name that `wlr-randr` recognises (see `wlr-randr --list`).

## Hardware wiring

| Raspberry Pi | MPU6050 |
|--------------|---------|
| 3.3 V        | VCC     |
| GND          | GND     |
| GPIO2 (SDA1) | SDA     |
| GPIO3 (SCL1) | SCL     |

Keep your wires short and twisted where possible to reduce noise.

## Install & run manually

```bash
sudo mkdir -p /opt
sudo cp -r /path/to/this/project /opt/piautorotate   # adjust the source path
sudo chown -R pi:pi /opt/piautorotate                 # or whichever user will run it
cd /opt/piautorotate
sudo apt install -y python3-smbus
AUTOROTATE_OUTPUT=HDMI-A-1 python3 autorotate.py
```

Set `AUTOROTATE_OUTPUT` (and other env vars) so that the script knows which
display to rotate.

## Systemd service

1. Copy the project (including `autorotate.py` and `systemd/` files) into
   `/opt/piautorotate` or another directory owned by the service user.
2. Install the unit file:
   ```bash
   sudo install -m 644 systemd/piautorotate.service /etc/systemd/system/piautorotate.service
   ```
3. Install and edit the environment file:
   ```bash
   sudo install -m 644 systemd/piautorotate.env /etc/default/piautorotate
   sudo nano /etc/default/piautorotate
   ```
   Update `AUTOROTATE_OUTPUT`, `AUTOROTATE_INTERVAL`, etc. to match your setup.
4. Reload systemd, enable, and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable piautorotate.service
   sudo systemctl start piautorotate.service
   ```
5. Check logs with `journalctl -u piautorotate -f`.

If you need to run the script inside a graphical Wayland session, make sure the
service user has the right `DISPLAY` and `XDG_RUNTIME_DIR`. The provided unit
sets defaults that work for the `pi` user on Raspberry Pi OS.

## Configuration reference

| Environment variable          | Default   | Description                                                |
|-------------------------------|-----------|------------------------------------------------------------|
| `AUTOROTATE_OUTPUT`           | HDMI-A-1  | Output name passed to `wlr-randr`.                         |
| `AUTOROTATE_INTERVAL`         | 0.5       | Seconds between sensor polls.                              |
| `AUTOROTATE_THRESHOLD`        | 0.5       | Minimum g-force (absolute) to trigger a rotation decision. |
| `AUTOROTATE_DEFAULT_ROTATION` | normal    | Rotation to use when the device is upright.                |
| `AUTOROTATE_BUS_ID`           | 1         | I2C bus number (1 on most Raspberry Pi models).            |

## Troubleshooting

- **`wlr-randr not found`** – ensure your compositor provides it or install
  `wlroots` utilities.
- **`I2C read error` spam** – check cabling, enable I2C, and confirm the MPU6050
  address (`0x68`) matches the wiring (AD0 pin low).
- **Display does not rotate** – run `wlr-randr --list` to verify the output
  name, and confirm the compositor allows transforms on that output.
